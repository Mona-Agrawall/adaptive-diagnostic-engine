"""Assessment lifecycle: creation, serving, grading, adaptive updates, and results.

Concurrency model: every state transition is a single `update_one` on the assessment document,
filtered by the expected `version`, `status` and current question. If two requests race, exactly
one matches; the other receives a 409 and the document is never partially updated.
"""

from __future__ import annotations

import logging
import random
import uuid
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import ValidationError

from . import irt
from .config import Settings
from .db import Database, Doc
from .errors import ConflictError, GoneError, NotFoundError, UnprocessableError
from .question_bank import QuestionRecord
from .schemas import (
    AbilitySummary,
    AnswerFeedback,
    AnswerResponse,
    AssessmentState,
    Progress,
    ResultsResponse,
    ReviewItem,
    ServedQuestion,
    StudyPlan,
    TopicInfo,
    TopicResult,
    TrajectoryPoint,
)
from .selection import Candidate, StopReason, select_next_item, stop_reason

logger = logging.getLogger(__name__)

MIN_TOPIC_ITEMS_FOR_ESTIMATE = 3
MODEL_NOTICE = (
    "Ability is estimated with a 2PL item response model using provisional, uncalibrated item "
    "parameters. Treat the estimate and interval as a diagnostic indication, not an official score."
)

Clock = Callable[[], datetime]


def to_mongo_precision(value: datetime) -> datetime:
    """Truncate to milliseconds, the precision MongoDB stores, so responses match later reads."""
    return value.replace(microsecond=value.microsecond // 1000 * 1000)


def utc_now() -> datetime:
    return to_mongo_precision(datetime.now(UTC))


class AssessmentService:
    def __init__(
        self,
        db: Database,
        settings: Settings,
        *,
        rng: random.Random | None = None,
        clock: Clock = utc_now,
    ) -> None:
        self.db = db
        self.settings = settings
        self.rng = rng or random.SystemRandom()
        self.clock = clock

    # ----- question bank -----

    def list_topics(self) -> list[TopicInfo]:
        counts = {
            row["_id"]: row["count"]
            for row in self.db.questions.aggregate(
                [{"$match": {"active": True}}, {"$group": {"_id": "$topic", "count": {"$sum": 1}}}]
            )
        }
        topics = [
            TopicInfo(name=doc["name"], description=doc.get("description", ""), question_count=counts[doc["name"]])
            for doc in self.db.topics.find({}, {"_id": 0})
            if counts.get(doc["name"], 0) > 0
        ]
        return sorted(topics, key=lambda topic: topic.name)

    def _load_candidates(self, topics: Sequence[str], exclude: Sequence[str]) -> list[QuestionRecord]:
        cursor = self.db.questions.find(
            {"active": True, "topic": {"$in": list(topics)}, "question_id": {"$nin": list(exclude)}},
            {"_id": 0, "created_at": 0},
        )
        records: list[QuestionRecord] = []
        for doc in cursor:
            try:
                records.append(QuestionRecord.model_validate(doc))
            except ValidationError:
                logger.warning("Skipping invalid question document %s", doc.get("question_id", "<unknown>"))
        return records

    def _pick(
        self, theta: float, records: Sequence[QuestionRecord], administered_topics: Sequence[str], topics: Sequence[str]
    ) -> QuestionRecord | None:
        by_id = {record.question_id: record for record in records}
        chosen = select_next_item(
            theta,
            [Candidate(r.question_id, r.topic, r.params) for r in records],
            administered_topics,
            topics,
            self.rng,
        )
        return by_id[chosen.question_id] if chosen else None

    def _serve_snapshot(self, record: QuestionRecord, position: int, now: datetime) -> Doc:
        return {
            "question_id": record.question_id,
            "position": position,
            "topic": record.topic,
            "stem": record.stem,
            "options": record.options,
            "answer_index": record.answer_index,
            "explanation": record.explanation,
            "tags": record.tags,
            "a": record.a,
            "b": record.b,
            "served_at": now,
        }

    # ----- lifecycle -----

    def create(self, topics: list[str], max_questions: int) -> AssessmentState:
        available = {topic.name for topic in self.list_topics()}
        unknown = [topic for topic in topics if topic not in available]
        if unknown:
            raise UnprocessableError(f"Unknown or empty topic(s): {', '.join(unknown)}", code="unknown_topic")
        now = self.clock()
        first = self._pick(0.0, self._load_candidates(topics, []), [], topics)
        if first is None:
            raise UnprocessableError("No questions are available for the selected topics.", code="no_questions")
        doc: Doc = {
            "_id": uuid.uuid4().hex,
            "status": "active",
            "topics": topics,
            "max_questions": max_questions,
            "min_questions": min(self.settings.min_questions, max_questions),
            "se_target": self.settings.se_target,
            "version": 0,
            "theta": 0.0,
            "se": 1.0,
            "responses": [],
            "current": self._serve_snapshot(first, 1, now),
            "stop_reason": None,
            "created_at": now,
            "updated_at": now,
            "completed_at": None,
            "expires_at": now + timedelta(minutes=self.settings.assessment_ttl_minutes),
            "study_plan": None,
            "study_plan_ai_attempts": 0,
        }
        self.db.assessments.insert_one(doc)
        return self._state(doc)

    def _get(self, assessment_id: str) -> Doc:
        doc = self.db.assessments.find_one({"_id": assessment_id})
        if doc is None:
            raise NotFoundError("Assessment not found.", code="assessment_not_found")
        if doc["status"] == "active" and doc["expires_at"] <= self.clock():
            self.db.assessments.update_one(
                {"_id": assessment_id, "status": "active", "version": doc["version"]},
                {"$set": {"status": "expired", "current": None}, "$inc": {"version": 1}},
            )
            refreshed = self.db.assessments.find_one({"_id": assessment_id})
            assert refreshed is not None
            doc = refreshed
        return doc

    def get_state(self, assessment_id: str) -> AssessmentState:
        return self._state(self._get(assessment_id))

    def submit_answer(self, assessment_id: str, question_id: str, option_index: int) -> AnswerResponse:
        doc = self._get(assessment_id)
        self._require_active(doc)
        current = doc["current"]
        answered_ids = [r["question_id"] for r in doc["responses"]]
        if current is None or question_id != current["question_id"]:
            if question_id in answered_ids:
                raise ConflictError("This question has already been answered.", code="already_answered")
            raise ConflictError(
                "This question is not the current question for the assessment.", code="question_not_current"
            )
        if option_index >= len(current["options"]):
            raise UnprocessableError("The selected option does not exist for this question.", code="invalid_option")

        now = self.clock()
        correct = option_index == current["answer_index"]
        responses = [irt.Response(irt.ItemParams(r["a"], r["b"]), r["correct"]) for r in doc["responses"]] + [
            irt.Response(irt.ItemParams(current["a"], current["b"]), correct)
        ]
        estimate = irt.estimate_ability(responses)
        response_doc = {
            **{
                key: current[key]
                for key in (
                    "question_id",
                    "position",
                    "topic",
                    "stem",
                    "options",
                    "answer_index",
                    "explanation",
                    "tags",
                    "a",
                    "b",
                    "served_at",
                )
            },
            "selected_index": option_index,
            "correct": correct,
            "answered_at": now,
            "theta_after": estimate.theta,
            "se_after": estimate.se,
        }

        administered = [*answered_ids, question_id]
        candidates = self._load_candidates(doc["topics"], administered)
        reason = stop_reason(
            answered=len(administered),
            se=estimate.se,
            remaining_items=len(candidates),
            min_questions=doc["min_questions"],
            max_questions=doc["max_questions"],
            se_target=doc["se_target"],
        )
        next_snapshot: Doc | None = None
        if reason is None:
            administered_topics = [r["topic"] for r in doc["responses"]] + [current["topic"]]
            next_record = self._pick(estimate.theta, candidates, administered_topics, doc["topics"])
            if next_record is None:
                reason = StopReason.ITEM_BANK_EXHAUSTED
            else:
                next_snapshot = self._serve_snapshot(next_record, len(administered) + 1, now)

        update: dict[str, Any] = {
            "$set": {
                "theta": estimate.theta,
                "se": estimate.se,
                "current": next_snapshot,
                "updated_at": now,
                "expires_at": now + timedelta(minutes=self.settings.assessment_ttl_minutes),
                **(
                    {"status": "completed", "stop_reason": str(reason), "completed_at": now}
                    if reason is not None
                    else {}
                ),
            },
            "$push": {"responses": response_doc},
            "$inc": {"version": 1},
        }
        result = self.db.assessments.update_one(
            {
                "_id": assessment_id,
                "version": doc["version"],
                "status": "active",
                "current.question_id": question_id,
            },
            update,
        )
        if result.matched_count != 1:
            latest = self._get(assessment_id)
            if any(r["question_id"] == question_id for r in latest["responses"]):
                raise ConflictError("This question has already been answered.", code="already_answered")
            self._require_active(latest)
            raise ConflictError("The assessment changed while this answer was processed. Reload and retry.")

        saved = self.db.assessments.find_one({"_id": assessment_id})
        assert saved is not None
        return AnswerResponse(
            feedback=AnswerFeedback(
                question_id=question_id,
                correct=correct,
                selected_index=option_index,
                correct_index=current["answer_index"],
                explanation=current["explanation"],
            ),
            assessment=self._state(saved),
        )

    @staticmethod
    def _require_active(doc: Doc) -> None:
        if doc["status"] == "completed":
            raise ConflictError("This assessment is already complete.", code="assessment_completed")
        if doc["status"] == "expired":
            raise GoneError("This assessment expired due to inactivity. Start a new one.", code="assessment_expired")

    # ----- views -----

    def _state(self, doc: Doc) -> AssessmentState:
        current = doc.get("current")
        return AssessmentState(
            assessment_id=doc["_id"],
            status=doc["status"],
            topics=doc["topics"],
            progress=Progress(
                answered=len(doc["responses"]),
                max_questions=doc["max_questions"],
                min_questions=doc["min_questions"],
            ),
            current_question=ServedQuestion(
                question_id=current["question_id"],
                position=current["position"],
                topic=current["topic"],
                stem=current["stem"],
                options=current["options"],
            )
            if current and doc["status"] == "active"
            else None,
            stop_reason=doc.get("stop_reason"),
            created_at=doc["created_at"],
            updated_at=doc["updated_at"],
            completed_at=doc.get("completed_at"),
            expires_at=doc["expires_at"] if doc["status"] == "active" else None,
        )

    def get_completed(self, assessment_id: str) -> Doc:
        doc = self._get(assessment_id)
        if doc["status"] == "expired":
            raise GoneError("This assessment expired before it was completed.", code="assessment_expired")
        if doc["status"] != "completed":
            raise ConflictError("Finish the assessment to see results.", code="assessment_not_completed")
        return doc

    def results(self, assessment_id: str) -> ResultsResponse:
        return build_results(self.get_completed(assessment_id))

    def save_study_plan(self, assessment_id: str, plan: StudyPlan) -> StudyPlan:
        plan = plan.model_copy(update={"generated_at": to_mongo_precision(plan.generated_at)})
        self.db.assessments.update_one(
            {"_id": assessment_id, "status": "completed"},
            {"$set": {"study_plan": plan.model_dump(mode="python")}},
        )
        return plan

    def reserve_ai_attempt(self, assessment_id: str) -> bool:
        """Atomically consume one AI attempt; False once the per-assessment budget is spent."""
        result = self.db.assessments.update_one(
            {
                "_id": assessment_id,
                "status": "completed",
                "study_plan_ai_attempts": {"$lt": self.settings.study_plan_max_ai_attempts},
            },
            {"$inc": {"study_plan_ai_attempts": 1}},
        )
        return result.modified_count == 1


def _ability(theta: float, se: float) -> AbilitySummary:
    estimate = irt.AbilityEstimate(theta, se)
    low, high = estimate.ci95
    band, description = irt.ability_band(theta)
    return AbilitySummary(
        theta=theta, se=se, ci95_low=round(low, 3), ci95_high=round(high, 3), band=band, band_description=description
    )


def build_results(doc: Doc) -> ResultsResponse:
    responses = doc["responses"]
    correct_total = sum(1 for r in responses if r["correct"])
    topic_results: list[TopicResult] = []
    for topic in doc["topics"]:
        items = [r for r in responses if r["topic"] == topic]
        estimate = irt.estimate_ability([irt.Response(irt.ItemParams(r["a"], r["b"]), r["correct"]) for r in items])
        correct = sum(1 for r in items if r["correct"])
        topic_results.append(
            TopicResult(
                topic=topic,
                answered=len(items),
                correct=correct,
                accuracy=round(correct / len(items), 4) if items else 0.0,
                theta=estimate.theta,
                se=estimate.se,
                sufficient_data=len(items) >= MIN_TOPIC_ITEMS_FOR_ESTIMATE,
            )
        )
    trajectory = [TrajectoryPoint(position=0, theta=0.0, se=1.0)] + [
        TrajectoryPoint(position=r["position"], theta=r["theta_after"], se=r["se_after"]) for r in responses
    ]
    review = [
        ReviewItem(
            position=r["position"],
            question_id=r["question_id"],
            topic=r["topic"],
            stem=r["stem"],
            options=r["options"],
            selected_index=r["selected_index"],
            correct_index=r["answer_index"],
            correct=r["correct"],
            explanation=r["explanation"],
            tags=r.get("tags", []),
            time_seconds=round((r["answered_at"] - r["served_at"]).total_seconds(), 1),
        )
        for r in responses
    ]
    plan = doc.get("study_plan")
    return ResultsResponse(
        assessment_id=doc["_id"],
        status=doc["status"],
        topics=doc["topics"],
        stop_reason=doc.get("stop_reason"),
        created_at=doc["created_at"],
        completed_at=doc.get("completed_at"),
        ability=_ability(doc["theta"], doc["se"]),
        answered=len(responses),
        correct=correct_total,
        accuracy=round(correct_total / len(responses), 4) if responses else 0.0,
        topic_results=topic_results,
        trajectory=trajectory,
        review=review,
        study_plan=StudyPlan.model_validate(plan) if plan else None,
        model_notice=MODEL_NOTICE,
    )
