from __future__ import annotations

from typing import Any

from .base import InspectionIssue, InspectionResult


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
    if _contains_sensitive_marker(field_name):
        return True

    if not field_schema:
        return False

    return any(
        _contains_sensitive_marker(field_schema.get(metadata_key))
        for metadata_key in SENSITIVE_SCHEMA_METADATA_KEYS
    )


class SensitiveRequiredFieldPolicy:
    async def inspect(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        tool_schema: dict[str, Any] | None,
        context: Any,
    ) -> InspectionResult:
        if tool_schema is None:
            return InspectionResult.ok()

        required_fields = tool_schema.get("required")
        if not isinstance(required_fields, list):
            return InspectionResult.ok()

        issues: list[InspectionIssue] = []
        for field in required_fields:
            if not isinstance(field, str):
                continue
            if field in arguments and not _is_empty_required_value(arguments[field]):
                continue

            field_schema = _field_schema(field, tool_schema)
            if not is_sensitive_field(field, field_schema):
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


def _field_schema(
    field_name: str,
    tool_schema: dict[str, Any],
) -> dict[str, Any]:
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


def _contains_sensitive_marker(value: Any) -> bool:
    if not isinstance(value, str):
        return False

    normalized = value.lower()
    separated = "".join(
        character if character.isalnum() else "_" for character in normalized
    )
    compact = "".join(character for character in normalized if character.isalnum())

    for marker in SENSITIVE_FIELD_MARKERS:
        if marker in normalized:
            return True
        if marker in separated:
            return True
        if marker.replace("_", "") in compact:
            return True
    return False
