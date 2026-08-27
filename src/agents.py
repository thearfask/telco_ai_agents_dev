from __future__ import annotations

import json
from typing import Annotated, TypedDict

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from langgraph.graph import (
    END,
    START,
    StateGraph,
)

from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from models import (
    DomainFindingUpdate,
    DomainRequest,
    IncidentContext,
    IncidentObjective,
    InvestigationEvidenceState,
    RCAAction,
    RCADecision,
    RCAStopReason,
)

from prompts import (
    COMMON_SPECIALIST_PROMPT,
    DOMAIN_FINALIZER_PROMPT,
    DOMAIN_PROMPTS,
    INCIDENT_PARSER_PROMPT,
    RCA_PROMPT,
)

from tools import (
    COMMON_TOOLS,
    create_llm,
)


MAX_TOOL_CALLS_PER_DOMAIN_ROUND = 3

AVAILABLE_DOMAINS = [
    "telemetry",
    "alarms",
    "topology",
]


# ============================================================
# INCIDENT
# ============================================================


def parse_incident(
    incident_text: str,
) -> IncidentContext:
    model = create_llm(
        max_completion_tokens=1200,
    ).with_structured_output(
        IncidentContext,
        method="json_schema",
    )

    prompt = f"""
{INCIDENT_PARSER_PROMPT}

INCIDENT|
{incident_text}
"""

    result = model.invoke(prompt)

    result.raw_text = incident_text

    return result


def build_objective(
    incident: IncidentContext,
) -> IncidentObjective:
    return IncidentObjective(
        incident_id=incident.incident_id,
        problem_statement=incident.problem_statement,
        investigation_goal=incident.investigation_goal,
        symptoms=incident.symptoms[:8],
        window_ids=incident.window_ids,
        component_ids=incident.component_ids,
        site_ids=incident.site_ids,
        region=incident.region,
        zone=incident.zone,
        start_time=incident.start_time,
        end_time=incident.end_time,
    )


# ============================================================
# SPECIALIST SUBGRAPH
# ============================================================


class DomainGraphState(
    TypedDict,
    total=False,
):
    messages: Annotated[
        list[BaseMessage],
        add_messages,
    ]

    tool_calls_used: int

    final_update: DomainFindingUpdate


def _tool_model():
    return create_llm(
        max_completion_tokens=1200,
    ).bind_tools(
        COMMON_TOOLS
    )


def _finalizer_model():
    return create_llm(
        max_completion_tokens=1600,
    ).with_structured_output(
        DomainFindingUpdate,
        method="json_schema",
    )


def _agent_node(
    state: DomainGraphState,
) -> dict:
    response = _tool_model().invoke(
        state["messages"]
    )

    calls = (
        getattr(
            response,
            "tool_calls",
            [],
        )
        or []
    )

    # Hard guard:
    # execute at most one tool request per reasoning turn.
    if len(calls) > 1:
        response.tool_calls = calls[:1]
        calls = calls[:1]

    return {
        "messages": [response],
        "tool_calls_used": (
            state.get(
                "tool_calls_used",
                0,
            )
            + len(calls)
        ),
    }


def _route_after_agent(
    state: DomainGraphState,
) -> str:
    last = state["messages"][-1]

    calls = (
        getattr(
            last,
            "tool_calls",
            [],
        )
        or []
    )

    if not calls:
        return "finalize"

    if (
        state.get(
            "tool_calls_used",
            0,
        )
        >= MAX_TOOL_CALLS_PER_DOMAIN_ROUND
    ):
        return "finalize"

    return "tools"


def _compact_transcript(
    messages: list[BaseMessage],
) -> str:
    lines = []

    for message in messages[-14:]:
        if isinstance(
            message,
            SystemMessage,
        ):
            continue

        if isinstance(
            message,
            HumanMessage,
        ):
            lines.append(
                "REQUEST_CONTEXT: "
                + str(message.content)[:3500]
            )

        elif isinstance(
            message,
            AIMessage,
        ):
            if message.tool_calls:
                for call in message.tool_calls:
                    lines.append(
                        "TOOL_REQUEST: "
                        + json.dumps(
                            {
                                "name": call.get("name"),
                                "args": call.get("args"),
                            },
                            default=str,
                        )[:2000]
                    )

            elif message.content:
                lines.append(
                    "SPECIALIST_OUTPUT: "
                    + str(message.content)[:2200]
                )

        elif isinstance(
            message,
            ToolMessage,
        ):
            lines.append(
                "TOOL_RESULT: "
                + str(message.content)[:5000]
            )

    return "\n".join(lines)


def _finalize_node(
    state: DomainGraphState,
) -> dict:
    transcript = _compact_transcript(
        state["messages"]
    )

    prompt = f"""
{DOMAIN_FINALIZER_PROMPT}

INVESTIGATION TRANSCRIPT|
{transcript}
"""

    result = _finalizer_model().invoke(
        prompt
    )

    # Defensive cleanup.
    result.resolved_question_ids = [
        value
        for value in result.resolved_question_ids
        if value
        and value.strip().lower()
        not in {
            "none",
            "(none)",
            "n/a",
            "na",
        }
    ]

    return {
        "final_update": result
    }


def build_domain_graph():
    builder = StateGraph(
        DomainGraphState
    )

    builder.add_node(
        "agent",
        _agent_node,
    )

    builder.add_node(
        "tools",
        ToolNode(COMMON_TOOLS),
    )

    builder.add_node(
        "finalize",
        _finalize_node,
    )

    builder.add_edge(
        START,
        "agent",
    )

    builder.add_conditional_edges(
        "agent",
        _route_after_agent,
        {
            "tools": "tools",
            "finalize": "finalize",
        },
    )

    builder.add_edge(
        "tools",
        "agent",
    )

    builder.add_edge(
        "finalize",
        END,
    )

    return builder.compile()


DOMAIN_GRAPH = build_domain_graph()


def _domain_messages(
    *,
    domain: str,
    objective: IncidentObjective,
    request: DomainRequest,
    evidence_state: InvestigationEvidenceState,
) -> list[BaseMessage]:
    system_prompt = (
        COMMON_SPECIALIST_PROMPT
        + "\n\n"
        + DOMAIN_PROMPTS[domain]
    )

    context = f"""
INCIDENT OBJECTIVE|
{objective.model_dump_json(exclude_none=True)}

RCA REQUEST|
{request.model_dump_json(exclude_none=True)}

CURRENT EVIDENCE|
{evidence_state.model_dump_json(exclude_none=True)}

Investigate only what is necessary to answer the RCA request.
"""

    return [
        SystemMessage(
            content=system_prompt
        ),
        HumanMessage(
            content=context
        ),
    ]


def _tool_audit(
    messages: list[BaseMessage],
) -> list[dict]:
    audit = []
    pending = {}

    for message in messages:
        if isinstance(
            message,
            AIMessage,
        ):
            for call in (
                message.tool_calls
                or []
            ):
                pending[
                    call.get("id")
                ] = {
                    "tool": call.get("name"),
                    "args": call.get("args"),
                }

        elif isinstance(
            message,
            ToolMessage,
        ):
            item = pending.get(
                message.tool_call_id,
                {
                    "tool": message.name,
                    "args": {},
                },
            )

            audit.append(
                {
                    "tool": item["tool"],
                    "args": item["args"],
                    "result": str(
                        message.content
                    ),
                }
            )

    return audit


def run_domain_agent(
    *,
    domain: str,
    objective: IncidentObjective,
    request: DomainRequest,
    evidence_state: InvestigationEvidenceState,
) -> dict:
    if domain not in DOMAIN_PROMPTS:
        raise ValueError(
            f"Unsupported domain: {domain}"
        )

    result = DOMAIN_GRAPH.invoke(
        {
            "messages": _domain_messages(
                domain=domain,
                objective=objective,
                request=request,
                evidence_state=evidence_state,
            ),
            "tool_calls_used": 0,
        }
    )

    audit = _tool_audit(
        result["messages"]
    )

    return {
        "domain": domain,
        "request": request,
        "update": result["final_update"],
        "tool_audit": audit,
        "tool_calls_used": len(audit),
    }


# ============================================================
# RCA
# ============================================================


def run_rca(
    *,
    objective: IncidentObjective,
    evidence_state: InvestigationEvidenceState,
    latest_update: DomainFindingUpdate | None,
    rounds_used: int,
    max_rounds: int,
) -> RCADecision:
    model = create_llm(
        max_completion_tokens=1800,
    ).with_structured_output(
        RCADecision,
        method="json_schema",
    )

    latest = (
        latest_update.model_dump_json(
            exclude_none=True
        )
        if latest_update
        else "{}"
    )

    prompt = f"""
{RCA_PROMPT}

INCIDENT OBJECTIVE|
{objective.model_dump_json(exclude_none=True)}

CURRENT EVIDENCE|
{evidence_state.model_dump_json(exclude_none=True)}

LATEST DOMAIN UPDATE|
{latest}

ROUNDS USED|
{rounds_used}/{max_rounds}

AVAILABLE DOMAINS|
{AVAILABLE_DOMAINS}
"""

    decision = model.invoke(prompt)

    # ========================================================
    # DETERMINISTIC ROUND LIMIT
    # ========================================================

    if rounds_used >= max_rounds:
        decision.action = RCAAction.CONCLUDE
        decision.request = None
        decision.stop_reason = (
            RCAStopReason.MAX_ROUNDS_REACHED
        )

        if not decision.conclusion:
            decision.conclusion = (
                "ROOT CAUSE UNDETERMINED: "
                "the available evidence does not establish "
                "the underlying physical cause."
            )

        return decision

    # ========================================================
    # REQUEST MORE
    # ========================================================

    if (
        decision.action
        == RCAAction.REQUEST_MORE
    ):
        if not decision.request:
            raise RuntimeError(
                "RCA requested more evidence "
                "without a domain request."
            )

        if (
            decision.request.domain
            not in AVAILABLE_DOMAINS
        ):
            raise RuntimeError(
                "Unsupported RCA domain: "
                + decision.request.domain
            )

        decision.conclusion = None
        decision.stop_reason = None

        return decision

    # ========================================================
    # CONCLUDE
    # ========================================================

    decision.request = None

    if decision.stop_reason is None:
        decision.stop_reason = (
            RCAStopReason.SUFFICIENT_EVIDENCE
        )

    if not decision.conclusion:
        decision.conclusion = (
            "ROOT CAUSE UNDETERMINED: "
            "the available evidence does not establish "
            "a defensible root cause."
        )

    return decision