# Otclick Employer Acquisition Engine

AI-система поиска и квалификации работодателей для массового найма.

## Требования

- Python 3.12+
- PostgreSQL 16
- Redis 7

## Быстрый старт

### 1. Создание виртуального окружения

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Установка зависимостей

```bash
pip install -e ".[dev]"
```

### 3. Настройка окружения

```bash
cp .env.example .env
# Отредактируйте .env
```

### 4. Запуск инфраструктуры

```bash
cd docker
docker compose up -d
```

### 5. Применение миграций

```bash
alembic upgrade head
```

### 6. Запуск приложения

```bash
uvicorn app.main:app --reload
```

### 7. Проверка

```bash
curl http://localhost:8000/api/v1/health
```

## Тестирование

```bash
pytest tests/unit/test_state_machine.py -v
```

## Структура проекта

```
app/
├── api/          # FastAPI endpoints
├── config/       # Settings
├── core/         # State machine, exceptions
├── models/       # Enums, domain models, ORM
└── storage/      # Database, Redis

docker/           # Docker configuration
migrations/       # Alembic migrations
tests/            # Unit and integration tests
workers/          # Celery tasks
```
