import os

from pydantic import BaseModel


class Settings(BaseModel):
    service_name: str = "itinerary-service"
    service_port: int = int(os.getenv("PORT", "8002"))
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./itineraries.db")
    airport_service_url: str = os.getenv(
        "AIRPORT_SERVICE_URL", "http://airport-service:8001"
    )
    rabbitmq_url: str = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
    otlp_endpoint: str = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://jaeger:4317")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    jwt_secret_key: str = os.getenv(
        "JWT_SECRET_KEY", "dev-super-secret-jwt-key-2026-hs256-32b"
    )
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    jwt_expire_minutes: int = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))
    jwt_auth_enabled: bool = os.getenv("JWT_AUTH_ENABLED", "true").lower() in (
        "true",
        "1",
        "yes",
    )


settings = Settings()
