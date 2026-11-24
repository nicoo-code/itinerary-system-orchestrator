import importlib.util
import sys
from contextlib import contextmanager
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parents[2]


@contextmanager
def _load_service_module(service_name: str, rel_path: str, alias: str):
    service_dir = str(ROOT_DIR / "services" / service_name)
    file_path = str(ROOT_DIR / "services" / service_name / rel_path)
    saved_path = list(sys.path)
    saved_modules = {
        k: v for k, v in sys.modules.items() if k == "src" or k.startswith("src.")
    }
    try:
        for k in list(saved_modules.keys()):
            sys.modules.pop(k, None)
        if service_dir in sys.path:
            sys.path.remove(service_dir)
        sys.path.insert(0, service_dir)

        spec = importlib.util.spec_from_file_location(alias, file_path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[alias] = module
        spec.loader.exec_module(module)
        yield module
    finally:
        sys.modules.pop(alias, None)
        for k in [m for m in list(sys.modules) if m == "src" or m.startswith("src.")]:
            sys.modules.pop(k, None)
        sys.modules.update(saved_modules)
        sys.path[:] = saved_path


def test_airport_service_metrics_and_circuit_breaker_gauge():
    with _load_service_module(
        "airport-service", "src/main.py", "airport_main_metrics_test"
    ) as mod:
        client = TestClient(mod.app)

        # Petición previa para registrar métricas HTTP
        health_resp = client.get("/health")
        assert health_resp.status_code == 200

        # Estado CLOSED -> 0.0
        mod.circuit_breaker.state = mod.circuit_breaker.state.__class__.CLOSED
        resp = client.get("/metrics")
        assert resp.status_code == 200
        assert "text/plain" in resp.headers["content-type"]
        body = resp.text
        assert "http_requests_total" in body
        assert "http_request_duration_seconds" in body
        assert 'service="airport-service"' in body
        assert "airport_circuit_breaker_state 0.0" in body

        # Estado OPEN -> 2.0
        mod.circuit_breaker.state = mod.circuit_breaker.state.__class__.OPEN
        resp_open = client.get("/metrics")
        assert resp_open.status_code == 200
        assert "airport_circuit_breaker_state 2.0" in body or (
            "airport_circuit_breaker_state 2.0" in resp_open.text
        )


def test_itinerary_service_metrics_endpoint(tmp_path, monkeypatch):
    db_path = tmp_path / "metrics_itineraries.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    with _load_service_module(
        "itinerary-service", "src/main.py", "itinerary_main_metrics_test"
    ) as mod:
        client = TestClient(mod.app)

        health_resp = client.get("/health")
        assert health_resp.status_code == 200

        resp = client.get("/metrics")
        assert resp.status_code == 200
        assert "text/plain" in resp.headers["content-type"]
        body = resp.text
        assert "http_requests_total" in body
        assert "http_request_duration_seconds" in body
        assert 'service="itinerary-service"' in body
        assert "itineraries_created_total" in body


def test_notification_service_metrics_endpoint(tmp_path, monkeypatch):
    notif_db = tmp_path / "metrics_notifications.db"
    monkeypatch.setenv("NOTIFICATIONS_DB_PATH", str(notif_db))

    with _load_service_module(
        "notification-service", "src/main.py", "notification_main_metrics_test"
    ) as mod:
        client = TestClient(mod.app)

        health_resp = client.get("/health")
        assert health_resp.status_code == 200

        resp = client.get("/metrics")
        assert resp.status_code == 200
        assert "text/plain" in resp.headers["content-type"]
        body = resp.text
        assert "http_requests_total" in body
        assert "http_request_duration_seconds" in body
        assert 'service="notification-service"' in body


def test_api_gateway_metrics_endpoint():
    with _load_service_module(
        "api-gateway", "src/gateway.py", "gateway_main_metrics_test"
    ) as mod:
        client = TestClient(mod.app)

        health_resp = client.get("/health")
        assert health_resp.status_code == 200

        resp = client.get("/metrics")
        assert resp.status_code == 200
        assert "text/plain" in resp.headers["content-type"]
        body = resp.text
        assert "http_requests_total" in body
        assert "http_request_duration_seconds" in body
        assert 'service="api-gateway"' in body


def test_prometheus_config_and_alerts_yaml_validity():
    prom_file = ROOT_DIR / "infra" / "prometheus" / "prometheus.yml"
    alerts_file = ROOT_DIR / "infra" / "prometheus" / "alerts.yml"

    assert prom_file.exists(), "Debe existir infra/prometheus/prometheus.yml"
    assert alerts_file.exists(), "Debe existir infra/prometheus/alerts.yml"

    prom_cfg = yaml.safe_load(prom_file.read_text(encoding="utf-8"))
    assert prom_cfg["global"]["scrape_interval"] == "15s"
    assert "/etc/prometheus/alerts.yml" in prom_cfg["rule_files"]

    scrape_targets = {
        job["job_name"]: job["static_configs"][0]["targets"][0]
        for job in prom_cfg["scrape_configs"]
    }
    assert scrape_targets["api-gateway"] == "api-gateway:8000"
    assert scrape_targets["airport-service"] == "airport-service:8001"
    assert scrape_targets["itinerary-service"] == "itinerary-service:8002"
    assert scrape_targets["notification-service"] == "notification-service:8003"

    alerts_cfg = yaml.safe_load(alerts_file.read_text(encoding="utf-8"))
    rules = alerts_cfg["groups"][0]["rules"]
    alerts_by_name = {rule["alert"]: rule for rule in rules}

    assert "AirportCircuitBreakerOpen" in alerts_by_name
    assert (
        alerts_by_name["AirportCircuitBreakerOpen"]["expr"]
        == "airport_circuit_breaker_state == 2"
    )
    assert alerts_by_name["AirportCircuitBreakerOpen"]["for"] == "30s"
    assert (
        alerts_by_name["AirportCircuitBreakerOpen"]["labels"]["severity"] == "critical"
    )

    assert "HighHttp5xxErrorRate" in alerts_by_name
    assert "5.." in alerts_by_name["HighHttp5xxErrorRate"]["expr"]
    assert alerts_by_name["HighHttp5xxErrorRate"]["labels"]["severity"] == "warning"

    assert "MicroserviceDown" in alerts_by_name
    assert alerts_by_name["MicroserviceDown"]["expr"] == "up == 0"
    assert alerts_by_name["MicroserviceDown"]["for"] == "1m"
    assert alerts_by_name["MicroserviceDown"]["labels"]["severity"] == "critical"


def test_docker_compose_includes_prometheus_service():
    compose_file = ROOT_DIR / "docker-compose.yml"
    compose_cfg = yaml.safe_load(compose_file.read_text(encoding="utf-8"))

    assert "prometheus" in compose_cfg["services"]
    prom_svc = compose_cfg["services"]["prometheus"]
    assert prom_svc["image"] == "prom/prometheus:v2.51.2"
    assert "9090:9090" in prom_svc["ports"]
    assert "backend-net" in prom_svc["networks"]
    volumes_joined = " ".join(prom_svc["volumes"])
    assert "infra/prometheus/prometheus.yml" in volumes_joined
    assert "infra/prometheus/alerts.yml" in volumes_joined


def test_kubernetes_manifests_validity_and_probes():
    k8s_dir = ROOT_DIR / "k8s"
    expected_files = [
        "00-namespace-config.yaml",
        "01-infrastructure.yaml",
        "02-airport-service.yaml",
        "03-itinerary-service.yaml",
        "04-notification-service.yaml",
        "05-api-gateway.yaml",
    ]

    all_docs = []
    for fname in expected_files:
        fpath = k8s_dir / fname
        assert fpath.exists(), f"Falta el manifiesto {fname} en k8s/"
        docs = [
            d
            for d in yaml.safe_load_all(fpath.read_text(encoding="utf-8"))
            if d is not None
        ]
        assert len(docs) > 0, f"El manifiesto {fname} está vacío"
        all_docs.extend(docs)

    kinds = {d["kind"] for d in all_docs}
    assert {"Namespace", "ConfigMap", "Secret", "Deployment", "Service"}.issubset(kinds)

    namespaces = [d for d in all_docs if d["kind"] == "Namespace"]
    assert any(ns["metadata"]["name"] == "itinerarios-app" for ns in namespaces)

    deployments = {
        d["metadata"]["name"]: d for d in all_docs if d["kind"] == "Deployment"
    }
    for svc_name in [
        "airport-service",
        "itinerary-service",
        "notification-service",
        "api-gateway",
    ]:
        assert svc_name in deployments, f"Falta Deployment para {svc_name}"
        container = deployments[svc_name]["spec"]["template"]["spec"]["containers"][0]
        assert "readinessProbe" in container, f"{svc_name} debe definir readinessProbe"
        assert "livenessProbe" in container, f"{svc_name} debe definir livenessProbe"
        assert container["readinessProbe"]["httpGet"]["path"] == "/health"
        assert container["livenessProbe"]["httpGet"]["path"] == "/health"
        assert "resources" in container
        assert "requests" in container["resources"]
        assert "limits" in container["resources"]

    assert deployments["airport-service"]["spec"]["replicas"] == 2
    assert deployments["itinerary-service"]["spec"]["replicas"] == 2
