# Plan: Seguridad, Emisión y Validación de JWT (Gateway y Servicios Internos)

- **Fecha:** 2026-11-19
- **Nivel de Rúbrica:** Nivel 2 — Avanzado (`Propagación de JWT` y `API Gateway`)
- **Servicio(s) Afectado(s):** `services/api-gateway`, `services/itinerary-service`, `frontend`

---

## 1. Objetivo
Implementar autenticación real basada en **JWT (HS256)** con emisión de tokens en el `api-gateway`, protección de endpoints sensibles y **propagación + validación** del token hacia `itinerary-service`, cumpliendo el criterio de rúbrica *"Protección de endpoints y propagación del token a servicios internos"* sin degradar la experiencia del frontend.

---

## 2. Estado Actual y Brechas Detectadas
1. En `services/api-gateway/src/gateway.py` únicamente se reenvía el encabezado `Authorization` si existe, pero no se valida ningún token ni se rechazan peticiones sin credenciales válidas.
2. Ningún microservicio interno verifica el token JWT propagado ni extrae la identidad del usuario.
3. No existe un endpoint para emitir un JWT de prueba/sesión para usuarios o clientes Swagger/Postman.

---

## 3. Pasos de Implementación Detallados

### Paso 1: Dependencias y Configuración Compartida
- Agregar `PyJWT>=2.8.0` en `services/api-gateway/requirements.txt` y `services/itinerary-service/requirements.txt`.
- Definir variables de entorno con valores seguros por defecto para desarrollo local (y configurables en `docker-compose.yml`):
  - `JWT_SECRET_KEY` (ej. `dev-super-secret-jwt-key-2026`)
  - `JWT_ALGORITHM=HS256`
  - `JWT_EXPIRE_MINUTES=60`
  - `JWT_AUTH_ENABLED=true` (permite desactivar solo en pruebas unitarias heredadas si hace falta, pero activo por defecto en producción/Docker).

### Paso 2: Endpoint de Autenticación y Validación en `api-gateway`
- En `services/api-gateway/src/auth.py` (nuevo módulo):
  - `create_access_token(subject: str, role: str = "traveler") -> str` usando `PyJWT` con `sub`, `role`, `iat`, `exp`.
  - `verify_access_token(token: str) -> dict` lanzando `HTTPException(401)` si falta, es inválido o expiró.
- En `services/api-gateway/src/gateway.py`:
  - Agregar `POST /api/v1/auth/token`: recibe `{"username": "..."}` (con validación Pydantic) y retorna `{"access_token": "<jwt>", "token_type": "bearer", "expires_in": 3600}`.
  - En las rutas mutadoras de itinerarios (`POST /api/v1/itineraries`, `PUT/DELETE /api/v1/itineraries/{path}`): validar el header `Authorization: Bearer <token>` antes de reenviar; si es inválido o ausente, responder `401 Unauthorized`.
  - Reenviar el header `Authorization` íntegro hacia `itinerary-service`.
  - Mantener públicos los endpoints de consulta de catálogo/mapa (`/api/v1/airports*`, `/health`, `/docs`, archivos estáticos del frontend).

### Paso 3: Validación S2S del JWT Propagado en `itinerary-service`
- Crear `services/itinerary-service/src/infrastructure/api/auth.py`:
  - Dependencia FastAPI `require_jwt_token(request: Request)` que lee `Authorization: Bearer <token>`, valida firma y expiración con `PyJWT` y `settings.jwt_secret_key`, y retorna el payload (`sub`, `role`).
  - Si `JWT_AUTH_ENABLED=true` y el token es ausente/inválido, retornar `401 Unauthorized`.
- Aplicar la dependencia en los endpoints de escritura (`POST`, `PUT`, `DELETE`) en `services/itinerary-service/src/infrastructure/api/router.py` (manteniendo `GET` y `/health` accesibles o configurables para facilitar inspección).
- Actualizar `services/itinerary-service/src/infrastructure/config.py` para incluir `jwt_secret_key`, `jwt_algorithm` y `jwt_auth_enabled`.

### Paso 4: Integración Transparente en el Frontend (`frontend/app.js`)
- Al cargar la aplicación (o antes de enviar un `POST`/`DELETE` de itinerario), solicitar automáticamente un token de sesión a `POST /api/v1/auth/token` (guardándolo en `sessionStorage`) y adjuntar `Authorization: Bearer <token>` en las peticiones `fetch` hacia `/api/v1/itineraries`.
- Si una respuesta devuelve `401`, renovar el token automáticamente una vez y reintentar.

---

## 4. Pruebas y Verificación
1. **Pruebas Unitarias:**
   - Crear `tests/unit/test_jwt_auth.py` probando:
     - Emisión de token desde `POST /api/v1/auth/token`.
     - Rechazo con `401` al intentar `POST /api/v1/itineraries` sin token o con token manipulado/expirado.
     - Aceptación y propagación correcta con token válido.
2. **Asegurar compatibilidad con tests existentes:**
   - Verificar que `tests/unit/` y `services/itinerary-service/tests/` siguen pasando al 100%.
3. **Verificación:**
   - `pytest tests/unit -v`
   - `ruff check .`
   - `black --check .`

---

## 5. Criterios de Aceptación
- Existen endpoints reales de emisión y validación de JWT en `api-gateway` e `itinerary-service`.
- El token se propaga del cliente → `api-gateway` → `itinerary-service` y ambos validan su firma y vigencia.
- El frontend funciona sin fricción obteniendo y adjuntando el token Bearer.
- `ruff`, `black` y `pytest` pasan sin errores.
