from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from mcp_elicitation_proxy.config import AppConfig, ToolPolicyConfig, load_config


def _write_config(tmp_path: Path, content: str) -> Path:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(dedent(content), encoding="utf-8")
    return config_path


def test_loads_minimal_config(tmp_path: Path) -> None:
    config = load_config(
        _write_config(
            tmp_path,
            """
            upstream:
              url: "http://localhost:8001/mcp"
            """,
        )
    )

    assert config.upstream.url == "http://localhost:8001/mcp"
    assert config.proxy.name == "mcp-elicitation-proxy"
    assert config.elicitation.enabled is True
    assert config.elicitation.fallback_on_unsupported == "structured_error"
    assert config.policies.schema_required.enabled is True
    assert config.policies.sensitive_required.enabled is True
    assert config.tools == {}


def test_loads_tool_required_fields(tmp_path: Path) -> None:
    config = load_config(
        _write_config(
            tmp_path,
            """
            upstream:
              url: "http://localhost:8001/mcp"
            tools:
              search_docs:
                required:
                  - query
                  - project
            """,
        )
    )

    assert config.tools["search_docs"].required == ["query", "project"]


def test_uses_default_factories_for_mutable_fields() -> None:
    first = AppConfig.model_validate(
        {"upstream": {"url": "http://localhost:8001/mcp"}}
    )
    second = AppConfig.model_validate(
        {"upstream": {"url": "http://localhost:8002/mcp"}}
    )

    first.tools["search_docs"] = ToolPolicyConfig(required=["query"])
    first.tools["search_docs"].required.append("project")

    assert second.tools == {}


def test_loads_policy_enabled_flags(tmp_path: Path) -> None:
    config = load_config(
        _write_config(
            tmp_path,
            """
            upstream:
              url: "http://localhost:8001/mcp"
            policies:
              schema_required:
                enabled: false
              sensitive_required:
                enabled: true
            """,
        )
    )

    assert config.policies.schema_required.enabled is False
    assert config.policies.sensitive_required.enabled is True

    config = load_config(
        _write_config(
            tmp_path,
            """
            upstream:
              url: "http://localhost:8001/mcp"
            policies:
              schema_required:
                enabled: true
              sensitive_required:
                enabled: false
            """,
        )
    )

    assert config.policies.schema_required.enabled is True
    assert config.policies.sensitive_required.enabled is False
