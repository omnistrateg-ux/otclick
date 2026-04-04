# Deployment — Otclick Employer Acquisition Engine

## Local Development

### Prerequisites
- Python 3.12+
- Docker + Docker Compose
- Node.js (не нужен для бэкенда, только если будет фронт)

### Quick Start

```bash
# 1. Клонировать и настроить
git clone <repo>
cd otclick_employer_engine
cp .env.example .env
# Заполнить API ключи в .env

# 2. Поднять инфраструктуру
docker compose up -d postgres redis mailhog

# 3. Установить зависимости
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 4. Миграции
alembic upgrade head

# 5. Запуск API
uvicorn app.main:app --reload --port 8000

# 6. Запуск воркеров (отдельный терминал)
celery -A workers.celery_app worker -l info -c 4

# 7. Запуск scheduler (отдельный терминал)
celery -A workers.celery_app beat -l info
```

### Dev URLs
- API: http://localhost:8000
- API docs: http://localhost:8000/docs
- MailHog (перехват email): http://localhost:8025

---

## Production

### Docker

```bash
# Build
docker build -t otclick-engine:latest .
docker build -t otclick-worker:latest -f docker/Dockerfile.worker .

# Run
docker compose -f docker/docker-compose.yml up -d
```

### Yandex Cloud

| Компонент | Сервис YC |
|-----------|-----------|
| API + Workers | Compute Instance (2 vCPU, 4 GB) |
| PostgreSQL | Managed PostgreSQL |
| Redis | Managed Redis |
| Email | Mailgun (external) |
| Мониторинг | Yandex Monitoring |
| Логи | Yandex Cloud Logging |

### AWS

| Компонент | Сервис AWS |
|-----------|-----------|
| API | ECS Fargate / EC2 |
| Workers | ECS Fargate |
| PostgreSQL | RDS |
| Redis | ElastiCache |
| Email | SES / Mailgun |
| Мониторинг | CloudWatch + Sentry |

---

## Мониторинг

### Health checks
- `GET /api/v1/health` — liveness (app responds)
- `GET /api/v1/health` — readiness (DB + Redis connected)
- `GET /api/v1/health/providers` — LLM provider status

### Метрики (Prometheus endpoint)
- `otclick_leads_total` — counter по статусам
- `otclick_emails_sent_total` — counter
- `otclick_email_open_rate` — gauge
- `otclick_email_reply_rate` — gauge
- `otclick_llm_requests_total` — counter по провайдерам
- `otclick_llm_latency_seconds` — histogram
- `otclick_llm_cost_usd_total` — counter

### Алерты
- Reply rate < 2% за 7 дней → проверить email quality
- Bounce rate > 5% → остановить отправку, проверить домен
- LLM provider down > 5 мин → fallback alert
- Celery queue > 1000 tasks → scale workers
