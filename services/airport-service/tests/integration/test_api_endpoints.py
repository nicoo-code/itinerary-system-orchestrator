import pytest
from httpx import ASGITransport, AsyncClient
from src.main import app


@pytest.mark.asyncio
async def test_health_endpoint():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "UP"
        assert data["service"] == "airport-service"
        assert "circuit_breaker" in data


@pytest.mark.asyncio
async def test_get_airports_endpoint():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/airports")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert "iata_code" in data[0]


@pytest.mark.asyncio
async def test_get_airport_by_id_endpoint():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/airports/1")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert "iata_code" in data
        assert len(data["iata_code"]) == 3


@pytest.mark.asyncio
async def test_get_airport_by_id_not_found():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/airports/999999")
        assert response.status_code == 404
        assert "no encontrado" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_plotly_map_endpoint():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/airports/map/plotly")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "layout" in data
        assert "count" in data


@pytest.mark.asyncio
async def test_get_airports_pagination_and_total_count_header():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        full_res = await client.get("/api/v1/airports")
        assert full_res.status_code == 200
        full_data = full_res.json()
        total = len(full_data)
        assert full_res.headers.get("X-Total-Count") == str(total)

        page_res = await client.get("/api/v1/airports?limit=3&offset=1")
        assert page_res.status_code == 200
        page_data = page_res.json()
        assert len(page_data) == 3
        assert page_res.headers.get("X-Total-Count") == str(total)
        assert page_data[0]["id"] == full_data[1]["id"]


@pytest.mark.asyncio
async def test_delete_airports_cache_endpoint():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        await client.get("/api/v1/airports")
        del_res = await client.delete("/api/v1/airports/cache")
        assert del_res.status_code == 200
        payload = del_res.json()
        assert "invalidated" in payload
        assert payload["cache_key"] == "airports:all:catalog"
