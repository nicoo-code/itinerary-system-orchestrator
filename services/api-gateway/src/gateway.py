import json
import logging
import os
import sys
import time
from collections import defaultdict

import httpx
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Variables de entorno
PORT = int(os.getenv("PORT", "8000"))
AIRPORT_SERVICE_URL = os.getenv("AIRPORT_SERVICE_URL", "http://airport-service:8001")
ITINERARY_SERVICE_URL = os.getenv(
    "ITINERARY_SERVICE_URL", "http://itinerary-service:8002"
)
NOTIFICATION_SERVICE_URL = os.getenv(
    "NOTIFICATION_SERVICE_URL", "http://notification-service:8003"
)
FRONTEND_DIR = os.getenv("FRONTEND_DIR", "/app/frontend")
OTEL_EXPORTER_OTLP_ENDPOINT = os.getenv(
    "OTEL_EXPORTER_OTLP_ENDPOINT", "http://jaeger:4317"
)


def _get_active_span_ids() -> tuple[str | None, str | None]:
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if span is not None:
            ctx = span.get_span_context()
            if ctx is not None and getattr(ctx, "is_valid", False):
                return format(ctx.trace_id, "032x"), format(ctx.span_id, "016x")
    except (ImportError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
        logging.getLogger("api-gateway").debug(
            f"Could not read active OpenTelemetry span: {exc}"
        )
    return None, None


# Logging Estructurado JSON
class JsonFormatter(logging.Formatter):
    def format(self, record):
        otel_trace_id, otel_span_id = _get_active_span_ids()
        trace_id = (
            getattr(record, "trace_id", None)
            or otel_trace_id
            or "00000000000000000000000000000000"
        )
        span_id = getattr(record, "span_id", None) or otel_span_id or "0000000000000000"
        log_record = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%SZ"),
            "level": record.levelname,
            "service": "api-gateway",
            "message": record.getMessage(),
            "module": record.module,
            "trace_id": trace_id,
            "span_id": span_id,
        }
        return json.dumps(log_record)


handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JsonFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler])
logger = logging.getLogger("api-gateway")

app = FastAPI(
    title="API Gateway / BFF - Perímetro del Sistema",
    description="Punto único de entrada del sistema. Enrutamiento, Rate Limiting y Propagación de Seguridad JWT y Tracing.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Algoritmo de Rate Limiting (Token Bucket / Sliding Window por IP)
RATE_LIMIT_MAX = 60
RATE_LIMIT_WINDOW = 60.0
request_counters = defaultdict(list)


@app.middleware("http")
async def rate_limit_and_tracing_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()

    # Ignorar archivos estáticos del rate limit estricto
    if not request.url.path.startswith("/api/"):
        return await call_next(request)

    # Limpiar timestamps antiguos de la ventana
    timestamps = [t for t in request_counters[client_ip] if now - t < RATE_LIMIT_WINDOW]
    if len(timestamps) >= RATE_LIMIT_MAX:
        logger.warning(f"Rate limit exceeded for IP: {client_ip}")
        return Response(
            content=json.dumps(
                {"detail": "Too Many Requests (Rate limit: 60 req/min)"}
            ),
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            media_type="application/json",
        )

    timestamps.append(now)
    request_counters[client_ip] = timestamps

    # Propagación o generación de W3C Trace Context
    otel_trace_id, otel_span_id = _get_active_span_ids()
    traceparent = request.headers.get("traceparent")
    if not traceparent:
        trace_id = otel_trace_id or os.urandom(16).hex()
        span_id = otel_span_id or os.urandom(8).hex()
        traceparent = f"00-{trace_id}-{span_id}-01"
    else:
        parts = traceparent.split("-")
        trace_id = (
            parts[1]
            if len(parts) >= 2 and parts[1]
            else (otel_trace_id or os.urandom(16).hex())
        )
        span_id = otel_span_id or (
            parts[2] if len(parts) >= 3 and parts[2] else os.urandom(8).hex()
        )
        traceparent = f"00-{trace_id}-{span_id}-01"

    request.state.trace_id = trace_id
    request.state.span_id = span_id
    request.state.traceparent = traceparent

    start_time = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start_time) * 1000
    response.headers["traceparent"] = traceparent
    logger.info(
        f"{request.method} {request.url.path} - Status {response.status_code} ({duration_ms:.2f}ms)",
        extra={"trace_id": trace_id, "span_id": span_id},
    )
    return response


def setup_gateway_telemetry(
    fastapi_app: FastAPI,
    service_name: str = "api-gateway",
    otlp_endpoint: str | None = OTEL_EXPORTER_OTLP_ENDPOINT,
):
    try:
        from opentelemetry import trace
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource.create({"service.name": service_name})
        provider = TracerProvider(resource=resource)

        if otlp_endpoint and os.getenv("TESTING") != "1":
            try:
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                    OTLPSpanExporter,
                )

                exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
                provider.add_span_processor(BatchSpanProcessor(exporter))
            except (
                ImportError,
                RuntimeError,
                ValueError,
                TypeError,
                OSError,
            ) as exp_err:
                logger.warning(
                    f"OTLPSpanExporter could not be initialized for {service_name}: {exp_err}"
                )

        trace.set_tracer_provider(provider)
        FastAPIInstrumentor.instrument_app(fastapi_app, tracer_provider=provider)
        httpx_instrumentor = HTTPXClientInstrumentor()
        if not getattr(httpx_instrumentor, "_is_instrumented_by_opentelemetry", False):
            httpx_instrumentor.instrument(tracer_provider=provider)
        return provider
    except (
        ImportError,
        RuntimeError,
        ValueError,
        TypeError,
        AttributeError,
        OSError,
    ) as exc:
        logger.warning(
            f"OpenTelemetry initialization skipped for {service_name}: {exc}"
        )
        return None


setup_gateway_telemetry(app)


# Enrutador genérico inverso (Reverse Proxy)
async def forward_request(target_url: str, request: Request) -> Response:
    body = await request.body()
    headers = dict(request.headers)
    headers.pop("host", None)
    headers.pop("content-length", None)

    # Inyectar traceparent y preservar Authorization JWT
    headers["traceparent"] = getattr(request.state, "traceparent", "")
    if "authorization" in request.headers:
        headers["authorization"] = request.headers["authorization"]

    timeout = httpx.Timeout(10.0, connect=3.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            resp = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                params=request.query_params,
                content=body,
            )
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                headers=dict(resp.headers),
                media_type=resp.headers.get("content-type"),
            )
        except httpx.RequestError as exc:
            logger.error(f"Gateway forwarding error to {target_url}: {exc}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Service unavailable upstream: {exc}",
            )


# Rutas de aeropuertos
@app.api_route("/api/v1/airports/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def route_airports(path: str, request: Request):
    if path == "health":
        target = f"{AIRPORT_SERVICE_URL}/health"
    else:
        target = f"{AIRPORT_SERVICE_URL}/api/v1/airports/{path}"
    return await forward_request(target, request)


@app.api_route("/api/v1/airports", methods=["GET"])
async def route_airports_root(request: Request):
    target = f"{AIRPORT_SERVICE_URL}/api/v1/airports"
    return await forward_request(target, request)


# Rutas de itinerarios
@app.api_route(
    "/api/v1/itineraries/{path:path}", methods=["GET", "POST", "PUT", "DELETE"]
)
async def route_itineraries(path: str, request: Request):
    if path == "health":
        target = f"{ITINERARY_SERVICE_URL}/health"
    else:
        target = f"{ITINERARY_SERVICE_URL}/api/v1/itineraries/{path}"
    return await forward_request(target, request)


@app.api_route("/api/v1/itineraries", methods=["GET", "POST"])
async def route_itineraries_root(request: Request):
    target = f"{ITINERARY_SERVICE_URL}/api/v1/itineraries"
    return await forward_request(target, request)


# Rutas de notificaciones
@app.api_route("/api/v1/notifications/{path:path}", methods=["GET"])
async def route_notifications(path: str, request: Request):
    if path == "health":
        target = f"{NOTIFICATION_SERVICE_URL}/health"
    else:
        target = f"{NOTIFICATION_SERVICE_URL}/api/v1/notifications/{path}"
    return await forward_request(target, request)


# Healthcheck del Gateway
@app.get("/health")
async def health():
    return {"status": "UP", "service": "api-gateway", "timestamp": time.time()}


# Resolver directorio frontend
effective_frontend_dir = FRONTEND_DIR
if not os.path.exists(effective_frontend_dir):
    candidate = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../../frontend")
    )
    if os.path.exists(candidate):
        effective_frontend_dir = candidate

# Montar frontend estático y servir rutas raíz
if os.path.exists(effective_frontend_dir):
    app.mount("/static", StaticFiles(directory=effective_frontend_dir), name="static")

    @app.get("/")
    async def serve_index():
        index_path = os.path.join(effective_frontend_dir, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return {"message": "API Gateway running. Frontend index.html not found."}

    @app.get("/style.css")
    async def serve_root_style():
        p = os.path.join(effective_frontend_dir, "style.css")
        if os.path.exists(p):
            return FileResponse(p, media_type="text/css")
        return Response(status_code=404)

    @app.get("/app.js")
    async def serve_root_js():
        p = os.path.join(effective_frontend_dir, "app.js")
        if os.path.exists(p):
            return FileResponse(p, media_type="application/javascript")
        return Response(status_code=404)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=PORT)
