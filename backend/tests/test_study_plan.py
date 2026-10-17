from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import groq
import httpx
import pytest
from fastapi.testclient import TestClient

from app.schemas import ResultsResponse, StudyPlan, StudyPlanStep
from app.study_plan import (
    AI_BUDGET_SPENT,
    AI_FAILED,
    AI_NOT_CONFIGURED,
    AIProviderError,
    GroqStudyPlanProvider,
    build_prompt_payload,
    build_rule_based_plan,
    validate_ai_output,
)

from .conftest import build_client, make_settings, run_to_completion


class FakeProvider:
    model = "fake-model"

    def __init__(self, fail: bool = False) -> None:
        self.calls = 0
        self.fail = fail

    def generate(self, results: ResultsResponse) -> StudyPlan:
        self.calls += 1
        if self.fail:
            raise AIProviderError("simulated timeout")
        return StudyPlan(
            source="ai",
            generated_at=datetime.now(UTC),
            summary="A focused plan built from your results.",
            steps=[
                StudyPlanStep(
                    title="Practice",
                    topic=results.topics[0],
                    rationale="Grounded in the assessment data.",
                    actions=["Do practice"],
                )
            ],
            model=self.model,
        )


def completed_assessment(client: TestClient, *, correct: bool = False) -> str:
    state = client.post("/api/assessments", json={"topics": ["Algebra", "Geometry"], "max_questions": 10}).json()
    return str(run_to_completion(client, state, correct=correct)["assessment_id"])


def plan_for(client: TestClient, aid: str) -> dict[str, Any]:
    response = client.post(f"/api/assessments/{aid}/study-plan")
    assert response.status_code == 200, response.text
    return response.json()  # type: ignore[no-any-return]


def with_provider(provider: FakeProvider | None, **settings: Any) -> TestClient:
    return build_client(make_settings(**settings), provider)


def close(client: TestClient) -> None:
    client.app.state.db.drop_database()  # type: ignore[attr-defined]
    client.__exit__(None, None, None)


def test_rule_based_plan_without_ai_is_grounded_and_cached(client: TestClient) -> None:
    aid = completed_assessment(client)
    plan = plan_for(client, aid)
    assert plan["source"] == "rule_based" and plan["notice"] == AI_NOT_CONFIGURED
    results = client.get(f"/api/assessments/{aid}/results").json()
    missed = {item["position"] for item in results["review"] if not item["correct"]}
    evidence = {p for step in plan["steps"] for p in step["evidence_positions"]}
    assert evidence and evidence <= missed
    assert results["study_plan"] == plan
    assert plan_for(client, aid) == plan  # cached, not regenerated


def test_rule_based_plan_for_perfect_score_suggests_stretch(client: TestClient) -> None:
    plan = plan_for(client, completed_assessment(client, correct=True))
    assert plan["steps"][0]["title"] == "Stretch with harder material"
    assert all(step["evidence_positions"] == [] for step in plan["steps"])


def test_ai_plan_is_generated_once_and_cached() -> None:
    provider = FakeProvider()
    client = with_provider(provider)
    try:
        aid = completed_assessment(client)
        first = plan_for(client, aid)
        second = plan_for(client, aid)
        assert first["source"] == "ai" and first["model"] == "fake-model"
        assert first == second and provider.calls == 1
    finally:
        close(client)


def test_ai_failure_falls_back_then_respects_attempt_budget() -> None:
    provider = FakeProvider(fail=True)
    client = with_provider(provider, study_plan_max_ai_attempts=2)
    try:
        aid = completed_assessment(client)
        notices = [plan_for(client, aid)["notice"] for _ in range(4)]
        assert notices == [AI_FAILED, AI_FAILED, AI_BUDGET_SPENT, AI_BUDGET_SPENT]
        assert provider.calls == 2
    finally:
        close(client)


def test_ai_recovers_after_transient_failure() -> None:
    provider = FakeProvider(fail=True)
    client = with_provider(provider)
    try:
        aid = completed_assessment(client)
        assert plan_for(client, aid)["source"] == "rule_based"
        provider.fail = False
        assert plan_for(client, aid)["source"] == "ai"
    finally:
        close(client)


def test_study_plan_endpoint_is_rate_limited() -> None:
    client = with_provider(None, rate_limit_study_plan_per_minute=2)
    try:
        aid = completed_assessment(client)
        codes = [client.post(f"/api/assessments/{aid}/study-plan").status_code for _ in range(3)]
        assert codes == [200, 200, 429]
    finally:
        close(client)


def test_ai_never_changes_scores() -> None:
    client = with_provider(FakeProvider())
    try:
        aid = completed_assessment(client)
        before = client.get(f"/api/assessments/{aid}/results").json()
        plan_for(client, aid)
        after = client.get(f"/api/assessments/{aid}/results").json()
        for key in ("ability", "answered", "correct", "topic_results", "review", "trajectory"):
            assert before[key] == after[key]
    finally:
        close(client)


# ---------- output validation ----------


@pytest.fixture
def results(client: TestClient) -> ResultsResponse:
    aid = completed_assessment(client)
    return ResultsResponse.model_validate(client.get(f"/api/assessments/{aid}/results").json())


def _ai_json(**overrides: Any) -> str:
    body: dict[str, Any] = {
        "summary": "You are developing in algebra and geometry.",
        "steps": [
            {
                "title": "Algebra drills",
                "topic": "Algebra",
                "rationale": "Missed algebra items.",
                "actions": ["Practice factoring"],
                "evidence_positions": [1, 2, 99],
            },
            {"title": "Retest", "topic": "All topics", "rationale": "Measure progress later.", "actions": ["Retake"]},
        ],
    }
    body.update(overrides)
    return json.dumps(body)


def test_valid_ai_output_is_cross_checked(results: ResultsResponse) -> None:
    plan = validate_ai_output(_ai_json(), results, "m")
    missed = {r.position for r in results.review if not r.correct}
    assert plan.source == "ai"
    assert set(plan.steps[0].evidence_positions) <= missed
    assert 99 not in plan.steps[0].evidence_positions


@pytest.mark.parametrize(
    "raw",
    [
        "not json at all",
        "[]",
        json.dumps({"summary": "short"}),
        _ai_json(steps=[]),
        _ai_json(
            steps=[
                {
                    "title": "Astrology",
                    "topic": "Astrology",
                    "rationale": "Unrelated topic here.",
                    "actions": ["Read stars"],
                }
            ]
            * 2
        ),
    ],
)
def test_malformed_ai_output_is_rejected(results: ResultsResponse, raw: str) -> None:
    with pytest.raises(AIProviderError):
        validate_ai_output(raw, results, "m")


def test_prompt_contains_only_server_side_data(results: ResultsResponse) -> None:
    payload = build_prompt_payload(results)
    text = json.dumps(payload)
    assert set(payload) == {"assessed_topics", "overall", "topics", "missed_questions"}
    assert "selected_index" not in text and "assessment_id" not in text
    assert "answer_index" not in text and "correct_index" not in text


def test_rule_based_plan_marks_tentative_topics(results: ResultsResponse) -> None:
    plan = build_rule_based_plan(results, None)
    assert plan.steps[-1].topic == "All topics"
    assert 2 <= len(plan.steps) <= 5


# ---------- Groq provider error mapping (no network) ----------


class _FakeCompletions:
    def __init__(self, behaviour: Any) -> None:
        self.behaviour = behaviour

    def create(self, **kwargs: Any) -> Any:
        assert kwargs["response_format"] == {"type": "json_object"}
        if isinstance(self.behaviour, Exception):
            raise self.behaviour
        return self.behaviour


def _provider_with(behaviour: Any) -> GroqStudyPlanProvider:
    provider = GroqStudyPlanProvider(make_settings(groq_api_key="gsk_test"))
    provider._client = type("C", (), {"chat": type("Chat", (), {"completions": _FakeCompletions(behaviour)})()})()  # type: ignore[assignment]
    return provider


def _completion(content: str | None) -> Any:
    message = type("M", (), {"content": content})()
    return type("R", (), {"choices": [type("Ch", (), {"message": message})()]})()


def test_groq_timeout_maps_to_provider_error(results: ResultsResponse) -> None:
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    with pytest.raises(AIProviderError, match="APITimeoutError"):
        _provider_with(groq.APITimeoutError(request=request)).generate(results)


def test_groq_empty_and_valid_responses(results: ResultsResponse) -> None:
    with pytest.raises(AIProviderError, match="empty"):
        _provider_with(_completion(None)).generate(results)
    plan = _provider_with(_completion(_ai_json())).generate(results)
    assert plan.source == "ai"
    assert plan.model == make_settings().groq_model == "openai/gpt-oss-120b"


def test_groq_provider_requires_key() -> None:
    with pytest.raises(ValueError, match="GROQ_API_KEY"):
        GroqStudyPlanProvider(make_settings(groq_api_key=None))
