import os
import warnings

import jwt
from fastapi import HTTPException, Request, status
from src.infrastructure.config import settings

try:
    from jwt.warnings import InsecureKeyLengthWarning

    warnings.filterwarnings("ignore", category=InsecureKeyLengthWarning)
except ImportError:  # pragma: no cover
    pass


def _is_jwt_auth_enabled() -> bool:
    env_val = os.getenv("JWT_AUTH_ENABLED")
    if env_val is not None and env_val.lower() in ("false", "0", "no"):
        return False
    return bool(settings.jwt_auth_enabled)


def require_jwt_token(request: Request) -> dict:
    if not _is_jwt_auth_enabled():
        payload = {"sub": "anonymous", "role": "traveler"}
        request.state.jwt_payload = payload
        return payload

    auth_header = request.headers.get("authorization")
    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Encabezado Authorization Bearer requerido.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    parts = auth_header.strip().split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Formato de Authorization inválido. Use 'Bearer <token>'.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1].strip()
    secret = os.getenv("JWT_SECRET_KEY", settings.jwt_secret_key)
    algorithm = os.getenv("JWT_ALGORITHM", settings.jwt_algorithm)

    try:
        payload = jwt.decode(token, secret, algorithms=[algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El token JWT ha expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token JWT inválido.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if not isinstance(payload, dict) or not payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token JWT sin identidad de sujeto ('sub').",
            headers={"WWW-Authenticate": "Bearer"},
        )

    request.state.jwt_payload = payload
    return payload
