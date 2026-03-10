from pydantic import BaseModel
from typing import List, Optional

class Question(BaseModel):
    question_id: str
    question_text: str
    options: List[str]
    correct_answer: str
    difficulty: float
    topic: str
    tags: List[str]

class UserSession(BaseModel):
    session_id: str
    ability_score: float = 0.5
    questions_asked: List[str] = []
    correct_answers: int = 0
    incorrect_answers: int = 0
    topics_missed: List[str] = []
    completed: bool = False