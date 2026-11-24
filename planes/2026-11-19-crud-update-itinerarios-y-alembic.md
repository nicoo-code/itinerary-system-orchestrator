# Plan: CRUD Completo de Itinerarios (`PUT`/`PATCH`) y Migraciones Alembic en Arranque

- **Fecha:** 2026-11-19
- **Nivel de Rúbrica:** Nivel 1 — Base (Obligatorio)
- **Servicio(s) Afectado(s):** `services/itinerary-service`

---

## 1. Objetivo
Completar el criterio obligatorio de **CRUD completo** en `itinerary-service` añadiendo la operación de actualización (`PUT /api/v1/itineraries/{itinerary_id}`) con validación síncrona de aeropuertos y consistencia transaccional, y garantizar que las migraciones de **Alembic** (`alembic upgrade head`) se ejecuten automáticamente al iniciar el contenedor en lugar de depender únicamente de `Base.metadata.create_all()`.

---

## 2. Estado Actual y Brechas Detectadas
1. En `services/itinerary-service/src/infrastructure/api/router.py` solo existen `POST`, `GET` (listado y por ID) y `DELETE`. No existe operación de actualización (`PUT`/`PATCH`).
2. `ItineraryRepositoryPort` (`services/itinerary-service/src/domain/ports/itinerary_repository_port.py`) y `SqlAlchemyItineraryRepository` (`services/itinerary-service/src/infrastructure/persistence/sqlalchemy_itinerary_repo.py`) carecen de un método `update(...)`.
3. `services/itinerary-service/Dockerfile` ejecuta directamente `uvicorn src.main:app ...` y `src/main.py` usa `Base.metadata.create_all(bind=engine)`, dejando las migraciones de Alembic sin ejecutarse en el despliegue real.

---

## 3. Pasos de Implementación Detallados

### Paso 1: Puerto de Repositorio (`domain/ports/itinerary_repository_port.py`)
- Agregar el método abstracto:
  ```python
  @abstractmethod
  async def update(self, itinerary: Itinerary) -> Itinerary | None:
      """Actualiza un itinerario existente en la base de datos."""
  ```

### Paso 2: Caso de Uso (`application/update_itinerary.py`)
- Crear `UpdateItineraryUseCase(itinerary_repo: ItineraryRepositoryPort, airport_validator: AirportValidatorPort)`.
- Método `async def execute(self, itinerary_id: uuid.UUID, user_name: str, origin_airport_id: int, destination_airport_id: int, departure_date: datetime, duration_minutes: int, status: str | None = None) -> Itinerary | None`:
  1. Verificar que el itinerario existe mediante `find_by_id(itinerary_id)`. Si no existe, retornar `None`.
  2. Validar reglas de dominio:
     - `origin_airport_id != destination_airport_id` (lanzar `InvalidItineraryException`).
     - `duration_minutes > 0` (lanzar `InvalidItineraryException`).
     - `status` válido si se envía (`CREATED`, `CONFIRMED`, `CANCELLED`).
  3. Validar síncronamente contra `airport_validator` que tanto `origin_airport_id` como `destination_airport_id` existen (lanzar `AirportNotFoundException` si alguno no existe).
  4. Construir la entidad `Itinerary` actualizada manteniendo `id` y `created_at` originales y actualizando `updated_at = datetime.now(UTC)`.
  5. Persistir llamando a `itinerary_repo.update(updated_itinerary)`.

### Paso 3: Repositorio SQLAlchemy (`infrastructure/persistence/sqlalchemy_itinerary_repo.py`)
- Implementar `async def update(self, itinerary: Itinerary) -> Itinerary | None`:
  - Buscar `ItineraryModel` por `str(itinerary.id)`.
  - Si no existe, retornar `None`.
  - Actualizar `user_name`, `origin_airport_id`, `destination_airport_id`, `departure_date`, `duration_minutes`, `status` y `updated_at`.
  - Hacer `session.commit()`, `session.refresh(model)` y devolver `self._to_domain_itinerary(model)`.
  - En caso de excepción, ejecutar `session.rollback()` y relanzar.

### Paso 4: Esquemas Pydantic y Router FastAPI
- En `services/itinerary-service/src/infrastructure/api/schemas.py`:
  - Crear `UpdateItineraryRequest` con validaciones Pydantic (`user_name`, `origin_airport_id`, `destination_airport_id`, `departure_date`, `duration_minutes`, `status: str = "CREATED"`).
- En `services/itinerary-service/src/infrastructure/api/router.py`:
  - Recibir `update_uc: UpdateItineraryUseCase` en `create_itinerary_router(...)`.
  - Exponer `PUT /api/v1/itineraries/{itinerary_id}` retornando `ItineraryResponse` (`200 OK`):
    - `404 Not Found` si no existe.
    - `400 Bad Request` si falla `AirportNotFoundException`.
    - `422 Unprocessable Entity` si falla `InvalidItineraryException`.
- En `services/itinerary-service/src/main.py`:
  - Instanciar `update_uc = UpdateItineraryUseCase(itinerary_repo=itinerary_repo, airport_validator=airport_validator)` e inyectarlo en `create_itinerary_router(...)`.

### Paso 5: Ejecución Automática de Alembic al Arrancar
- Revisar `services/itinerary-service/src/infrastructure/persistence/alembic/env.py` para asegurarse de que lee `DATABASE_URL` desde variables de entorno (`os.getenv("DATABASE_URL")`) correctamente.
- Crear un script de arranque `services/itinerary-service/entrypoint.sh` (o comando compuesto en `Dockerfile`):
  ```sh
  #!/bin/sh
  set -e
  alembic upgrade head
  exec uvicorn src.main:app --host 0.0.0.0 --port "${PORT:-8002}"
  ```
- Actualizar `services/itinerary-service/Dockerfile` para copiar `entrypoint.sh`, darle permisos `+x` y usarlo como `CMD` (asegurando saltos de línea LF).
- Mantener `Base.metadata.create_all(bind=engine)` solo como respaldo seguro para entornos SQLite de pruebas si aplica, o documentar claramente su uso.

---

## 4. Pruebas y Verificación
1. **Pruebas Unitarias:** Agregar tests en `services/itinerary-service/tests/unit/test_itinerary_usecases.py` y `tests/unit/test_itinerary_usecases.py` cubriendo:
   - Actualización exitosa de un itinerario existente.
   - Retorno `None` / `404` cuando el itinerario no existe.
   - Rechazo cuando origen y destino son iguales (`InvalidItineraryException`).
   - Rechazo cuando algún aeropuerto no existe (`AirportNotFoundException`).
2. **Pruebas de Integración:** Agregar test de `PUT /api/v1/itineraries/{id}` en `services/itinerary-service/tests/integration/test_itinerary_api.py`.
3. **Verificación de calidad:**
   - `pytest tests/unit -v`
   - `pytest services/itinerary-service/tests -v`
   - `ruff check .`
   - `black --check .`

---

## 5. Criterios de Aceptación
- `PUT /api/v1/itineraries/{itinerary_id}` funciona end-to-end respetando Arquitectura Hexagonal.
- El contenedor de `itinerary-service` ejecuta `alembic upgrade head` antes de levantar Uvicorn.
- Todos los tests unitarios y de integración pasan en verde, sin errores de `ruff` ni `black`.
