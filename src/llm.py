from __future__ import annotations

from langchain_openai import ChatOpenAI

from config import get_llm_config
from runtime import get_runtime_api_key


def get_llm(
    profile: str = "default",
) -> ChatOpenAI:

    config = get_llm_config(
        profile
    )

    model = config.get(
        "model"
    )

    if not model:
        raise ValueError(
            f"No model configured for profile: {profile}"
        )

    return ChatOpenAI(
        model=model,
        api_key=get_runtime_api_key(),
        reasoning_effort=config.get(
            "reasoning_effort",
            "low",
        ),
        temperature=config.get(
            "temperature",
            0,
        ),
        use_responses_api=config.get(
            "use_responses_api",
            True,
        ),
    )