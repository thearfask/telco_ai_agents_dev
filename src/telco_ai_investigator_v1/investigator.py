import json
import os
from typing import Any

from groq import Groq
from dotenv import load_dotenv

from telco_ai_investigator_v1.tools import (
    get_window_health,
    get_telemetry_detail,
    get_alarms,
    get_topology,
)

load_dotenv()

MODEL = os.getenv("GROQ_MODEL")

SYSTEM_PROMPT = """
You are an L1/L2 telecom incident investigator.

Your task is to produce initial technical findings from the evidence provided.

Rules:

1. Never invent evidence.
2. Never claim a definite root cause unless the evidence strongly supports it.
3. Separate observations from hypotheses.
4. Mention missing evidence that would be useful for further RCA.
5. Treat alarms as observations, not root-cause labels.
6. Use topology only to understand dependencies; do not assume an upstream
   component is faulty without evidence.
7. Be concise and useful to a network engineer.
8. Return valid JSON only.

Return exactly this structure:

{
  "summary": "short investigation summary",
  "affected_component": "component id",
  "severity_assessment": "LOW | MODERATE | HIGH | CRITICAL",
  "observations": [
    "evidence-backed observation"
  ],
  "leading_hypothesis": {
    "hypothesis": "best current explanation",
    "confidence": 0.0,
    "reasoning": [
      "evidence supporting hypothesis"
    ]
  },
  "alternative_hypotheses": [
    {
      "hypothesis": "alternative explanation",
      "reason": "why still plausible"
    }
  ],
  "missing_evidence": [
    "information required for stronger RCA"
  ],
  "recommended_next_steps": [
    "next investigation action"
  ]
}
"""

def get_client() -> Groq:

    api_key = os.getenv(
        "GROQ_API_KEY"
    )

    if not api_key:

        raise RuntimeError(
            "GROQ_API_KEY is not configured."
        )

    return Groq(
        api_key=api_key
    )


def build_evidence(window_id: str) -> dict[str, Any]:
    health = get_window_health(window_id)

    if health is None:
        raise ValueError(f"Unknown window_id: {window_id}")

    alarms = get_alarms(window_id)
    topology = get_topology(window_id)

    # For the first investigator test, retrieve only the KPI detail
    # most relevant to radio-quality investigation.
    detail = get_telemetry_detail(
        window_id=window_id,
        metrics=[
            "RSRP",
            "DL_BLER",
            "DL_MCS",
            "UL_BLER",
            "UL_MCS",
            "UL_SNR",
            "PRB_Utilization_DL",
            "PRB_Utilization_UL",
        ],
        limit=25,
    )

    return {
        "window_health": health,
        "alarms": alarms,
        "topology": topology,
        "telemetry_detail": detail,
    }


def investigate(window_id: str) -> dict[str, Any]:
    evidence = build_evidence(window_id)
    client = get_client()

    user_prompt = f"""
        Investigate the following telecom observation window.

        WINDOW:
        {window_id}

        EVIDENCE:
        {json.dumps(evidence, default=str, indent=2)}

        Produce initial findings only.
        Do not assume access to logs, configuration changes, historical incidents,
        or any information that is not included above.
    """

    response = client.chat.completions.create(
        model=MODEL,
        temperature=0.1,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
    )

    content = response.choices[0].message.content

    return json.loads(content)


def main() -> None:
    window_id = "WIN-001287"

    print(f"\nInvestigating {window_id}...\n")

    result = investigate(window_id)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()