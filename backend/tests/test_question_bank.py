from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.assessment import AssessmentService
from app.db import Database
from app.question_bank import DEFAULT_BANK_PATH, QuestionRecord, load_bank, seed_questions
from app.seed import main as seed_main

from .conftest import answer_key


def _raw_bank() -> dict[str, Any]:
    return json.loads(DEFAULT_BANK_PATH.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def _write(tmp_path: Path, data: dict[str, Any]) -> Path:
    path = tmp_path / "bank.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_shipped_bank_is_valid_and_balanced() -> None:
    bank = load_bank()
    assert len(bank.questions) >= 50
    for topic in bank.topics:
        items = [q for q in bank.questions if q.topic == topic]
        assert len(items) >= 10
        assert min(q.b for q in items) < -1 and max(q.b for q in items) > 1
    # Answer keys are not concentrated in one position.
    positions = [q.answer_index for q in bank.questions]
    assert max(positions.count(i) for i in set(positions)) / len(positions) < 0.4


def test_duplicate_ids_are_rejected(tmp_path: Path) -> None:
    data = _raw_bank()
    data["questions"].append(dict(data["questions"][0]))
    with pytest.raises(ValidationError, match="duplicate question_id"):
        load_bank(_write(tmp_path, data))


def test_undeclared_topic_is_rejected(tmp_path: Path) -> None:
    data = _raw_bank()
    data["questions"][0]["topic"] = "Chemistry"
    with pytest.raises(ValidationError, match="undeclared topics"):
        load_bank(_write(tmp_path, data))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("answer_index", 9),
        ("options", ["Same", "same"]),
        ("options", ["Only one"]),
        ("a", 0.0),
        ("b", 7.5),
        ("question_id", "bad id"),
    ],
)
def test_invalid_items_are_rejected(field: str, value: Any) -> None:
    item = _raw_bank()["questions"][0] | {field: value}
    with pytest.raises(ValidationError):
        QuestionRecord.model_validate(item)


def test_seeding_is_idempotent(database: Database) -> None:
    again = seed_questions(database.questions, database.topics, load_bank())
    assert again["inserted"] == 0 and again["modified"] == 0
    assert database.questions.count_documents({}) == len(load_bank().questions)


def test_seeding_updates_changed_items_without_deleting_others(database: Database, tmp_path: Path) -> None:
    database.questions.insert_one({"question_id": "zzz-001", "note": "added by an operator"})
    data = _raw_bank()
    data["questions"][0]["explanation"] = "An updated explanation."
    stats = seed_questions(database.questions, database.topics, load_bank(_write(tmp_path, data)))
    assert stats == {"inserted": 0, "matched": len(data["questions"]), "modified": 1, "total": len(data["questions"])}
    assert database.questions.find_one({"question_id": "zzz-001"}) is not None


def test_existing_sessions_survive_reseeding(service: AssessmentService) -> None:
    state = service.create(["Algebra", "Geometry"], 10)
    assert state.current_question is not None
    for _ in range(3):
        seed_questions(service.db.questions, service.db.topics, load_bank())
    qid = state.current_question.question_id
    result = service.submit_answer(state.assessment_id, qid, answer_key(service.db, qid))
    assert result.feedback.correct is True
    assert result.assessment.status == "active"


def test_invalid_and_legacy_documents_are_never_served(service: AssessmentService) -> None:
    service.db.questions.delete_many({"topic": "Algebra"})
    service.db.questions.insert_many(
        [
            # Legacy shape from the previous version: no `active` flag, no IRT parameters.
            {"question_id": "9f0c", "question_text": "Old", "options": ["1"], "topic": "Algebra"},
            # Active but with impossible parameters.
            {
                "question_id": "alg-900",
                "topic": "Algebra",
                "stem": "Broken item",
                "options": ["1", "2"],
                "answer_index": 0,
                "explanation": "None given",
                "a": -1,
                "b": 0,
                "tags": [],
                "active": True,
            },
        ]
    )
    with pytest.raises(Exception, match="No questions are available"):
        service.create(["Algebra"], 10)


def test_seed_cli_check_mode(capsys: pytest.CaptureFixture[str]) -> None:
    assert seed_main(["--check"]) == 0
    assert "Validated" in capsys.readouterr().out


def test_seed_cli_reports_invalid_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert seed_main(["--file", str(bad), "--check"]) == 1
    assert "invalid" in capsys.readouterr().err
