"""Request and response schemas for the public API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

AssessmentStatus = Literal["active", "completed", "expired"]
StopReasonValue = Literal["precision_reached", "max_questions", "item_bank_exhausted"]
ASSESSMENT_ID_PATTERN = r"^[0-9a-f]{32}$"
QUESTION_ID_PATTERN = r"^[a-z]{3}-\d{3}$"
ALLOWED_LENGTHS = (10, 15, 20)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------- Requests ----------


class CreateAssessmentRequest(StrictModel):
    topics: list[str] = Field(min_length=1, max_length=10, description="Topics to include.")
    max_questions: int = Field(default=15, description="Maximum length: 10, 15 or 20.")

    @field_validator("topics")
    @classmethod
    def _dedupe(cls, topics: list[str]) -> list[str]:
        cleaned = list(dict.fromkeys(topic.strip() for topic in topics))
        if any(not topic or len(topic) > 60 for topic in cleaned):
            raise ValueError("topic names must be 1-60 characters")
        return cleaned

    @field_validator("max_questions")
    @classmethod
    def _allowed_length(cls, value: int) -> int:
        if value not in ALLOWED_LENGTHS:
            raise ValueError(f"must be one of {', '.join(map(str, ALLOWED_LENGTHS))}")
        return value


class SubmitAnswerRequest(StrictModel):
    question_id: str = Field(pattern=QUESTION_ID_PATTERN)
    option_index: int = Field(ge=0, le=9)


# ---------- Responses ----------


class TopicInfo(BaseModel):
    name: str
    description: str
    question_count: int


class TopicsResponse(BaseModel):
    topics: list[TopicInfo]


class ServedQuestion(BaseModel):
    question_id: str
    position: int = Field(description="1-based position of this question in the assessment.")
    topic: str
    stem: str
    options: list[str]


class Progress(BaseModel):
    answered: int
    max_questions: int
    min_questions: int


class AssessmentState(BaseModel):
    assessment_id: str
    status: AssessmentStatus
    topics: list[str]
    progress: Progress
    current_question: ServedQuestion | None
    stop_reason: StopReasonValue | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    expires_at: datetime | None


class AbilitySummary(BaseModel):
    theta: float = Field(description="EAP ability estimate on the logit scale.")
    se: float = Field(description="Posterior standard deviation of theta.")
    ci95_low: float
    ci95_high: float
    band: str
    band_description: str


class AnswerFeedback(BaseModel):
    question_id: str
    correct: bool
    selected_index: int
    correct_index: int
    explanation: str


class AnswerResponse(BaseModel):
    feedback: AnswerFeedback
    assessment: AssessmentState


class TopicResult(BaseModel):
    topic: str
    answered: int
    correct: int
    accuracy: float
    theta: float
    se: float
    sufficient_data: bool = Field(description="False when fewer than the minimum items were seen.")


class TrajectoryPoint(BaseModel):
    position: int
    theta: float
    se: float


class ReviewItem(BaseModel):
    position: int
    question_id: str
    topic: str
    stem: str
    options: list[str]
    selected_index: int
    correct_index: int
    correct: bool
    explanation: str
    tags: list[str]
    time_seconds: float | None


class StudyPlanStep(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    topic: str = Field(min_length=1, max_length=60)
    rationale: str = Field(min_length=10, max_length=600)
    actions: list[str] = Field(min_length=1, max_length=5)
    evidence_positions: list[int] = Field(default_factory=list, max_length=20)

    @field_validator("actions")
    @classmethod
    def _bounded_actions(cls, actions: list[str]) -> list[str]:
        cleaned = [action.strip() for action in actions if action.strip()]
        if not cleaned or any(len(action) > 300 for action in cleaned):
            raise ValueError("actions must be 1-300 characters each")
        return cleaned


class StudyPlan(BaseModel):
    source: Literal["ai", "rule_based"]
    generated_at: datetime
    summary: str = Field(min_length=10, max_length=1200)
    steps: list[StudyPlanStep] = Field(min_length=1, max_length=5)
    notice: str | None = None
    model: str | None = None


class ResultsResponse(BaseModel):
    assessment_id: str
    status: AssessmentStatus
    topics: list[str]
    stop_reason: StopReasonValue | None
    created_at: datetime
    completed_at: datetime | None
    ability: AbilitySummary
    answered: int
    correct: int
    accuracy: float
    topic_results: list[TopicResult]
    trajectory: list[TrajectoryPoint]
    review: list[ReviewItem]
    study_plan: StudyPlan | None
    model_notice: str


class ComponentHealth(BaseModel):
    status: Literal["up", "down", "configured", "not_configured"]


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    database: ComponentHealth
    ai: ComponentHealth


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: object | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
