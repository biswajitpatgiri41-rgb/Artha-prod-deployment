from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_compose_api_healthcheck_matches_production_readiness_endpoint():
    compose = (ROOT / "docker-compose.yml").read_text()
    app = (ROOT / "app/api/main.py").read_text()

    assert "healthcheck:" in compose
    assert "http://127.0.0.1:8000/readyz" in compose
    assert "@app.get(\"/readyz\")" in app
    assert '@app.get("/health")' in app
    assert "condition: service_healthy" in compose


def test_backend_container_runs_non_root_and_declares_healthcheck():
    dockerfile = (ROOT / "Dockerfile").read_text()

    assert "adduser --system --ingroup app app" in dockerfile
    assert "USER app" in dockerfile
    assert "HEALTHCHECK" in dockerfile


def test_environment_files_are_excluded_from_git_and_docker_contexts():
    gitignore = (ROOT / ".gitignore").read_text()
    dockerignore = (ROOT / ".dockerignore").read_text()

    assert ".env" in gitignore
    assert ".env.*" in gitignore
    assert ".env" in dockerignore
    assert ".env.*" in dockerignore
    assert "!.env.example" in gitignore
