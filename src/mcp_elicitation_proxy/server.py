from __future__ import annotations

import argparse
import os
from typing import Any

from .config import AppConfig, load_config
from .logging import configure_logging
from .upstream import create_upstream_proxy


def build_server(config: AppConfig) -> Any:
    server = create_upstream_proxy(config)
    # Elicitation middleware will be attached here in a later slice.
    return server


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the MCP elicitation proxy server.")
    parser.add_argument(
        "--config",
        help="Path to the YAML configuration file. "
        "Falls back to MCP_ELICITATION_PROXY_CONFIG.",
    )
    args = parser.parse_args(argv)

    config_path = args.config or os.environ.get("MCP_ELICITATION_PROXY_CONFIG")
    if not config_path:
        parser.error(
            "missing configuration: pass --config PATH or set MCP_ELICITATION_PROXY_CONFIG"
        )

    try:
        configure_logging()
        config = load_config(config_path)
        server = build_server(config)
    except Exception as exc:
        parser.exit(status=1, message=f"error: {exc}\n")

    server.run()
