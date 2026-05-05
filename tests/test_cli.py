from __future__ import annotations

from pathlib import Path

import pytest

from mcp_elicitation_proxy.config import AppConfig, UpstreamConfig
from mcp_elicitation_proxy import server as server_module


class DummyServer:
    def __init__(self) -> None:
        self.ran = False

    def run(self) -> None:
        self.ran = True


def test_main_requires_config(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        server_module.main([])

    assert exc_info.value.code == 2
    assert (
        "missing configuration: pass --config PATH or set MCP_ELICITATION_PROXY_CONFIG"
        in capsys.readouterr().err
    )


def test_main_loads_config_and_runs_server(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("upstream:\n  url: upstream.py\n", encoding="utf-8")
    loaded_paths: list[str | Path] = []
    built_configs: list[AppConfig] = []
    dummy_server = DummyServer()
    config = AppConfig(upstream=UpstreamConfig(url="upstream.py"))

    def fake_load_config(path: str | Path) -> AppConfig:
        loaded_paths.append(path)
        return config

    def fake_build_server(loaded_config: AppConfig) -> DummyServer:
        built_configs.append(loaded_config)
        return dummy_server

    monkeypatch.setattr(server_module, "configure_logging", lambda: None)
    monkeypatch.setattr(server_module, "load_config", fake_load_config)
    monkeypatch.setattr(server_module, "build_server", fake_build_server)

    server_module.main(["--config", str(config_path)])

    assert loaded_paths == [str(config_path)]
    assert built_configs == [config]
    assert dummy_server.ran is True
