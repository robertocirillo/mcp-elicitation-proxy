from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

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
    assert config.upstream.command is None
    assert config.upstream.args == []
    assert config.upstream.env == {}
    assert config.proxy.name == "mcp-elicitation-proxy"
    assert config.elicitation.enabled is True
    assert config.elicitation.fallback_on_unsupported == "structured_error"
    assert config.policies.schema_required.enabled is True
    assert config.policies.sensitive_required.enabled is True
    assert config.tools == {}


def test_loads_command_config(tmp_path: Path) -> None:
    config = load_config(
        _write_config(
            tmp_path,
            """
            upstream:
              command: "npx"
              args:
                - -y
                - "@modelcontextprotocol/server-everything"
            """,
        )
    )

    assert config.upstream.url is None
    assert config.upstream.command == "npx"
    assert config.upstream.args == ["-y", "@modelcontextprotocol/server-everything"]
    assert config.upstream.env == {}


def test_loads_command_config_with_env(tmp_path: Path) -> None:
    config = load_config(
        _write_config(
            tmp_path,
            """
            upstream:
              command: "uvx"
              args:
                - "some-mcp-server"
              env:
                SOME_KEY: "some-value"
            """,
        )
    )

    assert config.upstream.command == "uvx"
    assert config.upstream.args == ["some-mcp-server"]
    assert config.upstream.env == {"SOME_KEY": "some-value"}


def test_rejects_url_and_command_together(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="exactly one of 'url' or 'command'"):
        load_config(
            _write_config(
                tmp_path,
                """
                upstream:
                  url: "http://localhost:8001/mcp"
                  command: "npx"
                """,
            )
        )


def test_rejects_missing_upstream_target(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="exactly one of 'url' or 'command'"):
        load_config(
            _write_config(
                tmp_path,
                """
                upstream: {}
                """,
            )
        )


def test_rejects_args_without_command(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="upstream.args requires upstream.command"):
        load_config(
            _write_config(
                tmp_path,
                """
                upstream:
                  url: "http://localhost:8001/mcp"
                  args:
                    - "--verbose"
                """,
            )
        )


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
