from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, ValidationError


class UpstreamConfig(BaseModel):
    url: str


class ProxyConfig(BaseModel):
    name: str = "mcp-elicitation-proxy"


class ElicitationConfig(BaseModel):
    enabled: bool = True
    fallback_on_unsupported: str = "structured_error"


class AppConfig(BaseModel):
    upstream: UpstreamConfig
    proxy: ProxyConfig = Field(default_factory=ProxyConfig)
    elicitation: ElicitationConfig = Field(default_factory=ElicitationConfig)


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"configuration file not found: {config_path}")
    if not config_path.is_file():
        raise ValueError(f"configuration path is not a file: {config_path}")

    try:
        raw_config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid YAML in configuration file {config_path}: {exc}") from exc

    if raw_config is None:
        raw_config = {}
    if not isinstance(raw_config, dict):
        raise ValueError(
            f"configuration file {config_path} must contain a YAML mapping at the top level"
        )

    try:
        return AppConfig.model_validate(raw_config)
    except ValidationError as exc:
        raise ValueError(f"invalid configuration in {config_path}: {exc}") from exc
