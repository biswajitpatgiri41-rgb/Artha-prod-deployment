from app.core.config import Settings
from app.security.config import SecuritySettings


def test_core_settings_read_environment_aliases(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "test-provider-key")
    monkeypatch.setenv("NVIDIA_MODEL", "test-model")
    settings = Settings(_env_file=None)
    assert settings.nvidia_api_key == "test-provider-key"
    assert settings.nvidia_model == "test-model"


def test_security_settings_read_environment_aliases(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
    settings = SecuritySettings(_env_file=None)
    assert settings.environment == "development"
    assert settings.rate_limit_enabled is False
