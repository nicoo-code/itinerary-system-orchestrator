import logging

from src.application.list_airports import CACHE_KEY_AIRPORTS
from src.domain.ports.cache_port import CachePort

logger = logging.getLogger(__name__)


class InvalidateAirportsCacheUseCase:
    """Caso de uso para invalidar explícitamente la caché del catálogo de aeropuertos."""

    def __init__(self, cache_port: CachePort, cache_key: str = CACHE_KEY_AIRPORTS):
        self._cache_port = cache_port
        self._cache_key = cache_key

    async def execute(self) -> dict:
        invalidated = False
        try:
            invalidated = bool(await self._cache_port.delete(self._cache_key))
            logger.info(
                f"Airports cache invalidation executed for key '{self._cache_key}' (invalidated={invalidated})"
            )
        except (RuntimeError, ValueError, OSError) as e:
            logger.warning(f"Failed to invalidate cache key '{self._cache_key}': {e}")
        return {"invalidated": invalidated, "cache_key": self._cache_key}
