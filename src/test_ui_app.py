from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import streamlit as st
from pydantic import BaseModel

from intelligence import (
    find_diagnostic_patterns,
    get_mandatory_agent_context,
    resolve_metric_context,
    search_runbooks,
)
from llm import get_llm
from prompts import SQL_PLANNER_PROMPT
from runtime import set_runtime_api_key
from tools import (
    SQL_TABLES,
    execute_sql,
    get_schema,
    validate_required_scope,
    validate_sql,
    validate_with_duckdb,
)


# ============================================================
# PATHS
# ============================================================


PROJECT_ROOT = Path(__file__).resolve().parents[1]

TRACE_DIR = PROJECT_ROOT / "traces"


# ============================================================
# TRACE
# ============================================================


class InvestigationTrace:
    """
    Simple development trace.

    Stores the complete input/output of each stage so that the
    investigation can be inspected after execution.

    IMPORTANT:
    Never place credentials in this object.
    """

    def __init__(
        self,
        raw_incident: str,
    ):
        self.incident_id = "UNKNOWN"

        self.started_at = (
            datetime.now()
            .astimezone()
            .isoformat()
        )

        self.raw_incident = raw_incident

        self.stages: list[
            dict[str, Any]
        ] = []

    def set_incident_id(
        self,
        incident_id: str | None,
    ) -> None:
        if incident_id:
            self.incident_id = (
                incident_id
            )

    def add_stage(
        self,
        *,
        stage: str,
        agent: str,
        input_data: Any = None,
        output_data: Any = None,
        metadata: dict | None = None,
    ) -> None:

        self.stages.append(
            {
                "stage": stage,
                "agent": agent,
                "timestamp": (
                    datetime.now()
                    .astimezone()
                    .isoformat()
                ),
                "input": self._serialize(
                    input_data
                ),
                "output": self._serialize(
                    output_data
                ),
                "metadata": (
                    metadata or {}
                ),
            }
        )

    def add_failure(
        self,
        *,
        stage: str,
        agent: str,
        input_data: Any,
        error: Exception,
    ) -> None:

        self.add_stage(
            stage=stage,
            agent=agent,
            input_data=input_data,
            output_data={
                "status": "failed",
                "error_type": (
                    type(error).__name__
                ),
                "error": str(error),
            },
        )

    def save(
        self,
    ) -> Path:

        TRACE_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        timestamp = (
            datetime.now()
            .strftime(
                "%Y%m%d_%H%M%S"
            )
        )

        safe_incident_id = (
            self.incident_id
            .replace("/", "_")
            .replace("\\", "_")
            .replace(" ", "_")
        )

        path = (
            TRACE_DIR
            / (
                f"{safe_incident_id}_"
                f"{timestamp}.json"
            )
        )

        payload = {
            "incident_id": (
                self.incident_id
            ),
            "started_at": (
                self.started_at
            ),
            "completed_at": (
                datetime.now()
                .astimezone()
                .isoformat()
            ),
            "raw_incident": (
                self.raw_incident
            ),
            "stage_count": len(
                self.stages
            ),
            "stages": (
                self.stages
            ),
        }

        with path.open(
            "w",
            encoding="utf-8",
        ) as handle:

            json.dump(
                payload,
                handle,
                indent=2,
                ensure_ascii=False,
                default=str,
            )

        return path

    @staticmethod
    def _serialize(
        value: Any,
    ) -> Any:

        if value is None:
            return None

        if hasattr(
            value,
            "model_dump",
        ):
            return value.model_dump(
                exclude_none=True
            )

        if isinstance(
            value,
            dict,
        ):
            return {
                str(key): (
                    InvestigationTrace
                    ._serialize(item)
                )
                for key, item
                in value.items()
            }

        if isinstance(
            value,
            (list, tuple),
        ):
            return [
                InvestigationTrace
                ._serialize(item)
                for item in value
            ]

        if isinstance(
            value,
            (
                str,
                int,
                float,
                bool,
            ),
        ):
            return value

        return str(value)


# ============================================================
# GENERAL UTILITIES
# ============================================================


def compact_json(
    value: Any,
) -> str:

    return json.dumps(
        InvestigationTrace._serialize(
            value
        ),
        ensure_ascii=False,
        default=str,
        separators=(",", ":"),
    )


def estimate_tokens(
    text: str,
) -> int:
    """
    Rough development estimate only.

    This is NOT an OpenAI billing token count.
    """

    if not text:
        return 0

    return max(
        1,
        round(
            len(text) / 4
        ),
    )


def show_context_block(
    title: str,
    content: str,
) -> None:

    st.markdown(
        f"**{title}**"
    )

    st.caption(
        "Approximate context size: "
        f"{estimate_tokens(content):,} tokens"
    )

    st.code(
        content,
        language=None,
    )


def show_json(
    title: str,
    value: Any,
) -> None:

    st.markdown(
        f"**{title}**"
    )

    st.json(
        InvestigationTrace._serialize(
            value
        )
    )


def save_failed_trace(
    trace: InvestigationTrace,
) -> None:

    try:
        path = trace.save()

        st.warning(
            f"Partial trace saved to: {path}"
        )

    except Exception as trace_error:

        st.warning(
            "The investigation failed and the "
            "trace could not be saved."
        )

        st.exception(
            trace_error
        )


# ============================================================
# TELEMETRY TOOL DESCRIPTIONS
# ============================================================


TELEMETRY_TOOL_DESCRIPTIONS = """
You have the following telemetry-domain capabilities.

1. telemetry_patterns

Purpose:
Retrieve curated diagnostic hypotheses and evidence relationships.

Use when:
- multiple technical mechanisms could explain the incident;
- you need supporting and contradicting evidence;
- you need to determine what evidence discriminates hypotheses.

Knowledge only.
It does not provide incident evidence.


2. telemetry_metrics

Purpose:
Resolve engineering concepts into telemetry metrics and metric
semantics.

Use when:
- you know the evidence concept but not the exact metric;
- you need trusted metric meaning;
- you need to avoid inventing metric names.

Knowledge only.
It does not provide incident evidence.


3. telemetry_runbook

Purpose:
Retrieve deeper engineering troubleshooting methodology.

Use when:
- the investigation is complex;
- procedural guidance would materially improve the investigation.

Knowledge only.
Do not use automatically.


4. telemetry_sql

Purpose:
Retrieve actual operational telemetry evidence from DuckDB.

Use when:
- you know what evidence is required;
- actual KPI values, distributions, timestamps, samples or
  comparisons are required.

This is an operational evidence tool.


5. telemetry_schema

Purpose:
Inspect the currently available telemetry schema.

Use when:
- table or field availability is genuinely uncertain.

Do not use SQL to rediscover known schema.
"""


# ============================================================
# STAGE 1
# INCIDENT UNDERSTANDING
# ============================================================


class IncidentTrace(BaseModel):

    incident_id: str | None = None

    problem_statement: str

    investigation_goal: str

    symptoms: list[str]

    window_ids: list[str]

    explicit_hypotheses: list[str]

    constraints: list[str]

    missing_context: list[str]


INCIDENT_SYSTEM_PROMPT = """
You are parsing a telecom incident for a telemetry investigation.

Do not investigate the incident.

Extract only what the incident explicitly says or clearly requires.

Do not invent:
- KPI values;
- timestamps;
- network elements;
- root causes;
- data availability.

Preserve the difference between:
- reported symptoms;
- proposed hypotheses;
- investigation constraints.

Keep the structured output concise.
"""


def parse_incident(
    incident_text: str,
):

    structured_model = (
        get_llm(
            "incident_parser"
        )
        .with_structured_output(
            IncidentTrace,
            method="json_schema",
        )
    )

    user_prompt = f"""
INCIDENT|

{incident_text}
"""

    result = (
        structured_model.invoke(
            [
                (
                    "system",
                    INCIDENT_SYSTEM_PROMPT,
                ),
                (
                    "user",
                    user_prompt,
                ),
            ]
        )
    )

    return (
        INCIDENT_SYSTEM_PROMPT,
        user_prompt,
        result,
    )


# ============================================================
# STAGE 2
# TELEMETRY INVESTIGATION PLANNER
# ============================================================


ToolName = Literal[
    "telemetry_patterns",
    "telemetry_metrics",
    "telemetry_runbook",
    "telemetry_sql",
    "telemetry_schema",
]


class HypothesisPlan(BaseModel):

    hypothesis: str

    evidence_needed: list[str]


class TelemetryPlan(BaseModel):

    incident_intent: str

    intent_clarity: Literal[
        "clear",
        "partially_clear",
        "unclear",
    ]

    hypotheses: list[
        HypothesisPlan
    ]

    recommended_sequence: list[
        ToolName
    ]

    metric_concepts: list[str]

    diagnostic_pattern_query: (
        str | None
    ) = None

    runbook_query: (
        str | None
    ) = None

    analysis_granularity: Literal[
        "native",
        "sample",
        "second",
        "minute",
        "window_summary",
        "determine_from_data",
    ]

    evidence_goal: str


TELEMETRY_PLANNER_SYSTEM = """
You are a senior Telemetry Domain Engineer.

Your job is to design the smallest useful telemetry investigation.

Do not determine the root cause yet.

WORKFLOW:

1. Understand the incident.
2. Identify plausible telemetry mechanisms.
3. Identify evidence that would distinguish them.
4. Determine which engineering concepts need metric resolution.
5. Choose the smallest useful tool sequence.
6. Choose analysis granularity appropriate to the measurement data.
7. Define the focused operational evidence goal.

IMPORTANT:

Do not mechanically use minute or 5-minute buckets.

For short/high-frequency telemetry windows, preserve native or
sample-level behavior unless aggregation is justified.

Do not assume correlation proves causation.

Do not invent unavailable metrics.

Do not perform SQL in this stage.

Do not claim that any hypothesis is supported until operational
evidence exists.

OUTPUT DISCIPLINE:

- maximum 5 hypotheses;
- maximum 4 evidence items per hypothesis;
- maximum 5 metric concepts;
- maximum 4 tools in recommended_sequence;
- keep evidence_goal concise;
- do not repeat the full incident.
"""


def build_telemetry_plan(
    incident: IncidentTrace,
):

    mandatory_context = (
        get_mandatory_agent_context(
            "telemetry"
        )
    )

    user_prompt = f"""
INCIDENT CONTEXT|

{incident.model_dump_json(exclude_none=True)}

MANDATORY POLICY AND EVIDENCE RULES|

{compact_json(mandatory_context)}

AVAILABLE TELEMETRY TOOLS|

{TELEMETRY_TOOL_DESCRIPTIONS}

Create the telemetry investigation plan.

Do not execute a tool.
"""

    structured_model = (
        get_llm(
            "telemetry"
        )
        .with_structured_output(
            TelemetryPlan,
            method="json_schema",
        )
    )

    result = (
        structured_model.invoke(
            [
                (
                    "system",
                    TELEMETRY_PLANNER_SYSTEM,
                ),
                (
                    "user",
                    user_prompt,
                ),
            ]
        )
    )

    return (
        TELEMETRY_PLANNER_SYSTEM,
        user_prompt,
        mandatory_context,
        result,
    )


# ============================================================
# STAGE 3
# DOMAIN INTELLIGENCE RETRIEVAL
# ============================================================


def retrieve_intelligence(
    plan: TelemetryPlan,
) -> dict[str, Any]:

    result: dict[
        str,
        Any,
    ] = {}

    sequence = set(
        plan.recommended_sequence
    )

    # --------------------------------------------------------
    # DIAGNOSTIC PATTERNS
    # --------------------------------------------------------

    if (
        "telemetry_patterns"
        in sequence
        and plan.diagnostic_pattern_query
    ):

        tool_input = {
            "query": (
                plan.diagnostic_pattern_query
            ),
            "domain": "telemetry",
            "top_k": 4,
        }

        tool_output = (
            find_diagnostic_patterns(
                query=(
                    plan.diagnostic_pattern_query
                ),
                domain="telemetry",
                top_k=4,
            )
        )

        result[
            "telemetry_patterns"
        ] = {
            "input": tool_input,
            "output": tool_output,
        }

    # --------------------------------------------------------
    # METRIC CATALOG
    # --------------------------------------------------------

    if (
        "telemetry_metrics"
        in sequence
        and plan.metric_concepts
    ):

        tool_input = {
            "concepts": (
                plan.metric_concepts
            )
        }

        tool_output = (
            resolve_metric_context(
                concepts=(
                    plan.metric_concepts
                )
            )
        )

        result[
            "telemetry_metrics"
        ] = {
            "input": tool_input,
            "output": tool_output,
        }

    # --------------------------------------------------------
    # RUNBOOK
    # --------------------------------------------------------

    if (
        "telemetry_runbook"
        in sequence
        and plan.runbook_query
    ):

        tool_input = {
            "query": (
                plan.runbook_query
            ),
            "domain": "telemetry",
            "top_k": 3,
        }

        tool_output = (
            search_runbooks(
                query=(
                    plan.runbook_query
                ),
                domain="telemetry",
                top_k=3,
            )
        )

        result[
            "telemetry_runbook"
        ] = {
            "input": tool_input,
            "output": tool_output,
        }

    return result


# ============================================================
# STAGE 4
# SQL GENERATION
# ============================================================


class SQLPlan(BaseModel):

    can_answer: bool

    sql: str | None = None

    reason: str | None = None


SQL_TRACE_RULES = """
SQL ENGINEERING RULES|

Generate one focused DuckDB SELECT query.

Use only the supplied schema.

Use only columns that exist.

Preserve explicit window_id scope.

When querying telemetry_measurements for a named window, filter
telemetry_measurements.window_id directly.

Do not use information_schema.

Do not use SQL for schema discovery.

Do not manufacture throughput from TX_Bytes or RX_Bytes unless their
counter/time semantics are explicitly established.

Do not manufacture packet loss or retransmission counters.

Do not create coarse temporal buckets unless the investigation plan
requires them.

For short/high-frequency telemetry windows, prefer sample_index and
event_timestamp so temporal behavior is not destroyed.

Prefer simple SQL.

Do not try to perform the entire RCA in one SQL statement.

If the schema cannot answer the focused evidence request, return
can_answer=false with the precise reason.
"""


def build_sql_context(
    *,
    incident: IncidentTrace,
    plan: TelemetryPlan,
    intelligence_trace: dict,
    schema: str,
) -> str:

    intelligence_context = {
        name: item[
            "output"
        ]
        for name, item
        in intelligence_trace.items()
    }

    return f"""
{SQL_PLANNER_PROMPT}

{SQL_TRACE_RULES}

INCIDENT|

{incident.model_dump_json(exclude_none=True)}

TELEMETRY INVESTIGATION PLAN|

{plan.model_dump_json(exclude_none=True)}

RETRIEVED DOMAIN INTELLIGENCE|

{compact_json(intelligence_context)}

DATABASE SCHEMA|

{schema}

FOCUSED OPERATIONAL EVIDENCE GOAL|

{plan.evidence_goal}
"""


def generate_sql_trace(
    *,
    incident: IncidentTrace,
    plan: TelemetryPlan,
    intelligence_trace: dict,
):

    schema = get_schema(
        SQL_TABLES
    )

    sql_prompt = (
        build_sql_context(
            incident=incident,
            plan=plan,
            intelligence_trace=(
                intelligence_trace
            ),
            schema=schema,
        )
    )

    structured_model = (
        get_llm(
            "sql"
        )
        .with_structured_output(
            SQLPlan,
            method="json_schema",
        )
    )

    result = (
        structured_model.invoke(
            sql_prompt
        )
    )

    return (
        schema,
        sql_prompt,
        result,
    )


# ============================================================
# STAGE 5
# SQL VALIDATION + EXECUTION
# ============================================================


def execute_generated_sql(
    *,
    sql_plan: SQLPlan,
    incident: IncidentTrace,
) -> dict[str, Any]:

    if not sql_plan.can_answer:

        return {
            "status": "unsupported",
            "reason": (
                sql_plan.reason
            ),
        }

    if not sql_plan.sql:

        return {
            "status": "failed",
            "stage": "generation",
            "reason": (
                "SQL planner returned no SQL."
            ),
        }

    raw_sql = sql_plan.sql

    trace: dict[
        str,
        Any,
    ] = {
        "status": "pending",
        "raw_sql": raw_sql,
    }

    # --------------------------------------------------------
    # SQLGLOT
    # --------------------------------------------------------

    try:

        validated_sql = (
            validate_sql(
                sql=raw_sql,
                allowed_tables=(
                    SQL_TABLES
                ),
            )
        )

        trace[
            "sqlglot_validated_sql"
        ] = validated_sql

    except Exception as exc:

        trace[
            "status"
        ] = "failed"

        trace[
            "stage"
        ] = "sqlglot_validation"

        trace[
            "error_type"
        ] = type(exc).__name__

        trace[
            "error"
        ] = str(exc)

        return trace

    # --------------------------------------------------------
    # SCOPE VALIDATION
    # --------------------------------------------------------

    scope_question = (
        " ".join(
            incident.window_ids
        )
    )

    try:

        validate_required_scope(
            sql=validated_sql,
            question=scope_question,
        )

        trace[
            "scope_validation"
        ] = "passed"

    except Exception as exc:

        trace[
            "status"
        ] = "failed"

        trace[
            "stage"
        ] = "scope_validation"

        trace[
            "error_type"
        ] = type(exc).__name__

        trace[
            "error"
        ] = str(exc)

        return trace

    # --------------------------------------------------------
    # DUCKDB EXPLAIN
    # --------------------------------------------------------

    try:

        validate_with_duckdb(
            validated_sql
        )

        trace[
            "duckdb_explain"
        ] = "passed"

    except Exception as exc:

        trace[
            "status"
        ] = "failed"

        trace[
            "stage"
        ] = "duckdb_explain"

        trace[
            "error_type"
        ] = type(exc).__name__

        trace[
            "error"
        ] = str(exc)

        return trace

    # --------------------------------------------------------
    # EXECUTION
    # --------------------------------------------------------

    try:

        result = execute_sql(
            validated_sql
        )

    except Exception as exc:

        trace[
            "status"
        ] = "failed"

        trace[
            "stage"
        ] = "execution"

        trace[
            "error_type"
        ] = type(exc).__name__

        trace[
            "error"
        ] = str(exc)

        return trace

    trace[
        "status"
    ] = "completed"

    trace[
        "result"
    ] = result

    return trace


# ============================================================
# STAGE 6
# TELEMETRY FINAL ASSESSMENT
# ============================================================


class HypothesisAssessment(
    BaseModel
):

    hypothesis: str

    status: Literal[
        "supported",
        "contradicted",
        "inconclusive",
        "not_testable",
    ]

    evidence: list[str]


class TelemetryTraceOutput(
    BaseModel
):

    confirmed_observations: (
        list[str]
    )

    hypothesis_assessments: (
        list[
            HypothesisAssessment
        ]
    )

    evidence_gaps: list[str]

    context_quality_issues: (
        list[str]
    )

    next_best_action: (
        str | None
    ) = None

    summary: str


TELEMETRY_FINALIZER_SYSTEM = """
You are a senior Telemetry Domain Engineer reviewing one investigation
trace.

Distinguish carefully between:

1. incident statements;
2. engineering/domain knowledge;
3. operational observations;
4. engineering inference.

Only executed operational evidence may be reported as a confirmed
observation.

Diagnostic patterns, metric catalogs, runbooks and policies are
knowledge. They are not incident proof.

Classify each hypothesis as:

SUPPORTED
CONTRADICTED
INCONCLUSIVE
NOT_TESTABLE

Do not claim physical root cause unless operational evidence
establishes it.

Also inspect the quality of the context supplied to you.

Identify if:

- the investigation request was ambiguous;
- required measurement context was missing;
- temporal granularity was inappropriate;
- schema information was missing;
- tool requests were unnecessarily broad;
- SQL requested evidence unavailable from the schema;
- knowledge was mistaken for operational evidence;
- important incident context was lost between stages.

Keep the output concise.
"""


def build_finalizer_prompt(
    *,
    incident: IncidentTrace,
    plan: TelemetryPlan,
    mandatory_context: dict,
    intelligence_trace: dict,
    sql_plan: SQLPlan,
    sql_execution: dict,
) -> str:

    intelligence_outputs = {
        key: value[
            "output"
        ]
        for key, value
        in intelligence_trace.items()
    }

    return f"""
INCIDENT|

{incident.model_dump_json(exclude_none=True)}

MANDATORY POLICY / EVIDENCE RULES|

{compact_json(mandatory_context)}

TELEMETRY PLAN|

{plan.model_dump_json(exclude_none=True)}

DOMAIN KNOWLEDGE RETRIEVED|

{compact_json(intelligence_outputs)}

SQL PLANNER OUTPUT|

{sql_plan.model_dump_json(exclude_none=True)}

OPERATIONAL SQL EXECUTION RESULT|

{compact_json(sql_execution)}

Generate the telemetry assessment.

Do not add facts absent from the operational evidence.
"""


def finalize_trace(
    *,
    incident: IncidentTrace,
    plan: TelemetryPlan,
    mandatory_context: dict,
    intelligence_trace: dict,
    sql_plan: SQLPlan,
    sql_execution: dict,
):

    user_prompt = (
        build_finalizer_prompt(
            incident=incident,
            plan=plan,
            mandatory_context=(
                mandatory_context
            ),
            intelligence_trace=(
                intelligence_trace
            ),
            sql_plan=sql_plan,
            sql_execution=(
                sql_execution
            ),
        )
    )

    structured_model = (
        get_llm(
            "telemetry"
        )
        .with_structured_output(
            TelemetryTraceOutput,
            method="json_schema",
        )
    )

    result = (
        structured_model.invoke(
            [
                (
                    "system",
                    TELEMETRY_FINALIZER_SYSTEM,
                ),
                (
                    "user",
                    user_prompt,
                ),
            ]
        )
    )

    return (
        TELEMETRY_FINALIZER_SYSTEM,
        user_prompt,
        result,
    )


# ============================================================
# STREAMLIT UI
# ============================================================


st.set_page_config(
    page_title=(
        "Telemetry Context Trace Lab"
    ),
    page_icon="🔬",
    layout="wide",
)


st.title(
    "Telemetry Context Trace Lab"
)

st.caption(
    "Trace every telemetry investigation stage. "
    "The complete input/output trace is written to one JSON file."
)


# ============================================================
# SIDEBAR
# ============================================================


with st.sidebar:

    st.header(
        "Runtime"
    )

    api_key = st.text_input(
        "OpenAI API Key",
        type="password",
        placeholder="sk-...",
    )

    execute_sql_toggle = (
        st.checkbox(
            "Execute generated SQL",
            value=True,
        )
    )

    st.divider()

    st.markdown(
        """
### Trace

The generated JSON contains:

- raw incident;
- incident-parser context;
- incident-parser output;
- telemetry-planner context;
- telemetry plan;
- intelligence retrieval queries;
- intelligence retrieval results;
- SQL-planner context;
- generated SQL;
- SQLGlot validation;
- DuckDB validation;
- DuckDB result;
- telemetry-finalizer context;
- final telemetry assessment;
- failures, if any.

The API key is never written to the trace.
"""
    )


# ============================================================
# DEFAULT INCIDENT
# ============================================================


default_incident = """INC-COMPLEX-001

Users report intermittent uplink performance degradation during WIN-000037.

The degradation is not continuous. Upload performance appears to drop sharply for short periods and then recover.

Initial monitoring suggests:
- UL_BLER may increase during some degraded periods.
- UL_SNR may fluctuate, but it is unclear whether signal quality consistently explains the degradation.
- UL_MCS appears unstable.
- Uplink PRB utilization may increase during parts of the window.
- Buffer buildup may also be occurring.

Determine whether the telemetry evidence is more consistent with:

1. poor uplink signal quality,
2. uplink radio reliability degradation,
3. uplink resource congestion,
4. buffering or traffic-pressure effects,
5. interaction between multiple mechanisms,
6. or another telemetry mechanism.

Do not assume that correlation between two metrics proves causation.

Identify evidence that would support or contradict the competing mechanisms, and determine what telemetry should be examined to distinguish them.

If the available telemetry cannot distinguish the mechanisms, clearly identify the evidence gap rather than forcing a conclusion.
"""


incident_text = (
    st.text_area(
        "Incident",
        value=default_incident,
        height=420,
    )
)


run = st.button(
    "Run Context Trace",
    type="primary",
    use_container_width=True,
)


# ============================================================
# EXECUTION
# ============================================================


if run:

    if not api_key.strip():

        st.error(
            "Enter an OpenAI API key."
        )

        st.stop()

    if not incident_text.strip():

        st.error(
            "Enter an incident."
        )

        st.stop()

    # --------------------------------------------------------
    # Runtime secret
    # --------------------------------------------------------

    set_runtime_api_key(
        api_key.strip()
    )

    # --------------------------------------------------------
    # Initialize trace
    # --------------------------------------------------------

    trace = InvestigationTrace(
        raw_incident=(
            incident_text.strip()
        )
    )

    # ========================================================
    # STAGE 1
    # ========================================================

    st.header(
        "Stage 1 — Incident Parser"
    )

    try:

        (
            parser_system,
            parser_user,
            incident,
        ) = parse_incident(
            incident_text.strip()
        )

        trace.set_incident_id(
            incident.incident_id
        )

        trace.add_stage(
            stage=(
                "01_incident_parser"
            ),
            agent=(
                "incident_parser"
            ),
            input_data={
                "model_profile": (
                    "incident_parser"
                ),
                "system_prompt": (
                    parser_system
                ),
                "user_prompt": (
                    parser_user
                ),
                "raw_incident": (
                    incident_text.strip()
                ),
            },
            output_data=incident,
            metadata={
                "estimated_input_tokens": (
                    estimate_tokens(
                        parser_system
                        + parser_user
                    )
                )
            },
        )

    except Exception as exc:

        trace.add_failure(
            stage=(
                "01_incident_parser"
            ),
            agent=(
                "incident_parser"
            ),
            input_data={
                "model_profile": (
                    "incident_parser"
                ),
                "system_prompt": (
                    INCIDENT_SYSTEM_PROMPT
                ),
                "raw_incident": (
                    incident_text.strip()
                ),
            },
            error=exc,
        )

        st.error(
            "Incident parser failed."
        )

        st.exception(
            exc
        )

        save_failed_trace(
            trace
        )

        st.stop()

    with st.expander(
        "INPUT — Incident Parser"
    ):

        show_context_block(
            "System Prompt",
            parser_system,
        )

        show_context_block(
            "User Prompt",
            parser_user,
        )

    show_json(
        "OUTPUT — Incident Parser",
        incident,
    )

    # ========================================================
    # STAGE 2
    # ========================================================

    st.header(
        "Stage 2 — Telemetry Planner"
    )

    try:

        (
            planner_system,
            planner_user,
            mandatory_context,
            plan,
        ) = build_telemetry_plan(
            incident
        )

        trace.add_stage(
            stage=(
                "02_telemetry_planner"
            ),
            agent="telemetry",
            input_data={
                "model_profile": (
                    "telemetry"
                ),
                "system_prompt": (
                    planner_system
                ),
                "user_prompt": (
                    planner_user
                ),
                "parsed_incident": (
                    incident
                ),
                "mandatory_context": (
                    mandatory_context
                ),
                "available_tools": (
                    TELEMETRY_TOOL_DESCRIPTIONS
                ),
            },
            output_data=plan,
            metadata={
                "estimated_input_tokens": (
                    estimate_tokens(
                        planner_system
                        + planner_user
                    )
                )
            },
        )

    except Exception as exc:

        trace.add_failure(
            stage=(
                "02_telemetry_planner"
            ),
            agent="telemetry",
            input_data={
                "model_profile": (
                    "telemetry"
                ),
                "system_prompt": (
                    TELEMETRY_PLANNER_SYSTEM
                ),
                "parsed_incident": (
                    incident
                ),
            },
            error=exc,
        )

        st.error(
            "Telemetry planner failed."
        )

        st.exception(
            exc
        )

        save_failed_trace(
            trace
        )

        st.stop()

    with st.expander(
        "INPUT — Telemetry Planner",
        expanded=True,
    ):

        show_context_block(
            "System Prompt",
            planner_system,
        )

        show_context_block(
            "User Prompt",
            planner_user,
        )

    show_json(
        "OUTPUT — Telemetry Planner",
        plan,
    )

    st.info(
        "Recommended sequence: "
        + " → ".join(
            plan.recommended_sequence
        )
    )

    # ========================================================
    # STAGE 3
    # ========================================================

    st.header(
        "Stage 3 — Domain Intelligence"
    )

    try:

        intelligence_trace = (
            retrieve_intelligence(
                plan
            )
        )

    except Exception as exc:

        trace.add_failure(
            stage=(
                "03_domain_intelligence"
            ),
            agent=(
                "telemetry_intelligence"
            ),
            input_data={
                "telemetry_plan": (
                    plan
                )
            },
            error=exc,
        )

        st.error(
            "Domain intelligence retrieval failed."
        )

        st.exception(
            exc
        )

        save_failed_trace(
            trace
        )

        st.stop()

    if not intelligence_trace:

        trace.add_stage(
            stage=(
                "03_domain_intelligence"
            ),
            agent=(
                "telemetry_intelligence"
            ),
            input_data={
                "recommended_sequence": (
                    plan.recommended_sequence
                )
            },
            output_data={
                "status": (
                    "no_retrieval_selected"
                )
            },
        )

        st.info(
            "No domain-intelligence retrieval selected."
        )

    else:

        for (
            tool_name,
            tool_data,
        ) in intelligence_trace.items():

            trace.add_stage(
                stage=(
                    f"03_{tool_name}"
                ),
                agent=tool_name,
                input_data=(
                    tool_data[
                        "input"
                    ]
                ),
                output_data=(
                    tool_data[
                        "output"
                    ]
                ),
            )

            with st.expander(
                tool_name,
                expanded=True,
            ):

                show_json(
                    "INPUT",
                    tool_data[
                        "input"
                    ],
                )

                show_json(
                    "OUTPUT",
                    tool_data[
                        "output"
                    ],
                )

    # ========================================================
    # STAGE 4
    # ========================================================

    st.header(
        "Stage 4 — SQL Planner"
    )

    try:

        (
            schema,
            sql_prompt,
            sql_plan,
        ) = generate_sql_trace(
            incident=incident,
            plan=plan,
            intelligence_trace=(
                intelligence_trace
            ),
        )

        trace.add_stage(
            stage=(
                "04_sql_planner"
            ),
            agent="sql",
            input_data={
                "model_profile": "sql",
                "schema": schema,
                "full_prompt": (
                    sql_prompt
                ),
                "parsed_incident": (
                    incident
                ),
                "telemetry_plan": (
                    plan
                ),
                "retrieved_intelligence": (
                    intelligence_trace
                ),
            },
            output_data=(
                sql_plan
            ),
            metadata={
                "estimated_input_tokens": (
                    estimate_tokens(
                        sql_prompt
                    )
                )
            },
        )

    except Exception as exc:

        trace.add_failure(
            stage=(
                "04_sql_planner"
            ),
            agent="sql",
            input_data={
                "model_profile": "sql",
                "parsed_incident": (
                    incident
                ),
                "telemetry_plan": (
                    plan
                ),
                "retrieved_intelligence": (
                    intelligence_trace
                ),
            },
            error=exc,
        )

        st.error(
            "SQL planner failed."
        )

        st.exception(
            exc
        )

        save_failed_trace(
            trace
        )

        st.stop()

    with st.expander(
        "INPUT — SQL Planner",
        expanded=True,
    ):

        show_context_block(
            "Full SQL Planner Context",
            sql_prompt,
        )

    show_json(
        "OUTPUT — SQL Planner",
        sql_plan,
    )

    if sql_plan.sql:

        st.markdown(
            "**Generated SQL**"
        )

        st.code(
            sql_plan.sql,
            language="sql",
        )

    # ========================================================
    # STAGE 5
    # ========================================================

    st.header(
        "Stage 5 — SQL Validation / DuckDB"
    )

    if execute_sql_toggle:

        sql_execution = (
            execute_generated_sql(
                sql_plan=sql_plan,
                incident=incident,
            )
        )

    else:

        sql_execution = {
            "status": (
                "execution_disabled"
            )
        }

    trace.add_stage(
        stage=(
            "05_sql_execution"
        ),
        agent="duckdb",
        input_data={
            "generated_sql": (
                sql_plan.sql
            ),
            "window_ids": (
                incident.window_ids
            ),
            "execute_enabled": (
                execute_sql_toggle
            ),
        },
        output_data=(
            sql_execution
        ),
    )

    show_json(
        "SQL EXECUTION TRACE",
        sql_execution,
    )

    if (
        sql_execution.get(
            "sqlglot_validated_sql"
        )
    ):

        with st.expander(
            "SQLGlot Validated SQL"
        ):

            st.code(
                sql_execution[
                    "sqlglot_validated_sql"
                ],
                language="sql",
            )

    # ========================================================
    # STAGE 6
    # ========================================================

    st.header(
        "Stage 6 — Telemetry Finalizer"
    )

    try:

        (
            finalizer_system,
            finalizer_user,
            final_result,
        ) = finalize_trace(
            incident=incident,
            plan=plan,
            mandatory_context=(
                mandatory_context
            ),
            intelligence_trace=(
                intelligence_trace
            ),
            sql_plan=sql_plan,
            sql_execution=(
                sql_execution
            ),
        )

        trace.add_stage(
            stage=(
                "06_telemetry_finalizer"
            ),
            agent="telemetry",
            input_data={
                "model_profile": (
                    "telemetry"
                ),
                "system_prompt": (
                    finalizer_system
                ),
                "user_prompt": (
                    finalizer_user
                ),
                "parsed_incident": (
                    incident
                ),
                "telemetry_plan": (
                    plan
                ),
                "mandatory_context": (
                    mandatory_context
                ),
                "retrieved_intelligence": (
                    intelligence_trace
                ),
                "sql_plan": (
                    sql_plan
                ),
                "sql_execution": (
                    sql_execution
                ),
            },
            output_data=(
                final_result
            ),
            metadata={
                "estimated_input_tokens": (
                    estimate_tokens(
                        finalizer_system
                        + finalizer_user
                    )
                )
            },
        )

    except Exception as exc:

        trace.add_failure(
            stage=(
                "06_telemetry_finalizer"
            ),
            agent="telemetry",
            input_data={
                "model_profile": (
                    "telemetry"
                ),
                "parsed_incident": (
                    incident
                ),
                "telemetry_plan": (
                    plan
                ),
                "retrieved_intelligence": (
                    intelligence_trace
                ),
                "sql_plan": (
                    sql_plan
                ),
                "sql_execution": (
                    sql_execution
                ),
            },
            error=exc,
        )

        st.error(
            "Telemetry finalizer failed."
        )

        st.exception(
            exc
        )

        save_failed_trace(
            trace
        )

        st.stop()

    with st.expander(
        "INPUT — Telemetry Finalizer",
        expanded=True,
    ):

        show_context_block(
            "System Prompt",
            finalizer_system,
        )

        show_context_block(
            "User Prompt",
            finalizer_user,
        )

    show_json(
        "OUTPUT — Telemetry Finalizer",
        final_result,
    )

    # ========================================================
    # STAGE 7
    # CONTEXT FOOTPRINT
    # ========================================================

    context_footprint = {
        "incident_parser": (
            estimate_tokens(
                parser_system
                + parser_user
            )
        ),
        "telemetry_planner": (
            estimate_tokens(
                planner_system
                + planner_user
            )
        ),
        "sql_planner": (
            estimate_tokens(
                sql_prompt
            )
        ),
        "telemetry_finalizer": (
            estimate_tokens(
                finalizer_system
                + finalizer_user
            )
        ),
    }

    trace.add_stage(
        stage=(
            "07_context_footprint"
        ),
        agent=(
            "trace_system"
        ),
        input_data=None,
        output_data=(
            context_footprint
        ),
        metadata={
            "note": (
                "Token counts are rough "
                "character/4 estimates."
            )
        },
    )

    # ========================================================
    # SAVE COMPLETE TRACE
    # ========================================================

    try:

        trace_path = (
            trace.save()
        )

    except Exception as exc:

        st.error(
            "Investigation completed, but "
            "the trace file could not be saved."
        )

        st.exception(
            exc
        )

        st.stop()

    # ========================================================
    # FINAL UI
    # ========================================================

    st.divider()

    st.header(
        "Complete Investigation Trace"
    )

    st.success(
        f"Trace saved to: {trace_path}"
    )

    st.markdown(
        "**Context footprint**"
    )

    st.json(
        context_footprint
    )

    st.caption(
        "Token counts are approximate only."
    )

    st.markdown(
        "**Context-quality issues identified by Telemetry**"
    )

    if (
        final_result
        .context_quality_issues
    ):

        for issue in (
            final_result
            .context_quality_issues
        ):

            st.warning(
                issue
            )

    else:

        st.success(
            "No material context-quality "
            "issues identified."
        )

    st.markdown(
        "**Evidence gaps**"
    )

    if (
        final_result
        .evidence_gaps
    ):

        for gap in (
            final_result
            .evidence_gaps
        ):

            st.write(
                f"- {gap}"
            )

    else:

        st.write(
            "None identified."
        )

    # --------------------------------------------------------
    # Show raw trace in UI as well
    # --------------------------------------------------------

    with trace_path.open(
        "r",
        encoding="utf-8",
    ) as handle:

        complete_trace = (
            json.load(
                handle
            )
        )

    with st.expander(
        "View complete raw trace",
        expanded=False,
    ):

        st.json(
            complete_trace
        )