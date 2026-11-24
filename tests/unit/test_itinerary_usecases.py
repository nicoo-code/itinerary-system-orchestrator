import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from src.application.create_itinerary import (
    AirportNotFoundException,
    CreateItineraryUseCase,
    InvalidItineraryException,
)
from src.application.get_itinerary import (
    DeleteItineraryUseCase,
    GetItineraryUseCase,
    ListItinerariesUseCase,
)
from src.application.update_itinerary import UpdateItineraryUseCase
from src.domain.models.itinerary import Itinerary, OutboxEvent


@pytest.fixture
def mock_repo():
    repo = AsyncMock()
    # Simular save_with_outbox retornando el itinerario
    repo.save_with_outbox.side_effect = lambda itin, outbox: itin
    return repo


@pytest.fixture
def mock_validator():
    validator = AsyncMock()
    validator.validate_airport_exists.return_value = True
    return validator


@pytest.mark.asyncio
async def test_create_itinerary_success(mock_repo, mock_validator):
    use_case = CreateItineraryUseCase(mock_repo, mock_validator)

    departure = datetime.now(UTC)
    itinerary = await use_case.execute(
        user_name="Carlos Gomez",
        origin_airport_id=1,
        destination_airport_id=5,
        departure_date=departure,
        duration_minutes=60,
        trace_id="test-trace-12345",
    )

    assert itinerary is not None
    assert itinerary.user_name == "Carlos Gomez"
    assert itinerary.origin_airport_id == 1
    assert itinerary.destination_airport_id == 5
    assert itinerary.status == "CREATED"

    # Verificar que el validador consultó ambos aeropuertos
    assert mock_validator.validate_airport_exists.call_count == 2

    # Verificar que se llamó a save_with_outbox pasando el itinerario y el evento OutboxEvent
    mock_repo.save_with_outbox.assert_called_once()
    args = mock_repo.save_with_outbox.call_args[0]
    passed_itin, passed_outbox = args[0], args[1]

    assert isinstance(passed_itin, Itinerary)
    assert isinstance(passed_outbox, OutboxEvent)
    assert passed_outbox.event_type == "ItineraryCreatedEvent"
    assert passed_outbox.status == "PENDING"
    assert passed_outbox.payload["data"]["user_name"] == "Carlos Gomez"


@pytest.mark.asyncio
async def test_create_itinerary_fails_same_airports(mock_repo, mock_validator):
    use_case = CreateItineraryUseCase(mock_repo, mock_validator)

    with pytest.raises(InvalidItineraryException):
        await use_case.execute(
            user_name="Ana Lopez",
            origin_airport_id=1,
            destination_airport_id=1,
            departure_date=datetime.now(UTC),
            duration_minutes=45,
        )

    # No debió guardar nada en base de datos
    mock_repo.save_with_outbox.assert_not_called()


@pytest.mark.asyncio
async def test_create_itinerary_fails_origin_not_found(mock_repo, mock_validator):
    # Simular que el aeropuerto de origen no existe
    mock_validator.validate_airport_exists.side_effect = lambda aid: aid != 999
    use_case = CreateItineraryUseCase(mock_repo, mock_validator)

    with pytest.raises(AirportNotFoundException) as excinfo:
        await use_case.execute(
            user_name="Pedro Pascal",
            origin_airport_id=999,
            destination_airport_id=5,
            departure_date=datetime.now(UTC),
            duration_minutes=50,
        )

    assert "999" in str(excinfo.value)
    mock_repo.save_with_outbox.assert_not_called()


@pytest.mark.asyncio
async def test_get_and_list_itineraries(mock_repo):
    test_id = uuid.uuid4()
    dummy_itin = Itinerary(
        id=test_id,
        user_name="Luis",
        origin_airport_id=1,
        destination_airport_id=9,
        departure_date=datetime.now(UTC),
        duration_minutes=40,
    )
    mock_repo.find_by_id.return_value = dummy_itin
    mock_repo.list_all.return_value = [dummy_itin]
    mock_repo.delete.return_value = True

    get_uc = GetItineraryUseCase(mock_repo)
    list_uc = ListItinerariesUseCase(mock_repo)
    del_uc = DeleteItineraryUseCase(mock_repo)

    found = await get_uc.execute(test_id)
    assert found.id == test_id

    all_items = await list_uc.execute()
    assert len(all_items) == 1

    deleted = await del_uc.execute(test_id)
    assert deleted is True


@pytest.mark.asyncio
async def test_update_itinerary_success(mock_repo, mock_validator):
    test_id = uuid.uuid4()
    original_created_at = datetime.now(UTC)
    existing_itin = Itinerary(
        id=test_id,
        user_name="Carlos Original",
        origin_airport_id=1,
        destination_airport_id=5,
        departure_date=original_created_at,
        duration_minutes=60,
        status="CREATED",
        created_at=original_created_at,
        updated_at=original_created_at,
    )
    mock_repo.find_by_id.return_value = existing_itin
    mock_repo.update.side_effect = lambda itin: itin

    use_case = UpdateItineraryUseCase(mock_repo, mock_validator)
    new_departure = datetime.now(UTC)
    updated = await use_case.execute(
        itinerary_id=test_id,
        user_name="Carlos Actualizado",
        origin_airport_id=2,
        destination_airport_id=8,
        departure_date=new_departure,
        duration_minutes=90,
        status="CONFIRMED",
    )

    assert updated is not None
    assert updated.id == test_id
    assert updated.user_name == "Carlos Actualizado"
    assert updated.origin_airport_id == 2
    assert updated.destination_airport_id == 8
    assert updated.duration_minutes == 90
    assert updated.status == "CONFIRMED"
    assert updated.created_at == original_created_at
    assert mock_validator.validate_airport_exists.call_count == 2
    mock_repo.update.assert_called_once()


@pytest.mark.asyncio
async def test_update_itinerary_not_found_returns_none(mock_repo, mock_validator):
    mock_repo.find_by_id.return_value = None
    use_case = UpdateItineraryUseCase(mock_repo, mock_validator)

    result = await use_case.execute(
        itinerary_id=uuid.uuid4(),
        user_name="Inexistente",
        origin_airport_id=1,
        destination_airport_id=5,
        departure_date=datetime.now(UTC),
        duration_minutes=60,
    )

    assert result is None
    mock_repo.update.assert_not_called()


@pytest.mark.asyncio
async def test_update_itinerary_fails_same_airports(mock_repo, mock_validator):
    test_id = uuid.uuid4()
    mock_repo.find_by_id.return_value = Itinerary(
        id=test_id,
        user_name="Ana Lopez",
        origin_airport_id=1,
        destination_airport_id=5,
        departure_date=datetime.now(UTC),
        duration_minutes=45,
    )
    use_case = UpdateItineraryUseCase(mock_repo, mock_validator)

    with pytest.raises(InvalidItineraryException):
        await use_case.execute(
            itinerary_id=test_id,
            user_name="Ana Lopez",
            origin_airport_id=3,
            destination_airport_id=3,
            departure_date=datetime.now(UTC),
            duration_minutes=45,
        )

    mock_repo.update.assert_not_called()


@pytest.mark.asyncio
async def test_update_itinerary_fails_airport_not_found(mock_repo, mock_validator):
    test_id = uuid.uuid4()
    mock_repo.find_by_id.return_value = Itinerary(
        id=test_id,
        user_name="Pedro Pascal",
        origin_airport_id=1,
        destination_airport_id=5,
        departure_date=datetime.now(UTC),
        duration_minutes=50,
    )
    mock_validator.validate_airport_exists.side_effect = lambda aid: aid != 888
    use_case = UpdateItineraryUseCase(mock_repo, mock_validator)

    with pytest.raises(AirportNotFoundException) as excinfo:
        await use_case.execute(
            itinerary_id=test_id,
            user_name="Pedro Pascal",
            origin_airport_id=1,
            destination_airport_id=888,
            departure_date=datetime.now(UTC),
            duration_minutes=50,
        )

    assert "888" in str(excinfo.value)
    mock_repo.update.assert_not_called()
