import inspect
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from src.auth import create_access_token, verify_access_token
from src.domain.models.itinerary import Itinerary
from src.gateway import app as gateway_app
from src.infrastructure.api.auth import require_jwt_token
from src.infrastructure.api.router import create_itinerary_router
from src.infrastructure.config import settings as itinerary_settings
from starlette.requests import Request as StarletteRequest


def _build_itinerary_test_app() -> FastAPI:
    created_itinerary = Itinerary(
        id=uuid.uuid4(),
        user_name="Santiago Botero",
        origin_airport_id=1,
        destination_airport_id=4,
        departure_date=datetime.now(UTC),
        duration_minutes=45,
        status="CREATED",
    )

    mock_create_uc = AsyncMock()
    mock_create_uc.execute.return_value = created_itinerary
    mock_get_uc = AsyncMock()
    mock_get_uc.execute.return_value = created_itinerary
    mock_list_uc = AsyncMock()
    mock_list_uc.execute.return_value = [created_itinerary]
    mock_delete_uc = AsyncMock()
    mock_delete_uc.execute.return_value = True
    mock_update_uc = AsyncMock()
    mock_update_uc.execute.return_value = created_itinerary

    kwargs = {
        "create_uc": mock_create_uc,
        "get_uc": mock_get_uc,
        "list_uc": mock_list_uc,
        "delete_uc": mock_delete_uc,
        "session_factory": MagicMock(),
        "worker_status_callback": lambda: True,
    }
    sig = inspect.signature(create_itinerary_router)
    if "update_uc" in sig.parameters:
        kwargs["update_uc"] = mock_update_uc

    app = FastAPI()
    app.include_router(create_itinerary_router(**kwargs))
    return app


def test_create_and_verify_access_token_roundtrip():
    token = create_access_token(subject="maria.gomez", role="traveler")
    assert isinstance(token, str)
    assert token.count(".") == 2

    payload = verify_access_token(token)
    assert payload["sub"] == "maria.gomez"
    assert payload["role"] == "traveler"
    assert "iat" in payload
    assert "exp" in payload
    assert payload["exp"] > payload["iat"]


def test_verify_access_token_rejects_expired_and_tampered():
    expired_token = create_access_token(
        subject="expired.user",
        expires_delta=timedelta(seconds=-10),
    )
    with pytest.raises(HTTPException) as exc_expired:
        verify_access_token(expired_token)
    assert exc_expired.value.status_code == 401
    assert "expirado" in exc_expired.value.detail.lower()

    valid_token = create_access_token(subject="valid.user")
    tampered_token = valid_token[:-4] + "XXXX"
    with pytest.raises(HTTPException) as exc_tampered:
        verify_access_token(tampered_token)
    assert exc_tampered.value.status_code == 401


@pytest.mark.asyncio
async def test_gateway_auth_token_endpoint_issues_valid_jwt():
    async with AsyncClient(
        transport=ASGITransport(app=gateway_app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/auth/token",
            json={"username": "camilo.torres"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["token_type"] == "bearer"
        assert body["expires_in"] == 3600
        assert "access_token" in body

        decoded = verify_access_token(body["access_token"])
        assert decoded["sub"] == "camilo.torres"
        assert decoded["role"] == "traveler"


@pytest.mark.asyncio
async def test_gateway_auth_token_rejects_blank_username():
    async with AsyncClient(
        transport=ASGITransport(app=gateway_app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/auth/token",
            json={"username": "   "},
        )
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_gateway_rejects_mutating_itinerary_requests_without_or_invalid_jwt():
    payload = {
        "user_name": "Laura Restrepo",
        "origin_airport_id": 1,
        "destination_airport_id": 2,
        "departure_date": datetime.now(UTC).isoformat(),
        "duration_minutes": 55,
    }

    async with AsyncClient(
        transport=ASGITransport(app=gateway_app), base_url="http://test"
    ) as client:
        # 1. Sin header Authorization -> 401
        res_no_token = await client.post("/api/v1/itineraries", json=payload)
        assert res_no_token.status_code == 401

        # 2. Con token manipulado -> 401
        res_bad_token = await client.post(
            "/api/v1/itineraries",
            json=payload,
            headers={"Authorization": "Bearer invalid.jwt.token"},
        )
        assert res_bad_token.status_code == 401

        # 3. Con token expirado -> 401
        expired = create_access_token(
            subject="laura", expires_delta=timedelta(seconds=-30)
        )
        res_expired = await client.post(
            "/api/v1/itineraries",
            json=payload,
            headers={"Authorization": f"Bearer {expired}"},
        )
        assert res_expired.status_code == 401

        # 4. PUT y DELETE sin token -> 401
        target_id = uuid.uuid4()
        res_put_no_token = await client.put(
            f"/api/v1/itineraries/{target_id}", json=payload
        )
        assert res_put_no_token.status_code == 401

        res_delete_no_token = await client.delete(f"/api/v1/itineraries/{target_id}")
        assert res_delete_no_token.status_code == 401


@pytest.mark.asyncio
async def test_gateway_accepts_and_propagates_valid_jwt_to_itinerary_service(
    monkeypatch,
):
    captured = {}
    orig_request = httpx.AsyncClient.request

    async def fake_request(self, method, url, **kwargs):
        if isinstance(self._transport, ASGITransport):
            return await orig_request(self, method, url, **kwargs)
        captured["method"] = method
        captured["url"] = str(url)
        captured["headers"] = kwargs.get("headers") or {}
        return httpx.Response(
            status_code=201,
            json={"id": str(uuid.uuid4()), "status": "CREATED"},
            headers={"content-type": "application/json"},
        )

    monkeypatch.setattr(httpx.AsyncClient, "request", fake_request)

    async with AsyncClient(
        transport=ASGITransport(app=gateway_app), base_url="http://test"
    ) as client:
        token_res = await client.post(
            "/api/v1/auth/token",
            json={"username": "andres.cepeda"},
        )
        token = token_res.json()["access_token"]

        payload = {
            "user_name": "Andres Cepeda",
            "origin_airport_id": 1,
            "destination_airport_id": 3,
            "departure_date": datetime.now(UTC).isoformat(),
            "duration_minutes": 60,
        }
        res = await client.post(
            "/api/v1/itineraries",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 201
        assert captured["method"] == "POST"
        assert captured["headers"].get("authorization") == f"Bearer {token}"

        # Verificar que el token propagado también pasa la validación S2S de itinerary-service
        s2s_scope = {
            "type": "http",
            "headers": [(b"authorization", f"Bearer {token}".encode())],
            "state": {},
        }
        starlette_req = StarletteRequest(s2s_scope)
        s2s_payload = require_jwt_token(starlette_req)
        assert s2s_payload["sub"] == "andres.cepeda"


@pytest.mark.asyncio
async def test_itinerary_service_s2s_jwt_protection(monkeypatch):
    monkeypatch.setattr(itinerary_settings, "jwt_auth_enabled", True)
    monkeypatch.setenv("JWT_AUTH_ENABLED", "true")

    itinerary_app = _build_itinerary_test_app()
    payload = {
        "user_name": "Santiago Botero",
        "origin_airport_id": 1,
        "destination_airport_id": 4,
        "departure_date": datetime.now(UTC).isoformat(),
        "duration_minutes": 45,
    }

    async with AsyncClient(
        transport=ASGITransport(app=itinerary_app), base_url="http://test"
    ) as client:
        # 1. POST directo a itinerary-service sin JWT cuando JWT_AUTH_ENABLED=true -> 401
        res_unauth = await client.post("/api/v1/itineraries", json=payload)
        assert res_unauth.status_code == 401

        # 2. POST con JWT válido -> 201
        token = create_access_token(subject="santiago.botero")
        res_auth = await client.post(
            "/api/v1/itineraries",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res_auth.status_code == 201
        created_id = res_auth.json()["id"]

        # 3. GET sigue público -> 200
        res_get = await client.get(f"/api/v1/itineraries/{created_id}")
        assert res_get.status_code == 200

        # 4. DELETE sin JWT -> 401
        res_del_unauth = await client.delete(f"/api/v1/itineraries/{created_id}")
        assert res_del_unauth.status_code == 401

        # 5. DELETE con JWT válido -> 204
        res_del_auth = await client.delete(
            f"/api/v1/itineraries/{created_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res_del_auth.status_code == 204
