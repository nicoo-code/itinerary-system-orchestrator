from unittest.mock import AsyncMock

import pytest
from src.application.get_airport_by_id import GetAirportByIdUseCase
from src.application.get_airports_for_plotly import GetAirportsForPlotlyUseCase
from src.application.invalidate_airports_cache import InvalidateAirportsCacheUseCase
from src.application.list_airports import CACHE_KEY_AIRPORTS, ListAirportsUseCase
from src.domain.models.airport import Airport
from src.infrastructure.adapters.plotly_adapter import PlotlyAdapter
from src.infrastructure.adapters.redis_cache_adapter import RedisCacheAdapter


@pytest.fixture
def sample_airports():
    return [
        Airport(
            id=1,
            name="El Dorado",
            iata_code="BOG",
            city="Bogota",
            department="Cundinamarca",
            latitude=4.7016,
            longitude=-74.1469,
            type="Internacional",
        ),
        Airport(
            id=5,
            name="Jose Maria Cordova",
            iata_code="MDE",
            city="Medellin",
            department="Antioquia",
            latitude=6.1645,
            longitude=-75.4231,
            type="Internacional",
        ),
    ]


@pytest.mark.asyncio
async def test_list_airports_fetches_from_external_when_cache_miss(sample_airports):
    mock_external = AsyncMock()
    mock_external.get_all_airports.return_value = sample_airports

    mock_cache = AsyncMock()
    mock_cache.get.return_value = None  # Cache miss

    use_case = ListAirportsUseCase(external_port=mock_external, cache_port=mock_cache)
    result = await use_case.execute()

    assert len(result) == 2
    mock_external.get_all_airports.assert_called_once()
    mock_cache.set.assert_called_once()


@pytest.mark.asyncio
async def test_list_airports_uses_cache_when_available(sample_airports):
    import json

    mock_external = AsyncMock()
    mock_cache = AsyncMock()
    cached_data = json.dumps([a.to_dict() for a in sample_airports])
    mock_cache.get.return_value = cached_data

    use_case = ListAirportsUseCase(external_port=mock_external, cache_port=mock_cache)
    result = await use_case.execute()

    assert len(result) == 2
    mock_external.get_all_airports.assert_not_called()


@pytest.mark.asyncio
async def test_get_airport_by_id_found(sample_airports):
    mock_external = AsyncMock()
    mock_cache = AsyncMock()
    mock_cache.get.return_value = None
    mock_external.get_all_airports.return_value = sample_airports
    mock_external.get_airport_by_id.return_value = sample_airports[0]

    list_uc = ListAirportsUseCase(external_port=mock_external, cache_port=mock_cache)
    get_uc = GetAirportByIdUseCase(external_port=mock_external, list_use_case=list_uc)

    airport = await get_uc.execute(1)
    assert airport is not None
    assert airport.id == 1
    assert airport.iata_code == "BOG"


@pytest.mark.asyncio
async def test_get_airport_by_id_not_found(sample_airports):
    mock_external = AsyncMock()
    mock_cache = AsyncMock()
    mock_cache.get.return_value = None
    mock_external.get_all_airports.return_value = sample_airports
    mock_external.get_airport_by_id.return_value = None

    list_uc = ListAirportsUseCase(external_port=mock_external, cache_port=mock_cache)
    get_uc = GetAirportByIdUseCase(external_port=mock_external, list_use_case=list_uc)

    airport = await get_uc.execute(999)
    assert airport is None


@pytest.mark.asyncio
async def test_get_airports_for_plotly(sample_airports):
    mock_external = AsyncMock()
    mock_cache = AsyncMock()
    mock_cache.get.return_value = None
    mock_external.get_all_airports.return_value = sample_airports

    list_uc = ListAirportsUseCase(external_port=mock_external, cache_port=mock_cache)
    plotly_adapter = PlotlyAdapter()
    plotly_uc = GetAirportsForPlotlyUseCase(
        list_use_case=list_uc, plotly_adapter=plotly_adapter
    )

    result = await plotly_uc.execute()
    assert "data" in result
    assert "layout" in result
    assert result["count"] == 2


@pytest.mark.asyncio
async def test_invalidate_airports_cache_use_case():
    mock_cache = AsyncMock()
    mock_cache.delete.return_value = True

    uc = InvalidateAirportsCacheUseCase(cache_port=mock_cache)
    result = await uc.execute()

    assert result == {"invalidated": True, "cache_key": CACHE_KEY_AIRPORTS}
    mock_cache.delete.assert_called_once_with(CACHE_KEY_AIRPORTS)


@pytest.mark.asyncio
async def test_redis_cache_adapter_in_memory_fallback_delete():
    adapter = RedisCacheAdapter(redis_url="redis://invalid-host-for-test:6379/0")
    adapter._get_client = AsyncMock(return_value=None)

    await adapter.set("test:key", "value", ttl_seconds=60)
    assert await adapter.get("test:key") == "value"

    deleted = await adapter.delete("test:key")
    assert deleted is True
    assert await adapter.get("test:key") is None

    deleted_again = await adapter.delete("test:key")
    assert deleted_again is False
