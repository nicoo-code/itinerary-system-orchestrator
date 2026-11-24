# Plan: Suite de Pruebas E2E Reales con Testcontainers

- **Fecha:** 2026-11-19
- **Nivel de Rúbrica:** Nivel 2 — Avanzado (`Pruebas E2E con Testcontainers`)
- **Archivos Afectados:** `tests/e2e/test_e2e_testcontainers.py`, `pytest.ini`, `tests/requirements-e2e.txt`

---

## 1. Objetivo
Implementar una suite E2E real basada en **Testcontainers** (`testcontainers[postgres,redis,rabbitmq]`) que levante contenedores efímeros de **PostgreSQL**, **Redis** y **RabbitMQ**, ejecute las migraciones de Alembic, valide el flujo completo (`Airport Service` → `Itinerary Service` + `Transactional Outbox` → `OutboxRelayWorker` → `RabbitMQ` → `SendNotificationFunction`) y destruya automáticamente los contenedores al finalizar.

---

## 2. Estado Actual y Brechas Detectadas
- `tests/e2e/test_full_flow.py` prueba la lógica en memoria usando SQLite y simulando el relé hacia notificaciones sin contenedores reales de PostgreSQL, Redis ni RabbitMQ.
- La rúbrica de Nivel 2 exige específicamente: *"Suite E2E con Testcontainers que verifica el flujo completo y lo destruye"*.

---

## 3. Pasos de Implementación Detallados

### Paso 1: Dependencias y Marcador Pytest
- Crear `tests/requirements-e2e.txt` con:
  - `testcontainers[postgres,redis,rabbitmq]>=4.7.0`
  - `pytest>=8.0.0`
  - `pytest-asyncio>=0.23.0`
  - `httpx>=0.27.0`
- En `pytest.ini`, registrar el marcador `e2e_containers`:
  ```ini
  markers =
      e2e_containers: Pruebas E2E reales que requieren Docker y Testcontainers
  ```

### Paso 2: Implementar `tests/e2e/test_e2e_testcontainers.py`
- Decorar los tests con `@pytest.mark.e2e_containers` y `@pytest.mark.asyncio`.
- Agregar verificación previa: si `testcontainers` no está instalado o Docker daemon no está disponible, hacer `pytest.skip("Docker/Testcontainers no disponible en este entorno")` para no romper entornos sin Docker, mientras falla explícitamente si algún paso del flujo real falla cuando Docker sí corre.
- Flujo del test `test_complete_flow_with_real_containers(tmp_path)`:
  1. Levantar con context managers (`with PostgresContainer("postgres:15-alpine") as pg, RedisContainer("redis:7-alpine") as redis_c, RabbitMqContainer("rabbitmq:3.12-alpine") as rabbit_c:`):
     - Obtener `pg_url`, `redis_url`, `amqp_url` reales de los contenedores.
  2. **PostgreSQL + Alembic:** Ejecutar las tablas/migraciones en la instancia real de PostgreSQL (usando `alembic.command.upgrade` o `Base.metadata.create_all` verificando el esquema de `itineraries` y `outbox_events`).
  3. **Redis Real:** Instanciar `RedisCacheAdapter(redis_url=redis_url)`, comprobar `await cache.ping() is True`, poblar y leer caché real de aeropuertos.
  4. **Itinerary Service + Transactional Outbox Real en PostgreSQL:**
     - Instanciar `SqlAlchemyItineraryRepository` apuntando a PostgreSQL real y `CreateItineraryUseCase`.
     - Crear un itinerario y verificar en PostgreSQL que existen tanto el registro en `itineraries` como el evento `PENDING` en `outbox_events`.
  5. **RabbitMQ Real + OutboxRelayWorker + Consumer FaaS:**
     - Conectar `RabbitMQPublisher(amqp_url=amqp_url)` real.
     - Iniciar `RabbitMQEventConsumer(amqp_url=amqp_url, notification_func=SendNotificationFunction(repo=notif_repo))` en tarea asíncrona.
     - Ejecutar un ciclo de `OutboxRelayWorker` para publicar el evento real en RabbitMQ y marcarlo como `PUBLISHED` en PostgreSQL.
     - Esperar (con timeout acotado, ej. 10s) a que `notif_repo.list_all()` registre la notificación con `status == "SENT"` y el `itinerary_id` correcto.
  6. **Teardown:** Al salir de los context managers, Testcontainers destruye automáticamente los 3 contenedores.

### Paso 3: Mantener `tests/e2e/test_full_flow.py` Intacto
- No romper ni eliminar el test rápido `tests/e2e/test_full_flow.py` (que corre en CI sin levantar 3 contenedores extra).

---

## 4. Pruebas y Verificación
- Verificar sintaxis, tipado, formato y que `pytest tests/e2e/test_e2e_testcontainers.py -v` se ejecuta limpiamente (corriendo si Docker está activo, o haciendo skip limpio si no hay daemon Docker).
- Ejecutar:
  - `pytest tests/unit tests/e2e/test_full_flow.py -v`
  - `ruff check .`
  - `black --check .`

---

## 5. Criterios de Aceptación
- Existe `tests/e2e/test_e2e_testcontainers.py` con contenedores reales de PostgreSQL, Redis y RabbitMQ.
- El flujo prueba persistencia real, caché real, publicación real en RabbitMQ y consumo real por `notification-service`.
- Los contenedores se destruyen automáticamente al finalizar el test.
- No se rompe el pipeline de CI existente (`ruff`, `black`, `pytest tests/unit`).
