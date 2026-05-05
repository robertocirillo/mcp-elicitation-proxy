from __future__ import annotations

import pytest
from pydantic import ValidationError

from mcp_elicitation_proxy.config import AppConfig


def _config(raw: dict | None = None) -> AppConfig:
    return AppConfig.model_validate(
        {
            "upstream": {"url": "http://localhost:8001/mcp"},
            **(raw or {}),
        }
    )


def test_elicitation_enabled_default_true() -> None:
    assert _config().elicitation.enabled is True


def test_elicitation_can_be_disabled() -> None:
    config = _config({"elicitation": {"enabled": False}})

    assert config.elicitation.enabled is False


def test_fallback_on_unsupported_accepts_structured_error() -> None:
    config = _config(
        {"elicitation": {"fallback_on_unsupported": "structured_error"}}
    )

    assert config.elicitation.fallback_on_unsupported == "structured_error"


def test_invalid_fallback_on_unsupported_is_rejected() -> None:
    with pytest.raises(ValidationError):
        _config({"elicitation": {"fallback_on_unsupported": "plain_text"}})
