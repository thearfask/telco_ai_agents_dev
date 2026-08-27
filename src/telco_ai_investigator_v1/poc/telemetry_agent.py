from __future__ import annotations

import json
import os

from langchain_openai import ChatOpenAI

from .models import (
    DomainEvidence,
    DomainFindingUpdate,
    DomainRequest,
    DomainWorkingState,
    EvidenceFact,
    IncidentContext,
    OpenQuestion,
    RuledOutHypothesis,
    TelemetryAction,
    TelemetryAnalysisPlan,
)

from .sql_tool import (
    get_schema,
    sql_tool,
)
from dotenv import load_dotenv

load_dotenv()

MODEL = os.getenv(
    "POC_MODEL",
    "gpt-5.4-nano",
)


TELEMETRY_TABLES = {
    "telemetry_windows",
    "telemetry_summary",
    "telemetry_measurements",
}


# ============================================================
# DOMAIN KNOWLEDGE
# ============================================================


TELEMETRY_GUIDANCE = """
TELEMETRY DOMAIN KNOWLEDGE|

RSRP
- Measures received signal strength.
- Strong/stable RSRP argues against weak-coverage impairment.
- Persistently poor RSRP can support weak-coverage impairment.
- RSRP alone does not identify the physical reason for poor RF conditions.
- Avoid qualitative labels when the available evidence does not
  justify the classification.

BLER
- Elevated BLER indicates transmission/decoding reliability problems.
- BLER is an impairment indicator, not automatically a physical root cause.
- Compare UL and DL severity before declaring direction dominance.

PRB UTILIZATION
- Relative differences do NOT automatically imply congestion.
- Congestion requires high absolute resource utilization or additional
  resource-pressure evidence.
- Low absolute PRB utilization argues against resource saturation.

SNR
- Low SNR can support noisy/interference-like radio conditions.
- Healthy SNR does not prove absence of every interference mechanism.
- Do not invent interference measurements if only SNR is available.

MCS
- Low or falling MCS can support degraded link adaptation.
- MCS alone does not identify why link adaptation degraded.

TRAFFIC
- TX/RX changes can support service-impact correlation.
- Traffic imbalance alone does not identify root cause.

UNAVAILABLE DATA
- If the request requires metrics that do not exist in the schema,
  explicitly report that telemetry cannot resolve the question.
- Never invent substitute fields.
- Examples might include:
  RSRQ,
  interference power,
  noise floor,
  HARQ ACK/NACK reason,
  retransmission cause,
  hardware diagnostics,
  scheduler-internal reasons.

EVIDENCE_LANGUAGE
- Separate observation from interpretation.
- Never claim causality from correlation alone.
- Never describe a condition as persistent, consistent,
  intermittent, periodic, or bursty from only AVG/MIN/MAX.
- Temporal claims require temporal, distributional,
  threshold-frequency, or sample-level evidence.
- Do not convert a numeric metric into a qualitative condition
  such as weak, severe, congested, or unstable unless the
  interpretation is supported by domain knowledge and available evidence.
- When evidence supports an impairment but not its mechanism,
  state the impairment and preserve the mechanism as uncertain.
- Do not make a stronger claim than the evidence supports.

GENERAL
Always distinguish:
1. confirmed telemetry impairment,
2. supported technical interpretation,
3. hypotheses telemetry argues against,
4. physical root cause that remains unknown.

Do NOT claim:
hardware fault,
interference source,
scheduler defect,
device failure,
configuration fault,
or physical infrastructure failure

unless telemetry data specifically proves it.
"""


# ============================================================
# LLM MODELS
# ============================================================


def _planner_model():

    llm = ChatOpenAI(
        model=MODEL,
        temperature=0,
        reasoning_effort=None,
        max_completion_tokens=900,
    )

    return llm.with_structured_output(
        TelemetryAnalysisPlan,
        method="json_schema",
    )


def _analysis_model():

    llm = ChatOpenAI(
        model=MODEL,
        temperature=0,
        reasoning_effort=None,
        max_completion_tokens=1300,
    )

    return llm.with_structured_output(
        DomainFindingUpdate,
        method="json_schema",
    )


# ============================================================
# HELPERS
# ============================================================


def _normalize(
    value: str,
) -> str:

    return " ".join(
        value
        .lower()
        .strip()
        .split()
    )


def _state_json(
    state: DomainWorkingState,
) -> str:

    return state.model_dump_json(
        exclude_none=True
    )


# ============================================================
# WINDOW RESOLUTION
# ============================================================


def resolve_windows(
    incident: IncidentContext,
) -> list[str]:

    # --------------------------------------------------------
    # Explicit windows supplied in ticket
    # --------------------------------------------------------

    if incident.window_ids:

        question = f"""
Validate which of these telemetry window IDs exist:

{incident.window_ids}

Use telemetry_windows.

Return only existing window_id values.
"""

    # --------------------------------------------------------
    # Resolve from incident scope
    # --------------------------------------------------------

    else:

        scope_parts = []

        if incident.start_time:

            scope_parts.append(
                f"incident_start={incident.start_time}"
            )

        if incident.end_time:

            scope_parts.append(
                f"incident_end={incident.end_time}"
            )

        if incident.zone:

            scope_parts.append(
                f"zone={incident.zone}"
            )

        if incident.application:

            scope_parts.append(
                f"application={incident.application}"
            )

        if incident.mobility:

            scope_parts.append(
                f"mobility={incident.mobility}"
            )

        if incident.congestion:

            scope_parts.append(
                f"congestion={incident.congestion}"
            )

        if not scope_parts:

            raise RuntimeError(
                "Telemetry cannot resolve a window "
                "from the currently available incident scope."
            )

        scope = "\n".join(
            scope_parts
        )

        question = f"""
Find telemetry windows relevant to this incident.

INCIDENT SCOPE|
{scope}

Use telemetry_windows.

RULES|
- use overlapping time windows when incident time is supplied
- apply only metadata supplied by the incident
- do not invent topology mappings
- return window_id, start_time, end_time
- return at most 5 matching windows
"""

    result = sql_tool(
        question=question,
        allowed_tables=TELEMETRY_TABLES,
    )

    if (
        result.get("status")
        != "completed"
    ):

        raise RuntimeError(
            "Unable to resolve telemetry windows: "
            + str(
                result.get("reason")
                or result.get("error")
            )
        )

    rows = (
        result.get("result")
        or {}
    ).get(
        "rows",
        [],
    )

    windows = []

    for row in rows:

        value = row.get(
            "window_id"
        )

        if (
            value
            and value not in windows
        ):
            windows.append(
                value
            )

    if not windows:

        raise RuntimeError(
            "No telemetry windows matched "
            "the incident."
        )

    return windows[:5]


# ============================================================
# PLAN DOMAIN INVESTIGATION
# ============================================================


def _plan_analysis(
    *,
    request: DomainRequest,
    state: DomainWorkingState,
) -> TelemetryAnalysisPlan:

    schema = get_schema(
        TELEMETRY_TABLES
    )

    prompt = f"""
ROLE|TELEMETRY_DOMAIN_INVESTIGATOR

{TELEMETRY_GUIDANCE}

AVAILABLE TELEMETRY SCHEMA|
{schema}

DOMAIN REQUEST|
{request.question}

WINDOWS|
{request.window_ids}

CURRENT TELEMETRY WORKING STATE|
{_state_json(state)}

TASK|
Determine the smallest appropriate action needed
to answer the domain request.

You have exactly three choices:

USE_EXISTING
Existing working-state facts already answer the question.

QUERY_MORE
Required source metrics exist in AVAILABLE TELEMETRY SCHEMA
and one small analytical SQL query can materially improve the answer.

EVIDENCE_UNAVAILABLE
The request requires evidence that does not exist in
AVAILABLE TELEMETRY SCHEMA.

DECISION RULES|
- Do NOT query simply because this is a new investigation round.
- Reuse confirmed facts and ruled-out hypotheses first.
- If the state is empty and the request is answerable, QUERY_MORE.
- Never request columns absent from AVAILABLE TELEMETRY SCHEMA.
- Never invent substitute metrics.
- Query only a material evidence gap.
- Ask for the smallest useful calculation.
- Prefer one aggregate result row when possible.
- Maximum expected result approximately 8 rows.
- Never request raw sample dumps.
- Never request nested lists.
- Never request huge distributions.
- Do not perform final RCA.

OUTPUT|

USE_EXISTING:
action=use_existing
query_question=null

QUERY_MORE:
action=query_more
query_question=<precise analytical question>

EVIDENCE_UNAVAILABLE:
action=evidence_unavailable
query_question=null
reason=<what cannot be established using telemetry and why>
"""

    return _planner_model().invoke(
        prompt
    )


# ============================================================
# TELEMETRY DOMAIN ANALYSIS
# ============================================================


def _analyze(
    *,
    request: DomainRequest,
    state: DomainWorkingState,
    current_rows: list[dict],
    query_used: bool,
) -> DomainFindingUpdate:

    rows_json = json.dumps(
        current_rows,
        default=str,
        separators=(",", ":"),
    )

    prompt = f"""
ROLE|TELEMETRY_DOMAIN_ANALYST

{TELEMETRY_GUIDANCE}

DOMAIN REQUEST|
{request.question}

WINDOWS|
{request.window_ids}

CURRENT TELEMETRY WORKING STATE|
{_state_json(state)}

NEW TOOL RESULT|
{rows_json}

QUERY_USED|
{query_used}

TASK|
Answer the telemetry domain request using:
1. existing working-state facts,
2. any new SQL result.

Return ONLY new information that should be added
to telemetry state.

For each new confirmed finding provide:

statement:
A concise telemetry-domain fact.

evidence:
Minimal numerical evidence supporting the statement.

confidence:
LOW, MEDIUM or HIGH.

Also identify:
new_ruled_out
new_open_questions

RULES|
- Maximum 5 new confirmed findings.
- Maximum 4 new ruled-out hypotheses.
- Maximum 4 new open questions.
- Do not repeat facts already in working state.
- Do not dump every metric.
- Interpret absolute severity, not just relative difference.
- Low absolute PRB utilization must not be called congestion.
- BLER is a transmission impairment, not automatically root cause.
- Weak RSRP supports poor RF conditions but does not explain
  the physical reason for those conditions.
- Do not invent unavailable measurements.
- Do not perform final RCA.
- Do not request another SQL query here.

SUMMARY|
Provide a concise domain-level answer useful to RCA.
"""

    return _analysis_model().invoke(
        prompt
    )


# ============================================================
# APPLY DOMAIN STATE UPDATE
# ============================================================


def _apply_update(
    *,
    state: DomainWorkingState,
    update: DomainFindingUpdate,
    round_number: int,
) -> tuple[
    DomainWorkingState,
    list[EvidenceFact],
    list[RuledOutHypothesis],
    list[OpenQuestion],
]:

    added_facts = []
    added_ruled_out = []
    added_questions = []

    # --------------------------------------------------------
    # CONFIRMED
    # --------------------------------------------------------

    existing_facts = {
        _normalize(
            item.statement
        )
        for item
        in state.confirmed
    }

    for index, draft in enumerate(
        update.new_confirmed,
        start=1,
    ):

        normalized = _normalize(
            draft.statement
        )

        if normalized in existing_facts:
            continue

        fact = EvidenceFact(
            fact_id=(
                f"TEL-R{round_number}-F{index}"
            ),
            domain="telemetry",
            statement=draft.statement,
            evidence=draft.evidence,
            confidence=draft.confidence,
        )

        state.confirmed.append(
            fact
        )

        added_facts.append(
            fact
        )

        existing_facts.add(
            normalized
        )

    # --------------------------------------------------------
    # RULED OUT
    # --------------------------------------------------------

    existing_ruled = {
        _normalize(
            item.hypothesis
        )
        for item
        in state.ruled_out
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

        ruled = RuledOutHypothesis(
            hypothesis_id=(
                f"TEL-R{round_number}-X{index}"
            ),
            domain="telemetry",
            hypothesis=draft.hypothesis,
            reason=draft.reason,
            confidence=draft.confidence,
        )

        state.ruled_out.append(
            ruled
        )

        added_ruled_out.append(
            ruled
        )

        existing_ruled.add(
            normalized
        )

    # --------------------------------------------------------
    # OPEN QUESTIONS
    # --------------------------------------------------------

    existing_questions = {
        _normalize(
            item.question
        )
        for item
        in state.open_questions
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

        question = OpenQuestion(
            question_id=f"TEL-R{round_number}-Q{index}",
            question=draft.question,
            domain="telemetry",
            answerable_by_current_domain=(
                draft.answerable_by_current_domain
            ),
            required_evidence=(
                draft.required_evidence
            ),
        )

        state.open_questions.append(
            question
        )

        added_questions.append(
            question
        )

        existing_questions.add(
            normalized
        )

    # --------------------------------------------------------
    # HARD BOUNDS
    # --------------------------------------------------------

    state.confirmed = (
        state.confirmed[-8:]
    )

    state.ruled_out = (
        state.ruled_out[-6:]
    )

    state.open_questions = (
        state.open_questions[-6:]
    )

    return (
        state,
        added_facts,
        added_ruled_out,
        added_questions,
    )


# ============================================================
# HANDLE UNAVAILABLE EVIDENCE
# ============================================================


def _unavailable_evidence(
    *,
    request: DomainRequest,
    state: DomainWorkingState,
    reason: str,
    query_used: bool,
    sql: str | None = None,
) -> tuple[
    DomainEvidence,
    DomainWorkingState,
]:

    statement = (
        "Telemetry cannot resolve this evidence gap "
        "from the available telemetry source: "
        + reason
    )

    question = OpenQuestion(
        question_id=(
            f"TEL-R{request.round_number}-Q1"
        ),
        question=statement[:300],
        domain="telemetry",
    )

    existing_questions = {
        _normalize(
            item.question
        )
        for item
        in state.open_questions
    }

    if (
        _normalize(question.question)
        not in existing_questions
    ):

        state.open_questions.append(
            question
        )

    state.open_questions = (
        state.open_questions[-6:]
    )

    evidence = DomainEvidence(
        request_id=request.request_id,
        round_number=request.round_number,
        domain="telemetry",
        status="completed",
        question=request.question,
        window_ids=request.window_ids,

        query_used=query_used,

        sql=sql,
        row_count=0,
        rows=[],

        findings=[],
        ruled_out=[],
        open_questions=[
            question
        ],

        domain_summary=(
            "Requested telemetry evidence is unavailable. "
            + reason
        ),

        planner_reason=reason,

        error=None,
    )

    return (
        evidence,
        state,
    )


# ============================================================
# MAIN TELEMETRY AGENT
# ============================================================


def investigate_telemetry(
    *,
    request: DomainRequest,
    state: DomainWorkingState,
) -> tuple[
    DomainEvidence,
    DomainWorkingState,
]:

    if not request.window_ids:

        return (
            DomainEvidence(
                request_id=request.request_id,
                round_number=request.round_number,
                domain="telemetry",
                status="unsupported",
                question=request.question,
                error=(
                    "No telemetry windows supplied."
                ),
            ),
            state,
        )

    # ========================================================
    # 1. REASON BEFORE TOOL USE
    # ========================================================

    plan = _plan_analysis(
        request=request,
        state=state,
    )

    # ========================================================
    # 2. SOURCE CANNOT ANSWER
    # ========================================================

    if (
        plan.action
        == TelemetryAction.EVIDENCE_UNAVAILABLE
    ):

        return _unavailable_evidence(
            request=request,
            state=state,
            reason=plan.reason,
            query_used=False,
        )

    # ========================================================
    # 3. OPTIONAL QUERY
    # ========================================================

    query_used = False

    sql = None

    rows = []

    row_count = 0

    if (
        plan.action
        == TelemetryAction.QUERY_MORE
    ):

        if not plan.query_question:

            return (
                DomainEvidence(
                    request_id=request.request_id,
                    round_number=request.round_number,
                    domain="telemetry",
                    status="failed",
                    question=request.question,
                    window_ids=request.window_ids,
                    planner_reason=plan.reason,
                    error=(
                        "Telemetry planner selected "
                        "QUERY_MORE without query_question."
                    ),
                ),
                state,
            )

        sql_question = f"""
TELEMETRY WINDOWS|
{request.window_ids}

ANALYTICAL REQUEST|
{plan.query_question}

RULES|
- Restrict analysis to supplied windows.
- Analyze all relevant samples.
- Prefer compact aggregation.
- Return only information needed for the request.
- Target approximately 1-8 rows.
- Never return raw sample dumps.
- Never return nested lists.
- Never invent unavailable columns.
"""

        result = sql_tool(
            question=sql_question,
            allowed_tables=TELEMETRY_TABLES,
        )

        # ----------------------------------------------------
        # VALID DATA LIMITATION
        # ----------------------------------------------------

        if (
            result.get("status")
            == "unsupported"
        ):

            return _unavailable_evidence(
                request=request,
                state=state,
                reason=(
                    result.get("reason")
                    or "Requested evidence does not "
                       "exist in telemetry."
                ),
                query_used=True,
                sql=result.get("sql"),
            )

        # ----------------------------------------------------
        # ACTUAL TOOL FAILURE
        # ----------------------------------------------------

        if (
            result.get("status")
            != "completed"
        ):

            return (
                DomainEvidence(
                    request_id=request.request_id,
                    round_number=request.round_number,
                    domain="telemetry",
                    status="failed",
                    question=request.question,
                    window_ids=request.window_ids,
                    query_used=True,
                    sql=result.get("sql"),
                    planner_reason=plan.reason,
                    error=(
                        result.get("error")
                        or "Telemetry SQL execution failed."
                    ),
                ),
                state,
            )

        sql_result = (
            result.get("result")
            or {}
        )

        query_used = True

        sql = result.get(
            "sql"
        )

        rows = sql_result.get(
            "rows",
            [],
        )

        row_count = sql_result.get(
            "row_count",
            0,
        )

    # ========================================================
    # 4. SPECIALIST INTERPRETATION
    # ========================================================

    update = _analyze(
        request=request,
        state=state,
        current_rows=rows,
        query_used=query_used,
    )

    # ========================================================
    # 5. UPDATE PRIVATE TELEMETRY MEMORY
    # ========================================================

    (
        state,
        new_facts,
        new_ruled_out,
        new_questions,
    ) = _apply_update(
        state=state,
        update=update,
        round_number=request.round_number,
    )

    # ========================================================
    # 6. RETURN ONLY NEW FINDINGS TO ORCHESTRATOR/RCA
    # ========================================================

    evidence = DomainEvidence(
        request_id=request.request_id,
        round_number=request.round_number,
        domain="telemetry",
        status="completed",
        question=request.question,
        window_ids=request.window_ids,

        query_used=query_used,

        # audit
        sql=sql,
        row_count=row_count,
        rows=rows,

        # bounded findings
        findings=new_facts,
        ruled_out=new_ruled_out,
        open_questions=new_questions,

        domain_summary=(
            update.summary
        ),

        planner_reason=(
            plan.reason
        ),

        error=None,
    )

    return (
        evidence,
        state,
    )