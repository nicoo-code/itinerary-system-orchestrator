from fastapi import APIRouter, HTTPException, Query, Response, status
from src.application.get_airport_by_id import GetAirportByIdUseCase
from src.application.get_airports_for_plotly import GetAirportsForPlotlyUseCase
from src.application.invalidate_airports_cache import InvalidateAirportsCacheUseCase
from src.application.list_airports import ListAirportsUseCase
from src.infrastructure.api.schemas import AirportResponse, HealthCheckResponse


def create_airport_router(
    list_airports_use_case: ListAirportsUseCase,
    get_airport_by_id_use_case: GetAirportByIdUseCase,
    get_plotly_use_case: GetAirportsForPlotlyUseCase,
    redis_adapter,
    circuit_breaker,
    invalidate_cache_use_case: InvalidateAirportsCacheUseCase | None = None,
) -> APIRouter:
    router = APIRouter(prefix="", tags=["Airports"])
    effective_invalidate_uc = (
        invalidate_cache_use_case
        or InvalidateAirportsCacheUseCase(cache_port=redis_adapter)
    )

    @router.get(
        "/api/v1/airports",
        response_model=list[AirportResponse],
        summary="Listar todos los aeropuertos",
        description="Retorna el catálogo canónico completo de aeropuertos colombianos adaptado al dominio, con soporte opcional de paginación (limit/offset).",
    )
    async def get_airports(
        response: Response,
        limit: int | None = Query(default=None, ge=1, le=500),
        offset: int = Query(default=0, ge=0),
    ):
        airports = await list_airports_use_case.execute()
        total = len(airports)
        response.headers["X-Total-Count"] = str(total)
        sliced = (
            airports[offset : offset + limit]
            if limit is not None
            else airports[offset:]
        )
        return [AirportResponse.model_validate(a.to_dict()) for a in sliced]

    @router.delete(
        "/api/v1/airports/cache",
        status_code=status.HTTP_200_OK,
        summary="Invalidar caché de aeropuertos",
        description="Invalida explícitamente la clave del catálogo de aeropuertos en Redis y en el fallback en memoria.",
    )
    async def invalidate_airports_cache():
        return await effective_invalidate_uc.execute()

    @router.get(
        "/api/v1/airports/map/plotly",
        summary="Obtener estructura Scattergeo de Plotly JS",
        description="Retorna las coordenadas, marcas y metadatos formateados específicamente para Plotly.newPlot().",
    )
    async def get_plotly_map():
        return await get_plotly_use_case.execute()

    @router.get(
        "/api/v1/airports/{airport_id}",
        response_model=AirportResponse,
        summary="Buscar aeropuerto por ID",
        description="Retorna los datos de un aeropuerto específico. Utilizado por Itinerary Service para validación síncrona.",
    )
    async def get_airport(airport_id: int):
        airport = await get_airport_by_id_use_case.execute(airport_id)
        if not airport:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Aeropuerto con ID {airport_id} no encontrado en el catálogo.",
            )
        return AirportResponse.model_validate(airport.to_dict())

    @router.get(
        "/health",
        response_model=HealthCheckResponse,
        tags=["Health"],
        summary="Healthcheck y estado de dependencias",
    )
    @router.get(
        "/api/v1/airports/health",
        response_model=HealthCheckResponse,
        tags=["Health"],
        summary="Healthcheck y estado de dependencias (alias)",
        include_in_schema=False,
    )
    async def healthcheck():
        redis_ok = await redis_adapter.ping()
        cb_status = circuit_breaker.get_status()
        return HealthCheckResponse(
            status="UP",
            service="airport-service",
            redis_connected=redis_ok,
            circuit_breaker=cb_status,
        )

    return router
