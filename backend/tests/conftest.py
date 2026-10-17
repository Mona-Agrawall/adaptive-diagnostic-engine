"""Shared fixtures.

Integration tests run against a real MongoDB server (default mongodb://localhost:27017, override
with TEST_MONGODB_URI). Every test session uses a throwaway database named `ade_test_<random>`
that is dropped afterwards, so no real data is touched and no production credentials are needed.
"""

from __future__ import annotations

import os
import random
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pymongo import MongoClient
from pymongo.errors import PyMongoError

from app.assessment import AssessmentService
from app.config import Settings
from app.db import Database
from app.main import create_app
from app.question_bank import load_bank, seed_questions
from app.study_plan import StudyPlanProvider

TEST_MONGODB_URI = os.environ.get("TEST_MONGODB_URI", "mongodb://localhost:27017")
# Every database created by this test session shares this prefix and is dropped at the end.
SESSION_PREFIX = f"ade_test_{uuid.uuid4().hex[:6]}_"


def make_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "mongodb_uri": TEST_MONGODB_URI,
        "db_name": f"{SESSION_PREFIX}{uuid.uuid4().hex[:8]}",
        "groq_api_key": None,
        "serve_frontend": False,
        "mongodb_timeout_ms": 3000,
        "cors_origins": [],
        "rate_limit_create_per_minute": 10_000,
        "rate_limit_answer_per_minute": 10_000,
        "rate_limit_study_plan_per_minute": 1000,
        "log_level": "WARNING",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.fixture(scope="session", autouse=True)
def _require_mongodb() -> Iterator[None]:
    client: MongoClient[dict[str, Any]] = MongoClient(TEST_MONGODB_URI, serverSelectionTimeoutMS=3000)
    try:
        client.admin.command("ping")
    except PyMongoError as exc:
        client.close()
        pytest.exit(
            f"MongoDB is required for the test suite but {TEST_MONGODB_URI} is unreachable "
            f"({type(exc).__name__}). Start MongoDB or set TEST_MONGODB_URI.",
            returncode=2,
        )
    try:
        yield
    finally:
        for name in client.list_database_names():
            if name.startswith(SESSION_PREFIX):
                client.drop_database(name)
        client.close()


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def settings() -> Settings:
    return make_settings()


@pytest.fixture
def database(settings: Settings) -> Iterator[Database]:
    db = Database(settings)
    db.ensure_indexes()
    seed_questions(db.questions, db.topics, load_bank())
    try:
        yield db
    finally:
        db.drop_database()
        db.close()


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def service(database: Database, settings: Settings, clock: Clock) -> AssessmentService:
    return AssessmentService(database, settings, rng=random.Random(7), clock=clock)


def build_client(settings: Settings, provider: StudyPlanProvider | None = None, *, seed: bool = True) -> TestClient:
    app = create_app(settings, ai_provider=provider, use_default_ai_provider=False, rng=random.Random(11))
    client = TestClient(app)
    client.__enter__()
    if seed:
        db: Database = app.state.db
        seed_questions(db.questions, db.topics, load_bank())
    return client


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    test_client = build_client(settings)
    try:
        yield test_client
    finally:
        test_client.app.state.db.drop_database()  # type: ignore[attr-defined]
        test_client.__exit__(None, None, None)


def answer_key(db: Database, question_id: str) -> int:
    doc = db.questions.find_one({"question_id": question_id})
    assert doc is not None
    return int(doc["answer_index"])


def wrong_option(db: Database, question_id: str) -> int:
    # Every item has at least four options, so this index always exists and is never the key.
    return (answer_key(db, question_id) + 1) % 4


def run_to_completion(client: TestClient, assessment: dict[str, Any], *, correct: bool = True) -> dict[str, Any]:
    db: Database = client.app.state.db  # type: ignore[attr-defined]
    state = assessment
    while state["status"] == "active":
        qid = state["current_question"]["question_id"]
        option = answer_key(db, qid) if correct else wrong_option(db, qid)
        response = client.post(
            f"/api/assessments/{state['assessment_id']}/answers", json={"question_id": qid, "option_index": option}
        )
        assert response.status_code == 200, response.text
        state = response.json()["assessment"]
    return state
