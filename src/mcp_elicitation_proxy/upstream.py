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


def create_upstream_proxy(config: AppConfig) -> Any:
    return create_proxy(config.upstream.url, name=config.proxy.name)
