from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import ConfigurationError, Settings, get_settings
from app.main import create_app

from .conftest import TEST_MONGODB_URI, make_settings

ENV_VARS = ("MONGODB_URI", "DB_NAME", "GROQ_API_KEY", "CORS_ORIGINS", "LOG_LEVEL")


@pytest.fixture
def isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    env_file = tmp_path / ".env"
    monkeypatch.setitem(Settings.model_config, "env_file", env_file)
    get_settings.cache_clear()
    yield env_file
    get_settings.cache_clear()


def test_missing_mongodb_uri_gives_a_clear_error(isolated_env: Path) -> None:
    with pytest.raises(ConfigurationError, match=r"MONGODB_URI: Field required.*Copy .env.example"):
        get_settings()


def test_invalid_values_are_reported_without_echoing_secrets(isolated_env: Path) -> None:
    isolated_env.write_text("MONGODB_URI=postgres://user:hunter2@db\nLOG_LEVEL=LOUD\n", encoding="utf-8")
    with pytest.raises(ConfigurationError) as excinfo:
        get_settings()
    message = str(excinfo.value)
    assert "MONGODB_URI" in message and "hunter2" not in message


def test_env_file_is_loaded_and_optional_values_default(isolated_env: Path) -> None:
    isolated_env.write_text(
        f"MONGODB_URI={TEST_MONGODB_URI}\nGROQ_API_KEY=   \nCORS_ORIGINS=http://a.test, http://b.test\n",
        encoding="utf-8",
    )
    settings = get_settings()
    assert settings.groq_api_key is None and settings.ai_enabled is False
    assert settings.cors_origins == ["http://a.test", "http://b.test"]
    assert settings.db_name == "adaptive_diagnostic"


def test_secret_values_are_masked_in_repr() -> None:
    settings = make_settings(groq_api_key="gsk_secret_value")
    assert "gsk_secret_value" not in repr(settings)
    assert settings.ai_enabled


@pytest.mark.parametrize("name", ["bad/name", "has space", "dots.in.name", ""])
def test_invalid_database_names_are_rejected(name: str) -> None:
    with pytest.raises(ValidationError):
        make_settings(db_name=name)


def test_app_starts_without_ai_credentials_and_core_flow_works() -> None:
    settings = make_settings(groq_api_key=None)
    app = create_app(settings)  # default provider wiring, no key
    with TestClient(app) as client:
        assert client.get("/api/health").json()["ai"]["status"] == "not_configured"
        from app.question_bank import load_bank, seed_questions

        seed_questions(app.state.db.questions, app.state.db.topics, load_bank())
        assert client.post("/api/assessments", json={"topics": ["Algebra"]}).status_code == 201
        app.state.db.drop_database()


def test_app_with_ai_key_builds_provider_lazily_without_network() -> None:
    settings = make_settings(groq_api_key="gsk_test_not_real")
    app = create_app(settings)
    with TestClient(app) as client:
        assert client.get("/api/health").json()["ai"]["status"] == "configured"
        app.state.db.drop_database()


def test_seed_on_startup_populates_question_bank() -> None:
    settings = make_settings(seed_on_startup=True)
    app = create_app(settings, use_default_ai_provider=False)
    with TestClient(app) as client:
        assert len(client.get("/api/topics").json()["topics"]) == 5
        app.state.db.drop_database()


def test_frontend_is_served_with_spa_fallback(tmp_path: Path) -> None:
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><title>ADE</title>", encoding="utf-8")
    (tmp_path / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path / "favicon.svg").write_text("<svg/>", encoding="utf-8")
    settings = make_settings(serve_frontend=True, frontend_dist=tmp_path)
    app = create_app(settings, use_default_ai_provider=False)
    with TestClient(app) as client:
        assert "<title>ADE</title>" in client.get("/assessment/abc").text
        assert client.get("/assets/app.js").text == "console.log(1)"
        assert client.get("/favicon.svg").text == "<svg/>"
        assert "<title>ADE</title>" in client.get("/../../etc/passwd").text
        assert client.get("/api/unknown").status_code == 404
