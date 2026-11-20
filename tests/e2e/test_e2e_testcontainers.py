import asyncio
import contextlib
import importlib.util
import os
import sys
import time
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

# Agregar rutas de servicios al sys.path para soportar carpetas con guiones
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
AIRPORT_SERVICE_DIR = os.path.join(ROOT_DIR, "services/airport-service")
ITINERARY_SERVICE_DIR = os.path.join(ROOT_DIR, "services/itinerary-service")
NOTIFICATION_SERVICE_DIR = os.path.join(ROOT_DIR, "services/notification-service")

for svc_dir in (
    AIRPORT_SERVICE_DIR,
    ITINERARY_SERVICE_DIR,
    NOTIFICATION_SERVICE_DIR,
):
    if svc_dir not in sys.path:
        sys.path.insert(0, svc_dir)

from src.application.create_itinerary import CreateItineraryUseCase
from src.application.get_airport_by_id import GetAirportByIdUseCase
from src.application.list_airports import (
    CACHE_KEY_AIRPORTS,
    ListAirportsUseCase,
)
from src.consumers.rabbitmq_event_consumer import RabbitMQEventConsumer
from src.domain.ports.airport_validator_port import AirportValidatorPort
from src.functions.send_notification_function import SendNotificationFunction
from src.infrastructure.adapters.api_colombia_adapter import ApiColombiaAdapter
from src.infrastructure.adapters.redis_cache_adapter import RedisCacheAdapter
from src.infrastructure.messaging.outbox_relay_worker import OutboxRelayWorker
from src.infrastructure.messaging.rabbitmq_publisher import RabbitMQPublisher
from src.infrastructure.persistence.models import (
    Base,
    ItineraryModel,
    OutboxEventModel,
)
from src.infrastructure.persistence.sqlalchemy_itinerary_repo import (
    SqlAlchemyItineraryRepository,
)
from src.storage.notification_repository import NotificationRepository


class LocalAirportValidator(AirportValidatorPort):
    def __init__(self, airport_uc: GetAirportByIdUseCase):
        self.airport_uc = airport_uc

    async def validate_airport_exists(self, airport_id: int) -> bool:
        airport = await self.airport_uc.execute(airport_id)
        return airport is not None


def _require_testcontainers_and_docker():
    """Verifica que testcontainers y el daemon de Docker estén disponibles."""
    try:
        import docker
        from docker.errors import DockerException
        from testcontainers.postgres import PostgresContainer
        from testcontainers.rabbitmq import RabbitMqContainer
        from testcontainers.redis import RedisContainer
    except ImportError as exc:
        pytest.skip(f"Docker/Testcontainers no disponible en este entorno: {exc}")

    try:
        client = docker.from_env()
        client.ping()
        client.close()
    except (DockerException, OSError, RuntimeError, ValueError) as exc:
        pytest.skip(f"Docker/Testcontainers no disponible en este entorno: {exc}")

    return PostgresContainer, RedisContainer, RabbitMqContainer


def _run_alembic_migrations(pg_url: str, engine) -> None:
    """Ejecuta las migraciones reales de Alembic sobre PostgreSQL y verifica el esquema."""
    with contextlib.suppress(ImportError):
        from alembic import command as alembic_command
        from alembic.config import Config as AlembicConfig

        config_path = os.path.join(
            ITINERARY_SERVICE_DIR, "src/infrastructure/config.py"
        )
        spec = importlib.util.spec_from_file_location(
            "src.infrastructure.config", config_path
        )
        if spec and spec.loader:
            cfg_module = importlib.util.module_from_spec(spec)
            sys.modules["src.infrastructure.config"] = cfg_module
            spec.loader.exec_module(cfg_module)
            cfg_module.settings.database_url = pg_url

        alembic_ini_path = os.path.join(ITINERARY_SERVICE_DIR, "alembic.ini")
        alembic_script_location = os.path.join(
            ITINERARY_SERVICE_DIR, "src/infrastructure/persistence/alembic"
        )
        alembic_cfg = AlembicConfig(alembic_ini_path)
        alembic_cfg.set_main_option("script_location", alembic_script_location)
        alembic_cfg.set_main_option("sqlalchemy.url", pg_url)
        alembic_command.upgrade(alembic_cfg, "head")

    Base.metadata.create_all(bind=engine)


@pytest.mark.e2e_containers
@pytest.mark.asyncio
async def test_complete_flow_with_real_containers(tmp_path):
    PostgresContainer, RedisContainer, RabbitMqContainer = (
        _require_testcontainers_and_docker()
    )

    with (
        PostgresContainer("postgres:15-alpine") as pg,
        RedisContainer("redis:7-alpine") as redis_c,
        RabbitMqContainer("rabbitmq:3.12-alpine") as rabbit_c,
    ):
        pg_url = pg.get_connection_url()
        redis_host = redis_c.get_container_host_ip()
        redis_port = redis_c.get_exposed_port(6379)
        redis_url = f"redis://{redis_host}:{redis_port}/0"

        rabbit_host = rabbit_c.get_container_host_ip()
        rabbit_port = rabbit_c.get_exposed_port(5672)
        rabbit_user = getattr(rabbit_c, "username", "guest")
        rabbit_pass = getattr(rabbit_c, "password", "guest")
        amqp_url = f"amqp://{rabbit_user}:{rabbit_pass}@{rabbit_host}:{rabbit_port}/"

        # 2. PostgreSQL + Alembic: ejecutar migraciones y verificar esquema
        engine = create_engine(pg_url, echo=False)
        _run_alembic_migrations(pg_url, engine)

        inspector = inspect(engine)
        table_names = set(inspector.get_table_names())
        assert "itineraries" in table_names
        assert "outbox_events" in table_names

        # 3. Redis Real: verificar ping, poblar y leer caché real de aeropuertos
        cache = RedisCacheAdapter(redis_url=redis_url)
        assert await cache.ping() is True

        api_adapter = ApiColombiaAdapter(max_retries=1)
        list_airports_uc = ListAirportsUseCase(
            external_port=api_adapter, cache_port=cache
        )
        get_airport_uc = GetAirportByIdUseCase(
            external_port=api_adapter, list_use_case=list_airports_uc
        )

        airports = await list_airports_uc.execute()
        assert len(airports) >= 2
        cached_payload = await cache.get(CACHE_KEY_AIRPORTS)
        assert cached_payload is not None
        assert len(cache._in_memory_fallback) == 0

        cached_airports = await list_airports_uc.execute()
        assert len(cached_airports) == len(airports)
        origin = cached_airports[0]
        dest = cached_airports[1]

        # 4. Itinerary Service + Transactional Outbox Real en PostgreSQL
        session_factory = sessionmaker(bind=engine)
        itinerary_repo = SqlAlchemyItineraryRepository(session_factory=session_factory)
        validator = LocalAirportValidator(get_airport_uc)
        create_itin_uc = CreateItineraryUseCase(
            itinerary_repo=itinerary_repo, airport_validator=validator
        )

        new_itinerary = await create_itin_uc.execute(
            user_name="Usuario Testcontainers E2E",
            origin_airport_id=origin.id,
            destination_airport_id=dest.id,
            departure_date=datetime.now(UTC),
            duration_minutes=65,
            trace_id="trace-e2e-testcontainers-001",
        )
        assert new_itinerary.id is not None
        assert new_itinerary.status == "CREATED"

        with session_factory() as db_session:
            persisted_itin = (
                db_session.query(ItineraryModel)
                .filter(ItineraryModel.id == str(new_itinerary.id))
                .first()
            )
            assert persisted_itin is not None
            persisted_outbox = (
                db_session.query(OutboxEventModel)
                .filter(OutboxEventModel.aggregate_id == str(new_itinerary.id))
                .first()
            )
            assert persisted_outbox is not None
            assert persisted_outbox.status == "PENDING"

        # 5. RabbitMQ Real + OutboxRelayWorker + Consumer FaaS
        notif_db = str(tmp_path / "e2e_containers_notifications.db")
        notif_repo = NotificationRepository(db_path=notif_db)
        notif_func = SendNotificationFunction(repo=notif_repo)

        publisher = RabbitMQPublisher(amqp_url=amqp_url)
        await publisher.connect()

        consumer = RabbitMQEventConsumer(
            amqp_url=amqp_url, notification_func=notif_func
        )
        relay_worker = OutboxRelayWorker(
            outbox_repo=itinerary_repo,
            publisher=publisher,
            poll_interval_seconds=0.2,
        )

        consumer_task = asyncio.create_task(consumer.start())
        await asyncio.sleep(1.0)
        relay_task = asyncio.create_task(relay_worker.start())

        try:
            deadline = time.monotonic() + 10.0
            logs = []
            while time.monotonic() < deadline:
                logs = notif_repo.list_all()
                if any(
                    item["itinerary_id"] == str(new_itinerary.id)
                    and item["status"] == "SENT"
                    for item in logs
                ):
                    break
                await asyncio.sleep(0.25)

            assert len(logs) == 1
            assert logs[0]["itinerary_id"] == str(new_itinerary.id)
            assert logs[0]["status"] == "SENT"
            assert "Usuario Testcontainers E2E" in logs[0]["recipient"]

            with session_factory() as db_session:
                published_outbox = (
                    db_session.query(OutboxEventModel)
                    .filter(OutboxEventModel.aggregate_id == str(new_itinerary.id))
                    .first()
                )
                assert published_outbox is not None
                assert published_outbox.status == "PUBLISHED"
        finally:
            relay_worker.stop()
            consumer.stop()
            for task in (relay_task, consumer_task):
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            await publisher.close()
            if cache._redis_client is not None:
                await cache._redis_client.aclose()
            engine.dispose()
