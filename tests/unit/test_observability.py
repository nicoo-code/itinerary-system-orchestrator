import json
import logging
import sys
import uuid
from datetime import UTC, datetime
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient
from src.domain.models.itinerary import Itinerary
from src.functions.send_notification_function import SendNotificationFunction
from src.gateway import JsonFormatter as GatewayJsonFormatter
from src.gateway import setup_gateway_telemetry
from src.infrastructure.api.router import create_itinerary_router
from src.infrastructure.clients.airport_http_validator import AirportHttpValidator
from src.infrastructure.observability import JsonFormatter as ServiceJsonFormatter
from src.infrastructure.observability import (
    extract_trace_context,
    parse_traceparent,
    setup_telemetry,
)


def test_setup_telemetry_without_jaeger_does_not_fail(monkeypatch):
    """Verifica que setup_telemetry y setup_gateway_telemetry no fallen sin Jaeger activo ni SDK instalado."""
    monkeypatch.setenv("TESTING", "1")
    dummy_app = FastAPI()
    # 1. No debe lanzar excepción aunque opentelemetry no esté instalado o Jaeger no esté corriendo
    setup_telemetry(
        app=dummy_app,
        service_name="test-itinerary-service",
        otlp_endpoint="http://jaeger:4317",
    )
    setup_gateway_telemetry(
        fastapi_app=dummy_app,
        service_name="api-gateway",
        otlp_endpoint="http://jaeger:4317",
    )

    # 2. Simulando módulos de OpenTelemetry, verifica que se registren TracerProvider, FastAPIInstrumentor y HTTPXClientInstrumentor
    mock_trace = ModuleType("opentelemetry.trace")
    mock_trace.set_tracer_provider = MagicMock()
    mock_otel = ModuleType("opentelemetry")
    mock_otel.trace = mock_trace

    mock_fastapi_mod = ModuleType("opentelemetry.instrumentation.fastapi")
    mock_fastapi_inst = MagicMock()
    mock_fastapi_mod.FastAPIInstrumentor = mock_fastapi_inst

    mock_httpx_mod = ModuleType("opentelemetry.instrumentation.httpx")
    mock_httpx_inst_instance = MagicMock()
    mock_httpx_inst_instance._is_instrumented_by_opentelemetry = False
    mock_httpx_mod.HTTPXClientInstrumentor = MagicMock(
        return_value=mock_httpx_inst_instance
    )

    mock_resources_mod = ModuleType("opentelemetry.sdk.resources")
    mock_resources_mod.Resource = MagicMock()

    mock_sdk_trace_mod = ModuleType("opentelemetry.sdk.trace")
    mock_provider_instance = MagicMock()
    mock_sdk_trace_mod.TracerProvider = MagicMock(return_value=mock_provider_instance)

    mock_export_mod = ModuleType("opentelemetry.sdk.trace.export")
    mock_export_mod.BatchSpanProcessor = MagicMock()

    with patch.dict(
        sys.modules,
        {
            "opentelemetry": mock_otel,
            "opentelemetry.trace": mock_trace,
            "opentelemetry.instrumentation": ModuleType(
                "opentelemetry.instrumentation"
            ),
            "opentelemetry.instrumentation.fastapi": mock_fastapi_mod,
            "opentelemetry.instrumentation.httpx": mock_httpx_mod,
            "opentelemetry.sdk": ModuleType("opentelemetry.sdk"),
            "opentelemetry.sdk.resources": mock_resources_mod,
            "opentelemetry.sdk.trace": mock_sdk_trace_mod,
            "opentelemetry.sdk.trace.export": mock_export_mod,
        },
    ):
        provider = setup_telemetry(
            app=dummy_app,
            service_name="itinerary-service",
            otlp_endpoint="http://jaeger:4317",
        )
        assert provider is mock_provider_instance
        mock_resources_mod.Resource.create.assert_called_once_with(
            {"service.name": "itinerary-service"}
        )
        mock_trace.set_tracer_provider.assert_called_once_with(mock_provider_instance)
        mock_fastapi_inst.instrument_app.assert_called_once_with(
            dummy_app, tracer_provider=mock_provider_instance
        )
        mock_httpx_inst_instance.instrument.assert_called_once_with(
            tracer_provider=mock_provider_instance
        )


def test_parse_traceparent_and_extract_trace_context():
    trace_id_expected = "4bf92f3577b34da6a3ce929d0e0e4736"
    span_id_expected = "00f067aa0ba902b7"
    tp_header = f"00-{trace_id_expected}-{span_id_expected}-01"

    parsed_tid, parsed_sid = parse_traceparent(tp_header)
    assert parsed_tid == trace_id_expected
    assert parsed_sid == span_id_expected

    mock_request = MagicMock(spec=Request)
    mock_request.headers = {"traceparent": tp_header}
    trace_id, span_id, traceparent = extract_trace_context(mock_request)

    assert trace_id == trace_id_expected
    assert len(span_id) == 16
    assert traceparent.startswith(f"00-{trace_id_expected}-")


@pytest.mark.asyncio
async def test_itinerary_middleware_extracts_traceparent_into_request_state(
    monkeypatch,
):
    """
    Verifica que el middleware de itinerary-service extraiga trace_id desde traceparent,
    lo inyecte en request.state.trace_id y lo propague al caso de uso CreateItineraryUseCase.
    """
    monkeypatch.setenv("JWT_AUTH_ENABLED", "false")
    test_app = FastAPI()

    @test_app.middleware("http")
    async def correlation_middleware(request: Request, call_next):
        trace_id, span_id, traceparent = extract_trace_context(request)
        request.state.trace_id = trace_id
        request.state.span_id = span_id
        request.state.traceparent = traceparent
        return await call_next(request)

    mock_create_uc = AsyncMock()
    mock_create_uc.execute.return_value = Itinerary(
        id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        user_name="Elena Nito",
        origin_airport_id=1,
        destination_airport_id=5,
        departure_date=datetime.now(UTC),
        duration_minutes=60,
        status="CREATED",
    )

    router = create_itinerary_router(
        create_uc=mock_create_uc,
        get_uc=AsyncMock(),
        list_uc=AsyncMock(),
        delete_uc=AsyncMock(),
        session_factory=MagicMock(),
        worker_status_callback=lambda: True,
    )
    test_app.include_router(router)

    expected_trace_id = "abcdef1234567890abcdef1234567890"
    expected_span_id = "1234567890abcdef"
    traceparent = f"00-{expected_trace_id}-{expected_span_id}-01"

    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/itineraries",
            headers={"traceparent": traceparent},
            json={
                "user_name": "Elena Nito",
                "origin_airport_id": 1,
                "destination_airport_id": 5,
                "departure_date": datetime.now(UTC).isoformat(),
                "duration_minutes": 60,
            },
        )

    assert response.status_code == 201
    mock_create_uc.execute.assert_called_once()
    call_kwargs = mock_create_uc.execute.call_args.kwargs
    assert call_kwargs["trace_id"] == expected_trace_id


@pytest.mark.asyncio
async def test_airport_http_validator_propagates_traceparent():
    validator = AirportHttpValidator(airport_service_url="http://airport-service:8001")
    tp = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"

    mock_response = MagicMock()
    mock_response.status_code = 200

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        exists = await validator.validate_airport_exists(1, traceparent=tp)
        assert exists is True
        mock_get.assert_called_once_with(
            "http://airport-service:8001/api/v1/airports/1",
            headers={"traceparent": tp},
        )


def test_json_formatters_emit_valid_json_with_trace_and_span_id():
    for formatter_cls in (ServiceJsonFormatter, GatewayJsonFormatter):
        formatter = formatter_cls()
        record = logging.LogRecord(
            name="test-logger",
            level=logging.INFO,
            pathname=__file__,
            lineno=10,
            msg="Test observability log message",
            args=(),
            exc_info=None,
        )
        record.trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
        record.span_id = "00f067aa0ba902b7"

        formatted = formatter.format(record)
        parsed = json.loads(formatted)

        assert parsed["message"] == "Test observability log message"
        assert parsed["trace_id"] == "4bf92f3577b34da6a3ce929d0e0e4736"
        assert parsed["span_id"] == "00f067aa0ba902b7"
        assert len(parsed["trace_id"]) > 0
        assert len(parsed["span_id"]) > 0


@pytest.mark.asyncio
async def test_notification_service_extracts_trace_id_from_metadata(tmp_path, caplog):
    from src.storage.notification_repository import NotificationRepository

    repo = NotificationRepository(db_path=str(tmp_path / "notif_obs.db"))
    func = SendNotificationFunction(repo=repo)

    payload = {
        "event_id": "evt-obs-001",
        "event_type": "ItineraryCreatedEvent",
        "metadata": {"trace_id": "trace-from-metadata-999"},
        "data": {
            "itinerary_id": "itin-001",
            "user_name": "Laura Gómez",
            "origin_airport_id": 1,
            "destination_airport_id": 5,
            "departure_date": "2026-11-20T12:00:00Z",
            "duration_minutes": 55,
        },
    }

    with caplog.at_level(logging.INFO, logger="notification-function"):
        result = await func.execute(payload)

    assert result is True
    matching_records = [
        r
        for r in caplog.records
        if getattr(r, "trace_id", None) == "trace-from-metadata-999"
    ]
    assert len(matching_records) == 1
