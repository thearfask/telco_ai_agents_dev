from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import TypedDict

from langgraph.graph import (
    END,
    START,
    StateGraph,
)

from agents import (
    parse_incident,
    run_domain_agent,
    run_rca,
)
from config import (
    get_runtime_config,
)
from models import (
    DomainUpdate,
    InvestigationState,
    RCADecision,
)
from runtime import (
    set_runtime_api_key,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]

TRACE_DIR = (
    PROJECT_ROOT
    / "traces"
)


class GraphState(
    TypedDict,
    total=False,
):

    incident_text: str

    investigation: (
        InvestigationState
    )

    rca_decision: (
        RCADecision
    )

    latest_update: (
        DomainUpdate
    )

    trace: list[dict]

    final_result: dict


# ============================================================
# TRACE
# ============================================================


def _trace(
    state: GraphState,
    *,
    stage: str,
    input_data=None,
    output_data=None,
):

    trace = list(
        state.get(
            "trace",
            [],
        )
    )

    def serialize(value):

        if value is None:
            return None

        if hasattr(
            value,
            "model_dump",
        ):
            return value.model_dump(
                exclude_none=True
            )

        return value

    trace.append(
        {
            "timestamp": (
                datetime.now()
                .astimezone()
                .isoformat()
            ),
            "stage": stage,
            "input": serialize(
                input_data
            ),
            "output": serialize(
                output_data
            ),
        }
    )

    return trace


# ============================================================
# NODES
# ============================================================


def parse_node(
    state: GraphState,
):

    incident = parse_incident(
        state[
            "incident_text"
        ]
    )

    investigation = (
        InvestigationState(
            incident=incident
        )
    )

    return {
        "investigation": (
            investigation
        ),
        "trace": _trace(
            state,
            stage=(
                "incident_parser"
            ),
            input_data={
                "raw_incident": (
                    state[
                        "incident_text"
                    ]
                )
            },
            output_data=incident,
        ),
    }


def rca_node(
    state: GraphState,
):

    investigation = (
        state[
            "investigation"
        ]
    )

    decision = run_rca(
        investigation
    )

    if (
        decision.action
        == "request_more"
    ):

        investigation.current_task = (
            decision.request
        )

    return {
        "investigation": (
            investigation
        ),
        "rca_decision": (
            decision
        ),
        "trace": _trace(
            state,
            stage="rca",
            input_data={
                "round": (
                    investigation
                    .rounds_used
                ),
                "compact_state": {
                    "confirmed_fact_count": len(
                        investigation
                        .confirmed_facts
                    ),
                    "verdict_count": len(
                        investigation
                        .hypothesis_verdicts
                    ),
                    "open_question_count": len(
                        investigation
                        .open_questions
                    ),
                    "evidence_gap_count": len(
                        investigation
                        .evidence_gaps
                    ),
                },
            },
            output_data=decision,
        ),
    }


def route_after_rca(
    state: GraphState,
):

    decision = state[
        "rca_decision"
    ]

    if (
        decision.action
        == "conclude"
    ):
        return "finish"

    return "domain"


def domain_node(
    state: GraphState,
):

    investigation = (
        state[
            "investigation"
        ]
    )

    task = (
        investigation
        .current_task
    )

    if not task:
        raise RuntimeError(
            "Domain node called without "
            "a current DomainTask."
        )

    update, tool_trace = (
        run_domain_agent(
            state=investigation,
            task=task,
        )
    )

    trace = _trace(
        state,
        stage=(
            f"{task.domain}_specialist"
        ),
        input_data={
            "task": (
                task.model_dump()
            )
        },
        output_data={
            "domain_update": (
                update.model_dump()
            ),
            "tool_trace": (
                tool_trace
            ),
        },
    )

    return {
        "latest_update": (
            update
        ),
        "trace": trace,
    }


def apply_update_node(
    state: GraphState,
):

    investigation = (
        state[
            "investigation"
        ]
    )

    update = state[
        "latest_update"
    ]

    # Facts
    existing_fact_ids = {
        item.fact_id
        for item
        in investigation
        .confirmed_facts
    }

    for fact in (
        update.confirmed
    ):

        if (
            fact.fact_id
            not in existing_fact_ids
        ):
            investigation.confirmed_facts.append(
                fact
            )

    # Verdicts
    for verdict in (
        update.verdicts
    ):

        investigation.hypothesis_verdicts = [
            existing
            for existing
            in investigation
            .hypothesis_verdicts
            if (
                existing.hypothesis_id
                != verdict.hypothesis_id
            )
        ]

        investigation.hypothesis_verdicts.append(
            verdict
        )

    # Open questions — keep unique by question text.
    existing_questions = {
        item.question
        for item
        in investigation
        .open_questions
    }

    for question in (
        update.open_questions
    ):

        if (
            question.question
            not in existing_questions
        ):
            investigation.open_questions.append(
                question
            )

    # Evidence gaps
    existing_gaps = {
        item.missing_evidence
        for item
        in investigation
        .evidence_gaps
    }

    for gap in (
        update.evidence_gaps
    ):

        if (
            gap.missing_evidence
            not in existing_gaps
        ):
            investigation.evidence_gaps.append(
                gap
            )

    investigation.rounds_used += 1

    investigation.current_task = None

    return {
        "investigation": (
            investigation
        ),
        "trace": _trace(
            state,
            stage=(
                "blackboard_update"
            ),
            input_data=update,
            output_data={
                "confirmed_fact_count": len(
                    investigation
                    .confirmed_facts
                ),
                "verdict_count": len(
                    investigation
                    .hypothesis_verdicts
                ),
                "open_question_count": len(
                    investigation
                    .open_questions
                ),
                "evidence_gap_count": len(
                    investigation
                    .evidence_gaps
                ),
                "rounds_used": (
                    investigation
                    .rounds_used
                ),
            },
        ),
    }


def finish_node(
    state: GraphState,
):

    decision = (
        state[
            "rca_decision"
        ]
    )

    investigation = (
        state[
            "investigation"
        ]
    )

    result = {
        "incident": (
            investigation
            .incident
            .model_dump(
                exclude_none=True
            )
        ),
        "rounds_used": (
            investigation
            .rounds_used
        ),
        "confirmed_facts": [
            item.model_dump()
            for item
            in investigation
            .confirmed_facts
        ],
        "hypothesis_verdicts": [
            item.model_dump()
            for item
            in investigation
            .hypothesis_verdicts
        ],
        "open_questions": [
            item.model_dump()
            for item
            in investigation
            .open_questions
        ],
        "evidence_gaps": [
            item.model_dump()
            for item
            in investigation
            .evidence_gaps
        ],
        "final_rca": (
            decision.model_dump(
                exclude_none=True
            )
        ),
    }

    return {
        "final_result": result,
        "trace": _trace(
            state,
            stage="finish",
            output_data=result,
        ),
    }


# ============================================================
# GRAPH
# ============================================================


def build_graph():

    builder = StateGraph(
        GraphState
    )

    builder.add_node(
        "parse",
        parse_node,
    )

    builder.add_node(
        "rca",
        rca_node,
    )

    builder.add_node(
        "domain",
        domain_node,
    )

    builder.add_node(
        "apply_update",
        apply_update_node,
    )

    builder.add_node(
        "finish",
        finish_node,
    )

    builder.add_edge(
        START,
        "parse",
    )

    builder.add_edge(
        "parse",
        "rca",
    )

    builder.add_conditional_edges(
        "rca",
        route_after_rca,
        {
            "domain": (
                "domain"
            ),
            "finish": (
                "finish"
            ),
        },
    )

    builder.add_edge(
        "domain",
        "apply_update",
    )

    builder.add_edge(
        "apply_update",
        "rca",
    )

    builder.add_edge(
        "finish",
        END,
    )

    return builder.compile()


GRAPH = build_graph()


# ============================================================
# PUBLIC API
# ============================================================


def run_investigation(
    *,
    incident_text: str,
    api_key: str,
):

    set_runtime_api_key(
        api_key
    )

    result = GRAPH.invoke(
        {
            "incident_text": (
                incident_text
            ),
            "trace": [],
        }
    )

    if (
        get_runtime_config().get(
            "save_traces",
            True,
        )
    ):

        TRACE_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        incident_id = (
            result[
                "investigation"
            ]
            .incident
            .incident_id
            or "UNKNOWN"
        )

        timestamp = (
            datetime.now()
            .strftime(
                "%Y%m%d_%H%M%S"
            )
        )

        path = (
            TRACE_DIR
            / (
                f"{incident_id}_"
                f"{timestamp}.json"
            )
        )

        with path.open(
            "w",
            encoding="utf-8",
        ) as handle:

            json.dump(
                {
                    "final_result": (
                        result.get(
                            "final_result"
                        )
                    ),
                    "trace": (
                        result.get(
                            "trace",
                            [],
                        )
                    ),
                },
                handle,
                indent=2,
                default=str,
            )

        result[
            "trace_file"
        ] = str(
            path
        )

    return result