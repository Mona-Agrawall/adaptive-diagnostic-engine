from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.db import Database
from app.question_bank import load_bank

from .conftest import answer_key, build_client, make_settings, run_to_completion, wrong_option

ALL_TOPICS = list(load_bank().topics)


def start(client: TestClient, topics: list[str] | None = None, max_questions: int = 10) -> dict[str, Any]:
    response = client.post("/api/assessments", json={"topics": topics or ALL_TOPICS, "max_questions": max_questions})
    assert response.status_code == 201, response.text
    return response.json()


def submit(client: TestClient, state: dict[str, Any], question_id: str, option: int) -> Any:
    return client.post(
        f"/api/assessments/{state['assessment_id']}/answers", json={"question_id": question_id, "option_index": option}
    )


def db_of(client: TestClient) -> Database:
    return client.app.state.db  # type: ignore[attr-defined,no-any-return]


# ---------- system ----------


def test_health_reports_database_up_and_ai_not_configured(client: TestClient) -> None:
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["database"] == {"status": "up"}
    assert body["ai"] == {"status": "not_configured"}


def test_security_headers_and_no_store_on_api(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert response.headers["cache-control"] == "no-store"


def test_unknown_route_uses_error_envelope(client: TestClient) -> None:
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_topics_lists_active_topics_with_counts(client: TestClient) -> None:
    topics = client.get("/api/topics").json()["topics"]
    assert [t["name"] for t in topics] == sorted(ALL_TOPICS)
    assert all(t["question_count"] >= 10 and t["description"] for t in topics)


# ---------- creation and validation ----------


def test_create_assessment_serves_first_question_without_answer_key(client: TestClient) -> None:
    state = start(client)
    assert state["status"] == "active"
    assert state["progress"] == {"answered": 0, "max_questions": 10, "min_questions": 6}
    question = state["current_question"]
    assert question["position"] == 1
    assert set(question) == {"question_id", "position", "topic", "stem", "options"}
    raw = client.get(f"/api/assessments/{state['assessment_id']}").text
    for leaked in ("answer_index", "explanation", '"a"', '"b"', "difficulty"):
        assert leaked not in raw


def test_topic_filter_is_respected(client: TestClient) -> None:
    state = start(client, ["Geometry"], max_questions=10)
    final = run_to_completion(client, state)
    results = client.get(f"/api/assessments/{final['assessment_id']}/results").json()
    assert {item["topic"] for item in results["review"]} == {"Geometry"}
    assert [t["topic"] for t in results["topic_results"]] == ["Geometry"]


@pytest.mark.parametrize(
    "payload",
    [
        {"topics": []},
        {"topics": ["Algebra"], "max_questions": 12},
        {"topics": ["Algebra"], "extra": True},
        {"topics": "Algebra"},
        {},
    ],
)
def test_create_rejects_invalid_payloads(client: TestClient, payload: dict[str, Any]) -> None:
    response = client.post("/api/assessments", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_create_rejects_unknown_topics(client: TestClient) -> None:
    response = client.post("/api/assessments", json={"topics": ["Algebra", "Astrology"]})
    assert response.status_code == 422
    assert response.json()["error"] == {"code": "unknown_topic", "message": "Unknown or empty topic(s): Astrology"}


def test_get_unknown_and_malformed_assessment_ids(client: TestClient) -> None:
    missing = client.get(f"/api/assessments/{'0' * 32}")
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "assessment_not_found"
    malformed = client.get("/api/assessments/not-a-valid-id")
    assert malformed.status_code == 422


def test_get_state_is_idempotent_and_does_not_advance(client: TestClient) -> None:
    state = start(client)
    again = [client.get(f"/api/assessments/{state['assessment_id']}").json() for _ in range(3)]
    assert all(s["current_question"] == state["current_question"] for s in again)
    assert all(s["progress"]["answered"] == 0 for s in again)


# ---------- answer integrity ----------


def test_valid_answer_returns_feedback_and_next_question(client: TestClient) -> None:
    state = start(client)
    qid = state["current_question"]["question_id"]
    key = answer_key(db_of(client), qid)
    response = submit(client, state, qid, key)
    assert response.status_code == 200
    body = response.json()
    assert body["feedback"]["correct"] is True
    assert body["feedback"]["correct_index"] == key
    assert body["feedback"]["explanation"]
    nxt = body["assessment"]["current_question"]
    assert nxt["position"] == 2 and nxt["question_id"] != qid


def test_fabricated_question_id_is_rejected(client: TestClient) -> None:
    state = start(client)
    current = state["current_question"]["question_id"]
    other = next(q.question_id for q in load_bank().questions if q.question_id != current)
    for qid in (other, "zzz-999"):
        response = submit(client, state, qid, 0)
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "question_not_current"
    assert client.get(f"/api/assessments/{state['assessment_id']}").json()["progress"]["answered"] == 0


def test_malformed_question_id_and_option_fail_validation(client: TestClient) -> None:
    state = start(client)
    qid = state["current_question"]["question_id"]
    assert submit(client, state, "../../etc", 0).status_code == 422
    assert submit(client, state, qid, -1).status_code == 422
    assert (
        client.post(f"/api/assessments/{state['assessment_id']}/answers", json={"question_id": qid}).status_code == 422
    )


def test_option_outside_question_options_is_rejected(client: TestClient) -> None:
    state = start(client)
    qid = state["current_question"]["question_id"]
    count = len(state["current_question"]["options"])
    response = submit(client, state, qid, count)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_option"


def test_duplicate_submission_is_rejected_and_not_counted(client: TestClient) -> None:
    state = start(client)
    qid = state["current_question"]["question_id"]
    key = answer_key(db_of(client), qid)
    assert submit(client, state, qid, key).status_code == 200
    for _ in range(3):
        repeat = submit(client, state, qid, key)
        assert repeat.status_code == 409
        assert repeat.json()["error"]["code"] == "already_answered"
    doc = db_of(client).assessments.find_one({"_id": state["assessment_id"]})
    assert doc is not None and len(doc["responses"]) == 1 and doc["version"] == 1


def test_out_of_order_submission_for_a_future_question_is_rejected(client: TestClient) -> None:
    state = start(client)
    first = state["current_question"]["question_id"]
    second_state = submit(client, state, first, wrong_option(db_of(client), first)).json()["assessment"]
    second = second_state["current_question"]["question_id"]
    # Re-answering the first question after the second was served is stale.
    stale = submit(client, state, first, answer_key(db_of(client), first))
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "already_answered"
    assert submit(client, state, second, 0).status_code == 200


def test_completed_assessment_rejects_more_answers(client: TestClient) -> None:
    final = run_to_completion(client, start(client))
    assert final["status"] == "completed" and final["current_question"] is None
    last_qid = db_of(client).assessments.find_one({"_id": final["assessment_id"]})["responses"][-1]["question_id"]  # type: ignore[index]
    response = submit(client, final, last_qid, 0)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "assessment_completed"


def test_expired_assessment_rejects_answers_and_results(client: TestClient) -> None:
    state = start(client)
    service = client.app.state.service  # type: ignore[attr-defined]
    real_clock = service.clock
    service.clock = lambda: real_clock() + timedelta(minutes=121)
    try:
        response = submit(client, state, state["current_question"]["question_id"], 0)
        assert response.status_code == 410
        assert response.json()["error"]["code"] == "assessment_expired"
        view = client.get(f"/api/assessments/{state['assessment_id']}").json()
        assert view["status"] == "expired" and view["current_question"] is None
        assert client.get(f"/api/assessments/{state['assessment_id']}/results").status_code == 410
    finally:
        service.clock = real_clock


def test_activity_extends_expiry(client: TestClient) -> None:
    state = start(client)
    service = client.app.state.service  # type: ignore[attr-defined]
    real_clock = service.clock
    qid = state["current_question"]["question_id"]
    service.clock = lambda: real_clock() + timedelta(minutes=100)
    try:
        assert submit(client, state, qid, 0).status_code == 200
        service.clock = lambda: real_clock() + timedelta(minutes=200)
        assert client.get(f"/api/assessments/{state['assessment_id']}").json()["status"] == "active"
    finally:
        service.clock = real_clock


# ---------- adaptivity, stopping, results ----------


def test_strong_and_weak_students_are_separated(client: TestClient) -> None:
    strong = client.get(f"/api/assessments/{run_to_completion(client, start(client))['assessment_id']}/results").json()
    weak_final = run_to_completion(client, start(client), correct=False)
    weak = client.get(f"/api/assessments/{weak_final['assessment_id']}/results").json()
    assert strong["ability"]["theta"] > 1.0 > -1.0 > weak["ability"]["theta"]
    assert strong["ability"]["band"] == "Advanced" and weak["ability"]["band"] == "Foundational"
    assert strong["correct"] == strong["answered"] and weak["correct"] == 0


def test_max_questions_stop_and_no_repeats(client: TestClient) -> None:
    final = run_to_completion(client, start(client, max_questions=20), correct=False)
    results = client.get(f"/api/assessments/{final['assessment_id']}/results").json()
    ids = [item["question_id"] for item in results["review"]]
    assert len(ids) == len(set(ids))
    assert results["stop_reason"] in {"max_questions", "precision_reached"}
    assert results["answered"] <= 20


def test_item_bank_exhaustion_stops_the_assessment(client: TestClient) -> None:
    db_of(client).questions.update_many(
        {"topic": "Arithmetic", "question_id": {"$gt": "ari-004"}}, {"$set": {"active": False}}
    )
    final = run_to_completion(client, start(client, ["Arithmetic"], max_questions=20))
    results = client.get(f"/api/assessments/{final['assessment_id']}/results").json()
    assert results["answered"] == 4
    assert results["stop_reason"] == "item_bank_exhausted"


def test_results_require_completion(client: TestClient) -> None:
    state = start(client)
    response = client.get(f"/api/assessments/{state['assessment_id']}/results")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "assessment_not_completed"
    assert client.post(f"/api/assessments/{state['assessment_id']}/study-plan").status_code == 409


def test_results_content_and_persistence(client: TestClient) -> None:
    final = run_to_completion(client, start(client, max_questions=10))
    assessment_id = final["assessment_id"]
    results = client.get(f"/api/assessments/{assessment_id}/results").json()
    assert results["answered"] == len(results["review"]) == len(results["trajectory"]) - 1
    assert results["trajectory"][0] == {"position": 0, "theta": 0.0, "se": 1.0}
    assert results["ability"]["ci95_low"] < results["ability"]["theta"] < results["ability"]["ci95_high"]
    assert {t["topic"] for t in results["topic_results"]} == set(ALL_TOPICS)
    assert all(t["sufficient_data"] == (t["answered"] >= 3) for t in results["topic_results"])
    assert "provisional" in results["model_notice"]
    assert all(item["time_seconds"] is not None and item["time_seconds"] >= 0 for item in results["review"])
    # Persisted: a second read returns identical results.
    assert client.get(f"/api/assessments/{assessment_id}/results").json() == results


def test_export_is_a_json_attachment(client: TestClient) -> None:
    final = run_to_completion(client, start(client))
    response = client.get(f"/api/assessments/{final['assessment_id']}/export")
    assert response.status_code == 200
    assert response.headers["content-disposition"] == f'attachment; filename="assessment-{final["assessment_id"]}.json"'
    assert response.json()["assessment_id"] == final["assessment_id"]


def test_results_survive_question_bank_edits(client: TestClient) -> None:
    final = run_to_completion(client, start(client))
    first_qid = client.get(f"/api/assessments/{final['assessment_id']}/results").json()["review"][0]["question_id"]
    db_of(client).questions.update_one({"question_id": first_qid}, {"$set": {"stem": "Edited stem", "active": False}})
    review = client.get(f"/api/assessments/{final['assessment_id']}/results").json()["review"]
    assert review[0]["stem"] != "Edited stem"


# ---------- operational limits and failures ----------


def test_rate_limit_returns_429_with_retry_after() -> None:
    limited = build_client(make_settings(rate_limit_create_per_minute=2))
    try:
        codes = [limited.post("/api/assessments", json={"topics": ["Algebra"]}).status_code for _ in range(3)]
        assert codes == [201, 201, 429]
        response = limited.post("/api/assessments", json={"topics": ["Algebra"]})
        assert response.json()["error"]["code"] == "rate_limited"
        assert int(response.headers["retry-after"]) >= 1
    finally:
        db_of(limited).drop_database()
        limited.__exit__(None, None, None)


def test_database_outage_returns_503_and_degraded_health() -> None:
    down = build_client(make_settings(mongodb_uri="mongodb://127.0.0.1:1", mongodb_timeout_ms=500), seed=False)
    try:
        health = down.get("/api/health").json()
        assert health["status"] == "degraded" and health["database"] == {"status": "down"}
        response = down.get("/api/topics")
        assert response.status_code == 503
        assert response.json() == {
            "error": {"code": "database_unavailable", "message": "The database is temporarily unavailable."}
        }
    finally:
        down.__exit__(None, None, None)


def test_answer_limit_is_independent_of_creation_limit() -> None:
    """Regression: answers once shared the creation limit, so fast test-takers were throttled."""
    limited = build_client(make_settings(rate_limit_create_per_minute=1, rate_limit_answer_per_minute=3))
    try:
        state = start(limited)
        assert limited.post("/api/assessments", json={"topics": ["Algebra"]}).status_code == 429
        codes = []
        for _ in range(4):
            qid = state["current_question"]["question_id"]
            response = submit(limited, state, qid, 0)
            codes.append(response.status_code)
            if response.status_code == 200:
                state = response.json()["assessment"]
        assert codes == [200, 200, 200, 429]
    finally:
        db_of(limited).drop_database()
        limited.__exit__(None, None, None)


def test_unresolvable_srv_host_starts_degraded_instead_of_crashing() -> None:
    """Regression: SRV DNS failures raised inside MongoClient() and crashed startup."""
    settings = make_settings(mongodb_uri="mongodb+srv://user:secret@cluster.invalid", mongodb_timeout_ms=500)
    down = build_client(settings, seed=False)
    try:
        health = down.get("/api/health").json()
        assert health["status"] == "degraded"
        response = down.post("/api/assessments", json={"topics": ["Algebra"]})
        assert response.status_code == 503
        assert "secret" not in response.text
    finally:
        down.__exit__(None, None, None)
