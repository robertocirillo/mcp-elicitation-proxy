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


class SchemaRequiredPolicyConfig(BaseModel):
    enabled: bool = True


class SensitiveRequiredPolicyConfig(BaseModel):
    enabled: bool = True
    sensitive_name_markers: list[str] | None = None
    sensitive_schema_markers: list[str] | None = None


class PoliciesConfig(BaseModel):
    schema_required: SchemaRequiredPolicyConfig = Field(
        default_factory=SchemaRequiredPolicyConfig
    )
    sensitive_required: SensitiveRequiredPolicyConfig = Field(
        default_factory=SensitiveRequiredPolicyConfig
    )


class ToolElicitFieldConfig(BaseModel):
    type: str = "string"
    description: str | None = None


class ToolElicitConfig(BaseModel):
    message: str | None = None
    fields: dict[str, ToolElicitFieldConfig] = Field(default_factory=dict)


class ToolAmbiguityConfig(BaseModel):
    query_min_length: int | None = None
    generic_terms: list[str] = Field(default_factory=list)


class ToolConfirmConfig(BaseModel):
    always: bool = False


class ToolPolicyConfig(BaseModel):
    required: list[str] = Field(default_factory=list)
    ambiguous_if: ToolAmbiguityConfig | None = None
    confirm_if: ToolConfirmConfig | None = None
    elicit: ToolElicitConfig | None = None


class AppConfig(BaseModel):
    upstream: UpstreamConfig
    proxy: ProxyConfig = Field(default_factory=ProxyConfig)
    elicitation: ElicitationConfig = Field(default_factory=ElicitationConfig)
    policies: PoliciesConfig = Field(default_factory=PoliciesConfig)
    tools: dict[str, ToolPolicyConfig] = Field(default_factory=dict)


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
