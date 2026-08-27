from __future__ import annotations

from contextvars import ContextVar


_OPENAI_API_KEY: ContextVar[
    str | None
] = ContextVar(
    "openai_api_key",
    default=None,
)


def set_runtime_api_key(
    api_key: str,
) -> None:

    api_key = api_key.strip()

    if not api_key:
        raise ValueError(
            "OpenAI API key cannot be empty."
        )

    _OPENAI_API_KEY.set(
        api_key
    )


def get_runtime_api_key() -> str:

    api_key = _OPENAI_API_KEY.get()

    if not api_key:
        raise RuntimeError(
            "OpenAI API key has not been "
            "configured for this runtime."
        )

    return api_key


def clear_runtime_api_key() -> None:
    _OPENAI_API_KEY.set(
        None
    )