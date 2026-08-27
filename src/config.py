from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]

SETTINGS_FILE = (
    PROJECT_ROOT
    / "config"
    / "settings.yaml"
)


@lru_cache(maxsize=1)
def get_settings() -> dict[str, Any]:
    if not SETTINGS_FILE.exists():
        raise FileNotFoundError(
            f"Settings file not found: {SETTINGS_FILE}"
        )

    with SETTINGS_FILE.open(
        "r",
        encoding="utf-8",
    ) as handle:
        data = yaml.safe_load(handle)

    if not isinstance(data, dict):
        raise ValueError(
            "settings.yaml must contain a YAML object."
        )

    return data


def get_llm_config(
    profile: str = "default",
) -> dict[str, Any]:

    llm = get_settings().get(
        "llm",
        {},
    )

    default = llm.get(
        "default",
        {},
    )

    override = llm.get(
        profile,
        {},
    )

    return {
        **default,
        **override,
    }


def get_runtime_config() -> dict[str, Any]:
    return get_settings().get(
        "runtime",
        {},
    )


def get_context_config() -> dict[str, Any]:
    return get_settings().get(
        "context",
        {},
    )


def clear_config_cache() -> None:
    get_settings.cache_clear()