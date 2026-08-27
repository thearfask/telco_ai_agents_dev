from __future__ import annotations

from typing import TypedDict
from uuid import uuid4

from langgraph.checkpoint.memory import (
    InMemorySaver,
)

from langgraph.graph import (
    END,
    START,
    StateGraph,
)

from .domain_agents import (
    run_domain_agent,
)

from .incident_parser import (
    build_objective,
    parse_incident,
)

from .models import (
    DomainFindingUpdate,
    DomainRequest,
    EvidenceFact,
    IncidentContext,
    IncidentObjective,
    InvestigationEvidenceState,
    InvestigationResult,
    OpenQuestion,
    RCAAction,
    RCADecision,
    RuledOutHypothesis,
)

from .rca_agent import (
    run_rca,
)


MAX_RCA_ROUNDS = 3


# ============================================================
# GRAPH STATE
# ============================================================


class InvestigationGraphState(
    TypedDict,
    total=False,
):
    incident_text: str

    incident: IncidentContext

    objective: IncidentObjective

    evidence_state: InvestigationEvidenceState

    active_request: DomainRequest

    latest_update: DomainFindingUpdate

    rounds_used: int

    domain_history: list[dict]

    rca_history: list[RCADecision]

    final_rca: RCADecision


# ============================================================
# HELPERS
# ============================================================


def _normalize(
    value: str,
) -> str:

    return " ".join(
        value.lower()
        .strip()
        .split()
    )


def _request_id() -> str:

    return (
        "REQ-"
        + uuid4().hex[:8].upper()
    )


# ============================================================
# INTAKE
# ============================================================


def intake_node(
    state: InvestigationGraphState,
) -> dict:

    incident = parse_incident(
        state["incident_text"]
    )

    objective = build_objective(
        incident
    )

    return {
        "incident": incident,

        "objective": objective,

        "evidence_state":
            InvestigationEvidenceState(),

        "rounds_used": 0,

        "domain_history": [],

        "rca_history": [],
    }


# ============================================================
# RCA / SUPERVISOR
# ============================================================


def rca_node(
    state: InvestigationGraphState,
) -> dict:

    decision = run_rca(
        objective=state[
            "objective"
        ],

        evidence_state=state[
            "evidence_state"
        ],

        latest_update=state.get(
            "latest_update"
        ),

        rounds_used=state.get(
            "rounds_used",
            0,
        ),

        max_rounds=MAX_RCA_ROUNDS,
    )

    history = list(
        state.get(
            "rca_history",
            [],
        )
    )

    history.append(
        decision
    )

    update = {
        "rca_history": history,
    }

    if (
        decision.action
        == RCAAction.CONCLUDE
    ):

        update[
            "final_rca"
        ] = decision

        return update

    request = DomainRequest(
        request_id=_request_id(),

        domain=decision.request.domain,

        question=decision.request.question,
    )

    update[
        "active_request"
    ] = request

    return update


def route_after_rca(
    state: InvestigationGraphState,
) -> str:

    if state.get(
        "final_rca"
    ):
        return "end"

    domain = state[
        "active_request"
    ].domain

    if domain == "telemetry":
        return "telemetry"

    if domain == "alarms":
        return "alarms"

    if domain == "topology":
        return "topology"

    raise RuntimeError(
        f"Unknown domain route: {domain}"
    )


# ============================================================
# SPECIALIST NODES
# ============================================================


def _run_specialist(
    state: InvestigationGraphState,
    domain: str,
) -> dict:

    request = state[
        "active_request"
    ]

    result = run_domain_agent(
        domain=domain,

        objective=state[
            "objective"
        ],

        request=request,

        evidence_state=state[
            "evidence_state"
        ],
    )

    history = list(
        state.get(
            "domain_history",
            [],
        )
    )

    history.append(
        {
            "round":
                state.get(
                    "rounds_used",
                    0,
                )
                + 1,

            "domain":
                domain,

            "request":
                request.model_dump(
                    mode="json"
                ),

            "tool_calls_used":
                result[
                    "tool_calls_used"
                ],

            "tools": [
                item.get(
                    "tool"
                )
                for item
                in result[
                    "tool_audit"
                ]
            ],

            # Full tool audit stays here.
            # RCA does not receive it.
            "tool_audit":
                result[
                    "tool_audit"
                ],

            "domain_update":
                result[
                    "update"
                ].model_dump(
                    mode="json"
                ),
        }
    )

    return {
        "latest_update":
            result["update"],

        "domain_history":
            history,

        "rounds_used":
            state.get(
                "rounds_used",
                0,
            )
            + 1,
    }


def telemetry_node(
    state: InvestigationGraphState,
) -> dict:

    return _run_specialist(
        state,
        "telemetry",
    )


def alarms_node(
    state: InvestigationGraphState,
) -> dict:

    return _run_specialist(
        state,
        "alarms",
    )


def topology_node(
    state: InvestigationGraphState,
) -> dict:

    return _run_specialist(
        state,
        "topology",
    )


# ============================================================
# GLOBAL EVIDENCE MERGE
# ============================================================


def merge_evidence_node(
    state: InvestigationGraphState,
) -> dict:

    current = (
        state[
            "evidence_state"
        ].model_copy(
            deep=True
        )
    )

    update = state[
        "latest_update"
    ]

    round_number = state[
        "rounds_used"
    ]

    domain = state[
        "active_request"
    ].domain

    # --------------------------------------------------------
    # Resolve old open questions
    # --------------------------------------------------------

    resolved = set(
        update.resolved_question_ids
    )

    if resolved:

        current.open_questions = [
            item
            for item
            in current.open_questions
            if item.question_id
            not in resolved
        ]

    # --------------------------------------------------------
    # Confirmed facts
    # --------------------------------------------------------

    existing_fact_text = {
        _normalize(
            item.statement
        )
        for item
        in current.confirmed
    }

    for index, draft in enumerate(
        update.new_confirmed,
        start=1,
    ):

        normalized = _normalize(
            draft.statement
        )

        if normalized in existing_fact_text:
            continue

        fact = EvidenceFact(
            fact_id=(
                f"{domain[:3].upper()}"
                f"-R{round_number}-F{index}"
            ),

            domain=domain,

            statement=draft.statement,

            evidence=draft.evidence,

            confidence=draft.confidence,

            kind=draft.kind,

            sources=draft.sources,
        )

        current.confirmed.append(
            fact
        )

        existing_fact_text.add(
            normalized
        )

    # --------------------------------------------------------
    # Ruled-out hypotheses
    # --------------------------------------------------------

    existing_ruled_text = {
        _normalize(
            item.hypothesis
        )
        for item
        in current.ruled_out
    }

    for index, draft in enumerate(
        update.new_ruled_out,
        start=1,
    ):

        normalized = _normalize(
            draft.hypothesis
        )

        if normalized in existing_ruled_text:
            continue

        item = RuledOutHypothesis(
            hypothesis_id=(
                f"{domain[:3].upper()}"
                f"-R{round_number}-X{index}"
            ),

            domain=domain,

            hypothesis=draft.hypothesis,

            reason=draft.reason,

            confidence=draft.confidence,
        )

        current.ruled_out.append(
            item
        )

        existing_ruled_text.add(
            normalized
        )

    # --------------------------------------------------------
    # Open questions
    # --------------------------------------------------------

    existing_question_text = {
        _normalize(
            item.question
        )
        for item
        in current.open_questions
    }

    for index, draft in enumerate(
        update.new_open_questions,
        start=1,
    ):

        normalized = _normalize(
            draft.question
        )

        if normalized in existing_question_text:
            continue

        question = OpenQuestion(
            question_id=(
                f"{domain[:3].upper()}"
                f"-R{round_number}-Q{index}"
            ),

            question=draft.question,

            domain=domain,

            availability=draft.availability,

            required_evidence=(
                draft.required_evidence
            ),

            suggested_domain=(
                draft.suggested_domain
            ),
        )

        current.open_questions.append(
            question
        )

        existing_question_text.add(
            normalized
        )

    # --------------------------------------------------------
    # HARD GLOBAL MEMORY LIMITS
    # --------------------------------------------------------

    current.confirmed = (
        current.confirmed[-12:]
    )

    current.ruled_out = (
        current.ruled_out[-8:]
    )

    current.open_questions = (
        current.open_questions[-8:]
    )

    return {
        "evidence_state": current
    }


# ============================================================
# BUILD MAIN GRAPH
# ============================================================


def build_investigation_graph():

    builder = StateGraph(
        InvestigationGraphState
    )

    builder.add_node(
        "intake",
        intake_node,
    )

    builder.add_node(
        "rca",
        rca_node,
    )

    builder.add_node(
        "telemetry",
        telemetry_node,
    )

    builder.add_node(
        "alarms",
        alarms_node,
    )

    builder.add_node(
        "topology",
        topology_node,
    )

    builder.add_node(
        "merge_evidence",
        merge_evidence_node,
    )

    builder.add_edge(
        START,
        "intake",
    )

    builder.add_edge(
        "intake",
        "rca",
    )

    builder.add_conditional_edges(
        "rca",
        route_after_rca,
        {
            "telemetry": "telemetry",
            "alarms": "alarms",
            "topology": "topology",
            "end": END,
        },
    )

    builder.add_edge(
        "telemetry",
        "merge_evidence",
    )

    builder.add_edge(
        "alarms",
        "merge_evidence",
    )

    builder.add_edge(
        "topology",
        "merge_evidence",
    )

    builder.add_edge(
        "merge_evidence",
        "rca",
    )

    checkpointer = (
        InMemorySaver()
    )

    return builder.compile(
        checkpointer=checkpointer
    )


investigation_graph = (
    build_investigation_graph()
)


# ============================================================
# PUBLIC ENTRY POINT
# ============================================================


def run_investigation(
    incident_text: str,
    thread_id: str | None = None,
) -> InvestigationResult:

    thread_id = (
        thread_id
        or uuid4().hex
    )

    result = (
        investigation_graph.invoke(
            {
                "incident_text":
                    incident_text
            },

            config={
                "configurable": {
                    "thread_id":
                        thread_id
                }
            },
        )
    )

    final_rca = result.get(
        "final_rca"
    )

    if not final_rca:

        raise RuntimeError(
            "Investigation ended without "
            "a final RCA."
        )

    return InvestigationResult(
        incident=result[
            "incident"
        ],

        objective=result[
            "objective"
        ],

        rounds_used=result[
            "rounds_used"
        ],

        evidence_state=result[
            "evidence_state"
        ],

        domain_history=result.get(
            "domain_history",
            [],
        ),

        rca_history=result.get(
            "rca_history",
            [],
        ),

        final_rca=final_rca,
    )