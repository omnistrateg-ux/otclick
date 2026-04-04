# Deployment Guide

This guide covers deployment of the Otclick Employer Acquisition Engine to production environments.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Environment Configuration](#environment-configuration)
- [Docker Deployment](#docker-deployment)
- [Kubernetes Deployment](#kubernetes-deployment)
- [Database Setup](#database-setup)
- [Monitoring Setup](#monitoring-setup)
- [CI/CD Pipeline](#cicd-pipeline)
- [Security Considerations](#security-considerations)
- [Scaling Guidelines](#scaling-guidelines)
- [Troubleshooting](#troubleshooting)

## Prerequisites

### Required Software

- Docker 24.0+
- Docker Compose 2.20+
- PostgreSQL 16+ (if not using Docker)
- Redis 7+ (if not using Docker)
- Python 3.12+ (for local development)

### Required Accounts/Services

- GitHub Container Registry (ghcr.io) access
- Sentry account (for error tracking)
- SMTP service (for email delivery)
- OpenAI/Anthropic API keys (for LLM features)

## Environment Configuration

### Required Environment Variables

Create a `.env` file from the template:

```bash
cp .env.example .env
```

Configure the following variables:

```env
# Core Settings
OTCLICK_ENVIRONMENT=production
OTCLICK_SECRET_KEY=<generate-secure-key>

# Database
POSTGRES_PASSWORD=<strong-password>
OTCLICK_DATABASE_URL=postgresql+asyncpg://otclick:${POSTGRES_PASSWORD}@postgres:5432/otclick_employer

# Redis
OTCLICK_REDIS_URL=redis://redis:6379/0
OTCLICK_CELERY_BROKER_URL=redis://redis:6379/1

# API Authentication
OTCLICK_API_KEY_REQUIRED=true
OTCLICK_API_KEYS=key1,key2,key3

# Monitoring
SENTRY_DSN=https://xxx@sentry.io/xxx
OTCLICK_LOG_FORMAT=json

# LLM Providers (optional)
OTCLICK_OPENAI_API_KEY=sk-xxx
OTCLICK_ANTHROPIC_API_KEY=sk-ant-xxx

# Email (optional)
OTCLICK_SMTP_HOST=smtp.example.com
OTCLICK_SMTP_PORT=587
OTCLICK_SMTP_USER=user
OTCLICK_SMTP_PASSWORD=password
```

### Generate Secret Key

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

### Generate API Keys

```bash
# Generate multiple API keys
for i in {1..3}; do
  python -c "import secrets; print(f'otclick_{secrets.token_urlsafe(32)}')"
done
```

## Docker Deployment

### Build Images

```bash
# Build all images
docker compose -f docker-compose.prod.yml build

# Or build individually
docker build -t otclick-app:latest -f Dockerfile .
docker build -t otclick-worker:latest -f Dockerfile.worker .
```

### Start Services

```bash
# Start all services
docker compose -f docker-compose.prod.yml up -d

# Start with monitoring stack
docker compose -f docker-compose.prod.yml --profile monitoring up -d

# View logs
docker compose -f docker-compose.prod.yml logs -f app worker
```

### Health Checks

```bash
# Check API health
curl http://localhost:8000/api/v1/health

# Check all container statuses
docker compose -f docker-compose.prod.yml ps

# Check specific service
docker inspect --format='{{.State.Health.Status}}' otclick-app
```

### Update Deployment

```bash
# Pull latest images
docker compose -f docker-compose.prod.yml pull

# Restart with new images (zero-downtime)
docker compose -f docker-compose.prod.yml up -d --no-deps --build app worker

# Run database migrations
docker compose -f docker-compose.prod.yml exec app alembic upgrade head
```

## Kubernetes Deployment

### Namespace Setup

```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: otclick
  labels:
    name: otclick
```

### ConfigMap

```yaml
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: otclick-config
  namespace: otclick
data:
  OTCLICK_ENVIRONMENT: "production"
  OTCLICK_LOG_FORMAT: "json"
  OTCLICK_API_KEY_REQUIRED: "true"
  OTCLICK_RATE_LIMIT_ENABLED: "true"
  OTCLICK_RATE_LIMIT_REQUESTS_PER_MINUTE: "60"
```

### Secrets

```yaml
# k8s/secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: otclick-secrets
  namespace: otclick
type: Opaque
stringData:
  OTCLICK_SECRET_KEY: "<your-secret-key>"
  OTCLICK_DATABASE_URL: "postgresql+asyncpg://..."
  OTCLICK_REDIS_URL: "redis://..."
  OTCLICK_API_KEYS: "key1,key2,key3"
  SENTRY_DSN: "https://..."
```

### Deployment

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: otclick-api
  namespace: otclick
spec:
  replicas: 3
  selector:
    matchLabels:
      app: otclick-api
  template:
    metadata:
      labels:
        app: otclick-api
    spec:
      containers:
        - name: api
          image: ghcr.io/your-org/otclick-employer-engine:latest
          ports:
            - containerPort: 8000
          envFrom:
            - configMapRef:
                name: otclick-config
            - secretRef:
                name: otclick-secrets
          resources:
            requests:
              memory: "512Mi"
              cpu: "250m"
            limits:
              memory: "1Gi"
              cpu: "1000m"
          livenessProbe:
            httpGet:
              path: /api/v1/health
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /api/v1/health
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 5
```

### Service

```yaml
# k8s/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: otclick-api
  namespace: otclick
spec:
  selector:
    app: otclick-api
  ports:
    - port: 80
      targetPort: 8000
  type: ClusterIP
```

### Ingress

```yaml
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: otclick-ingress
  namespace: otclick
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
    - hosts:
        - api.otclick.ru
      secretName: otclick-tls
  rules:
    - host: api.otclick.ru
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: otclick-api
                port:
                  number: 80
```

### Apply Kubernetes Manifests

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml

# Check status
kubectl get pods -n otclick
kubectl get services -n otclick
```

## Database Setup

### Initial Setup

```bash
# Create database (if not using Docker)
psql -U postgres -c "CREATE DATABASE otclick_employer;"
psql -U postgres -c "CREATE USER otclick WITH ENCRYPTED PASSWORD 'your-password';"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE otclick_employer TO otclick;"

# Run migrations
docker compose -f docker-compose.prod.yml exec app alembic upgrade head

# Or locally
alembic upgrade head
```

### Backup Strategy

```bash
# Create backup
docker compose -f docker-compose.prod.yml exec postgres \
  pg_dump -U otclick otclick_employer > backup_$(date +%Y%m%d_%H%M%S).sql

# Restore from backup
cat backup_20240115_120000.sql | docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U otclick otclick_employer
```

### Automated Backups (cron)

```bash
# Add to crontab
0 2 * * * /path/to/backup-script.sh >> /var/log/otclick-backup.log 2>&1
```

## Monitoring Setup

### Prometheus + Grafana

```bash
# Start with monitoring profile
docker compose -f docker-compose.prod.yml --profile monitoring up -d

# Access Grafana
open http://localhost:3000
# Default: admin/admin (change immediately)

# Access Prometheus
open http://localhost:9090
```

### Sentry Setup

1. Create a Sentry project at https://sentry.io
2. Get the DSN from Project Settings > Client Keys
3. Set `SENTRY_DSN` environment variable

### Key Metrics to Monitor

| Metric | Alert Threshold | Description |
|--------|-----------------|-------------|
| `http_requests_total` | N/A | Total HTTP requests |
| `http_request_duration_seconds` | p95 > 1s | Response time |
| `active_leads_total` | N/A | Current lead count |
| `llm_requests_total` | Error rate > 5% | LLM API calls |
| `celery_tasks_total` | Failure rate > 10% | Background tasks |

### Grafana Dashboards

Import the following dashboards:

1. **API Overview**: Request rates, latency, error rates
2. **Lead Pipeline**: Funnel metrics, conversion rates
3. **Worker Status**: Celery task queue, processing times
4. **Infrastructure**: CPU, memory, disk usage

## CI/CD Pipeline

### GitHub Actions

The project includes two workflows:

- **CI** (`.github/workflows/ci.yml`): Runs on every push/PR
  - Linting (ruff)
  - Type checking (mypy)
  - Tests (pytest)
  - Security scan (bandit, safety)
  - Docker build test

- **CD** (`.github/workflows/cd.yml`): Runs on main branch and tags
  - Build and push Docker images
  - Deploy to staging (main branch)
  - Deploy to production (version tags)

### Deployment Flow

```
feature branch → PR → main → staging → v1.x.x tag → production
```

### Manual Deployment

```bash
# Deploy to staging
gh workflow run cd.yml -f environment=staging

# Deploy to production
git tag v1.0.0
git push origin v1.0.0
```

## Security Considerations

### API Authentication

All API endpoints (except health) require authentication:

```bash
curl -H "X-API-Key: your-api-key" https://api.otclick.ru/api/v1/leads
```

### Rate Limiting

Default: 60 requests per minute per IP/API key

Configure in environment:
```env
OTCLICK_RATE_LIMIT_ENABLED=true
OTCLICK_RATE_LIMIT_REQUESTS_PER_MINUTE=60
```

### Network Security

1. **Firewall Rules**: Only expose ports 80/443
2. **Internal Services**: Keep PostgreSQL/Redis on internal network
3. **TLS**: Use Let's Encrypt or similar for HTTPS

### Secrets Management

- Never commit secrets to git
- Use environment variables or secret management (Vault, AWS Secrets Manager)
- Rotate API keys periodically
- Use different secrets per environment

## Scaling Guidelines

### Horizontal Scaling

| Component | Scaling Strategy |
|-----------|-----------------|
| API | Replicas behind load balancer |
| Workers | Increase replica count |
| PostgreSQL | Read replicas, connection pooling |
| Redis | Redis Cluster or Sentinel |

### Vertical Scaling

| Component | Recommended Resources |
|-----------|----------------------|
| API | 1 CPU, 1GB RAM per instance |
| Worker | 2 CPU, 2GB RAM per instance |
| PostgreSQL | 4 CPU, 8GB RAM |
| Redis | 2 CPU, 512MB RAM |

### Connection Pooling

```python
# Recommended pool settings
OTCLICK_DB_POOL_SIZE=20
OTCLICK_DB_MAX_OVERFLOW=10
```

### Celery Worker Scaling

```bash
# Scale workers
docker compose -f docker-compose.prod.yml up -d --scale worker=3

# Or in Kubernetes
kubectl scale deployment otclick-worker --replicas=5 -n otclick
```

## Troubleshooting

### Common Issues

#### API Not Starting

```bash
# Check logs
docker compose -f docker-compose.prod.yml logs app

# Common causes:
# - Database not ready (wait for health check)
# - Missing environment variables
# - Port already in use
```

#### Database Connection Errors

```bash
# Check PostgreSQL is running
docker compose -f docker-compose.prod.yml exec postgres pg_isready

# Check connection string
docker compose -f docker-compose.prod.yml exec app python -c \
  "from app.config import settings; print(settings.database_url)"
```

#### Redis Connection Errors

```bash
# Check Redis is running
docker compose -f docker-compose.prod.yml exec redis redis-cli ping

# Check memory usage
docker compose -f docker-compose.prod.yml exec redis redis-cli info memory
```

#### Celery Workers Not Processing

```bash
# Check worker status
docker compose -f docker-compose.prod.yml exec worker celery -A workers.celery_app inspect active

# Check queue length
docker compose -f docker-compose.prod.yml exec redis redis-cli llen celery
```

### Debug Mode

For debugging in staging (NOT production):

```env
OTCLICK_DEBUG=true
OTCLICK_LOG_LEVEL=DEBUG
```

### Logs

```bash
# Application logs
docker compose -f docker-compose.prod.yml logs -f app

# Worker logs
docker compose -f docker-compose.prod.yml logs -f worker

# All logs with timestamps
docker compose -f docker-compose.prod.yml logs -f --timestamps
```

### Performance Profiling

```bash
# Run load tests
locust -f tests/load/locustfile.py --host=https://staging.otclick.ru \
  --users 50 --spawn-rate 5 --run-time 5m --headless

# Profile specific endpoints
curl -w "@curl-format.txt" -s https://api.otclick.ru/api/v1/leads > /dev/null
```

## Maintenance

### Database Maintenance

```bash
# Vacuum analyze
docker compose -f docker-compose.prod.yml exec postgres \
  psql -U otclick -d otclick_employer -c "VACUUM ANALYZE;"

# Check table sizes
docker compose -f docker-compose.prod.yml exec postgres \
  psql -U otclick -d otclick_employer -c "\dt+"
```

### Log Rotation

Configure in `/etc/logrotate.d/otclick`:

```
/var/log/otclick/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    create 0640 www-data www-data
}
```

### Updates

```bash
# Check for security updates
pip-audit

# Update dependencies
pip install --upgrade -r requirements.txt

# Run tests after updates
pytest tests/ -v
```

## Support

For issues and support:

- GitHub Issues: https://github.com/your-org/otclick-employer-engine/issues
- Documentation: https://docs.otclick.ru
- Email: support@otclick.ru
