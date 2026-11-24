import os
import sys

import pytest

SERVICE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if SERVICE_ROOT not in sys.path:
    sys.path.insert(0, SERVICE_ROOT)


@pytest.fixture(autouse=True)
def _disable_jwt_in_legacy_service_tests(monkeypatch):
    from src.infrastructure.config import settings

    monkeypatch.setattr(settings, "jwt_auth_enabled", False)
    monkeypatch.setenv("JWT_AUTH_ENABLED", "false")
