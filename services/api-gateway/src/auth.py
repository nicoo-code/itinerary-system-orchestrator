import os
import warnings
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import HTTPException, Request, status

try:
    from jwt.warnings import InsecureKeyLengthWarning

    warnings.filterwarnings("ignore", category=InsecureKeyLengthWarning)
except ImportError:  # pragma: no cover
    pass

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-super-secret-jwt-key-2026-hs256-32b")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))
JWT_AUTH_ENABLED = os.getenv("JWT_AUTH_ENABLED", "true").lower() in (
    "true",
    "1",
    "yes",
)


def is_jwt_auth_enabled() -> bool:
    env_val = os.getenv("JWT_AUTH_ENABLED")
    if env_val is not None:
        return env_val.lower() in ("true", "1", "yes")
    return bool(JWT_AUTH_ENABLED)


def create_access_token(
    subject: str,
    role: str = "traveler",
    expires_delta: timedelta | None = None,
) -> str:
    if not subject or not str(subject).strip():
        raise ValueError("El subject del token JWT no puede estar vacío.")

    now = datetime.now(UTC)
    expire_delta = (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=JWT_EXPIRE_MINUTES)
    )
    payload = {
        "sub": str(subject).strip(),
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + expire_delta).timestamp()),
    }
    secret = os.getenv("JWT_SECRET_KEY", JWT_SECRET_KEY)
    algorithm = os.getenv("JWT_ALGORITHM", JWT_ALGORITHM)
    return jwt.encode(payload, secret, algorithm=algorithm)


def verify_access_token(token: str) -> dict:
    if not token or not str(token).strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de autenticación ausente.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    raw_token = str(token).strip()
    if raw_token.lower().startswith("bearer "):
        raw_token = raw_token[7:].strip()

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token Bearer vacío o malformado.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    secret = os.getenv("JWT_SECRET_KEY", JWT_SECRET_KEY)
    algorithm = os.getenv("JWT_ALGORITHM", JWT_ALGORITHM)

    try:
        payload = jwt.decode(raw_token, secret, algorithms=[algorithm])
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
            detail="Payload del token JWT inválido: falta 'sub'.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload


def require_gateway_jwt(request: Request) -> dict:
    if not is_jwt_auth_enabled():
        return {"sub": "anonymous", "role": "traveler"}

    auth_header = request.headers.get("authorization")
    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Encabezado Authorization ausente.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    parts = auth_header.strip().split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Formato de Authorization inválido. Use 'Bearer <token>'.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = verify_access_token(parts[1].strip())
    request.state.jwt_payload = payload
    return payload
