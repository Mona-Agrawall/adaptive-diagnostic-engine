from database import questions_collection, sessions_collection
import math
import uuid

def create_session() -> dict:
    session = {
        "session_id": str(uuid.uuid4()),
        "ability_score": 0.5,
        "questions_asked": [],
        "correct_answers": 0,
        "incorrect_answers": 0,
        "topics_missed": [],
        "completed": False
    }
    sessions_collection.insert_one(session)
    return session

def get_session(session_id: str) -> dict:
    return sessions_collection.find_one({"session_id": session_id}, {"_id": 0})

def get_next_question(session: dict) -> dict:
    ability = session["ability_score"]
    asked = session["questions_asked"]

    # Find question closest in difficulty to current ability score
    pipeline = [
        {"$match": {"question_id": {"$nin": asked}}},
        {"$addFields": {"diff_score": {"$abs": {"$subtract": ["$difficulty", ability]}}}},
        {"$sort": {"diff_score": 1}},
        {"$limit": 1},
        {"$project": {"_id": 0, "correct_answer": 0}}
    ]
    result = list(questions_collection.aggregate(pipeline))
    return result[0] if result else None

def update_ability(ability: float, difficulty: float, correct: bool) -> float:
    # IRT-inspired update: shift ability toward or away from difficulty
    learning_rate = 0.1
    if correct:
        ability += learning_rate * (1 - ability) * difficulty
    else:
        ability -= learning_rate * ability * (1 - difficulty)
    return round(max(0.1, min(1.0, ability)), 4)

def submit_answer(session_id: str, question_id: str, answer: str) -> dict:
    session = get_session(session_id)
    if not session or session["completed"]:
        return {"error": "Session not found or already completed"}

    question = questions_collection.find_one({"question_id": question_id}, {"_id": 0})
    if not question:
        return {"error": "Question not found"}

    correct = answer.strip().lower() == question["correct_answer"].strip().lower()
    new_ability = update_ability(session["ability_score"], question["difficulty"], correct)

    update_data = {
        "ability_score": new_ability,
        "questions_asked": session["questions_asked"] + [question_id],
        "correct_answers": session["correct_answers"] + (1 if correct else 0),
        "incorrect_answers": session["incorrect_answers"] + (0 if correct else 1),
    }

    if not correct and question["topic"] not in session["topics_missed"]:
        update_data["topics_missed"] = session["topics_missed"] + [question["topic"]]

    total_asked = len(update_data["questions_asked"])
    if total_asked >= 10:
        update_data["completed"] = True

    sessions_collection.update_one({"session_id": session_id}, {"$set": update_data})

    return {
        "correct": correct,
        "correct_answer": question["correct_answer"],
        "new_ability_score": new_ability,
        "completed": update_data.get("completed", False)
    }