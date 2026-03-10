from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from adaptive import create_session, get_session, get_next_question, submit_answer
from ai_insights import generate_study_plan

app = FastAPI(title="Adaptive Diagnostic Engine")

class AnswerSubmission(BaseModel):
    session_id: str
    question_id: str
    answer: str

@app.post("/start-session")
def start_session():
    session = create_session()
    return {
        "session_id": session["session_id"],
        "message": "Session started! Call /next-question to get your first question.",
        "ability_score": session["ability_score"]
    }

@app.get("/next-question")
def next_question(session_id: str):
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session["completed"]:
        raise HTTPException(status_code=400, detail="Session completed. Call /study-plan to get your results.")

    question = get_next_question(session)
    if not question:
        raise HTTPException(status_code=404, detail="No more questions available")

    return {
        "question_id": question["question_id"],
        "question_text": question["question_text"],
        "options": question["options"],
        "topic": question["topic"],
        "difficulty": question["difficulty"],
        "current_ability": session["ability_score"]
    }

@app.post("/submit-answer")
def submit(answer: AnswerSubmission):
    result = submit_answer(answer.session_id, answer.question_id, answer.answer)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.get("/study-plan")
def study_plan(session_id: str):
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not session["completed"]:
        raise HTTPException(status_code=400, detail="Complete 10 questions first to get your study plan.")

    plan = generate_study_plan(session)
    return {
        "session_id": session_id,
        "final_ability_score": session["ability_score"],
        "correct_answers": session["correct_answers"],
        "incorrect_answers": session["incorrect_answers"],
        "topics_missed": session["topics_missed"],
        "study_plan": plan
    }

@app.get("/")
def root():
    return {"message": "Adaptive Diagnostic Engine is running!"}