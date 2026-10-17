"""Question bank file format, validation, and idempotent seeding."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pymongo import UpdateOne
from pymongo.collection import Collection

from .irt import A_MAX, A_MIN, B_MAX, B_MIN, ItemParams

DEFAULT_BANK_PATH = Path(__file__).resolve().parents[1] / "data" / "questions.json"
QUESTION_ID_PATTERN = re.compile(r"^[a-z]{3}-\d{3}$")


class QuestionRecord(BaseModel):
    """One item as stored in the bank file and in the `question_bank` collection."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    question_id: str = Field(pattern=QUESTION_ID_PATTERN.pattern)
    topic: str = Field(min_length=1, max_length=60)
    stem: str = Field(min_length=5, max_length=1000)
    options: list[str] = Field(min_length=2, max_length=6)
    answer_index: int = Field(ge=0)
    explanation: str = Field(min_length=5, max_length=1000)
    a: float = Field(ge=A_MIN, le=A_MAX)
    b: float = Field(ge=B_MIN, le=B_MAX)
    tags: list[str] = Field(default_factory=list, max_length=8)
    active: bool = True

    @field_validator("options")
    @classmethod
    def _unique_options(cls, options: list[str]) -> list[str]:
        cleaned = [option.strip() for option in options]
        if any(not option for option in cleaned):
            raise ValueError("options must not be blank")
        if len({option.casefold() for option in cleaned}) != len(cleaned):
            raise ValueError("options must be unique")
        return cleaned

    @model_validator(mode="after")
    def _answer_in_range(self) -> QuestionRecord:
        if self.answer_index >= len(self.options):
            raise ValueError("answer_index is out of range for the options")
        return self

    @property
    def params(self) -> ItemParams:
        return ItemParams(a=self.a, b=self.b)


class QuestionBankFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)
    notes: str = ""
    topics: dict[str, str] = Field(min_length=1)
    questions: list[QuestionRecord] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_consistency(self) -> QuestionBankFile:
        ids = [q.question_id for q in self.questions]
        duplicates = sorted({qid for qid in ids if ids.count(qid) > 1})
        if duplicates:
            raise ValueError(f"duplicate question_id values: {', '.join(duplicates)}")
        unknown = sorted({q.topic for q in self.questions} - set(self.topics))
        if unknown:
            raise ValueError(f"questions reference undeclared topics: {', '.join(unknown)}")
        return self


def load_bank(path: Path = DEFAULT_BANK_PATH) -> QuestionBankFile:
    with path.open(encoding="utf-8") as handle:
        return QuestionBankFile.model_validate(json.load(handle))


def seed_questions(
    questions: Collection[dict[str, Any]],
    topics: Collection[dict[str, Any]],
    bank: QuestionBankFile,
) -> dict[str, int]:
    """Upsert every question and topic by its stable identifier.

    Nothing is deleted. Re-running is a no-op when the file is unchanged, and editing an item
    updates it in place. Assessments keep their own snapshot of every administered item, so
    edits never rewrite history. To retire an item, set `"active": false` in the bank file.
    """
    now = datetime.now(UTC)
    question_ops = [
        UpdateOne(
            {"question_id": record.question_id},
            {"$set": record.model_dump(), "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
        for record in bank.questions
    ]
    topic_ops = [
        UpdateOne({"name": name}, {"$set": {"name": name, "description": description}}, upsert=True)
        for name, description in bank.topics.items()
    ]
    question_result = questions.bulk_write(question_ops, ordered=False)
    topics.bulk_write(topic_ops, ordered=False)
    return {
        "inserted": question_result.upserted_count,
        "matched": question_result.matched_count,
        "modified": question_result.modified_count,
        "total": len(bank.questions),
    }
