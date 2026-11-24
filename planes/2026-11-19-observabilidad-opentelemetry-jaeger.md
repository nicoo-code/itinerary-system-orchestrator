# Plan: Observabilidad Real con OpenTelemetry, Jaeger (OTLP) y Propagación `traceparent`

- **Fecha:** 2026-11-19
- **Nivel de Rúbrica:** Nivel 2 — Avanzado
- **Servicio(s) Afectado(s):** `services/airport-service`, `services/itinerary-service`, `services/api-gateway`, `services/notification-service`

---

## 1. Objetivo
Configurar instrumentación distribuida real con **OpenTelemetry** exportando spans vía OTLP gRPC hacia **Jaeger** (`http://jaeger:4317`) y unificar la propagación del encabezado W3C `traceparent` entre `api-gateway`, `itinerary-service`, `airport-service` y los logs JSON estructurados (`trace_id` y `span_id`).

---

## 2. Estado Actual y Brechas Detectadas
1. En `services/airport-service/src/main.py` y `services/itinerary-service/src/main.py` solo se llama `FastAPIInstrumentor.instrument_app(app)` sin configurar `TracerProvider`, `Resource(service.name=...)`, `BatchSpanProcessor` ni `OTLPSpanExporter`. Por ende, Jaeger no recibe trazas.
2. No está instrumentado `httpx` (`HTTPXClientInstrumentor().instrument()`), por lo que las llamadas salientes (`api-gateway -> itinerary-service -> airport-service -> api-colombia`) no generan spans hijos ni propagan el contexto automáticamente.
3. En `services/itinerary-service/src/main.py`, el middleware busca `x-trace-id` en lugar de `traceparent` y nunca asigna `request.state.trace_id`, provocando que `router.py` registre `trace_id = "00000000000000000000000000000000"` en el evento Outbox.
4. `services/api-gateway/requirements.txt` no incluye las dependencias de OpenTelemetry para aparecer como servicio raíz en Jaeger.

---

## 3. Pasos de Implementación Detallados

### Paso 1: Módulo de Inicialización de Telemetría en `airport-service` e `itinerary-service`
- Crear `src/infrastructure/observability.py` en `services/airport-service/` y en `services/itinerary-service/` con una función `setup_telemetry(app: FastAPI, service_name: str, otlp_endpoint: str | None)`:
  1. Crear `Resource.create({"service.name": service_name})`.
  2. Configurar `TracerProvider(resource=resource)` y registrarlo con `trace.set_tracer_provider(provider)`.
  3. Si `otlp_endpoint` está definido (por ejemplo `http://jaeger:4317`, leyendo `OTEL_EXPORTER_OTLP_ENDPOINT`) y no estamos en modo test (`TESTING != "1"`), añadir `BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True))`.
  4. Instrumentar `FastAPIInstrumentor.instrument_app(app)` y `HTTPXClientInstrumentor().instrument()`.
  5. Envolver la inicialización en un manejo seguro para no romper entornos sin collector levantado.

### Paso 2: Corregir Extracción de `trace_id` / `span_id` en Logs y `request.state`
- En `services/itinerary-service/src/main.py`:
  - Leer `traceparent` (formato W3C `00-<trace_id>-<span_id>-01`) o el span activo de OpenTelemetry (`trace.get_current_span().get_span_context()`).
  - Asignar `request.state.trace_id = trace_id` y `request.state.traceparent = traceparent` antes de `await call_next(request)`.
  - Incluir tanto `trace_id` como `span_id` en el `extra` del logger JSON.
- En `services/airport-service/src/main.py`:
  - Extraer `trace_id` y `span_id` del span activo de OpenTelemetry (con fallback al header `traceparent`) y pasarlos en `extra={"trace_id": trace_id, "span_id": span_id}` al logger.

### Paso 3: Propagación en `AirportHttpValidator` y `api-gateway`
- Revisar `services/itinerary-service/src/infrastructure/clients/airport_http_validator.py`:
  - Asegurar que usa `httpx.AsyncClient` (ya instrumentado por `HTTPXClientInstrumentor`) y que acepta opcionalmente `traceparent` para garantizar propagación explícita en headers.
- En `services/api-gateway/`:
  - Agregar `opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-instrumentation-fastapi`, `opentelemetry-instrumentation-httpx`, `opentelemetry-exporter-otlp-proto-grpc` a `requirements.txt`.
  - Inicializar el `TracerProvider` con `service.name="api-gateway"` apuntando a `OTEL_EXPORTER_OTLP_ENDPOINT` (añadir esta variable de entorno al servicio `api-gateway` en `docker-compose.yml`).
  - Asegurar que `span_id` también aparezca en `JsonFormatter` de `api-gateway`.

### Paso 4: Propagación de `trace_id` en `notification-service`
- En `services/notification-service/src/consumers/rabbitmq_event_consumer.py` y `src/main.py`:
  - Extraer `trace_id` del payload del evento `ItineraryCreatedEvent` (`metadata.trace_id` o `trace_id`) y pasarlo en `extra={"trace_id": trace_id}` al loguear el procesamiento de la notificación.

---

## 4. Pruebas y Verificación
1. **Pruebas Unitarias:**
   - Crear/actualizar tests verificando que `setup_telemetry` no falla sin Jaeger corriendo y que el middleware de `itinerary-service` extrae correctamente el `trace_id` desde `traceparent` y lo inyecta en `request.state.trace_id`.
   - Verificar que `JsonFormatter` emite JSON válido con `trace_id` y `span_id` no vacíos.
2. **Validación de Calidad:**
   - `pytest tests/unit -v`
   - `ruff check .`
   - `black --check .`

---

## 5. Criterios de Aceptación
- Al hacer `POST /api/v1/itineraries` a través de `api-gateway`, se genera una traza distribuida continua en Jaeger (`api-gateway` → `itinerary-service` → `airport-service`).
- Los logs JSON de todos los servicios comparten el mismo `trace_id` de la petición.
- Las pruebas unitarias existentes y nuevas pasan sin requerir un servidor Jaeger activo.
