from __future__ import annotations

from typing import Literal

from pydantic import (
    BaseModel,
    Field,
)


Confidence = Literal[
    "LOW",
    "MEDIUM",
    "HIGH",
]


DomainName = Literal[
    "telemetry",
    "alarms",
    "topology",
]


# ============================================================
# INCIDENT
# ============================================================


class IncidentContext(BaseModel):

    incident_id: str | None = None

    problem_statement: str

    investigation_goal: str

    symptoms: list[str] = Field(
        default_factory=list,
        max_length=10,
    )

    window_ids: list[str] = Field(
        default_factory=list,
        max_length=10,
    )

    component_ids: list[str] = Field(
        default_factory=list,
        max_length=10,
    )

    site_ids: list[str] = Field(
        default_factory=list,
        max_length=10,
    )

    region: str | None = None

    zone: str | None = None

    start_time: str | None = None

    end_time: str | None = None

    explicit_hypotheses: list[str] = Field(
        default_factory=list,
        max_length=8,
    )

    constraints: list[str] = Field(
        default_factory=list,
        max_length=8,
    )


# ============================================================
# EVIDENCE
# ============================================================


class EvidenceFact(BaseModel):

    fact_id: str

    domain: DomainName

    statement: str

    confidence: Confidence

    source_type: Literal[
        "sql",
        "log",
        "graph",
        "alarm",
        "existing",
    ]

    source_ref: str | None = None


class HypothesisVerdict(BaseModel):

    hypothesis_id: str

    domain: DomainName

    hypothesis: str

    status: Literal[
        "supported",
        "contradicted",
        "inconclusive",
    ]

    reason: str

    confidence: Confidence


class OpenQuestion(BaseModel):

    question_id: str

    domain: DomainName

    question: str

    required_evidence: str


class EvidenceGap(BaseModel):

    domain: DomainName

    missing_evidence: str

    reason: str


class ToolFailure(BaseModel):

    domain: DomainName

    tool: str

    stage: str

    error: str

    attempts: int = 1


# ============================================================
# DOMAIN TASK
# ============================================================


class DomainTask(BaseModel):

    request_id: str

    domain: DomainName

    question: str

    evidence_goal: str


# ============================================================
# DOMAIN RETURN CONTRACT
# ============================================================


class DomainUpdate(BaseModel):

    confirmed: list[
        EvidenceFact
    ] = Field(
        default_factory=list,
        max_length=4,
    )

    verdicts: list[
        HypothesisVerdict
    ] = Field(
        default_factory=list,
        max_length=3,
    )

    open_questions: list[
        OpenQuestion
    ] = Field(
        default_factory=list,
        max_length=2,
    )

    evidence_gaps: list[
        EvidenceGap
    ] = Field(
        default_factory=list,
        max_length=2,
    )

    summary: str


# ============================================================
# RCA
# ============================================================


class RCADecision(BaseModel):

    action: Literal[
        "request_more",
        "conclude",
    ]

    request: DomainTask | None = None

    conclusion: str | None = None

    confidence: Confidence = "MEDIUM"

    reasoning_summary: str

    stop_reason: Literal[
        "sufficient_evidence",
        "max_rounds_reached",
        "evidence_exhausted",
    ] | None = None


# ============================================================
# SHARED BLACKBOARD
# ============================================================


class InvestigationState(BaseModel):

    incident: IncidentContext

    confirmed_facts: list[
        EvidenceFact
    ] = Field(
        default_factory=list,
    )

    hypothesis_verdicts: list[
        HypothesisVerdict
    ] = Field(
        default_factory=list,
    )

    open_questions: list[
        OpenQuestion
    ] = Field(
        default_factory=list,
    )

    evidence_gaps: list[
        EvidenceGap
    ] = Field(
        default_factory=list,
    )

    tool_failures: list[
        ToolFailure
    ] = Field(
        default_factory=list,
    )

    current_task: DomainTask | None = None

    rounds_used: int = 0