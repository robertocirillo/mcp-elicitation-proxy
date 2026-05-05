from __future__ import annotations

from typing import Any

try:
    from fastmcp.server import create_proxy
except ImportError as exc:
    raise RuntimeError(
        "mcp-elicitation-proxy requires a modern FastMCP version exposing "
        "`fastmcp.server.create_proxy`."
    ) from exc

from .config import AppConfig


def _build_upstream_target(config: AppConfig) -> str | dict[str, Any]:
    if config.upstream.url is not None:
        return config.upstream.url

    if config.upstream.command is None:
        raise ValueError("upstream.command is required when upstream.url is not set")

    server_config: dict[str, Any] = {
        "command": config.upstream.command,
        "args": list(config.upstream.args),
    }
    if config.upstream.env:
        server_config["env"] = dict(config.upstream.env)

    return {
        "mcpServers": {
            "upstream": server_config,
        }
    }


def create_upstream_proxy(config: AppConfig) -> Any:
    return create_proxy(_build_upstream_target(config), name=config.proxy.name)
