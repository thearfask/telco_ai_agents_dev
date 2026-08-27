from __future__ import annotations

import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from .models import (
    DomainFindingUpdate,
    EvidenceConfidence,
    IncidentObjective,
    InvestigationEvidenceState,
    RCAAction,
    RCADecision,
    RCAStopReason,
)


load_dotenv()


MODEL = os.getenv(
    "POC_MODEL",
    "gpt-5.4-mini",
)


AVAILABLE_DOMAINS = [
    "telemetry",
    "alarms",
    "topology",
]


def _model():

    llm = ChatOpenAI(
        model=MODEL,
        temperature=0,
        reasoning_effort=None,
        max_completion_tokens=1800,
    )

    return llm.with_structured_output(
        RCADecision,
        method="json_schema",
    )


def run_rca(
    *,
    objective: IncidentObjective,
    evidence_state: InvestigationEvidenceState,
    latest_update: DomainFindingUpdate | None,
    rounds_used: int,
    max_rounds: int,
) -> RCADecision:

    final_round = (
        rounds_used
        >= max_rounds
    )

    latest_text = (
        latest_update.model_dump_json(
            exclude_none=True
        )
        if latest_update
        else "{}"
    )

    prompt = f"""
ROLE|RCA_SUPERVISOR

You own the overall incident investigation.

INCIDENT OBJECTIVE|
{objective.model_dump_json(exclude_none=True)}

CURRENT BOUNDED EVIDENCE STATE|
{evidence_state.model_dump_json(exclude_none=True)}

LATEST DOMAIN UPDATE|
{latest_text}

ROUNDS USED|
{rounds_used}/{max_rounds}

AVAILABLE SPECIALIST DOMAINS|
{AVAILABLE_DOMAINS}

RESPONSIBILITY|

Determine whether the incident objective can now be answered.

If not, identify the ONE specialist domain whose evidence could
most materially reduce uncertainty.

You choose the DOMAIN.

The specialist chooses its own tools.

Do not tell specialists which SQL query, log search, RAG query or
graph traversal to perform.

REASONING|

Separate:
- confirmed impairment
- supported technical driver
- hypotheses contradicted or ruled out
- physical root cause

Do not force a root cause.

Do not request information already present in evidence state.

Do not reopen strongly ruled-out hypotheses unless new evidence
contradicts them.

An open question marked UNAVAILABLE should not be sent back to the
same domain unless another domain may provide it.

A QUERYABLE open question may justify another specialist round only
when its answer could materially change the RCA.

Do not continue merely because an interesting question remains.

DOMAIN GUIDANCE|

telemetry:
measurements, KPI behavior, RF/link/resource/traffic evidence.

alarms:
alarms, event sequences, component alarm evidence.

topology:
network relationships, shared infrastructure, serving/dependency
evidence.

FINAL RESPONSE|

When concluding:
- state confirmed impairment
- state strongest supported technical explanation
- state important unsupported hypotheses
- explicitly say ROOT CAUSE UNDETERMINED when physical cause is
  not established

Maximum about 6 concise sentences.

If action=request_more:
- request must be one focused domain question
- stop_reason must be null
- conclusion must be null

If action=conclude:
- request must be null
- stop_reason must be populated

If rounds_used >= max_rounds:
- action must be conclude
"""

    result = _model().invoke(
        prompt
    )

    # --------------------------------------------------------
    # Deterministic guards
    # --------------------------------------------------------

    if final_round:

        result.action = (
            RCAAction.CONCLUDE
        )

        result.request = None

        if result.stop_reason is None:

            result.stop_reason = (
                RCAStopReason.MAX_ROUNDS_REACHED
            )

        if not result.conclusion:

            result.conclusion = (
                "ROOT CAUSE UNDETERMINED: "
                "the available evidence does not establish "
                "the underlying physical cause."
            )

        return result

    if (
        result.action
        == RCAAction.REQUEST_MORE
    ):

        if not result.request:

            raise RuntimeError(
                "RCA requested more evidence "
                "without a domain request."
            )

        if (
            result.request.domain
            not in AVAILABLE_DOMAINS
        ):

            raise RuntimeError(
                "RCA selected unsupported domain: "
                + result.request.domain
            )

        result.conclusion = None
        result.stop_reason = None

        return result

    result.request = None

    if result.stop_reason is None:

        result.stop_reason = (
            RCAStopReason.SUFFICIENT_EVIDENCE
        )

    if not result.conclusion:

        raise RuntimeError(
            "RCA concluded without a conclusion."
        )

    return result