from __future__ import annotations

from uuid import uuid4

from .incident_parser import (
    parse_incident,
)

from .models import (
    DomainEvidence,
    DomainRequest,
    DomainWorkingState,
    IncidentObjective,
    InvestigationEvidenceState,
    InvestigationResult,
    RCAAction,
)

from .rca_agent import (
    run_rca,
)

from .telemetry_agent import (
    investigate_telemetry,
    resolve_windows,
)


MAX_ROUNDS = 3


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


def _request_id() -> str:

    return (
        "REQ-"
        + uuid4().hex[:8].upper()
    )


# ============================================================
# RCA OBJECTIVE
# ============================================================


def _build_objective(
    *,
    incident,
    window_ids: list[str],
) -> IncidentObjective:

    return IncidentObjective(
        incident_id=(
            incident.incident_id
        ),

        problem=(
            incident.title
            or incident.investigation_goal
        ),

        symptoms=(
            incident.symptoms[:8]
        ),

        investigation_goal=(
            incident.investigation_goal
        ),

        scope={
            "window_ids":
                window_ids,

            "component_ids":
                incident.component_ids,

            "site_ids":
                incident.site_ids,

            "gnb_ids":
                incident.gnb_ids,

            "region":
                incident.region,

            "zone":
                incident.zone,

            "application":
                incident.application,

            "start_time":
                incident.start_time,

            "end_time":
                incident.end_time,
        },
    )


# ============================================================
# INITIAL TELEMETRY REQUEST
# ============================================================


def _initial_telemetry_question(
    window_ids: list[str],
) -> str:

    return f"""
Perform an initial telemetry-domain assessment for:

{window_ids}

Determine the dominant observable telemetry impairment.

Evaluate only what the telemetry supports across the complete
relevant window data.

Consider:
- received signal conditions
- DL transmission reliability
- UL transmission reliability
- link adaptation
- absolute resource utilization
- traffic behavior

Return compact domain findings.

Identify:
- confirmed telemetry facts
- explanations telemetry currently argues against
- meaningful unresolved telemetry questions

Do not attempt to identify a physical root cause unless
telemetry directly establishes it.
"""


# ============================================================
# GLOBAL EVIDENCE STATE
# ============================================================


def _merge_global_state(
    *,
    state: InvestigationEvidenceState,
    evidence: DomainEvidence,
) -> InvestigationEvidenceState:

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

    for item in evidence.findings:

        normalized = _normalize(
            item.statement
        )

        if normalized in existing_facts:
            continue

        state.confirmed.append(
            item
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

    for item in evidence.ruled_out:

        normalized = _normalize(
            item.hypothesis
        )

        if normalized in existing_ruled:
            continue

        state.ruled_out.append(
            item
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

    for item in evidence.open_questions:

        normalized = _normalize(
            item.question
        )

        if normalized in existing_questions:
            continue

        state.open_questions.append(
            item
        )

        existing_questions.add(
            normalized
        )

    # --------------------------------------------------------
    # HARD GLOBAL MEMORY LIMITS
    # --------------------------------------------------------

    state.confirmed = (
        state.confirmed[-12:]
    )

    state.ruled_out = (
        state.ruled_out[-8:]
    )

    state.open_questions = (
        state.open_questions[-8:]
    )

    return state


# ============================================================
# MAIN INVESTIGATION
# ============================================================


def investigate_incident(
    incident_text: str,
) -> InvestigationResult:

    # ========================================================
    # 1. INCIDENT INTAKE
    # ========================================================

    incident = parse_incident(
        incident_text
    )

    # ========================================================
    # 2. RESOLVE TELEMETRY SCOPE
    # ========================================================

    window_ids = resolve_windows(
        incident
    )

    # ========================================================
    # 3. RCA OBJECTIVE
    # ========================================================

    objective = _build_objective(
        incident=incident,
        window_ids=window_ids,
    )

    # ========================================================
    # 4. INITIALIZE GLOBAL + DOMAIN MEMORY
    # ========================================================

    evidence_state = (
        InvestigationEvidenceState()
    )

    telemetry_state = (
        DomainWorkingState(
            domain="telemetry"
        )
    )

    audit_history: list[
        DomainEvidence
    ] = []

    rca_history = []

    # ========================================================
    # 5. INITIAL REQUEST
    # ========================================================

    current_request = (
        DomainRequest(
            request_id=_request_id(),
            round_number=1,
            domain="telemetry",
            question=(
                _initial_telemetry_question(
                    window_ids
                )
            ),
            window_ids=window_ids,
        )
    )

    # ========================================================
    # 6. INVESTIGATION ROUNDS
    # ========================================================

    for round_number in range(
        1,
        MAX_ROUNDS + 1,
    ):

        current_request.round_number = (
            round_number
        )

        # ----------------------------------------------------
        # DOMAIN ROUTING
        # ----------------------------------------------------

        if (
            current_request.domain
            != "telemetry"
        ):

            raise RuntimeError(
                f"Domain '{current_request.domain}' "
                "is not implemented yet."
            )

        # ----------------------------------------------------
        # TELEMETRY SPECIALIST
        # ----------------------------------------------------

        (
            domain_evidence,
            telemetry_state,
        ) = investigate_telemetry(
            request=current_request,
            state=telemetry_state,
        )

        # Full audit trail.
        audit_history.append(
            domain_evidence
        )

        # ----------------------------------------------------
        # REAL DOMAIN/TOOL FAILURE
        #
        # EVIDENCE_UNAVAILABLE is returned as completed,
        # therefore it does NOT land here.
        # ----------------------------------------------------

        if (
            domain_evidence.status
            != "completed"
        ):

            raise RuntimeError(
                "Telemetry investigation failed: "
                + str(
                    domain_evidence.error
                    or "unknown error"
                )
            )

        # ----------------------------------------------------
        # MERGE ONLY COMPACT FINDINGS INTO GLOBAL RCA MEMORY
        # ----------------------------------------------------

        evidence_state = (
            _merge_global_state(
                state=evidence_state,
                evidence=domain_evidence,
            )
        )

        # ----------------------------------------------------
        # RCA
        # ----------------------------------------------------

        decision = run_rca(
            objective=objective,

            evidence_state=(
                evidence_state
            ),

            latest_evidence=(
                domain_evidence
            ),

            round_number=(
                round_number
            ),

            max_rounds=(
                MAX_ROUNDS
            ),
        )

        rca_history.append(
            decision
        )

        # ----------------------------------------------------
        # CONCLUDE
        # ----------------------------------------------------

        if (
            decision.action
            == RCAAction.CONCLUDE
        ):

            return InvestigationResult(
                incident=incident,

                objective=objective,

                resolved_window_ids=(
                    window_ids
                ),

                rounds_used=(
                    round_number
                ),

                evidence=(
                    audit_history
                ),

                rca_history=(
                    rca_history
                ),

                evidence_state=(
                    evidence_state
                ),

                final_rca=(
                    decision
                ),
            )

        # ----------------------------------------------------
        # FOLLOW-UP
        # ----------------------------------------------------

        if not decision.request:

            raise RuntimeError(
                "RCA requested another round "
                "without a specialist request."
            )

        current_request = (
            DomainRequest(
                request_id=(
                    _request_id()
                ),

                round_number=(
                    round_number + 1
                ),

                domain=(
                    decision
                    .request
                    .domain
                ),

                question=(
                    decision
                    .request
                    .question
                ),

                window_ids=(
                    window_ids
                ),
            )
        )

    raise RuntimeError(
        "Investigation ended unexpectedly."
    )