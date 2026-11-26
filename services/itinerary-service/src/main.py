import asyncio
import json
import logging
import sys
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    Counter,
    Histogram,
    generate_latest,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.application.create_itinerary import CreateItineraryUseCase
from src.application.get_itinerary import (
    DeleteItineraryUseCase,
    GetItineraryUseCase,
    ListItinerariesUseCase,
)
from src.application.update_itinerary import UpdateItineraryUseCase
from src.infrastructure.api.router import create_itinerary_router
from src.infrastructure.clients.airport_http_validator import AirportHttpValidator
from src.infrastructure.config import settings
from src.infrastructure.messaging.outbox_relay_worker import OutboxRelayWorker
from src.infrastructure.messaging.rabbitmq_publisher import RabbitMQPublisher
from src.infrastructure.observability import (
    DEFAULT_SPAN_ID,
    DEFAULT_TRACE_ID,
    extract_trace_context,
    get_active_span_ids,
    setup_telemetry,
)
from src.infrastructure.persistence.models import Base
from src.infrastructure.persistence.sqlalchemy_itinerary_repo import (
    SqlAlchemyItineraryRepository,
)


# Logging Estructurado JSON
class JsonFormatter(logging.Formatter):
    def format(self, record):
        otel_trace_id, otel_span_id = get_active_span_ids()
        trace_id = (
            getattr(record, "trace_id", None) or otel_trace_id or DEFAULT_TRACE_ID
        )
        span_id = getattr(record, "span_id", None) or otel_span_id or DEFAULT_SPAN_ID
        log_record = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%SZ"),
            "level": record.levelname,
            "service": settings.service_name,
            "message": record.getMessage(),
            "module": record.module,
            "trace_id": trace_id,
            "span_id": span_id,
        }
        return json.dumps(log_record)


handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JsonFormatter())
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO), handlers=[handler]
)
logger = logging.getLogger(settings.service_name)

# Configuración de Base de Datos
database_url = settings.database_url
if database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+psycopg2://", 1)
connect_args = {"check_same_thread": False} if "sqlite" in database_url else {}
engine = create_engine(database_url, connect_args=connect_args, echo=False)
SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Respaldo seguro para entornos SQLite de pruebas; en despliegue real las migraciones se ejecutan con `alembic upgrade head` en entrypoint.sh
Base.metadata.create_all(bind=engine)

# Inicialización Hexagonal
itinerary_repo = SqlAlchemyItineraryRepository(session_factory=SessionFactory)
airport_validator = AirportHttpValidator(
    airport_service_url=settings.airport_service_url
)
rabbitmq_publisher = RabbitMQPublisher(amqp_url=settings.rabbitmq_url)
outbox_worker = OutboxRelayWorker(
    outbox_repo=itinerary_repo, publisher=rabbitmq_publisher, poll_interval_seconds=1.0
)

create_uc = CreateItineraryUseCase(
    itinerary_repo=itinerary_repo, airport_validator=airport_validator
)
get_uc = GetItineraryUseCase(itinerary_repo=itinerary_repo)
list_uc = ListItinerariesUseCase(itinerary_repo=itinerary_repo)
update_uc = UpdateItineraryUseCase(
    itinerary_repo=itinerary_repo, airport_validator=airport_validator
)
delete_uc = DeleteItineraryUseCase(itinerary_repo=itinerary_repo)

worker_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global worker_task
    logger.info("Initializing Outbox Relay Worker and RabbitMQ connection...")
    try:
        await rabbitmq_publisher.connect()
    except (ImportError, OSError, TimeoutError, RuntimeError) as e:
        logger.warning(f"RabbitMQ initial connection postponed: {e}")

    worker_task = asyncio.create_task(outbox_worker.start())
    yield
    logger.info("Shutting down Outbox Relay Worker...")
    outbox_worker.stop()
    if worker_task:
        worker_task.cancel()
    await rabbitmq_publisher.close()


app = FastAPI(
    title="Itinerary Service API",
    description="Microservicio de Gestión de Itinerarios con arquitectura hexagonal y Transactional Outbox",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Middleware de Observabilidad y Correlación
@app.middleware("http")
async def correlation_logging_middleware(request: Request, call_next):
    trace_id, span_id, traceparent = extract_trace_context(request)
    request.state.trace_id = trace_id
    request.state.span_id = span_id
    request.state.traceparent = traceparent

    start_time = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start_time) * 1000

    extra = {"trace_id": trace_id, "span_id": span_id}
    logger.info(
        f"{request.method} {request.url.path} - Status {response.status_code} ({duration_ms:.2f}ms)",
        extra=extra,
    )
    return response


# OpenTelemetry (TracerProvider + OTLP + FastAPI + HTTPX)
setup_telemetry(
    app=app,
    service_name=settings.service_name,
    otlp_endpoint=settings.otlp_endpoint,
)

app.include_router(
    create_itinerary_router(
        create_uc=create_uc,
        get_uc=get_uc,
        list_uc=list_uc,
        delete_uc=delete_uc,
        session_factory=SessionFactory,
        worker_status_callback=lambda: outbox_worker._is_running,
        update_uc=update_uc,
    )
)


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
ITINERARIES_CREATED_TOTAL = _get_or_create_metric(
    Counter,
    "itineraries_created_total",
    "Total number of itineraries created",
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
    if (
        request.method == "POST"
        and path.rstrip("/") == "/api/v1/itineraries"
        and response.status_code == 201
    ):
        ITINERARIES_CREATED_TOTAL.inc()
    return response


@app.get("/metrics", tags=["Metrics"], summary="Exponer métricas Prometheus")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=settings.service_port)
