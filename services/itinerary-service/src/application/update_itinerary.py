import logging
import uuid
from datetime import UTC, datetime

from src.domain.exceptions import (
    AirportNotFoundException,
    InvalidItineraryException,
)
from src.domain.models.itinerary import Itinerary
from src.domain.ports.airport_validator_port import AirportValidatorPort
from src.domain.ports.itinerary_repository_port import ItineraryRepositoryPort

logger = logging.getLogger(__name__)

VALID_STATUSES = {"CREATED", "CONFIRMED", "CANCELLED"}


class UpdateItineraryUseCase:
    """Caso de uso para actualizar un itinerario existente validando aeropuertos y reglas de dominio."""

    def __init__(
        self,
        itinerary_repo: ItineraryRepositoryPort,
        airport_validator: AirportValidatorPort,
    ):
        self._itinerary_repo = itinerary_repo
        self._airport_validator = airport_validator

    async def execute(
        self,
        itinerary_id: uuid.UUID,
        user_name: str,
        origin_airport_id: int,
        destination_airport_id: int,
        departure_date: datetime,
        duration_minutes: int,
        status: str | None = None,
    ) -> Itinerary | None:
        # 1. Verificar que el itinerario existe
        existing = await self._itinerary_repo.find_by_id(itinerary_id)
        if not existing:
            return None

        # 2. Validar reglas de dominio
        if origin_airport_id == destination_airport_id:
            raise InvalidItineraryException(
                "El aeropuerto de salida y de llegada no pueden ser el mismo."
            )

        if duration_minutes <= 0:
            raise InvalidItineraryException(
                "La duración del vuelo debe ser mayor a 0 minutos."
            )

        target_status = status if status is not None else existing.status
        if target_status not in VALID_STATUSES:
            raise InvalidItineraryException(
                f"Estado de itinerario inválido: {target_status}. Valores permitidos: {', '.join(sorted(VALID_STATUSES))}."
            )

        # 3. Validar síncronamente contra airport_validator
        origin_exists = await self._airport_validator.validate_airport_exists(
            origin_airport_id
        )
        if not origin_exists:
            logger.error(
                f"Validation failed on update: Origin airport ID {origin_airport_id} does not exist."
            )
            raise AirportNotFoundException(
                f"El aeropuerto de salida con ID {origin_airport_id} no existe."
            )

        destination_exists = await self._airport_validator.validate_airport_exists(
            destination_airport_id
        )
        if not destination_exists:
            logger.error(
                f"Validation failed on update: Destination airport ID {destination_airport_id} does not exist."
            )
            raise AirportNotFoundException(
                f"El aeropuerto de llegada con ID {destination_airport_id} no existe."
            )

        # 4. Construir entidad Itinerary actualizada manteniendo id y created_at originales
        updated_itinerary = Itinerary(
            id=existing.id,
            user_name=user_name,
            origin_airport_id=origin_airport_id,
            destination_airport_id=destination_airport_id,
            departure_date=departure_date,
            duration_minutes=duration_minutes,
            status=target_status,
            created_at=existing.created_at,
            updated_at=datetime.now(UTC),
        )

        # 5. Persistir actualización
        return await self._itinerary_repo.update(updated_itinerary)
