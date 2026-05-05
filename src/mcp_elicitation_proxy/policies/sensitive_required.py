from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from .base import InspectionIssue, InspectionResult
from .required_fields import combined_required_fields


SENSITIVE_FIELD_MARKERS = (
    "password",
    "passphrase",
    "secret",
    "token",
    "access_token",
    "api_key",
    "apikey",
    "credential",
    "private_key",
    "payment",
    "card",
    "cvv",
)

SENSITIVE_SCHEMA_METADATA_KEYS = ("format", "description", "title")


def is_sensitive_field(
    field_name: str,
    field_schema: dict[str, Any] | None = None,
) -> bool:
    """Return whether a field should not be requested through form elicitation."""
    if _contains_sensitive_marker(field_name, SENSITIVE_FIELD_MARKERS):
        return True

    if not field_schema:
        return False

    return any(
        _contains_sensitive_marker(field_schema.get(metadata_key), SENSITIVE_FIELD_MARKERS)
        for metadata_key in SENSITIVE_SCHEMA_METADATA_KEYS
    )


class SensitiveRequiredFieldPolicy:
    def __init__(
        self,
        *,
        tool_required_fields: dict[str, Sequence[str]] | None = None,
        sensitive_name_markers: Sequence[str] | None = None,
        sensitive_schema_markers: Sequence[str] | None = None,
    ) -> None:
        self._tool_required_fields = {
            tool_name: list(required_fields)
            for tool_name, required_fields in (tool_required_fields or {}).items()
        }
        self._sensitive_name_markers = tuple(
            sensitive_name_markers or SENSITIVE_FIELD_MARKERS
        )
        self._sensitive_schema_markers = tuple(
            sensitive_schema_markers or SENSITIVE_FIELD_MARKERS
        )

    async def inspect(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        tool_schema: dict[str, Any] | None,
        context: Any,
    ) -> InspectionResult:
        required_fields = combined_required_fields(
            tool_name, tool_schema, self._tool_required_fields
        )
        if not required_fields:
            return InspectionResult.ok()

        issues: list[InspectionIssue] = []
        for field in required_fields:
            if field in arguments and not _is_empty_required_value(arguments[field]):
                continue

            field_schema = _field_schema(field, tool_schema)
            if not self._is_sensitive_field(field, field_schema):
                continue

            issues.append(
                InspectionIssue(
                    field=field,
                    reason="sensitive_required_field",
                    message=(
                        "Tool call blocked because form-mode elicitation cannot "
                        f"request sensitive required field '{field}'."
                    ),
                )
            )

        if issues:
            return InspectionResult.reject(issues)

        return InspectionResult.ok()

    def _is_sensitive_field(
        self,
        field_name: str,
        field_schema: dict[str, Any] | None = None,
    ) -> bool:
        if _contains_sensitive_marker(field_name, self._sensitive_name_markers):
            return True

        if not field_schema:
            return False

        return any(
            _contains_sensitive_marker(
                field_schema.get(metadata_key), self._sensitive_schema_markers
            )
            for metadata_key in SENSITIVE_SCHEMA_METADATA_KEYS
        )


def _field_schema(
    field_name: str,
    tool_schema: dict[str, Any] | None,
) -> dict[str, Any]:
    if tool_schema is None:
        return {}

    properties = tool_schema.get("properties")
    if not isinstance(properties, dict):
        return {}

    field_schema = properties.get(field_name)
    if isinstance(field_schema, dict):
        return field_schema
    return {}


def _is_empty_required_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, list | dict):
        return len(value) == 0
    return False


def _contains_sensitive_marker(value: Any, markers: Sequence[str]) -> bool:
    if not isinstance(value, str):
        return False

    normalized = value.lower()
    separated = "".join(
        character if character.isalnum() else "_" for character in normalized
    )
    compact = "".join(character for character in normalized if character.isalnum())

    for marker in markers:
        if not isinstance(marker, str) or not marker:
            continue
        marker = marker.lower()
        if marker in normalized:
            return True
        if marker in separated:
            return True
        if marker.replace("_", "") in compact:
            return True
    return False
