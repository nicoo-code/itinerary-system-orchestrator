import json
import logging
import os
import uuid
from typing import Any

from fastapi import FastAPI, Request

logger = logging.getLogger(__name__)

DEFAULT_TRACE_ID = "00000000000000000000000000000000"
DEFAULT_SPAN_ID = "0000000000000000"


class JsonFormatter(logging.Formatter):
    """Formateador JSON estructurado con propagación automática de trace_id y span_id."""

    def __init__(self, service_name: str = "service"):
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        otel_trace_id, otel_span_id = get_active_span_ids()
        trace_id = (
            getattr(record, "trace_id", None) or otel_trace_id or DEFAULT_TRACE_ID
        )
        span_id = getattr(record, "span_id", None) or otel_span_id or DEFAULT_SPAN_ID
        log_record = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%SZ"),
            "level": record.levelname,
            "service": getattr(record, "service", None) or self.service_name,
            "message": record.getMessage(),
            "module": record.module,
            "trace_id": trace_id,
            "span_id": span_id,
        }
        return json.dumps(log_record)


def get_active_span_ids() -> tuple[str | None, str | None]:
    """Obtiene (trace_id, span_id) en formato hexadecimal desde el span activo de OpenTelemetry."""
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if span is not None:
            ctx = span.get_span_context()
            if ctx is not None and getattr(ctx, "is_valid", False):
                return format(ctx.trace_id, "032x"), format(ctx.span_id, "016x")
    except (ImportError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
        logger.debug(f"Could not read active OpenTelemetry span: {exc}")
    return None, None


def parse_traceparent(traceparent: str | None) -> tuple[str | None, str | None]:
    """Extrae (trace_id, span_id) de un encabezado W3C traceparent ('00-<trace_id>-<span_id>-01')."""
    if not traceparent or "-" not in traceparent:
        return None, None
    parts = traceparent.strip().split("-")
    if len(parts) >= 3 and parts[1] and parts[2]:
        return parts[1], parts[2]
    if len(parts) >= 2 and parts[1]:
        return parts[1], None
    return None, None


def extract_trace_context(request: Request | None = None) -> tuple[str, str, str]:
    """
    Extrae (trace_id, span_id, traceparent) combinando el span activo de OpenTelemetry
    y los encabezados HTTP ('traceparent', 'x-trace-id').
    """
    incoming_tp = request.headers.get("traceparent") if request is not None else None
    header_trace_id, header_span_id = parse_traceparent(incoming_tp)
    otel_trace_id, otel_span_id = get_active_span_ids()

    x_trace_id = request.headers.get("x-trace-id") if request is not None else None

    trace_id = header_trace_id or otel_trace_id or x_trace_id or uuid.uuid4().hex
    span_id = otel_span_id or header_span_id or os.urandom(8).hex()
    traceparent = f"00-{trace_id}-{span_id}-01"
    return trace_id, span_id, traceparent


def setup_telemetry(
    app: FastAPI,
    service_name: str,
    otlp_endpoint: str | None = None,
) -> Any:
    """
    Configura TracerProvider, BatchSpanProcessor + OTLPSpanExporter,
    FastAPIInstrumentor y HTTPXClientInstrumentor de forma resiliente.
    """
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

        FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)

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
