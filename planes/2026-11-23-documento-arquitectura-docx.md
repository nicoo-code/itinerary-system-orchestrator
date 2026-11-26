# Plan: Edición In-Place del Documento de Arquitectura de Software (`.docx`)

- **Fecha:** 2026-11-23
- **Archivo Objetivo (EDICIÓN IN-PLACE OBLIGATORIA):** `C:\Users\nikol\Downloads\Ejemplo 1 de documento de arquitectura de software.docx`
- **Autores del Proyecto:** Linda Michell Ramirez Delgado y Nicolas Alejandro Hernandez Soler
- **Sistema:** Sistema Distribuido de Itinerarios Personales (AeroItinerarios)

---

## 1. Regla Crítica
**NO crear un documento de arquitectura aparte.** Se debe abrir, modificar y guardar **directamente sobre el mismo archivo** `C:\Users\nikol\Downloads\Ejemplo 1 de documento de arquitectura de software.docx` utilizando `python-docx` para conservar intactos la plantilla original, encabezados, pies de página, estilos de Word, tabla de contenido (TOC), bordes y sombreado de tablas.

*(Se puede guardar un respaldo temporal solo en la carpeta `scratch` durante la edición si hace falta, pero el resultado final debe quedar escrito directamente en `C:\Users\nikol\Downloads\Ejemplo 1 de documento de arquitectura de software.docx`.)*

---

## 2. Fuentes de Verdad del Código Real a Consultar
Antes de redactar cada sección, el agente debe basarse estrictamente en el estado real del repositorio `c:\Dev\Universidad\Arquitectura Soft\Taller-Git-Prueba`:
- `README.md` y `docs/architecture/SAD.md` + `docs/architecture/ADRs/*.md`
- `docs/asyncapi.yaml`
- `docker-compose.yml` (9 contenedores: `api-gateway`, `airport-service`, `itinerary-service`, `notification-service`, `postgres-itinerary`, `redis`, `rabbitmq`, `jaeger`, `prometheus`)
- `k8s/*.yaml` (manifiestos Kubernetes con `readinessProbe` y `livenessProbe`)
- `infra/prometheus/prometheus.yml` y `infra/prometheus/alerts.yml`
- `.github/workflows/ci-cd.yml` y `sonar-project.properties`
- Servicios implementados:
  - `services/api-gateway` (FastAPI, reverse proxy `httpx`, rate limiting 60 req/min, emisión/validación JWT `POST /api/v1/auth/token`, propagación `traceparent`, `/metrics`, sirve `frontend/` con Plotly JS)
  - `services/airport-service` (Arquitectura Hexagonal, `ExternalAirportPort`, `ApiColombiaAdapter`, `PlotlyAdapter`, `CircuitBreaker`, Retry exponencial con jitter, `RedisCacheAdapter` con `DELETE /api/v1/airports/cache`, paginación `limit`/`offset`/`X-Total-Count`, OpenTelemetry OTLP, `/metrics`)
  - `services/itinerary-service` (Arquitectura Hexagonal, CRUD completo `POST`/`GET`/`PUT`/`DELETE`, validación síncrona HTTP de aeropuertos, PostgreSQL 15 + SQLAlchemy 2.0 + Alembic automático en `entrypoint.sh`, Transactional Outbox `outbox_events` + `OutboxRelayWorker` + RabbitMQ Publisher Confirms, validación JWT S2S `require_jwt_token`, OpenTelemetry OTLP, `/metrics`)
  - `services/notification-service` (Componente reactivo Serverless/FaaS, `RabbitMQEventConsumer`, `SendNotificationFunction`, `GenerateReportFunction`, SQLite `notifications_log`, propagación `trace_id`, `/metrics`)

---

## 3. Mapa de Edición Sección por Sección sobre la Plantilla

1. **Portada y Encabezados/Pies de página:**
   - Reemplazar `<<DESCRIBIR EL NOMBRE DEL SISTEMA DE INFORMACIÓN>>` por `SISTEMA DISTRIBUIDO DE ITINERARIOS PERSONALES`.
   - Reemplazar referencias institucionales del ejemplo (`INSTITUTO COLOMBIANO DE BIENESTAR FAMILIAR`, `ICBF`, `SSII`, `CUENTAME`, `SIM`, `MTS`, `.NET Framework`, `ASP.NET`, `Azure`) por el contexto académico del **Taller de Arquitectura de Software** y nuestro sistema real.
   - Registrar en portada y/o control de versiones a ambos integrantes: **Linda Michell Ramirez Delgado** y **Nicolas Alejandro Hernandez Soler**.
2. **Tabla de Versionamiento:**
   - Registrar versión `1.0` con fecha `23/11/2026`, autores **Linda Michell Ramirez Delgado, Nicolas Alejandro Hernandez Soler**, descripción: *Definición inicial y consolidada de la arquitectura del Sistema Distribuido de Itinerarios Personales (Microservicios, Event-Driven, FaaS, Resiliencia y Observabilidad).*
3. **Sección 1 — Abreviaturas y Definiciones:**
   - Mantener las relevantes (`Framework`, `JSON`, `API`, `REST`, `Capa`, `Interface`, `Sistema de Información`) y añadir términos propios del proyecto (`DDD`, `AMQP`, `FaaS`, `JWT`, `OTLP`, `CORS`, `CI/CD`, `Transactional Outbox`, `Circuit Breaker`, `AsyncAPI`).
4. **Sección 2 — Introducción y Sección 3 — Alcance:**
   - Redactar introducción y alcance exactos del Sistema Distribuido de Itinerarios Personales (integración de Microservicios + Event-Driven + Serverless FaaS, mapa Plotly JS, resiliencia, observabilidad, CI/CD, Docker y Kubernetes).
   - Eliminar textos instructivos de plantilla (`Nota. ...`, `Breve resumen donde se explican...`).
5. **Sección 4 — Interesados:**
   - Adaptar los roles al proyecto real: Docente/Evaluador de Arquitectura de Software, Arquitectos y Desarrolladores (**Linda Michell Ramirez Delgado** y **Nicolas Alejandro Hernandez Soler**), Usuario Viajero Final, Equipo de QA/Pruebas y Operación DevOps.
6. **Sección 5 — Requerimientos No Funcionales (5.1 a 5.9):**
   - Completar TODAS las tablas de RNF (`RNF-01` a `RNF-22` con numeración consecutiva real, sin `<<Consecutivo>>` ni `Nombre del modulo`):
     - **5.1 Seguridad:** Autenticación JWT HS256 (`POST /api/v1/auth/token`), Autorización S2S (`require_jwt_token`), Transferencia Segura HTTPS/TLS, Código Seguro (OWASP Top 10 + Ruff + Black + SonarQube), Integridad Transaccional (ACID + Transactional Outbox), Auditoría estructurada (JSON logs + `notifications_log`).
     - **5.2 Interoperabilidad:** Integración REST con API Colombia (`ApiColombiaAdapter`), Mensajería asíncrona AMQP con RabbitMQ (`docs/asyncapi.yaml`), Telemetría OTLP hacia Jaeger y scrape Prometheus.
     - **5.3 Fiabilidad:** Disponibilidad, Escalabilidad horizontal (Kubernetes 2 réplicas en `airport-service` e `itinerary-service`), Escalabilidad vertical y de datos (PostgreSQL + Redis), Tolerancia a fallos (`Circuit Breaker`, Retry con Exponential Backoff + Jitter, fallback en memoria), Capacidad de recuperación (Outbox + colas durables RabbitMQ + Alembic).
     - **5.4 Eficiencia en desempeño:** Tiempos de respuesta (< 5ms en fallback fail-fast de Circuit Breaker, caché Redis TTL 3600s, pruebas de carga k6 y Locust).
     - **5.5 Arquitectura:** Arquitectura Hexagonal (Puertos y Adaptadores + DDD) y Microservicios + Event-Driven + FaaS.
     - **5.6 Mantenibilidad:** Reusabilidad, Modularidad, Capacidad de modificación (pruebas unitarias, integración y E2E), Parametrización por variables de entorno y ConfigMaps.
     - **5.7 Gestión de información:** Procesamiento asíncrono de eventos vía RabbitMQ y gestión histórica en PostgreSQL/SQLite.
     - **5.8 Puesta en producción:** Migraciones automáticas versionadas con Alembic (`entrypoint.sh`).
     - **5.9 DevOps:** Integración Continua y Despliegue Continuo con GitHub Actions (`.github/workflows/ci-cd.yml`) y Docker multi-stage.
7. **Sección 6 — Priorización de Atributos de Calidad:**
   - Llenar la tabla completa con los RNFs definidos y sus tuplas `(Importancia, Dificultad)` ej. `(H,H)`, `(H,M)`, `(H,L)`, `(M,M)`.
8. **Sección 7 — Tácticas de Arquitectura y Sección 8 — Verificación de Tácticas:**
   - Mapear cada RNF clave con su táctica, patrón real (Adapter, Circuit Breaker, Retry+Jitter, Cache-Aside, API Gateway, JWT Bearer, Transactional Outbox, Distributed Tracing, Prometheus Alerting), descripción y tecnología real; y su correspondiente escenario de calidad y criterio de aceptación medible en la sección 8.
9. **Sección 9 — Lineamientos Técnicos (9.1 Componentes):**
   - Componentes de reúso: API Colombia, PostgreSQL 15, Redis 7, RabbitMQ 3.12, Jaeger, Prometheus, Plotly JS v2.27.0.
   - Componentes desarrollados: `api-gateway`, `airport-service`, `itinerary-service`, `notification-service`, `frontend` Web App.
10. **Sección 10 — Vistas de Arquitectura (10.1 a 10.6):**
    - **10.1 Vista Lógica:** Contextos Delimitados DDD, tabla de Servicios de Negocio y Relaciones.
    - **10.2 Vista de Implementación:** Capas Hexagonales, componentes de alto nivel y detalle, tablas de componentes y relaciones, flujo de Autenticación (`POST /api/v1/auth/token`), Autorización S2S (`require_jwt_token`), Transacción Tipo A (Creación de Itinerario + validación HTTP + Outbox + RabbitMQ + Notificación FaaS).
    - **10.3 Vista de Integración:** Tabla de interfaces externas/internas (API Colombia, RabbitMQ, Redis, Jaeger, Prometheus) y tablas de relaciones con entrada/salida.
    - **10.4 Vista de Despliegue:** Ambiente de Pruebas (Docker Compose 9 contenedores + Testcontainers) y Ambiente de Producción (Kubernetes `k8s/` con Deployments, Services, Probes y redes aisladas).
    - **10.5 Procesos DevOps:** CI/CD GitHub Actions (`ruff`, `black`, `pytest`, `SonarQube`, `docker compose build/config`) en tablas de relaciones.
    - **10.6 Vista de Amenazas:** Tabla con amenazas reales del sistema (Falsificación de JWT, Abuso/DoS, Caída de API Colombia, Double Write / pérdida de eventos, Exposición de secretos/BD) con mitigaciones y RNFs impactados.
    - **Imágenes/Ilustraciones:** Si la plantilla contiene imágenes incrustadas de ejemplo del ICBF/Azure/`.NET`, generar diagramas limpios en PNG de NUESTRO sistema (Arquitectura de Componentes, Secuencia E2E/Auth, Integración y Despliegue Docker/K8s) con Python (`matplotlib`) y reemplazar las imágenes de ejemplo en el documento (o incrustar los diagramas reales en sus lugares correspondientes) para que no quede ni un solo vestigio del ejemplo ICBF.

---

## 4. Verificación Final
1. Verificar mediante un script Python que en `C:\Users\nikol\Downloads\Ejemplo 1 de documento de arquitectura de software.docx`:
   - No queden placeholders (`<<`, `ICBF`, `CUENTAME`, `SIM`, `ASP.NET`, `.NET Framework`, `Azure`, `SSII`, `Nota. Se deben`).
   - Aparecen ambos autores: **Linda Michell Ramirez Delgado** y **Nicolas Alejandro Hernandez Soler**.
   - El archivo se abre sin errores con `python-docx` y conserva todas las secciones 1–10.6, estilos y tablas.
