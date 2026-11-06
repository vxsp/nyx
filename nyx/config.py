"""Validate nonsecret settings without echoing invalid input values."""
from __future__ import annotations

import json
import math
from pathlib import Path


class ConfigurationError(ValueError):
    """An actionable configuration error safe to display or log."""


DEFAULTS = {
    "navidrome": {
        "enabled": True, "minimum_hours_between_reports": 24,
        "page_size": 200, "max_albums": 2000,
        "request_timeout_seconds": 12, "max_report_seconds": 600,
    },
    "resources": {
        "minimum_available_ram_gb": 3, "maximum_cpu_percent": 35,
        "only_when_plugged_in": True,
    },
}


def validate_settings(document: object) -> dict:
    if not isinstance(document, dict):
        raise ConfigurationError("settings.json must contain a JSON object.")
    result = dict(document)
    for section, defaults in DEFAULTS.items():
        supplied = document.get(section, {})
        if not isinstance(supplied, dict):
            raise ConfigurationError(f"settings.json: {section} must be an object.")
        values = {**defaults, **supplied}
        for key, value in values.items():
            if key not in defaults:
                continue
            field = f"{section}.{key}"
            if isinstance(defaults[key], bool):
                if not isinstance(value, bool):
                    raise ConfigurationError(f"settings.json: {field} must be true or false.")
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ConfigurationError(f"settings.json: {field} must be a finite number.")
            if key in ("page_size", "max_albums", "request_timeout_seconds", "max_report_seconds"):
                if not isinstance(value, int) or value < 1:
                    raise ConfigurationError(f"settings.json: {field} must be a positive integer.")
            elif value < 0:
                raise ConfigurationError(f"settings.json: {field} must be nonnegative.")
            if key == "page_size" and value > 500:
                raise ConfigurationError("settings.json: navidrome.page_size must be at most 500.")
            if key == "maximum_cpu_percent" and value > 100:
                raise ConfigurationError("settings.json: resources.maximum_cpu_percent must be at most 100.")
        result[section] = values
    return result


def load_settings(path: Path) -> dict:
    try:
        document = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        raise ConfigurationError("Cannot read settings.json; check the file exists and contains valid JSON.") from None
    return validate_settings(document)
