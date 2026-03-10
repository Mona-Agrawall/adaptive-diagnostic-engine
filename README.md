# Adaptive Diagnostic Engine

An AI-driven 1-Dimension Adaptive Testing system for GRE preparation. The system dynamically selects questions based on student performance using Item Response Theory (IRT), and generates a personalized study plan using an LLM.

## Tech Stack

- **Backend:** Python, FastAPI
- **Database:** MongoDB Atlas
- **Adaptive Algorithm:** IRT-inspired 1D ability estimation
- **AI Integration:** Groq API (LLaMA 3.3 70B)

## System Flow
1. User starts a test session
2. Backend estimates ability score
3. System selects next question closest to ability
4. Ability score updates after each response
5. After 10 questions an LLM generates a study plan

## Setup Instructions

### 1. Clone the repository
```bash
git clone https://github.com/Mona-Agrawall/adaptive-diagnostic-engine.git
cd adaptive-diagnostic-engine
```

### 2. Create and activate virtual environment
```bash
python -m venv venv
venv\Scripts\activate  # Windows
```

### 3. Install dependencies
```bash
pip install fastapi uvicorn pymongo python-dotenv groq pydantic
```

### 4. Configure environment variables
Create a `.env` file in the root directory:
```
MONGODB_URI=your_mongodb_connection_string
DB_NAME=adaptive_test
GROQ_API_KEY=your_groq_api_key
```

### 5. Seed the database
```bash
python seed.py
```

### 6. Run the server
```bash
uvicorn app:app --reload
```

### 7. Open API docs
Visit: http://127.0.0.1:8000/docs

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/start-session` | Start a new test session |
| GET | `/next-question?session_id=` | Get next adaptive question |
| POST | `/submit-answer` | Submit answer and update ability score |
| GET | `/study-plan?session_id=` | Get AI-generated study plan (after 10 questions) |
| GET | `/` | Health check |

---

## Adaptive Algorithm

The system uses a **1D IRT-inspired adaptive algorithm**:

1. **Starting Point:** Every student begins with a baseline ability score of `0.5` (on a scale of 0.1 to 1.0).

2. **Question Selection:** For each question, the system queries MongoDB for the question whose difficulty is closest to the student's current ability score using an aggregation pipeline.

3. **Ability Update Formula:**
   - If correct: `ability += 0.1 × (1 - ability) × difficulty`
   - If incorrect: `ability -= 0.1 × ability × (1 - difficulty)`
   - This ensures the score converges and never exceeds bounds.

4. **Session Completion:** After 10 questions, the session is marked complete and the study plan endpoint becomes available.

---

## AI Study Plan

Once a session is completed, the student's performance data (ability score, accuracy, topics missed) is sent to **Groq's LLaMA 3.3 70B model** with a structured prompt. The LLM returns a 3-step personalized study plan targeting the student's specific weak areas.

---

## AI Log

**Tools used:** Claude (claude.ai) for step-by-step guidance throughout the project.

**What AI helped with:**
- Generating the full project structure and all code files
- Debugging MongoDB aggregation pipeline for adaptive question selection
- Switching from deprecated `google-generativeai` to `groq` when Gemini quota was exhausted
- Writing the IRT-inspired ability update formula

**What AI couldn't solve:**
- Gemini free tier quota issues required manual API key management and switching providers entirely
- Model deprecation (llama3-8b-8192) required checking Groq's latest supported models
