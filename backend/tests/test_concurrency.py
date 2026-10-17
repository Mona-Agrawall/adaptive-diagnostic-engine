"""Race conditions: concurrent submissions must never double count or corrupt state."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.assessment import AssessmentService
from app.errors import AppError, ConflictError

from .conftest import answer_key


def _attempt(service: AssessmentService, barrier: threading.Barrier, aid: str, qid: str, option: int) -> str:
    barrier.wait()
    try:
        service.submit_answer(aid, qid, option)
    except AppError as exc:
        return exc.code
    return "ok"


@pytest.mark.parametrize("threads", [2, 8, 16])
def test_parallel_duplicate_submissions_count_exactly_once(service: AssessmentService, threads: int) -> None:
    state = service.create(["Algebra", "Geometry"], 10)
    assert state.current_question is not None
    qid = state.current_question.question_id
    key = answer_key(service.db, qid)
    barrier = threading.Barrier(threads)
    with ThreadPoolExecutor(threads) as pool:
        outcomes = list(pool.map(lambda _: _attempt(service, barrier, state.assessment_id, qid, key), range(threads)))
    assert outcomes.count("ok") == 1
    assert set(outcomes) - {"ok"} <= {"already_answered", "conflict"}
    doc = service.db.assessments.find_one({"_id": state.assessment_id})
    assert doc is not None
    assert len(doc["responses"]) == 1
    assert doc["version"] == 1
    assert doc["current"]["position"] == 2


def test_parallel_submissions_with_different_options_keep_one_answer(service: AssessmentService) -> None:
    state = service.create(["Vocabulary"], 10)
    assert state.current_question is not None
    qid = state.current_question.question_id
    barrier = threading.Barrier(4)
    with ThreadPoolExecutor(4) as pool:
        outcomes = list(pool.map(lambda i: _attempt(service, barrier, state.assessment_id, qid, i), range(4)))
    assert outcomes.count("ok") == 1
    doc = service.db.assessments.find_one({"_id": state.assessment_id})
    assert doc is not None and len(doc["responses"]) == 1


def test_interleaved_update_is_detected_as_conflict(
    service: AssessmentService, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Deterministically interleave two writers: the second must not overwrite the first."""
    state = service.create(["Algebra"], 10)
    assert state.current_question is not None
    qid = state.current_question.question_id
    original = service._load_candidates
    fired = False

    def racing_load(topics: list[str], exclude: list[str]) -> list:  # type: ignore[type-arg]
        nonlocal fired
        if not fired:
            fired = True
            # Another request bumps the version between our read and our write.
            service.db.assessments.update_one({"_id": state.assessment_id}, {"$inc": {"version": 1}})
        return original(topics, exclude)

    monkeypatch.setattr(service, "_load_candidates", racing_load)
    with pytest.raises(ConflictError) as excinfo:
        service.submit_answer(state.assessment_id, qid, 0)
    assert excinfo.value.code == "conflict"
    doc = service.db.assessments.find_one({"_id": state.assessment_id})
    assert doc is not None and doc["responses"] == []


def test_parallel_sessions_are_independent(service: AssessmentService) -> None:
    states = [service.create(["Data Analysis"], 10) for _ in range(6)]

    def answer_all(aid: str) -> int:
        current = service.get_state(aid)
        while current.status == "active" and current.current_question is not None:
            qid = current.current_question.question_id
            current = service.submit_answer(aid, qid, answer_key(service.db, qid)).assessment
        return current.progress.answered

    with ThreadPoolExecutor(6) as pool:
        answered = list(pool.map(answer_all, [s.assessment_id for s in states]))
    assert all(6 <= n <= 10 for n in answered)
    for state in states:
        doc = service.db.assessments.find_one({"_id": state.assessment_id})
        assert doc is not None and doc["status"] == "completed"
        assert len({r["question_id"] for r in doc["responses"]}) == len(doc["responses"])
