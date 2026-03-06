"""Typed configuration via pydantic-settings. Loaded from env vars."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class DatabaseSettings(BaseSettings):
    model_config = {"env_prefix": "LINTEL_DB_"}

    dsn: str = "postgresql://lintel:lintel@localhost:5432/lintel"
    pool_min: int = 5
    pool_max: int = 20


class NATSSettings(BaseSettings):
    model_config = {"env_prefix": "LINTEL_NATS_"}

    url: str = "nats://localhost:4222"
    enabled: bool = False


class SlackSettings(BaseSettings):
    model_config = {"env_prefix": "LINTEL_SLACK_"}

    bot_token: str = ""
    signing_secret: str = ""
    app_token: str = ""


class PIISettings(BaseSettings):
    model_config = {"env_prefix": "LINTEL_PII_"}

    risk_threshold: float = 0.6
    vault_encryption_key: str = ""


class ModelSettings(BaseSettings):
    model_config = {"env_prefix": "LINTEL_MODEL_"}

    default_provider: str = "anthropic"
    default_model: str = "claude-sonnet-4-20250514"
    fallback_provider: str = "ollama"
    fallback_model: str = "llama3.1:8b"


class SandboxSettings(BaseSettings):
    model_config = {"env_prefix": "LINTEL_SANDBOX_"}

    docker_host: str = "unix:///var/run/docker.sock"
    max_cpu: str = "2"
    max_memory: str = "4g"
    timeout_seconds: int = 1800
    network_mode: str = "none"


class Settings(BaseSettings):
    """Root settings aggregating all subsystems."""

    db: DatabaseSettings = Field(default_factory=DatabaseSettings)
    nats: NATSSettings = Field(default_factory=NATSSettings)
    slack: SlackSettings = Field(default_factory=SlackSettings)
    pii: PIISettings = Field(default_factory=PIISettings)
    model: ModelSettings = Field(default_factory=ModelSettings)
    sandbox: SandboxSettings = Field(default_factory=SandboxSettings)

    log_level: str = "INFO"
    log_format: str = "json"
    otel_endpoint: str = ""
    environment: str = "development"
