from __future__ import annotations

from typing import TypedDict
from uuid import uuid4

from langgraph.graph import (
    END,
    START,
    StateGraph,
)

from agents import (
    build_objective,
    parse_incident,
    run_domain_agent,
    run_rca,
)

from models import (
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

from tools import (
    set_runtime_api_key,
)


MAX_RCA_ROUNDS = 3


# ============================================================
# STATE
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
        value.lower().strip().split()
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
# RCA
# ============================================================


def rca_node(
    state: InvestigationGraphState,
) -> dict:
    decision = run_rca(
        objective=state["objective"],
        evidence_state=state["evidence_state"],
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

    history.append(decision)

    result = {
        "rca_history": history
    }

    if (
        decision.action
        == RCAAction.CONCLUDE
    ):
        result["final_rca"] = decision
        return result

    result["active_request"] = (
        DomainRequest(
            request_id=_request_id(),
            domain=decision.request.domain,
            question=decision.request.question,
        )
    )

    return result


def route_after_rca(
    state: InvestigationGraphState,
) -> str:
    if state.get("final_rca"):
        return "end"

    return state[
        "active_request"
    ].domain


# ============================================================
# SPECIALISTS
# ============================================================


def _specialist_node(
    state: InvestigationGraphState,
    domain: str,
) -> dict:
    request = state[
        "active_request"
    ]

    result = run_domain_agent(
        domain=domain,
        objective=state["objective"],
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

    round_number = (
        state.get(
            "rounds_used",
            0,
        )
        + 1
    )

    history.append(
        {
            "round": round_number,
            "domain": domain,

            "request": request.model_dump(
                mode="json"
            ),

            "tool_calls_used":
                result["tool_calls_used"],

            "tools": [
                item.get("tool")
                for item
                in result["tool_audit"]
            ],

            "tool_audit":
                result["tool_audit"],

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
            round_number,
    }


def telemetry_node(
    state: InvestigationGraphState,
) -> dict:
    return _specialist_node(
        state,
        "telemetry",
    )


def alarms_node(
    state: InvestigationGraphState,
) -> dict:
    return _specialist_node(
        state,
        "alarms",
    )


def topology_node(
    state: InvestigationGraphState,
) -> dict:
    return _specialist_node(
        state,
        "topology",
    )


# ============================================================
# EVIDENCE MERGE
# ============================================================


def merge_evidence_node(
    state: InvestigationGraphState,
) -> dict:
    current = state[
        "evidence_state"
    ].model_copy(
        deep=True
    )

    update = state[
        "latest_update"
    ]

    domain = state[
        "active_request"
    ].domain

    round_number = state[
        "rounds_used"
    ]

    # --------------------------------------------------------
    # RESOLVE QUESTIONS
    # --------------------------------------------------------

    resolved = {
        item
        for item
        in update.resolved_question_ids
        if item
    }

    if resolved:
        current.open_questions = [
            question
            for question
            in current.open_questions
            if question.question_id
            not in resolved
        ]

    # --------------------------------------------------------
    # CONFIRMED
    # --------------------------------------------------------

    existing = {
        _normalize(item.statement)
        for item in current.confirmed
    }

    for index, draft in enumerate(
        update.new_confirmed,
        start=1,
    ):
        normalized = _normalize(
            draft.statement
        )

        if normalized in existing:
            continue

        current.confirmed.append(
            EvidenceFact(
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
        )

        existing.add(normalized)

    # --------------------------------------------------------
    # RULED OUT
    # --------------------------------------------------------

    existing_ruled = {
        _normalize(item.hypothesis)
        for item in current.ruled_out
    }

    for index, draft in enumerate(
        update.new_ruled_out,
        start=1,
    ):
        normalized = _normalize(
            draft.hypothesis
        )

        if normalized in existing_ruled:
            continue

        current.ruled_out.append(
            RuledOutHypothesis(
                hypothesis_id=(
                    f"{domain[:3].upper()}"
                    f"-R{round_number}-X{index}"
                ),
                domain=domain,
                hypothesis=draft.hypothesis,
                reason=draft.reason,
                confidence=draft.confidence,
            )
        )

        existing_ruled.add(normalized)

    # --------------------------------------------------------
    # OPEN QUESTIONS
    #
    # Basic semantic normalization prevents exact/reworded-small
    # duplicates from exploding state.
    # --------------------------------------------------------

    existing_questions = {
        _normalize(item.question)
        for item in current.open_questions
    }

    for index, draft in enumerate(
        update.new_open_questions,
        start=1,
    ):
        normalized = _normalize(
            draft.question
        )

        if normalized in existing_questions:
            continue

        current.open_questions.append(
            OpenQuestion(
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
        )

        existing_questions.add(
            normalized
        )

    # Hard memory bounds.
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
# GRAPH
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
        "merge",
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
        "merge",
    )

    builder.add_edge(
        "alarms",
        "merge",
    )

    builder.add_edge(
        "topology",
        "merge",
    )

    builder.add_edge(
        "merge",
        "rca",
    )

    return builder.compile()


INVESTIGATION_GRAPH = (
    build_investigation_graph()
)


# ============================================================
# PUBLIC API
# ============================================================


def run_investigation(
    *,
    incident_text: str,
    openai_api_key: str,
) -> InvestigationResult:
    if not openai_api_key.strip():
        raise ValueError(
            "OpenAI API key is required."
        )

    # Runtime only.
    # It is never inserted into graph state.
    set_runtime_api_key(
        openai_api_key.strip()
    )

    result = (
        INVESTIGATION_GRAPH.invoke(
            {
                "incident_text":
                    incident_text
            }
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
        incident=result["incident"],
        objective=result["objective"],
        rounds_used=result["rounds_used"],
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