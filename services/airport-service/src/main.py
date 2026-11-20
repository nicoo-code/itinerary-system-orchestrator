import json
import logging
import sys
import time

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from src.application.get_airport_by_id import GetAirportByIdUseCase
from src.application.get_airports_for_plotly import GetAirportsForPlotlyUseCase
from src.application.list_airports import ListAirportsUseCase
from src.infrastructure.adapters.api_colombia_adapter import ApiColombiaAdapter
from src.infrastructure.adapters.circuit_breaker import CircuitBreaker
from src.infrastructure.adapters.plotly_adapter import PlotlyAdapter
from src.infrastructure.adapters.redis_cache_adapter import RedisCacheAdapter
from src.infrastructure.api.router import create_airport_router
from src.infrastructure.config import settings


# Configuración de Logging Estructurado JSON
class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%SZ"),
            "level": record.levelname,
            "service": settings.service_name,
            "message": record.getMessage(),
            "module": record.module,
            "trace_id": getattr(record, "trace_id", "00000000000000000000000000000000"),
            "span_id": getattr(record, "span_id", "0000000000000000"),
        }
        return json.dumps(log_record)


handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JsonFormatter())
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO), handlers=[handler]
)
logger = logging.getLogger(settings.service_name)

# Inicialización de dependencias hexagonales
circuit_breaker = CircuitBreaker(
    failure_threshold=3, recovery_timeout=30.0, name="ApiColombiaCircuitBreaker"
)
redis_adapter = RedisCacheAdapter(redis_url=settings.redis_url)
api_colombia_adapter = ApiColombiaAdapter(
    base_url=settings.api_colombia_url, circuit_breaker=circuit_breaker
)
plotly_adapter = PlotlyAdapter()

list_airports_uc = ListAirportsUseCase(
    external_port=api_colombia_adapter, cache_port=redis_adapter
)
get_airport_by_id_uc = GetAirportByIdUseCase(
    external_port=api_colombia_adapter, list_use_case=list_airports_uc
)
get_plotly_uc = GetAirportsForPlotlyUseCase(
    list_use_case=list_airports_uc, plotly_adapter=plotly_adapter
)

app = FastAPI(
    title="Airport Microservice - Arquitectura Hexagonal",
    description="Microservicio desacoplado para consulta, resiliencia y formateo geográfico de aeropuertos colombianos.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Middleware de Correlation ID y Logging
@app.middleware("http")
async def trace_and_log_middleware(request: Request, call_next):
    trace_parent = request.headers.get("traceparent")
    trace_id = "00000000000000000000000000000000"
    if trace_parent and "-" in trace_parent:
        parts = trace_parent.split("-")
        if len(parts) >= 2:
            trace_id = parts[1]

    start_time = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start_time) * 1000

    extra = {"trace_id": trace_id}
    logger.info(
        f"{request.method} {request.url.path} - Status {response.status_code} ({duration_ms:.2f}ms)",
        extra=extra,
    )
    return response


# OpenTelemetry opcional
try:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    FastAPIInstrumentor.instrument_app(app)
except (ImportError, RuntimeError, TypeError) as e:
    logger.debug(f"OpenTelemetry FastAPI instrumentation not loaded: {e}")

# Montar endpoints
app.include_router(
    create_airport_router(
        list_airports_use_case=list_airports_uc,
        get_airport_by_id_use_case=get_airport_by_id_uc,
        get_plotly_use_case=get_plotly_uc,
        redis_adapter=redis_adapter,
        circuit_breaker=circuit_breaker,
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
AIRPORT_CIRCUIT_BREAKER_STATE = _get_or_create_metric(
    Gauge,
    "airport_circuit_breaker_state",
    "Circuit breaker state for Airport Service (0=CLOSED, 1=HALF_OPEN, 2=OPEN)",
)

_CB_STATE_MAPPING = {"CLOSED": 0, "HALF_OPEN": 1, "OPEN": 2}


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
    state_str = getattr(circuit_breaker.state, "value", str(circuit_breaker.state))
    AIRPORT_CIRCUIT_BREAKER_STATE.set(_CB_STATE_MAPPING.get(state_str, 0))
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=settings.service_port)
