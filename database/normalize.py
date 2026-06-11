from __future__ import annotations

import re


def normalize_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def normalize_required_text(value: str, field_name: str) -> str:
    normalized_value = normalize_spaces(value)
    if not normalized_value:
        raise ValueError(f"El campo {field_name} no puede estar vacio.")
    return normalized_value


def normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized_value = normalize_spaces(value)
    return normalized_value or None


def normalize_slug(value: str, field_name: str) -> str:
    return normalize_required_text(value, field_name).upper()

