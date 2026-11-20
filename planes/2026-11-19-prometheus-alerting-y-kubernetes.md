# Plan: Monitoreo Prometheus + Reglas de Alerting y Manifiestos Kubernetes

- **Fecha:** 2026-11-19
- **Nivel de Rúbrica:** Nivel 3 — Experto (`Alerting` y `Kubernetes`)
- **Archivos Afectados:** `infra/prometheus/*`, `k8s/*`, `docker-compose.yml`, `services/*/requirements.txt`, `services/*/src/main.py`

---

## 1. Objetivo
1. Cerrar la brecha entre los diagramas de arquitectura (que ya mencionan Prometheus) y el despliegue real: instrumentar métricas `/metrics` en los servicios, añadir **Prometheus** con reglas de **Alerting** reales (`CircuitBreakerOpen`, `HighErrorRate5xx`, `ServiceDown`) a `docker-compose.yml`.
2. Crear manifiestos **Kubernetes** completos y válidos en `k8s/` con `Deployments`, `Services`, `ConfigMaps` y sondas `readinessProbe` y `livenessProbe` para toda la plataforma.

---

## 2. Estado Actual y Brechas Detectadas
1. Los diagramas en `README.md` y `docs/architecture/SAD.md` muestran `Prometheus Metrics`, pero no existe el contenedor de Prometheus ni endpoints `/metrics` ni reglas de alerta.
2. No existe carpeta `k8s/` con manifiestos Kubernetes ni definición de `readinessProbe` / `livenessProbe`.

---

## 3. Pasos de Implementación Detallados

### Paso 1: Métricas Prometheus (`/metrics`) en los Microservicios
- Agregar `prometheus-client>=0.20.0` a los `requirements.txt` de `airport-service`, `itinerary-service`, `api-gateway` y `notification-service`.
- En cada servicio, exponer `GET /metrics` devolviendo `generate_latest()` con `media_type=CONTENT_TYPE_LATEST`:
  - Métricas estándar HTTP (`http_requests_total` por `service`, `method`, `path`, `status_code` y `http_request_duration_seconds`).
  - En `airport-service`: métrica Gauge `airport_circuit_breaker_state` (`0=CLOSED`, `1=HALF_OPEN`, `2=OPEN`) actualizada al consultar `/metrics` desde `circuit_breaker.state`.
  - En `itinerary-service`: métrica Counter `itineraries_created_total`.

### Paso 2: Configuración de Prometheus y Alertas (`infra/prometheus/`)
- Crear `infra/prometheus/prometheus.yml`:
  - `scrape_interval: 15s`
  - `rule_files: ["/etc/prometheus/alerts.yml"]`
  - Scrape jobs para `api-gateway:8000`, `airport-service:8001`, `itinerary-service:8002`, `notification-service:8003`.
- Crear `infra/prometheus/alerts.yml` con al menos 3 alertas reales de producción:
  1. `AirportCircuitBreakerOpen`: `airport_circuit_breaker_state == 2` por `30s` (severidad `critical`).
  2. `HighHttp5xxErrorRate`: tasa de respuestas 5xx > 5% en 2 minutos (severidad `warning`).
  3. `MicroserviceDown`: `up == 0` por `1m` (severidad `critical`).
- Agregar el servicio `prometheus` (`prom/prometheus:v2.51.2`, puerto `9090:9090`) a `docker-compose.yml` montando `infra/prometheus/prometheus.yml` y `infra/prometheus/alerts.yml` en la red `backend-net`.

### Paso 3: Manifiestos Kubernetes (`k8s/`)
Crear manifiestos limpios, bien organizados y listos para `kubectl apply -f k8s/`:
1. `k8s/00-namespace-config.yaml`: `Namespace` `itinerarios-app` + `ConfigMap` con URLs internas y variables no sensibles + `Secret` de ejemplo para credenciales de BD/RabbitMQ.
2. `k8s/01-infrastructure.yaml`: `Deployment` + `Service` para `postgres-itinerary`, `redis`, `rabbitmq` y `jaeger`.
3. `k8s/02-airport-service.yaml`: `Deployment` (2 réplicas) + `Service` (puerto 8001) con `readinessProbe` y `livenessProbe` sobre `GET /health` y límites `resources` (`requests`/`limits`).
4. `k8s/03-itinerary-service.yaml`: `Deployment` (2 réplicas) + `Service` (puerto 8002) con `readinessProbe` y `livenessProbe` sobre `GET /health`.
5. `k8s/04-notification-service.yaml`: `Deployment` + `Service` (puerto 8003) con probes sobre `GET /health`.
6. `k8s/05-api-gateway.yaml`: `Deployment` + `Service` (`NodePort` o `LoadBalancer` en puerto 8000) con probes sobre `GET /health`.

---

## 4. Pruebas y Verificación
1. **Pruebas Unitarias:**
   - Verificar que `GET /metrics` retorna `200 OK` y métricas en formato Prometheus texto en los servicios.
   - Validar sintaxis YAML de `infra/prometheus/*.yml`, `k8s/*.yaml` y `docker-compose.yml` (usando `pyyaml` o `docker compose config` si está disponible).
2. **Calidad:**
   - `pytest tests/unit -v`
   - `ruff check .`
   - `black --check .`

---

## 5. Criterios de Aceptación
- Prometheus queda integrado en `docker-compose.yml` (puerto `9090`) con scrape activo y 3 reglas de alerta en `infra/prometheus/alerts.yml`.
- Los microservicios exponen `/metrics` con métricas HTTP y de negocio (`airport_circuit_breaker_state`).
- Todos los manifiestos en `k8s/` son YAML válido e incluyen `readinessProbe` y `livenessProbe`.
- `ruff`, `black` y `pytest` pasan sin errores.
