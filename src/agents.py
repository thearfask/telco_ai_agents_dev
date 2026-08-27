from __future__ import annotations

import json
import uuid
from typing import Any

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from config import (
    get_context_config,
    get_runtime_config,
)
from llm import get_llm
from models import (
    DomainTask,
    DomainUpdate,
    EvidenceFact,
    InvestigationState,
    RCADecision,
)
from prompts import (
    ALARM_GOVERNANCE,
    ALARMS_PROMPT,
    COMMON_SPECIALIST_PROMPT,
    DOMAIN_FINALIZER_PROMPT,
    INCIDENT_PARSER_PROMPT,
    RCA_PROMPT,
    TELEMETRY_GOVERNANCE,
    TELEMETRY_PROMPT,
    TOPOLOGY_GOVERNANCE,
    TOPOLOGY_PROMPT,
)
from tools import (
    ALARM_TOOLS,
    TELEMETRY_TOOLS,
    TOPOLOGY_TOOLS,
)


# ============================================================
# INCIDENT
# ============================================================


from models import IncidentContext


def parse_incident(
    incident_text: str,
) -> IncidentContext:

    model = (
        get_llm(
            "incident_parser"
        )
        .with_structured_output(
            IncidentContext,
            method="json_schema",
        )
    )

    return model.invoke(
        [
            SystemMessage(
                content=(
                    INCIDENT_PARSER_PROMPT
                )
            ),
            HumanMessage(
                content=(
                    "INCIDENT\n\n"
                    + incident_text
                )
            ),
        ]
    )


# ============================================================
# CONTEXT PROJECTIONS
# ============================================================


def _limits():
    return get_context_config()


def _relevant_facts(
    state: InvestigationState,
    domain: str | None = None,
) -> list[EvidenceFact]:

    facts = (
        state.confirmed_facts
    )

    if domain:
        domain_facts = [
            fact
            for fact in facts
            if fact.domain == domain
        ]

        cross_domain = [
            fact
            for fact in facts
            if fact.domain != domain
        ]

        facts = (
            domain_facts
            + cross_domain
        )

    limit = int(
        _limits().get(
            "max_confirmed_facts_for_agent",
            6,
        )
    )

    return facts[-limit:]


def build_rca_context(
    state: InvestigationState,
) -> dict[str, Any]:

    config = _limits()

    return {
        "incident": (
            state.incident.model_dump(
                exclude_none=True
            )
        ),
        "confirmed_facts": [
            item.model_dump()
            for item
            in state.confirmed_facts[
                -int(
                    config.get(
                        "max_confirmed_facts_for_agent",
                        6,
                    )
                ):
            ]
        ],
        "hypothesis_verdicts": [
            item.model_dump()
            for item
            in state.hypothesis_verdicts[
                -int(
                    config.get(
                        "max_verdicts_for_agent",
                        6,
                    )
                ):
            ]
        ],
        "open_questions": [
            item.model_dump()
            for item
            in state.open_questions[
                -int(
                    config.get(
                        "max_open_questions_for_agent",
                        4,
                    )
                ):
            ]
        ],
        "evidence_gaps": [
            item.model_dump()
            for item
            in state.evidence_gaps[
                -int(
                    config.get(
                        "max_evidence_gaps_for_agent",
                        4,
                    )
                ):
            ]
        ],
        "rounds_used": (
            state.rounds_used
        ),
        "max_rounds": int(
            get_runtime_config().get(
                "max_investigation_rounds",
                5,
            )
        ),
    }


def build_domain_context(
    state: InvestigationState,
    task: DomainTask,
) -> dict[str, Any]:

    config = _limits()

    relevant_verdicts = [
        verdict
        for verdict
        in state.hypothesis_verdicts
        if (
            verdict.domain
            == task.domain
        )
    ]

    relevant_questions = [
        question
        for question
        in state.open_questions
        if (
            question.domain
            == task.domain
        )
    ]

    relevant_gaps = [
        gap
        for gap
        in state.evidence_gaps
        if (
            gap.domain
            == task.domain
        )
    ]

    return {
        "incident": (
            state.incident.model_dump(
                exclude_none=True
            )
        ),
        "task": task.model_dump(),
        "existing_facts": [
            fact.model_dump()
            for fact
            in _relevant_facts(
                state,
                task.domain,
            )
        ],
        "existing_verdicts": [
            item.model_dump()
            for item
            in relevant_verdicts[
                -int(
                    config.get(
                        "max_verdicts_for_agent",
                        6,
                    )
                ):
            ]
        ],
        "open_questions": [
            item.model_dump()
            for item
            in relevant_questions[
                -int(
                    config.get(
                        "max_open_questions_for_agent",
                        4,
                    )
                ):
            ]
        ],
        "evidence_gaps": [
            item.model_dump()
            for item
            in relevant_gaps[
                -int(
                    config.get(
                        "max_evidence_gaps_for_agent",
                        4,
                    )
                ):
            ]
        ],
    }


# ============================================================
# RCA
# ============================================================


def run_rca(
    state: InvestigationState,
) -> RCADecision:

    max_rounds = int(
        get_runtime_config().get(
            "max_investigation_rounds",
            5,
        )
    )

    if (
        state.rounds_used
        >= max_rounds
    ):

        return RCADecision(
            action="conclude",
            conclusion=(
                "ROOT CAUSE UNDETERMINED: "
                "the available evidence does not "
                "establish a defensible physical "
                "root cause."
            ),
            confidence="MEDIUM",
            reasoning_summary=(
                "Maximum investigation rounds "
                "were reached."
            ),
            stop_reason=(
                "max_rounds_reached"
            ),
        )

    context = (
        build_rca_context(
            state
        )
    )

    model = (
        get_llm(
            "rca"
        )
        .with_structured_output(
            RCADecision,
            method="json_schema",
        )
    )

    decision = model.invoke(
        [
            SystemMessage(
                content=(
                    RCA_PROMPT
                )
            ),
            HumanMessage(
                content=(
                    "CURRENT INVESTIGATION STATE\n\n"
                    + json.dumps(
                        context,
                        default=str,
                    )
                )
            ),
        ]
    )

    if (
        decision.action
        == "request_more"
    ):

        if not decision.request:
            raise RuntimeError(
                "RCA requested more evidence "
                "without a DomainTask."
            )

        decision.conclusion = None
        decision.stop_reason = None

    else:

        decision.request = None

        if not decision.conclusion:
            decision.conclusion = (
                "ROOT CAUSE UNDETERMINED: "
                "available evidence is insufficient."
            )

        if not decision.stop_reason:
            decision.stop_reason = (
                "sufficient_evidence"
            )

    return decision


# ============================================================
# SPECIALIST CONFIGURATION
# ============================================================


def _domain_configuration(
    domain: str,
):

    if domain == "telemetry":

        return {
            "profile": "telemetry",
            "prompt": (
                COMMON_SPECIALIST_PROMPT
                + "\n\n"
                + TELEMETRY_GOVERNANCE
                + "\n\n"
                + TELEMETRY_PROMPT
            ),
            "tools": (
                TELEMETRY_TOOLS
            ),
        }

    if domain == "alarms":

        return {
            "profile": "alarms",
            "prompt": (
                COMMON_SPECIALIST_PROMPT
                + "\n\n"
                + ALARM_GOVERNANCE
                + "\n\n"
                + ALARMS_PROMPT
            ),
            "tools": (
                ALARM_TOOLS
            ),
        }

    if domain == "topology":

        return {
            "profile": "topology",
            "prompt": (
                COMMON_SPECIALIST_PROMPT
                + "\n\n"
                + TOPOLOGY_GOVERNANCE
                + "\n\n"
                + TOPOLOGY_PROMPT
            ),
            "tools": (
                TOPOLOGY_TOOLS
            ),
        }

    raise ValueError(
        f"Unsupported domain: {domain}"
    )


# ============================================================
# TOOL LOOP
# ============================================================


def run_domain_agent(
    *,
    state: InvestigationState,
    task: DomainTask,
) -> tuple[
    DomainUpdate,
    list[dict],
]:

    configuration = (
        _domain_configuration(
            task.domain
        )
    )

    tools = configuration[
        "tools"
    ]

    tool_map = {
        tool.name: tool
        for tool in tools
    }

    domain_context = (
        build_domain_context(
            state,
            task,
        )
    )

    system_prompt = (
        configuration[
            "prompt"
        ]
    )

    messages = [
        SystemMessage(
            content=system_prompt
        ),
        HumanMessage(
            content=(
                "DOMAIN CONTEXT\n\n"
                + json.dumps(
                    domain_context,
                    default=str,
                )
            )
        ),
    ]

    tool_model = (
        get_llm(
            configuration[
                "profile"
            ]
        )
        .bind_tools(
            tools
        )
    )

    max_calls = int(
        get_runtime_config().get(
            "max_domain_tool_calls",
            5,
        )
    )

    calls_used = 0

    trace = []

    specialist_synthesis = ""

    while True:

        response = (
            tool_model.invoke(
                messages
            )
        )

        messages.append(
            response
        )

        calls = (
            getattr(
                response,
                "tool_calls",
                [],
            )
            or []
        )

        if not calls:

            specialist_synthesis = (
                str(
                    response.content
                    or ""
                )
            )

            break

        for call in calls:

            if calls_used >= max_calls:
                break

            name = call.get(
                "name"
            )

            args = call.get(
                "args",
                {},
            )

            tool = tool_map.get(
                name
            )

            if not tool:

                result = {
                    "status": "failed",
                    "error": (
                        f"Unknown tool: {name}"
                    ),
                }

            else:

                try:

                    raw_result = (
                        tool.invoke(
                            args
                        )
                    )

                    result = (
                        raw_result
                    )

                except Exception as exc:

                    result = json.dumps(
                        {
                            "status": (
                                "failed"
                            ),
                            "error": str(
                                exc
                            ),
                        }
                    )

            trace.append(
                {
                    "tool": name,
                    "args": args,
                    "result": result,
                }
            )

            messages.append(
                ToolMessage(
                    tool_call_id=(
                        call.get(
                            "id"
                        )
                    ),
                    name=name,
                    content=str(
                        result
                    ),
                )
            )

            calls_used += 1

        if calls_used >= max_calls:

            synthesis_model = (
                get_llm(
                    configuration[
                        "profile"
                    ]
                )
            )

            messages.append(
                HumanMessage(
                    content=(
                        "Tool budget reached. "
                        "Produce the concise DOMAIN "
                        "SYNTHESIS now. Do not request "
                        "another tool."
                    )
                )
            )

            synthesis = (
                synthesis_model.invoke(
                    messages
                )
            )

            specialist_synthesis = (
                str(
                    synthesis.content
                    or ""
                )
            )

            break

    # ========================================================
    # COMPACT DOMAIN OUTPUT
    # ========================================================

    finalizer = (
        get_llm(
            "domain_finalizer"
        )
        .with_structured_output(
            DomainUpdate,
            method="json_schema",
        )
    )

    finalizer_context = {
        "incident_id": (
            state.incident.incident_id
        ),
        "task": (
            task.model_dump()
        ),
        "existing_facts": [
            fact.model_dump()
            for fact
            in _relevant_facts(
                state,
                task.domain,
            )
        ],
        "specialist_synthesis": (
            specialist_synthesis
        ),
    }

    update = finalizer.invoke(
        [
            SystemMessage(
                content=(
                    DOMAIN_FINALIZER_PROMPT
                )
            ),
            HumanMessage(
                content=json.dumps(
                    finalizer_context,
                    default=str,
                )
            ),
        ]
    )

    return (
        update,
        trace,
    )


# ============================================================
# IDS
# ============================================================


def new_request_id() -> str:
    return (
        "REQ-"
        + uuid.uuid4()
        .hex[:8]
        .upper()
    )