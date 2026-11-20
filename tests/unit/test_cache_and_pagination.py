import importlib.util
import os
import sys
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
AIRPORT_SRC = os.path.join(ROOT_DIR, "services/airport-service")
ITINERARY_SRC = os.path.join(ROOT_DIR, "services/itinerary-service")


def _load_module(name: str, file_path: str):
    spec = importlib.util.spec_from_file_location(name, file_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def airport_env(monkeypatch):
    monkeypatch.syspath_prepend(AIRPORT_SRC)
    for mod_name in list(sys.modules.keys()):
        if mod_name == "src" or mod_name.startswith("src."):
            sys.modules.pop(mod_name, None)
    yield
    for mod_name in list(sys.modules.keys()):
        if mod_name == "src" or mod_name.startswith("src."):
            sys.modules.pop(mod_name, None)


@pytest.fixture
def itinerary_env(monkeypatch):
    monkeypatch.syspath_prepend(ITINERARY_SRC)
    for mod_name in list(sys.modules.keys()):
        if mod_name == "src" or mod_name.startswith("src."):
            sys.modules.pop(mod_name, None)
    yield
    for mod_name in list(sys.modules.keys()):
        if mod_name == "src" or mod_name.startswith("src."):
            sys.modules.pop(mod_name, None)


@pytest.mark.asyncio
async def test_redis_cache_adapter_delete_memory_and_redis(airport_env):
    from src.infrastructure.adapters.redis_cache_adapter import RedisCacheAdapter

    adapter = RedisCacheAdapter(redis_url="redis://localhost:6379/0")
    adapter._get_client = AsyncMock(return_value=None)

    await adapter.set("airports:all:catalog", '[{"id": 1}]', ttl_seconds=120)
    assert await adapter.get("airports:all:catalog") is not None

    assert await adapter.delete("airports:all:catalog") is True
    assert await adapter.get("airports:all:catalog") is None
    assert await adapter.delete("airports:all:catalog") is False

    # Con cliente Redis simulado
    fake_redis = AsyncMock()
    fake_redis.delete.return_value = 1
    adapter._get_client = AsyncMock(return_value=fake_redis)
    assert await adapter.delete("airports:all:catalog") is True
    fake_redis.delete.assert_called_once_with("airports:all:catalog")


@pytest.mark.asyncio
async def test_invalidate_airports_cache_and_pagination_router(airport_env):
    from src.application.invalidate_airports_cache import InvalidateAirportsCacheUseCase
    from src.domain.models.airport import Airport
    from src.infrastructure.adapters.redis_cache_adapter import RedisCacheAdapter
    from src.infrastructure.api.router import create_airport_router

    airports = [
        Airport(
            id=i,
            name=f"Aeropuerto {i}",
            iata_code=f"A{i:02d}",
            city="Bogota",
            department="Cundinamarca",
            latitude=4.7,
            longitude=-74.1,
            type="Internacional",
        )
        for i in range(1, 16)
    ]

    cache_adapter = RedisCacheAdapter()
    cache_adapter._get_client = AsyncMock(return_value=None)
    await cache_adapter.set("airports:all:catalog", "cached-payload", ttl_seconds=300)

    list_uc = AsyncMock()
    list_uc.execute.return_value = airports
    get_by_id_uc = AsyncMock()
    plotly_uc = AsyncMock()
    cb = AsyncMock()
    invalidate_uc = InvalidateAirportsCacheUseCase(cache_port=cache_adapter)

    test_app = FastAPI()
    test_app.include_router(
        create_airport_router(
            list_airports_use_case=list_uc,
            get_airport_by_id_use_case=get_by_id_uc,
            get_plotly_use_case=plotly_uc,
            redis_adapter=cache_adapter,
            circuit_breaker=cb,
            invalidate_cache_use_case=invalidate_uc,
        )
    )

    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
    ) as client:
        # 1. Sin parámetros -> lista completa + X-Total-Count
        res_all = await client.get("/api/v1/airports")
        assert res_all.status_code == 200
        assert len(res_all.json()) == 15
        assert res_all.headers.get("X-Total-Count") == "15"

        # 2. Con limit y offset -> página solicitada + X-Total-Count intacto
        res_page = await client.get("/api/v1/airports?limit=5&offset=2")
        assert res_page.status_code == 200
        page_items = res_page.json()
        assert len(page_items) == 5
        assert [item["id"] for item in page_items] == [3, 4, 5, 6, 7]
        assert res_page.headers.get("X-Total-Count") == "15"

        # 3. Invalidar caché explícitamente
        res_del = await client.delete("/api/v1/airports/cache")
        assert res_del.status_code == 200
        assert res_del.json() == {
            "invalidated": True,
            "cache_key": "airports:all:catalog",
        }

        # Segunda llamada reporta False porque ya fue invalidada
        res_del_again = await client.delete("/api/v1/airports/cache")
        assert res_del_again.status_code == 200
        assert res_del_again.json()["invalidated"] is False


@pytest.mark.asyncio
async def test_itineraries_pagination_and_total_count_header(itinerary_env):
    from src.domain.models.itinerary import Itinerary
    from src.infrastructure.api.router import create_itinerary_router

    now = datetime.now(UTC)
    sample_itineraries = [
        Itinerary(
            id=uuid.uuid4(),
            user_name=f"Pasajero {i}",
            origin_airport_id=1,
            destination_airport_id=2,
            departure_date=now,
            duration_minutes=60 + i,
            status="CREATED",
            created_at=now,
        )
        for i in range(1, 11)
    ]

    create_uc = AsyncMock()
    get_uc = AsyncMock()
    list_uc = AsyncMock()
    list_uc.execute.return_value = sample_itineraries
    delete_uc = AsyncMock()

    test_app = FastAPI()
    test_app.include_router(
        create_itinerary_router(
            create_uc=create_uc,
            get_uc=get_uc,
            list_uc=list_uc,
            delete_uc=delete_uc,
            session_factory=lambda: None,
            worker_status_callback=lambda: True,
        )
    )

    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
    ) as client:
        # 1. Sin limit/offset -> lista completa
        res_all = await client.get("/api/v1/itineraries")
        assert res_all.status_code == 200
        assert len(res_all.json()) == 10
        assert res_all.headers.get("X-Total-Count") == "10"

        # 2. Con limit=5 y offset=0 -> primeros 5 y X-Total-Count=10
        res_page = await client.get("/api/v1/itineraries?limit=5&offset=0")
        assert res_page.status_code == 200
        page_items = res_page.json()
        assert len(page_items) == 5
        assert page_items[0]["user_name"] == "Pasajero 1"
        assert page_items[4]["user_name"] == "Pasajero 5"
        assert res_page.headers.get("X-Total-Count") == "10"

        # 3. Con limit=3 y offset=8 -> últimos 2
        res_tail = await client.get("/api/v1/itineraries?limit=3&offset=8")
        assert res_tail.status_code == 200
        tail_items = res_tail.json()
        assert len(tail_items) == 2
        assert [item["user_name"] for item in tail_items] == [
            "Pasajero 9",
            "Pasajero 10",
        ]
        assert res_tail.headers.get("X-Total-Count") == "10"
