import logging
import random
from datetime import UTC, datetime, timedelta

from locust import HttpUser, between, task

logger = logging.getLogger(__name__)


class SystemLoadUser(HttpUser):
    wait_time = between(1, 2.5)

    def on_start(self):
        self.headers = {"Content-Type": "application/json"}
        try:
            response = self.client.post(
                "/api/v1/auth/token",
                json={"username": "locust-user"},
                name="/api/v1/auth/token",
            )
            if response.status_code == 200:
                token = response.json().get("access_token")
                if token:
                    self.headers = {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {token}",
                    }
                    return
            logger.warning(
                "No se obtuvo token JWT real desde /api/v1/auth/token (status=%s). "
                "Se continuará sin cabecera Authorization.",
                response.status_code,
            )
        except (
            OSError,
            ValueError,
            KeyError,
            TypeError,
            AttributeError,
            RuntimeError,
        ) as exc:
            logger.warning(
                "Error solicitando token JWT en on_start(): %s. "
                "Se continuará sin cabecera Authorization.",
                exc,
            )

    @task(3)
    def view_airports_catalog(self):
        self.client.get("/api/v1/airports", name="/api/v1/airports")

    @task(2)
    def view_plotly_map(self):
        self.client.get(
            "/api/v1/airports/map/plotly", name="/api/v1/airports/map/plotly"
        )

    @task(1)
    def create_itinerary(self):
        origin = random.choice([1, 9, 12, 18])
        dest = random.choice([5, 15, 22, 25])
        future_date = (
            datetime.now(UTC) + timedelta(days=random.randint(1, 30))
        ).isoformat()

        payload = {
            "user_name": f"LocustPassenger_{random.randint(100, 999)}",
            "origin_airport_id": origin,
            "destination_airport_id": dest,
            "departure_date": future_date,
            "duration_minutes": random.choice([45, 60, 90, 120]),
        }

        self.client.post(
            "/api/v1/itineraries",
            json=payload,
            headers=self.headers,
            name="/api/v1/itineraries",
        )

    @task(2)
    def list_itineraries(self):
        self.client.get("/api/v1/itineraries", name="/api/v1/itineraries [GET]")
