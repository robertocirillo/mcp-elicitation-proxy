from __future__ import annotations

import re
from pathlib import Path

import yaml

from mcp_elicitation_proxy.config import AppConfig, load_config


def _readme_config_example() -> str:
    readme = Path("README.md").read_text(encoding="utf-8")
    match = re.search(
        r"Example `config\.yaml`:\n\n```yaml\n(?P<yaml>.*?)\n```",
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
