# Plan: Invalidación Explícita de Caché Redis y Paginación en APIs Versionadas

- **Fecha:** 2026-11-19
- **Nivel de Rúbrica:** Nivel 2 (`Cache Redis con invalidación`) + Nivel 3 (`API versioning y paginación`)
- **Servicio(s) Afectado(s):** `services/airport-service`, `services/itinerary-service`, `services/api-gateway`

---

## 1. Objetivo
1. Implementar **invalidación explícita de caché** en `airport-service` (`DELETE /api/v1/airports/cache`) respetando el puerto hexagonal `CachePort`.
2. Añadir **paginación retrocompatible** (`limit` y `offset` opcionales + cabecera `X-Total-Count`) en `GET /api/v1/airports` y `GET /api/v1/itineraries` para cumplir el criterio de *API versioning y paginación* sin romper el frontend actual.

---

## 2. Estado Actual y Brechas Detectadas
1. `CachePort` (`services/airport-service/src/domain/ports/cache_port.py`) solo define `get` y `set`; carece de `delete(key)` / `clear()`.
2. `RedisCacheAdapter` (`services/airport-service/src/infrastructure/adapters/redis_cache_adapter.py`) solo expira claves por TTL, sin soporte para invalidación manual.
3. Ni `GET /api/v1/airports` ni `GET /api/v1/itineraries` aceptan parámetros de paginación (`limit`, `offset`).

---

## 3. Pasos de Implementación Detallados

### Paso 1: Invalidación de Caché en `airport-service`
- En `services/airport-service/src/domain/ports/cache_port.py`:
  - Añadir método abstracto `async def delete(self, key: str) -> bool`.
- En `services/airport-service/src/infrastructure/adapters/redis_cache_adapter.py`:
  - Implementar `async def delete(self, key: str) -> bool`:
    - Eliminar la clave en Redis (`await client.delete(key)`) con manejo seguro de `RedisError`.
    - Eliminar también la clave de `self._in_memory_fallback` si existe.
    - Retornar `True` si existía en Redis o en memoria, `False` en caso contrario.
- Crear caso de uso `services/airport-service/src/application/invalidate_airports_cache.py`:
  - `InvalidateAirportsCacheUseCase(cache_port: CachePort)` con `execute() -> dict` que invalida la clave usada por `ListAirportsUseCase` (`airports:all` — verificar el nombre exacto de la clave en `list_airports.py`) y devuelve `{"invalidated": bool, "cache_key": ...}`.
- En `services/airport-service/src/infrastructure/api/router.py`:
  - Exponer `DELETE /api/v1/airports/cache` (`200 OK`) retornando el estado de invalidación.
  - Nota de orden de rutas en FastAPI: registrar `DELETE /api/v1/airports/cache` **antes** de `/api/v1/airports/{airport_id}` para evitar colisiones de ruta.
- Verificar que `services/api-gateway/src/gateway.py` ya enruta `DELETE` en `/api/v1/airports/{path:path}` (sí lo soporta en la línea 144).

### Paso 2: Paginación Retrocompatible en `GET /api/v1/airports`
- En `services/airport-service/src/infrastructure/api/router.py`:
  - Agregar parámetros de consulta opcionales con `Query`:
    - `limit: int | None = Query(default=None, ge=1, le=500)`
    - `offset: int = Query(default=0, ge=0)`
  - Inyectar `response: Response` para establecer `response.headers["X-Total-Count"] = str(total)`.
  - Si `limit is not None`, devolver `airports[offset : offset + limit]`; si `limit is None`, devolver desde `offset` en adelante (manteniendo 100% compatibilidad con el frontend cuando no envía parámetros).

### Paso 3: Paginación Retrocompatible en `GET /api/v1/itineraries`
- En `services/itinerary-service/src/infrastructure/api/router.py`:
  - Agregar `limit: int | None = Query(default=None, ge=1, le=500)` y `offset: int = Query(default=0, ge=0)`.
  - Establecer `response.headers["X-Total-Count"] = str(total)` y aplicar slice paginado (`items[offset : offset + limit]` si `limit` está definido).

---

## 4. Pruebas y Verificación
1. **Pruebas Unitarias:**
   - Actualizar mocks de `CachePort` existentes (si los hay en `tests/unit/` o `services/airport-service/tests/`) para incluir `delete`.
   - Agregar tests para `RedisCacheAdapter.delete` (fallback en memoria), `InvalidateAirportsCacheUseCase`, `DELETE /api/v1/airports/cache` y paginación (`limit`, `offset`, `X-Total-Count`) en ambos servicios.
2. **Verificación:**
   - `pytest tests/unit -v`
   - `pytest services/airport-service/tests -v`
   - `ruff check .`
   - `black --check .`

---

## 5. Criterios de Aceptación
- `DELETE /api/v1/airports/cache` invalida efectivamente la caché Redis y el fallback en memoria.
- `GET /api/v1/airports?limit=10&offset=0` y `GET /api/v1/itineraries?limit=5&offset=0` devuelven la página solicitada y el header `X-Total-Count`.
- Llamadas sin `limit`/`offset` siguen devolviendo la lista completa sin romper el frontend ni los tests existentes.
