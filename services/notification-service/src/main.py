import asyncio
import json
import logging
import sys
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    Counter,
    Histogram,
    generate_latest,
)
from src.config import settings
from src.consumers.rabbitmq_event_consumer import RabbitMQEventConsumer
from src.functions.generate_report_function import GenerateReportFunction
from src.functions.send_notification_function import SendNotificationFunction
from src.storage.notification_repository import NotificationRepository


# Logging Estructurado JSON
class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%SZ"),
            "level": record.levelname,
            "service": settings.service_name,
            "message": record.getMessage(),
            "module": record.module,
            "trace_id": getattr(record, "trace_id", "00000000000000000000000000000000"),
        }
        return json.dumps(log_record)


handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JsonFormatter())
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO), handlers=[handler]
)
logger = logging.getLogger(settings.service_name)

# Inicialización de dependencias
repo = NotificationRepository(db_path=settings.db_path)
send_func = SendNotificationFunction(repo=repo)
report_func = GenerateReportFunction(repo=repo)
consumer = RabbitMQEventConsumer(
    amqp_url=settings.rabbitmq_url, notification_func=send_func
)

consumer_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global consumer_task
    logger.info("Starting Serverless Notification Event Consumer...")
    consumer_task = asyncio.create_task(consumer.start())
    yield
    logger.info("Stopping Serverless Notification Event Consumer...")
    consumer.stop()
    if consumer_task:
        consumer_task.cancel()


app = FastAPI(
    title="Notification Microservice (Serverless / FaaS)",
    description="Componente reactivo para procesamiento asíncrono de eventos de itinerarios y reportes bajo demanda.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
@app.get("/api/v1/notifications/health")
async def health():
    return {
        "status": "UP",
        "service": "notification-service",
        "consumer_active": consumer._is_running,
    }


@app.get("/api/v1/notifications/report")
async def get_report():
    """Función serverless ejecutada bajo demanda para consolidar reportes."""
    return report_func.execute()


@app.get("/api/v1/notifications/logs")
async def get_logs():
    return repo.list_all()


def _get_or_create_metric(
    metric_cls, name: str, documentation: str, labelnames: tuple[str, ...] = ()
):
    if name in REGISTRY._names_to_collectors:
        return REGISTRY._names_to_collectors[name]
    return metric_cls(name, documentation, labelnames=labelnames)


HTTP_REQUESTS_TOTAL = _get_or_create_metric(
    Counter,
    "http_requests_total",
    "Total HTTP requests processed",
    ("service", "method", "path", "status_code"),
)
HTTP_REQUEST_DURATION_SECONDS = _get_or_create_metric(
    Histogram,
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ("service", "method", "path"),
)


@app.middleware("http")
async def prometheus_metrics_middleware(request: Request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start_time
    path = request.url.path
    HTTP_REQUESTS_TOTAL.labels(
        service=settings.service_name,
        method=request.method,
        path=path,
        status_code=str(response.status_code),
    ).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(
        service=settings.service_name,
        method=request.method,
        path=path,
    ).observe(duration)
    return response


@app.get("/metrics", tags=["Metrics"], summary="Exponer métricas Prometheus")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=settings.service_port)
