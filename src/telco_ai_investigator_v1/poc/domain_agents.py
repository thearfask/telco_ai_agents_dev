from __future__ import annotations

import json
import os
from typing import Annotated, TypedDict

from dotenv import load_dotenv

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from langchain_openai import ChatOpenAI

from langgraph.graph import (
    END,
    START,
    StateGraph,
)

from langgraph.graph.message import (
    add_messages,
)

from langgraph.prebuilt import (
    ToolNode,
)

from .common_tools import (
    COMMON_TOOLS,
)

from .models import (
    DomainFindingUpdate,
    DomainRequest,
    IncidentObjective,
    InvestigationEvidenceState,
)


load_dotenv()


MODEL = os.getenv(
    "POC_MODEL",
    "gpt-5.4-mini",
)


MAX_TOOL_CALLS_PER_DOMAIN_ROUND = 3


# ============================================================
# DOMAIN INSTRUCTIONS
# ============================================================


COMMON_DOMAIN_RULES = """
You are a specialist domain engineer participating in an RCA.

You receive:
- the incident objective
- the RCA's focused domain request
- a bounded global evidence state

You have access to common investigation tools.

TOOL CHOICE|

query_sql:
Use for structured operational facts and statistics.

search_knowledge:
Use for engineering meaning, KPI semantics, troubleshooting
knowledge, runbooks and known patterns.

search_logs:
Use for operational event/error/warning evidence.

query_graph:
Use for network relationships/dependencies.

You may:
- use no tool when existing evidence is sufficient
- use one tool
- use multiple different tools when materially necessary

Never call a tool just because it exists.

Maximum one tool request per reasoning turn.
Maximum three tool calls in this domain round.

EVIDENCE DISCIPLINE|

Always distinguish:

OBSERVED
Direct operational/tool evidence.

KNOWLEDGE
Retrieved engineering guidance.

INFERRED
Your domain interpretation.

Knowledge can suggest a hypothesis but does not prove that the
current incident has that root cause.

Never infer causality from correlation alone.

Never claim temporal persistence, intermittency, periodicity or
burstiness from AVG/MIN/MAX alone.

When comparing metrics, use appropriate baselines, distributions
or each metric's own meaningful threshold. Do not compare unrelated
metrics against arbitrary shared thresholds.

Prefer the smallest evidence collection required to answer the RCA
question.

If the requested evidence is unavailable, state that clearly rather
than inventing a substitute.
"""


DOMAIN_RULES = {
    "telemetry": """
You are the TELEMETRY specialist.

Your responsibility is to reason about:
- RF measurements
- BLER
- SNR
- MCS
- PRB utilization
- traffic counters
- time/distribution behavior
- radio telemetry evidence

Do not diagnose hardware, alarms or topology without supporting
cross-domain evidence.

Avoid hard-coded qualitative classification unless supported by
engineering knowledge. Use search_knowledge when interpretation is
materially important and uncertain.
""",

    "alarms": """
You are the ALARM specialist.

Your responsibility is to investigate:
- alarms
- events
- alarm sequences
- severity
- activation/clearance timing
- correlated alarm patterns
- probable alarm meaning

Use structured data, logs and engineering knowledge as appropriate.

An alarm definition or runbook is knowledge.
An alarm actually observed during the incident is operational
evidence.
""",

    "topology": """
You are the TOPOLOGY specialist.

Your responsibility is to investigate:
- component relationships
- serving relationships
- shared infrastructure
- dependencies
- blast radius
- topology correlations

Use graph queries where relationship traversal is needed.
Use SQL when relationships are represented as structured tables.
Use logs/RAG only when they materially help interpretation.
""",
}


# ============================================================
# SUBGRAPH STATE
# ============================================================


class DomainGraphState(TypedDict, total=False):
    messages: Annotated[
        list[BaseMessage],
        add_messages,
    ]

    tool_calls_used: int

    final_update: DomainFindingUpdate


# ============================================================
# MODEL FACTORIES
# ============================================================


def _tool_model():

    return ChatOpenAI(
        model=MODEL,
        temperature=0,
        reasoning_effort=None,
        max_completion_tokens=1200,
    ).bind_tools(
        COMMON_TOOLS
    )


def _finalizer_model():

    llm = ChatOpenAI(
        model=MODEL,
        temperature=0,
        reasoning_effort=None,
        max_completion_tokens=1700,
    )

    return llm.with_structured_output(
        DomainFindingUpdate,
        method="json_schema",
    )


# ============================================================
# TOOL-CHOICE NODE
# ============================================================


def _agent_node(
    state: DomainGraphState,
) -> dict:

    response = _tool_model().invoke(
        state["messages"]
    )

    calls = len(
        getattr(
            response,
            "tool_calls",
            [],
        )
        or []
    )

    return {
        "messages": [
            response
        ],

        "tool_calls_used": (
            state.get(
                "tool_calls_used",
                0,
            )
            + calls
        ),
    }


def _route_after_agent(
    state: DomainGraphState,
) -> str:

    last = state[
        "messages"
    ][-1]

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
        > MAX_TOOL_CALLS_PER_DOMAIN_ROUND
    ):
        return "finalize"

    return "tools"


# ============================================================
# FINALIZER
# ============================================================


def _compact_transcript(
    messages: list[BaseMessage],
) -> str:

    lines = []

    # Tool rounds are deliberately bounded.
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

            content = str(
                message.content
            )[:3500]

            lines.append(
                f"REQUEST_CONTEXT: {content}"
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
                                "name": call.get(
                                    "name"
                                ),
                                "args": call.get(
                                    "args"
                                ),
                            },
                            default=str,
                        )[:2200]
                    )

            elif message.content:

                lines.append(
                    "SPECIALIST_REASONING_OUTPUT: "
                    + str(
                        message.content
                    )[:2500]
                )

        elif isinstance(
            message,
            ToolMessage,
        ):

            lines.append(
                "TOOL_RESULT: "
                + str(
                    message.content
                )[:5000]
            )

    return "\n".join(
        lines
    )


def _finalize_node(
    state: DomainGraphState,
) -> dict:

    transcript = _compact_transcript(
        state["messages"]
    )

    prompt = f"""
ROLE|DOMAIN_EVIDENCE_EDITOR

Convert the specialist investigation transcript into a compact
DomainFindingUpdate for the RCA.

TRANSCRIPT|
{transcript}

OUTPUT RULES|

Return only NEW decision-relevant information.

new_confirmed:
maximum 4.

new_ruled_out:
maximum 2.

new_open_questions:
maximum 2.

resolved_question_ids:
include IDs of previous open questions that this round resolved,
when IDs are visible in the context.

summary:
maximum a few concise sentences.

SOURCE CLASSIFICATION|

Operational SQL result -> observed / sql
Operational log -> observed / log
Topology relationship -> observed / graph
Retrieved documentation -> knowledge / rag
Domain conclusion derived from those -> inferred

Do not copy large tool outputs.

Do not describe retrieved knowledge as incident observation.

Do not overclaim root cause.

For multi-window investigations:
report only material similarities or differences rather than one
finding per metric per window.

For open questions:
CURRENT means already answerable from known evidence.
QUERYABLE means another available tool can obtain the evidence.
UNAVAILABLE means the available tools/sources genuinely do not
contain the required evidence.
"""

    result = _finalizer_model().invoke(
        prompt
    )

    return {
        "final_update": result
    }


# ============================================================
# BUILD SPECIALIST SUBGRAPH
# ============================================================


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
        ToolNode(
            COMMON_TOOLS
        ),
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


# ============================================================
# DOMAIN INVOCATION
# ============================================================


def _build_domain_context(
    *,
    domain: str,
    objective: IncidentObjective,
    request: DomainRequest,
    evidence_state: InvestigationEvidenceState,
) -> list[BaseMessage]:

    instructions = (
        COMMON_DOMAIN_RULES
        + "\n"
        + DOMAIN_RULES[
            domain
        ]
    )

    context = f"""
INCIDENT OBJECTIVE|
{objective.model_dump_json(exclude_none=True)}

RCA DOMAIN REQUEST|
{request.model_dump_json(exclude_none=True)}

CURRENT GLOBAL EVIDENCE STATE|
{evidence_state.model_dump_json(exclude_none=True)}

Investigate only what is necessary to answer the RCA request.

Think about what is already known before selecting tools.
"""

    return [
        SystemMessage(
            content=instructions
        ),
        HumanMessage(
            content=context
        ),
    ]


def _extract_tool_audit(
    messages: list[BaseMessage],
) -> list[dict]:

    audit = []

    pending_calls = {}

    for message in messages:

        if isinstance(
            message,
            AIMessage,
        ):

            for call in (
                message.tool_calls
                or []
            ):

                call_id = call.get(
                    "id"
                )

                pending_calls[
                    call_id
                ] = {
                    "tool": call.get(
                        "name"
                    ),
                    "args": call.get(
                        "args"
                    ),
                }

        elif isinstance(
            message,
            ToolMessage,
        ):

            call_id = (
                message.tool_call_id
            )

            item = pending_calls.get(
                call_id,
                {
                    "tool": message.name,
                    "args": {},
                },
            )

            audit.append(
                {
                    "tool": item.get(
                        "tool"
                    ),
                    "args": item.get(
                        "args"
                    ),
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

    if domain not in DOMAIN_RULES:

        raise ValueError(
            f"Unsupported domain: {domain}"
        )

    initial_messages = (
        _build_domain_context(
            domain=domain,
            objective=objective,
            request=request,
            evidence_state=evidence_state,
        )
    )

    result = DOMAIN_GRAPH.invoke(
        {
            "messages":
                initial_messages,

            "tool_calls_used":
                0,
        }
    )

    update = result[
        "final_update"
    ]

    tool_audit = (
        _extract_tool_audit(
            result["messages"]
        )
    )

    return {
        "domain": domain,
        "request": request,
        "update": update,
        "tool_audit": tool_audit,
        "tool_calls_used": len(
            tool_audit
        ),
    }