"""Prometheus metrics for monitoring.

Метрики для Prometheus: счётчики, гистограммы, gauge'ы.
"""

import logging
import time
from contextlib import contextmanager
from typing import Any, Generator

from app.config import settings

logger = logging.getLogger(__name__)

_metrics_initialized = False
_metrics: "MetricsCollector | None" = None


class MetricsCollector:
    """Prometheus metrics collector.

    Collects and exposes metrics for:
    - HTTP requests (count, latency, errors)
    - Database operations
    - Celery tasks
    - Lead pipeline
    - Email operations
    - LLM calls
    """

    def __init__(self) -> None:
        """Initialize metrics collector."""
        self._counters: dict[str, Any] = {}
        self._histograms: dict[str, Any] = {}
        self._gauges: dict[str, Any] = {}
        self._summaries: dict[str, Any] = {}

        self._setup_metrics()

    def _setup_metrics(self) -> None:
        """Set up Prometheus metrics."""
        try:
            from prometheus_client import Counter, Gauge, Histogram, Summary

            # HTTP metrics
            self._counters["http_requests_total"] = Counter(
                "http_requests_total",
                "Total HTTP requests",
                ["method", "endpoint", "status"],
            )
            self._histograms["http_request_duration_seconds"] = Histogram(
                "http_request_duration_seconds",
                "HTTP request duration in seconds",
                ["method", "endpoint"],
                buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
            )

            # Database metrics
            self._counters["db_queries_total"] = Counter(
                "db_queries_total",
                "Total database queries",
                ["operation", "table"],
            )
            self._histograms["db_query_duration_seconds"] = Histogram(
                "db_query_duration_seconds",
                "Database query duration in seconds",
                ["operation"],
                buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0],
            )

            # Celery metrics
            self._counters["celery_tasks_total"] = Counter(
                "celery_tasks_total",
                "Total Celery tasks",
                ["task_name", "status"],
            )
            self._histograms["celery_task_duration_seconds"] = Histogram(
                "celery_task_duration_seconds",
                "Celery task duration in seconds",
                ["task_name"],
                buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 300.0],
            )

            # Lead pipeline metrics
            self._counters["leads_total"] = Counter(
                "leads_total",
                "Total leads processed",
                ["status", "source"],
            )
            self._gauges["leads_active"] = Gauge(
                "leads_active",
                "Currently active leads",
                ["status"],
            )

            # Email metrics
            self._counters["emails_total"] = Counter(
                "emails_total",
                "Total emails",
                ["type", "status"],
            )
            self._histograms["email_generation_duration_seconds"] = Histogram(
                "email_generation_duration_seconds",
                "Email generation duration in seconds",
                ["type"],
                buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
            )

            # LLM metrics
            self._counters["llm_requests_total"] = Counter(
                "llm_requests_total",
                "Total LLM requests",
                ["provider", "task_type", "status"],
            )
            self._histograms["llm_request_duration_seconds"] = Histogram(
                "llm_request_duration_seconds",
                "LLM request duration in seconds",
                ["provider", "task_type"],
                buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
            )
            self._counters["llm_tokens_total"] = Counter(
                "llm_tokens_total",
                "Total LLM tokens used",
                ["provider", "direction"],  # direction: input/output
            )

            # Rate limiting metrics
            self._counters["rate_limit_hits_total"] = Counter(
                "rate_limit_hits_total",
                "Total rate limit hits",
                ["endpoint", "limit_type"],
            )

            # Error metrics
            self._counters["errors_total"] = Counter(
                "errors_total",
                "Total errors",
                ["type", "component"],
            )

            logger.info("Prometheus metrics initialized")

        except ImportError:
            logger.warning("prometheus_client not installed, metrics disabled")

    # HTTP metrics
    def record_http_request(
        self,
        method: str,
        endpoint: str,
        status: int,
        duration: float,
    ) -> None:
        """Record HTTP request metrics.

        Args:
            method: HTTP method
            endpoint: Request endpoint
            status: Response status code
            duration: Request duration in seconds
        """
        if "http_requests_total" in self._counters:
            self._counters["http_requests_total"].labels(
                method=method,
                endpoint=endpoint,
                status=str(status),
            ).inc()

        if "http_request_duration_seconds" in self._histograms:
            self._histograms["http_request_duration_seconds"].labels(
                method=method,
                endpoint=endpoint,
            ).observe(duration)

    # Database metrics
    def record_db_query(
        self,
        operation: str,
        table: str,
        duration: float,
    ) -> None:
        """Record database query metrics.

        Args:
            operation: Query operation (select, insert, update, delete)
            table: Table name
            duration: Query duration in seconds
        """
        if "db_queries_total" in self._counters:
            self._counters["db_queries_total"].labels(
                operation=operation,
                table=table,
            ).inc()

        if "db_query_duration_seconds" in self._histograms:
            self._histograms["db_query_duration_seconds"].labels(
                operation=operation,
            ).observe(duration)

    # Celery metrics
    def record_celery_task(
        self,
        task_name: str,
        status: str,
        duration: float | None = None,
    ) -> None:
        """Record Celery task metrics.

        Args:
            task_name: Task name
            status: Task status (success, failure, retry)
            duration: Task duration in seconds
        """
        if "celery_tasks_total" in self._counters:
            self._counters["celery_tasks_total"].labels(
                task_name=task_name,
                status=status,
            ).inc()

        if duration is not None and "celery_task_duration_seconds" in self._histograms:
            self._histograms["celery_task_duration_seconds"].labels(
                task_name=task_name,
            ).observe(duration)

    # Lead metrics
    def record_lead(self, status: str, source: str) -> None:
        """Record lead processed.

        Args:
            status: Lead status
            source: Lead source
        """
        if "leads_total" in self._counters:
            self._counters["leads_total"].labels(
                status=status,
                source=source,
            ).inc()

    def set_active_leads(self, status: str, count: int) -> None:
        """Set active leads gauge.

        Args:
            status: Lead status
            count: Number of leads
        """
        if "leads_active" in self._gauges:
            self._gauges["leads_active"].labels(status=status).set(count)

    # Email metrics
    def record_email(
        self,
        email_type: str,
        status: str,
        generation_duration: float | None = None,
    ) -> None:
        """Record email metrics.

        Args:
            email_type: Email type
            status: Email status (sent, failed, bounced)
            generation_duration: Generation duration in seconds
        """
        if "emails_total" in self._counters:
            self._counters["emails_total"].labels(
                type=email_type,
                status=status,
            ).inc()

        if generation_duration is not None and "email_generation_duration_seconds" in self._histograms:
            self._histograms["email_generation_duration_seconds"].labels(
                type=email_type,
            ).observe(generation_duration)

    # LLM metrics
    def record_llm_request(
        self,
        provider: str,
        task_type: str,
        status: str,
        duration: float,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> None:
        """Record LLM request metrics.

        Args:
            provider: LLM provider
            task_type: Task type
            status: Request status (success, failure)
            duration: Request duration in seconds
            input_tokens: Input tokens used
            output_tokens: Output tokens used
        """
        if "llm_requests_total" in self._counters:
            self._counters["llm_requests_total"].labels(
                provider=provider,
                task_type=task_type,
                status=status,
            ).inc()

        if "llm_request_duration_seconds" in self._histograms:
            self._histograms["llm_request_duration_seconds"].labels(
                provider=provider,
                task_type=task_type,
            ).observe(duration)

        if "llm_tokens_total" in self._counters:
            self._counters["llm_tokens_total"].labels(
                provider=provider,
                direction="input",
            ).inc(input_tokens)
            self._counters["llm_tokens_total"].labels(
                provider=provider,
                direction="output",
            ).inc(output_tokens)

    # Rate limiting
    def record_rate_limit_hit(self, endpoint: str, limit_type: str) -> None:
        """Record rate limit hit.

        Args:
            endpoint: Request endpoint
            limit_type: Limit type (per_minute, per_hour)
        """
        if "rate_limit_hits_total" in self._counters:
            self._counters["rate_limit_hits_total"].labels(
                endpoint=endpoint,
                limit_type=limit_type,
            ).inc()

    # Errors
    def record_error(self, error_type: str, component: str) -> None:
        """Record error.

        Args:
            error_type: Error type
            component: Component where error occurred
        """
        if "errors_total" in self._counters:
            self._counters["errors_total"].labels(
                type=error_type,
                component=component,
            ).inc()

    @contextmanager
    def time_operation(
        self,
        histogram_name: str,
        **labels: str,
    ) -> Generator[None, None, None]:
        """Context manager to time an operation.

        Args:
            histogram_name: Name of histogram to record to
            **labels: Histogram labels

        Yields:
            None
        """
        start = time.perf_counter()
        try:
            yield
        finally:
            duration = time.perf_counter() - start
            if histogram_name in self._histograms:
                self._histograms[histogram_name].labels(**labels).observe(duration)


def init_metrics() -> MetricsCollector | None:
    """Initialize metrics collector.

    Returns:
        MetricsCollector instance or None
    """
    global _metrics_initialized, _metrics

    if _metrics_initialized:
        return _metrics

    if not settings.prometheus_enabled:
        logger.info("Prometheus metrics disabled")
        _metrics_initialized = True
        return None

    try:
        _metrics = MetricsCollector()
        _metrics_initialized = True
        return _metrics
    except Exception as e:
        logger.error(f"Failed to initialize metrics: {e}")
        _metrics_initialized = True
        return None


def get_metrics() -> MetricsCollector | None:
    """Get metrics collector instance.

    Returns:
        MetricsCollector or None
    """
    global _metrics

    if not _metrics_initialized:
        return init_metrics()

    return _metrics
