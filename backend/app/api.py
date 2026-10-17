"""HTTP routes. Handlers stay thin; business rules live in `assessment.py` and `study_plan.py`."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Request
from fastapi.responses import JSONResponse

from . import __version__
from .assessment import AssessmentService
from .db import Database
from .schemas import (
    ASSESSMENT_ID_PATTERN,
    AnswerResponse,
    AssessmentState,
    ComponentHealth,
    CreateAssessmentRequest,
    ErrorResponse,
    HealthResponse,
    ResultsResponse,
    StudyPlan,
    SubmitAnswerRequest,
    TopicsResponse,
)
from .study_plan import StudyPlanProvider, get_or_create_study_plan

AssessmentId = Annotated[str, Path(pattern=ASSESSMENT_ID_PATTERN, description="Assessment identifier.")]


def _errors(*codes: int) -> dict[int | str, dict[str, Any]]:
    return {code: {"model": ErrorResponse} for code in codes}


def get_service(request: Request) -> AssessmentService:
    service: AssessmentService = request.app.state.service
    service.db.ensure_indexes()
    return service


def get_provider(request: Request) -> StudyPlanProvider | None:
    provider: StudyPlanProvider | None = request.app.state.ai_provider
    return provider


def create_limit(request: Request) -> None:
    request.app.state.create_limiter.dependency(request)


def answer_limit(request: Request) -> None:
    request.app.state.answer_limiter.dependency(request)


def study_plan_limit(request: Request) -> None:
    request.app.state.study_plan_limiter.dependency(request)


Service = Annotated[AssessmentService, Depends(get_service)]
router = APIRouter(prefix="/api")


@router.get("/health", response_model=HealthResponse, tags=["system"])
def health(request: Request) -> JSONResponse:
    """Liveness plus dependency status. Returns 200 when the app is up; `status` is `degraded`
    when the database is unreachable. The AI provider is optional and never degrades health."""
    db: Database = request.app.state.db
    db_up = db.ping()
    body = HealthResponse(
        status="ok" if db_up else "degraded",
        version=__version__,
        database=ComponentHealth(status="up" if db_up else "down"),
        ai=ComponentHealth(status="configured" if request.app.state.ai_provider else "not_configured"),
    )
    return JSONResponse(body.model_dump())


@router.get("/topics", response_model=TopicsResponse, tags=["question bank"], responses=_errors(503))
def list_topics(service: Service) -> TopicsResponse:
    return TopicsResponse(topics=service.list_topics())


@router.post(
    "/assessments",
    status_code=201,
    response_model=AssessmentState,
    tags=["assessments"],
    dependencies=[Depends(create_limit)],
    responses=_errors(422, 429, 503),
)
def create_assessment(body: CreateAssessmentRequest, service: Service) -> AssessmentState:
    """Start an assessment. The response includes the first question."""
    return service.create(body.topics, body.max_questions)


@router.get(
    "/assessments/{assessment_id}",
    response_model=AssessmentState,
    tags=["assessments"],
    responses=_errors(404, 422, 503),
)
def get_assessment(assessment_id: AssessmentId, service: Service) -> AssessmentState:
    """Current state, including the question awaiting an answer. Safe to call repeatedly."""
    return service.get_state(assessment_id)


@router.post(
    "/assessments/{assessment_id}/answers",
    response_model=AnswerResponse,
    tags=["assessments"],
    dependencies=[Depends(answer_limit)],
    responses=_errors(404, 409, 410, 422, 429, 503),
)
def submit_answer(assessment_id: AssessmentId, body: SubmitAnswerRequest, service: Service) -> AnswerResponse:
    """Answer the current question. Only the question currently served is accepted, exactly once.

    409 `question_not_current` / `already_answered` / `assessment_completed` / `conflict`,
    410 `assessment_expired`, 422 `invalid_option`."""
    return service.submit_answer(assessment_id, body.question_id, body.option_index)


@router.get(
    "/assessments/{assessment_id}/results",
    response_model=ResultsResponse,
    tags=["results"],
    responses=_errors(404, 409, 410, 422, 503),
)
def get_results(assessment_id: AssessmentId, service: Service) -> ResultsResponse:
    return service.results(assessment_id)


@router.get(
    "/assessments/{assessment_id}/export",
    response_model=ResultsResponse,
    tags=["results"],
    responses=_errors(404, 409, 410, 422, 503),
)
def export_results(assessment_id: AssessmentId, service: Service) -> JSONResponse:
    """Completed results as a downloadable JSON file."""
    results = service.results(assessment_id)
    return JSONResponse(
        results.model_dump(mode="json"),
        headers={"Content-Disposition": f'attachment; filename="assessment-{assessment_id}.json"'},
    )


@router.post(
    "/assessments/{assessment_id}/study-plan",
    response_model=StudyPlan,
    tags=["results"],
    dependencies=[Depends(study_plan_limit)],
    responses=_errors(404, 409, 410, 422, 429, 503),
)
def study_plan(
    assessment_id: AssessmentId,
    service: Service,
    provider: Annotated[StudyPlanProvider | None, Depends(get_provider)],
) -> StudyPlan:
    """Return the cached study plan, or generate one. Falls back to a rule-based plan when the
    AI provider is not configured, fails, or the per-assessment AI attempt budget is spent."""
    return get_or_create_study_plan(service, provider, assessment_id)
