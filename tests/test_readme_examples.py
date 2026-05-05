from __future__ import annotations

import re
from pathlib import Path

import yaml

from mcp_elicitation_proxy.config import AppConfig, load_config


def _readme_config_example() -> str:
    readme = Path("README.md").read_text(encoding="utf-8")
    match = re.search(
        r"Example `config\.yaml` with an HTTP upstream:\n\n```yaml\n(?P<yaml>.*?)\n```",
        readme,
        flags=re.DOTALL,
    )
    assert match is not None
    return match.group("yaml")


def _readme_command_config_example() -> str:
    readme = Path("README.md").read_text(encoding="utf-8")
    match = re.search(
        r"Example `config\.yaml` with a command-based upstream:\n\n```yaml\n(?P<yaml>.*?)\n```",
        readme,
        flags=re.DOTALL,
    )
    assert match is not None
    return match.group("yaml")


def test_readme_config_example_matches_current_config_models(tmp_path: Path) -> None:
    config_yaml = _readme_config_example()
    raw_config = yaml.safe_load(config_yaml)

    config = AppConfig.model_validate(raw_config)
    assert config.upstream.url == "http://localhost:8001/mcp"
    assert config.proxy.name == "mcp-elicitation-proxy"
    assert config.elicitation.enabled is True
    assert config.elicitation.fallback_on_unsupported == "structured_error"

    search_docs = config.tools["search_docs"]
    assert search_docs.required == ["query", "project"]
    assert search_docs.elicit is not None
    assert search_docs.elicit.message == "La ricerca è ambigua. Specifica query e progetto."
    assert (
        search_docs.elicit.fields["project"].description
        == "Progetto o scope in cui cercare"
    )

    config_path = tmp_path / "config.yaml"
    config_path.write_text(config_yaml, encoding="utf-8")
    assert load_config(config_path) == config


def test_readme_command_config_example_matches_current_config_models() -> None:
    config_yaml = _readme_command_config_example()
    raw_config = yaml.safe_load(config_yaml)

    config = AppConfig.model_validate(raw_config)
    assert config.upstream.url is None
    assert config.upstream.command == "npx"
    assert config.upstream.args == ["-y", "@modelcontextprotocol/server-everything"]
    assert config.proxy.name == "mcp-elicitation-proxy"
