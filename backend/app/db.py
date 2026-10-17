"""MongoDB connection management and index initialisation."""

from __future__ import annotations

import logging
import threading
from typing import Any

from pymongo import ASCENDING, MongoClient
from pymongo.collection import Collection
from pymongo.database import Database as PyMongoDatabase
from pymongo.errors import PyMongoError

from .config import Settings

logger = logging.getLogger(__name__)

QUESTION_BANK = "question_bank"
TOPICS = "topics"
ASSESSMENTS = "assessments"

Doc = dict[str, Any]


class Database:
    """Owns the MongoClient for the lifetime of the application.

    The client is created lazily: `mongodb+srv://` URIs are resolved through DNS inside the
    MongoClient constructor, so creating it eagerly would crash startup whenever DNS or the
    cluster is unavailable. Lazily, the app starts, health reports the database as down, and
    data endpoints return 503 until the database is reachable.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: MongoClient[Doc] | None = None
        self._indexes_ready = False
        self._lock = threading.Lock()

    def _connect(self) -> MongoClient[Doc]:
        if self._client is None:
            with self._lock:
                if self._client is None:
                    self._client = MongoClient(
                        self._settings.mongodb_uri.get_secret_value(),
                        serverSelectionTimeoutMS=self._settings.mongodb_timeout_ms,
                        connectTimeoutMS=self._settings.mongodb_timeout_ms,
                        tz_aware=True,
                        appname="adaptive-diagnostic-engine",
                    )
        return self._client

    @property
    def _db(self) -> PyMongoDatabase[Doc]:
        return self._connect()[self._settings.db_name]

    @property
    def questions(self) -> Collection[Doc]:
        return self._db[QUESTION_BANK]

    @property
    def topics(self) -> Collection[Doc]:
        return self._db[TOPICS]

    @property
    def assessments(self) -> Collection[Doc]:
        return self._db[ASSESSMENTS]

    def ping(self) -> bool:
        try:
            self._connect().admin.command("ping")
        except PyMongoError:
            return False
        return True

    def ensure_indexes(self) -> None:
        """Create indexes once per process. Safe to call repeatedly; raises if the DB is down."""
        if self._indexes_ready:
            return
        questions, topics, assessments = self.questions, self.topics, self.assessments
        with self._lock:
            if self._indexes_ready:
                return
            questions.create_index([("question_id", ASCENDING)], unique=True)
            questions.create_index([("active", ASCENDING), ("topic", ASCENDING)])
            topics.create_index([("name", ASCENDING)], unique=True)
            assessments.create_index([("status", ASCENDING), ("expires_at", ASCENDING)])
            self._indexes_ready = True
            logger.info("MongoDB indexes verified")

    def drop_database(self) -> None:
        """Used by the test suite only."""
        self._connect().drop_database(self._settings.db_name)

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
