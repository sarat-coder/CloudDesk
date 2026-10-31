from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.middleware.request_id import RequestIdMiddleware


def test_health_endpoint_reports_service_metadata():
    client = TestClient(create_app(Settings(_env_file=None, environment="test")))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "clouddesk",
        "version": "0.1.0",
        "environment": "test",
    }
    assert response.headers["x-request-id"]


def test_live_endpoint_is_available_without_dependency_checks():
    settings = Settings(
        _env_file=None,
        database_url="",
        redis_url="",
        demo_mode=False,
        use_fake_redis=False,
        vector_store="qdrant",
        qdrant_url="",
        llm_provider="openai",
        llm_api_key=None,
    )
    client = TestClient(create_app(settings))

    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "alive"}
    assert response.headers["x-request-id"]


def test_readiness_uses_configuration_only_and_reports_degraded_dependencies():
    settings = Settings(
        _env_file=None,
        database_url="",
        redis_url="",
        demo_mode=False,
        use_fake_redis=False,
        vector_store="qdrant",
        qdrant_url="",
        llm_provider="openai",
        llm_api_key=None,
    )
    client = TestClient(create_app(settings))

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "degraded",
        "checks": {
            "database": {
                "status": "error",
                "detail": "Database URL is missing or uses an unsupported driver",
            },
            "redis": {"status": "error", "detail": "Redis URL is not configured"},
            "vector_store": {
                "status": "error",
                "detail": "Qdrant URL is not configured",
            },
            "llm": {"status": "error", "detail": "LLM API key is not configured"},
        },
    }


def test_ready_configuration_returns_all_ok_checks():
    client = TestClient(create_app(Settings(_env_file=None)))

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {
            "database": {"status": "ok"},
            "redis": {"status": "ok"},
            "vector_store": {"status": "ok"},
            "llm": {"status": "ok"},
        },
    }


def test_request_id_is_echoed_and_exposed_through_cors():
    settings = Settings(
        _env_file=None,
        cors_origins=["https://console.example"],
    )
    client = TestClient(create_app(settings))

    response = client.get(
        "/health/live",
        headers={"Origin": "https://console.example", "X-Request-ID": "req:abc-123"},
    )

    assert response.headers["x-request-id"] == "req:abc-123"
    assert response.headers["access-control-expose-headers"] == "X-Request-ID"


def test_invalid_request_id_is_replaced_with_uuid():
    client = TestClient(create_app(Settings(_env_file=None)))

    response = client.get("/health/live", headers={"X-Request-ID": "bad value\r\n"})

    request_id = response.headers["x-request-id"]
    assert len(request_id) == 36
    assert request_id.count("-") == 4
    assert response.headers["x-request-id"] != "bad value\r\n"


def test_not_found_response_has_request_id():
    client = TestClient(create_app(Settings(_env_file=None)))

    response = client.get("/does-not-exist")

    assert response.status_code == 404
    assert response.headers["x-request-id"]


def test_request_id_middleware_adds_header_to_error_responses():
    error_app = FastAPI()

    @error_app.get("/")
    async def fail() -> None:
        raise RuntimeError("expected test failure")

    client = TestClient(
        RequestIdMiddleware(error_app),
        raise_server_exceptions=False,
    )

    response = client.get("/", headers={"X-Request-ID": "server-error"})

    assert response.status_code == 500
    assert response.headers["x-request-id"] == "server-error"


def test_cors_preflight_response_has_request_id():
    client = TestClient(
        create_app(Settings(_env_file=None, cors_origins=["https://console.example"]))
    )

    response = client.options(
        "/health/live",
        headers={
            "Origin": "https://console.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["x-request-id"]
