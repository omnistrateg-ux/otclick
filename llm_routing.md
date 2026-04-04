# LLM Routing — Otclick Employer Acquisition Engine

## Принцип

Агент никогда не вызывает LLM-провайдера напрямую.

```
Agent → LLMRequest(task_type, system, user) → LLMRouter → Provider → LLMResponse
```

Router выбирает провайдера по:
1. Типу задачи (дешёвая vs премиум)
2. Доступности провайдера (fallback chain)
3. Бюджету (если лимит достигнут — переключение на дешёвый)

---

## Таблица маршрутизации

| Task Type | Tier | Провайдер 1 | Провайдер 2 | Провайдер 3 | ~Цена/req |
|-----------|------|-------------|-------------|-------------|-----------|
| classification | Low | Qwen-Turbo | YandexGPT-Lite | GPT-4o-mini | $0.001 |
| extraction | Low | Qwen-Plus | GPT-4o-mini | Claude Haiku | $0.002 |
| scoring | Mid | GPT-4o-mini | Claude Haiku | Qwen-Plus | $0.003 |
| segmentation | Mid | GPT-4o-mini | Qwen-Plus | Claude Haiku | $0.003 |
| personalization | High | Claude Sonnet | GPT-4o | — | $0.01 |
| email_generation | High | Claude Sonnet | GPT-4o | — | $0.015 |
| response_analysis | High | Claude Sonnet | GPT-4o | — | $0.008 |
| qualification | Premium | Claude Opus | GPT-4o | Claude Sonnet | $0.02 |
| summarization | Mid | GPT-4o | Claude Sonnet | — | $0.008 |

---

## Провайдеры

### OpenAI
- Модели: gpt-4o, gpt-4o-mini
- Сильные стороны: стабильность, скорость, JSON mode
- Слабые стороны: дороже Qwen для bulk задач

### Anthropic (Claude)
- Модели: claude-sonnet-4-20250514, claude-opus-4-20250514
- Сильные стороны: лучшее качество текста на русском, reasoning
- Слабые стороны: цена Opus, rate limits

### Qwen
- Модели: qwen-turbo, qwen-plus
- Сильные стороны: дёшево, быстро, приличное качество для bulk
- Слабые стороны: хуже для creative writing на русском

### YandexGPT
- Модели: yandexgpt-lite, yandexgpt-pro
- Сильные стороны: нативный русский, локализация
- Слабые стороны: API менее стабильно, нужен folder_id

---

## Fallback логика

```python
async def complete(self, request: LLMRequest) -> LLMResponse:
    providers = ROUTING_TABLE[request.task_type]
    
    for provider_name in providers:
        provider = self._providers.get(provider_name)
        if not provider or not provider.is_available():
            continue
        try:
            return await asyncio.wait_for(
                provider.complete(request),
                timeout=30.0,
            )
        except (TimeoutError, ProviderError) as e:
            logger.warning(f"{provider_name} failed: {e}")
            continue
    
    raise NoProviderAvailable(request.task_type)
```

---

## Cost tracking

Каждый вызов записывает:
```python
class LLMUsageRecord:
    timestamp: datetime
    task_type: LLMTaskType
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    cost_usd: float
    lead_id: UUID | None
    agent_name: str
```

Это позволяет:
- Считать "cost per warm lead"
- Оптимизировать routing (если Qwen даёт сопоставимое качество — переключить)
- Отслеживать budget burn rate
- A/B тестировать модели на одной задаче

---

## Конфигурация

```bash
# .env — хотя бы один провайдер обязателен
OTCLICK_OPENAI_API_KEY=sk-...
OTCLICK_ANTHROPIC_API_KEY=sk-ant-...
OTCLICK_QWEN_API_KEY=...
OTCLICK_YANDEXGPT_API_KEY=...
OTCLICK_YANDEXGPT_FOLDER_ID=b1g...
```
