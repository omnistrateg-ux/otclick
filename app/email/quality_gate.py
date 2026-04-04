"""Quality Gate for email validation.

Валидация письма перед отправкой из ARCHITECTURE.md раздел 7.4.
"""

from pydantic import BaseModel

from app.models.domain import EmployerLead
from app.models.enums import EmailType


class QualityResult(BaseModel):
    """Result of quality gate validation."""

    passed: bool
    issues: list[str]
    word_count: int
    subject_length: int


class QualityGate:
    """Validates emails before sending.

    Проверяет письмо на спам-слова, длину, наличие CTA,
    персонализацию и другие критерии качества.
    """

    # Спам-слова из ARCHITECTURE.md
    SPAM_WORDS: list[str] = [
        "уникальный",
        "бесплатно",
        "гарантируем",
        "эксклюзив",
        "революционный",
        "не пропустите",
        "срочно",
        "только сегодня",
        "специальное предложение",
        "мы рады предложить",
        "инновационный",
        "лучший на рынке",
        "невероятный",
        "потрясающий",
        "супер",
        "топ",
        "номер один",
        "100%",
        "абсолютно",
    ]

    # Сигналы наличия CTA
    CTA_SIGNALS: list[str] = [
        "?",
        "актуальн",
        "обсуд",
        "созвон",
        "ответ",
        "напиш",
        "подскаж",
        "имеет смысл",
        "стоит",
        "удобн",
        "интересн",
    ]

    # Максимальная длина темы
    MAX_SUBJECT_LENGTH: int = 60

    # Минимальное количество слов
    MIN_WORDS: int = 20

    # Максимальное количество слов по типам
    MAX_WORDS: dict[EmailType, int] = {
        EmailType.FIRST_TOUCH: 150,
        EmailType.FOLLOWUP_1: 80,
        EmailType.FOLLOWUP_2: 80,
        EmailType.BREAKUP: 50,
    }

    def validate(
        self,
        subject: str,
        body: str,
        email_type: EmailType,
        lead: EmployerLead,
    ) -> QualityResult:
        """Validate email before sending.

        Args:
            subject: Email subject
            body: Email body
            email_type: Type of email
            lead: Lead for context

        Returns:
            Validation result with issues if any
        """
        issues: list[str] = []

        # 1. Спам-слова
        issues.extend(self._check_spam_words(subject, body))

        # 2. Длина тела
        word_count = len(body.split())
        max_words = self.MAX_WORDS.get(email_type, 150)
        if word_count > max_words:
            issues.append(f"too_long:{word_count}/{max_words}")
        if word_count < self.MIN_WORDS:
            issues.append(f"too_short:{word_count}/{self.MIN_WORDS}")

        # 3. Наличие CTA
        if not self._has_cta(body):
            issues.append("missing_cta")

        # 4. Персонализация — упомянута компания
        if not self._has_company_mention(body, lead.company_name):
            issues.append("no_company_mention")

        # 5. Тема
        subject_length = len(subject)
        if subject_length > self.MAX_SUBJECT_LENGTH:
            issues.append(f"subject_too_long:{subject_length}/{self.MAX_SUBJECT_LENGTH}")
        if subject.endswith("!"):
            issues.append("subject_exclamation")
        if subject.isupper():
            issues.append("subject_all_caps")

        # 6. Проверка на emoji
        if self._has_emoji(subject) or self._has_emoji(body):
            issues.append("contains_emoji")

        # 7. Проверка на ссылки в первом письме
        if email_type == EmailType.FIRST_TOUCH:
            if self._has_links(body):
                issues.append("links_in_first_touch")

        return QualityResult(
            passed=len(issues) == 0,
            issues=issues,
            word_count=word_count,
            subject_length=subject_length,
        )

    def _check_spam_words(self, subject: str, body: str) -> list[str]:
        """Check for spam words.

        Args:
            subject: Email subject
            body: Email body

        Returns:
            List of found spam word issues
        """
        issues = []
        text = f"{subject} {body}".lower()

        for word in self.SPAM_WORDS:
            if word.lower() in text:
                issues.append(f"spam_word:{word}")

        return issues

    def _has_cta(self, body: str) -> bool:
        """Check if body has CTA.

        Args:
            body: Email body

        Returns:
            True if CTA found
        """
        body_lower = body.lower()
        return any(signal in body_lower for signal in self.CTA_SIGNALS)

    def _has_company_mention(self, body: str, company_name: str) -> bool:
        """Check if company is mentioned.

        Args:
            body: Email body
            company_name: Company name

        Returns:
            True if company mentioned
        """
        # Normalize for comparison
        body_lower = body.lower()
        company_lower = company_name.lower()

        # Direct mention
        if company_lower in body_lower:
            return True

        # Try first word of company name (e.g., "Пятёрочка" from "Пятёрочка ООО")
        first_word = company_lower.split()[0] if company_lower else ""
        if len(first_word) >= 4 and first_word in body_lower:
            return True

        return False

    def _has_emoji(self, text: str) -> bool:
        """Check if text contains emoji.

        Args:
            text: Text to check

        Returns:
            True if emoji found
        """
        import re

        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # flags
            "\U00002702-\U000027B0"  # dingbats
            "\U000024C2-\U0001F251"
            "]+",
            flags=re.UNICODE,
        )
        return bool(emoji_pattern.search(text))

    def _has_links(self, body: str) -> bool:
        """Check if body contains links.

        Args:
            body: Email body

        Returns:
            True if links found
        """
        import re

        url_pattern = re.compile(
            r"http[s]?://|www\.|\.ru/|\.com/|\.io/",
            re.IGNORECASE,
        )
        return bool(url_pattern.search(body))

    def validate_batch(
        self,
        emails: list[dict],
        email_type: EmailType,
        lead: EmployerLead,
    ) -> list[QualityResult]:
        """Validate batch of emails.

        Args:
            emails: List of emails with subject and body
            email_type: Type of emails
            lead: Lead for context

        Returns:
            List of validation results
        """
        return [
            self.validate(
                subject=email.get("subject", ""),
                body=email.get("body", ""),
                email_type=email_type,
                lead=lead,
            )
            for email in emails
        ]


# Singleton instance
quality_gate = QualityGate()
