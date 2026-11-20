import uuid

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
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
from src.infrastructure.api.schemas import (
    CreateItineraryRequest,
    HealthCheckResponse,
    ItineraryResponse,
    UpdateItineraryRequest,
)


def create_itinerary_router(
    create_uc: CreateItineraryUseCase,
    get_uc: GetItineraryUseCase,
    list_uc: ListItinerariesUseCase,
    delete_uc: DeleteItineraryUseCase,
    session_factory,
    worker_status_callback,
    update_uc: UpdateItineraryUseCase | None = None,
) -> APIRouter:
    router = APIRouter(prefix="", tags=["Itineraries"])

    @router.post(
        "/api/v1/itineraries",
        response_model=ItineraryResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Crear un nuevo itinerario",
        description="Valida la existencia de los aeropuertos vía HTTP con Airport Service y persiste atómicamente el itinerario y el evento outbox.",
    )
    async def create_itinerary(payload: CreateItineraryRequest, request: Request):
        # Extraer correlation trace_id si existe
        trace_id = getattr(
            request.state, "trace_id", "00000000000000000000000000000000"
        )

        try:
            itinerary = await create_uc.execute(
                user_name=payload.user_name,
                origin_airport_id=payload.origin_airport_id,
                destination_airport_id=payload.destination_airport_id,
                departure_date=payload.departure_date,
                duration_minutes=payload.duration_minutes,
                trace_id=trace_id,
            )
            return itinerary
        except AirportNotFoundException as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
            )
        except InvalidItineraryException as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
            )
        except (RuntimeError, ValueError, KeyError, OSError) as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error interno al procesar el itinerario: {exc}",
            ) from exc

    @router.get(
        "/api/v1/itineraries",
        response_model=list[ItineraryResponse],
        summary="Listar todos los itinerarios",
        description="Retorna el historial completo de itinerarios registrados en el sistema, con soporte opcional de paginación (limit/offset).",
    )
    async def get_all_itineraries(
        response: Response,
        limit: int | None = Query(default=None, ge=1, le=500),
        offset: int = Query(default=0, ge=0),
    ):
        items = await list_uc.execute()
        total = len(items)
        response.headers["X-Total-Count"] = str(total)
        return items[offset : offset + limit] if limit is not None else items[offset:]

    @router.get(
        "/api/v1/itineraries/{itinerary_id}",
        response_model=ItineraryResponse,
        summary="Buscar itinerario por UUID",
        description="Retorna la información detallada de un itinerario específico.",
    )
    async def get_itinerary_by_id(itinerary_id: uuid.UUID):
        itinerary = await get_uc.execute(itinerary_id)
        if not itinerary:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Itinerario con ID {itinerary_id} no encontrado.",
            )
        return itinerary

    @router.put(
        "/api/v1/itineraries/{itinerary_id}",
        response_model=ItineraryResponse,
        status_code=status.HTTP_200_OK,
        summary="Actualizar un itinerario existente",
        description="Actualiza los datos de un itinerario validando aeropuertos síncronamente con Airport Service.",
    )
    async def update_itinerary(
        itinerary_id: uuid.UUID, payload: UpdateItineraryRequest
    ):
        if update_uc is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Caso de uso de actualización no configurado.",
            )
        try:
            itinerary = await update_uc.execute(
                itinerary_id=itinerary_id,
                user_name=payload.user_name,
                origin_airport_id=payload.origin_airport_id,
                destination_airport_id=payload.destination_airport_id,
                departure_date=payload.departure_date,
                duration_minutes=payload.duration_minutes,
                status=payload.status,
            )
        except AirportNotFoundException as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
            )
        except InvalidItineraryException as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
            )
        except (RuntimeError, ValueError, KeyError, OSError) as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error interno al actualizar el itinerario: {exc}",
            ) from exc

        if not itinerary:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Itinerario con ID {itinerary_id} no encontrado.",
            )
        return itinerary

    @router.delete(
        "/api/v1/itineraries/{itinerary_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        summary="Eliminar un itinerario",
        description="Elimina el registro de un itinerario por su UUID.",
    )
    async def delete_itinerary(itinerary_id: uuid.UUID):
        success = await delete_uc.execute(itinerary_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Itinerario con ID {itinerary_id} no encontrado.",
            )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.get(
        "/health",
        response_model=HealthCheckResponse,
        tags=["Health"],
        summary="Healthcheck del servicio",
    )
    @router.get(
        "/api/v1/itineraries/health",
        response_model=HealthCheckResponse,
        tags=["Health"],
        summary="Healthcheck del servicio (alias)",
        include_in_schema=False,
    )
    async def healthcheck():
        db_ok = True
        try:
            session = session_factory()
            session.execute(text("SELECT 1"))
            session.close()
        except (SQLAlchemyError, OSError, RuntimeError):
            db_ok = False

        return HealthCheckResponse(
            status="UP",
            service="itinerary-service",
            database_connected=db_ok,
            outbox_worker_active=worker_status_callback(),
        )

    return router
