from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# ============================================================
# INCIDENT
# ============================================================


class IncidentContext(BaseModel):
    incident_id: str | None = None
    title: str | None = None
    priority: str | None = None
    service: str | None = None

    problem_statement: str = Field(max_length=800)
    investigation_goal: str = Field(max_length=500)

    symptoms: list[str] = Field(default_factory=list, max_length=10)

    window_ids: list[str] = Field(default_factory=list, max_length=10)
    component_ids: list[str] = Field(default_factory=list, max_length=10)
    site_ids: list[str] = Field(default_factory=list, max_length=10)

    region: str | None = None
    zone: str | None = None

    start_time: datetime | None = None
    end_time: datetime | None = None

    raw_text: str


class IncidentObjective(BaseModel):
    incident_id: str | None = None

    problem_statement: str = Field(max_length=800)
    investigation_goal: str = Field(max_length=500)

    symptoms: list[str] = Field(default_factory=list, max_length=8)

    window_ids: list[str] = Field(default_factory=list, max_length=10)
    component_ids: list[str] = Field(default_factory=list, max_length=10)
    site_ids: list[str] = Field(default_factory=list, max_length=10)

    region: str | None = None
    zone: str | None = None

    start_time: datetime | None = None
    end_time: datetime | None = None


# ============================================================
# EVIDENCE
# ============================================================


class EvidenceConfidence(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class EvidenceKind(str, Enum):
    OBSERVED = "observed"
    KNOWLEDGE = "knowledge"
    INFERRED = "inferred"


class EvidenceSource(str, Enum):
    SQL = "sql"
    KNOWLEDGE = "knowledge"
    LOG = "log"
    GRAPH = "graph"
    EXISTING = "existing"


class EvidenceAvailability(str, Enum):
    CURRENT = "current"
    QUERYABLE = "queryable"
    UNAVAILABLE = "unavailable"


class EvidenceFact(BaseModel):
    fact_id: str
    domain: str

    statement: str = Field(max_length=320)
    evidence: str = Field(max_length=450)

    confidence: EvidenceConfidence
    kind: EvidenceKind

    sources: list[EvidenceSource] = Field(
        default_factory=list,
        max_length=4,
    )


class RuledOutHypothesis(BaseModel):
    hypothesis_id: str
    domain: str

    hypothesis: str = Field(max_length=250)
    reason: str = Field(max_length=350)

    confidence: EvidenceConfidence


class OpenQuestion(BaseModel):
    question_id: str

    question: str = Field(max_length=320)

    domain: str | None = None
    availability: EvidenceAvailability

    required_evidence: str | None = Field(
        default=None,
        max_length=300,
    )

    suggested_domain: str | None = None


class InvestigationEvidenceState(BaseModel):
    confirmed: list[EvidenceFact] = Field(
        default_factory=list,
        max_length=12,
    )

    ruled_out: list[RuledOutHypothesis] = Field(
        default_factory=list,
        max_length=8,
    )

    open_questions: list[OpenQuestion] = Field(
        default_factory=list,
        max_length=8,
    )


# ============================================================
# DOMAIN
# ============================================================


class DomainRequest(BaseModel):
    request_id: str
    domain: str

    question: str = Field(max_length=800)


class FindingDraft(BaseModel):
    statement: str = Field(max_length=320)
    evidence: str = Field(max_length=450)

    confidence: EvidenceConfidence
    kind: EvidenceKind

    sources: list[EvidenceSource] = Field(
        default_factory=list,
        max_length=4,
    )


class RuledOutDraft(BaseModel):
    hypothesis: str = Field(max_length=250)
    reason: str = Field(max_length=350)

    confidence: EvidenceConfidence


class OpenQuestionDraft(BaseModel):
    question: str = Field(max_length=320)

    availability: EvidenceAvailability

    required_evidence: str | None = Field(
        default=None,
        max_length=300,
    )

    suggested_domain: str | None = None


class DomainFindingUpdate(BaseModel):
    new_confirmed: list[FindingDraft] = Field(
        default_factory=list,
        max_length=4,
    )

    new_ruled_out: list[RuledOutDraft] = Field(
        default_factory=list,
        max_length=2,
    )

    new_open_questions: list[OpenQuestionDraft] = Field(
        default_factory=list,
        max_length=2,
    )

    resolved_question_ids: list[str] = Field(
        default_factory=list,
        max_length=6,
    )

    summary: str = Field(max_length=550)


# ============================================================
# RCA
# ============================================================


class RCAAction(str, Enum):
    REQUEST_MORE = "request_more"
    CONCLUDE = "conclude"


class RCAStopReason(str, Enum):
    SUFFICIENT_EVIDENCE = "sufficient_evidence"
    REMAINING_GAPS_NOT_MATERIAL = "remaining_gaps_not_material"
    MAX_ROUNDS_REACHED = "max_rounds_reached"


class RCAFollowUp(BaseModel):
    domain: str
    question: str = Field(max_length=800)


class RCADecision(BaseModel):
    action: RCAAction

    request: RCAFollowUp | None = None

    conclusion: str | None = Field(
        default=None,
        max_length=1800,
    )

    confidence: EvidenceConfidence

    reasoning_summary: str = Field(max_length=900)

    stop_reason: RCAStopReason | None = None


# ============================================================
# FINAL RESULT
# ============================================================


class InvestigationResult(BaseModel):
    incident: IncidentContext
    objective: IncidentObjective

    rounds_used: int

    evidence_state: InvestigationEvidenceState

    domain_history: list[dict]
    rca_history: list[RCADecision]

    final_rca: RCADecision