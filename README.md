<div align="center">

<br/>

```
 █████╗ ██████╗  █████╗ ██████╗ ████████╗██╗██╗   ██╗███████╗
██╔══██╗██╔══██╗██╔══██╗██╔══██╗╚══██╔══╝██║██║   ██║██╔════╝
███████║██║  ██║███████║██████╔╝   ██║   ██║██║   ██║█████╗  
██╔══██║██║  ██║██╔══██║██╔═══╝    ██║   ██║╚██╗ ██╔╝██╔══╝  
██║  ██║██████╔╝██║  ██║██║        ██║   ██║ ╚████╔╝ ███████╗
╚═╝  ╚═╝╚═════╝ ╚═╝  ╚═╝╚═╝        ╚═╝   ╚═╝  ╚═══╝  ╚══════╝
```

# Adaptive Diagnostic Engine

### *AI-powered GRE prep that learns as you learn*

<br/>

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![MongoDB](https://img.shields.io/badge/MongoDB_Atlas-47A248?style=for-the-badge&logo=mongodb&logoColor=white)](https://www.mongodb.com/atlas)
[![Groq](https://img.shields.io/badge/Groq_LLaMA_3.3_70B-F55036?style=for-the-badge&logo=meta&logoColor=white)](https://groq.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)

<br/>

> A fully adaptive GRE diagnostic system that estimates your current ability level in real time, selects questions tailored to your skill, and generates a personalized study plan — powered by Item Response Theory and LLaMA 3.3.

<br/>

---

</div>

<br/>

## ✦ What is This?

The **Adaptive Diagnostic Engine** is an intelligent GRE preparation backend built around **1-Dimensional Item Response Theory (IRT)**. Instead of serving students a fixed set of questions, it continuously estimates a student's ability level and selects the *next best question* — always calibrated to be just challenging enough.

After 10 questions, it hands your session data to **Groq's LLaMA 3.3 70B** model to generate a concise, actionable 3-step study plan targeting your exact weak spots.

<br/>

---

## ⚙️ Tech Stack

| Layer | Technology |
|-------|------------|
| 🐍 **Backend** | Python · FastAPI |
| 🗄️ **Database** | MongoDB Atlas |
| 📐 **Algorithm** | IRT-inspired 1D Ability Estimation |
| 🤖 **AI Model** | Groq API · LLaMA 3.3 70B |

<br/>

---

## 🔄 System Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│   1. Student starts session      →   ability initialized at 0.5    │
│                                                                     │
│   2. System selects question     →   difficulty ≈ current ability  │
│                                                                     │
│   3. Student answers             →   ability score updates         │
│                                                                     │
│   4. Repeat for 10 questions     →   session marked complete       │
│                                                                     │
│   5. LLM generates study plan    →   personalized 3-step roadmap   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

<br/>

---

## 🚀 Setup & Installation

### 1 · Clone the repository

```bash
git clone https://github.com/Mona-Agrawall/adaptive-diagnostic-engine.git
cd adaptive-diagnostic-engine
```

### 2 · Create and activate a virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3 · Install dependencies

```bash
pip install -r requirements.txt
```

### 4 · Configure environment variables

Create a `.env` file in the root directory:

```env
MONGODB_URI=your_mongodb_connection_string
DB_NAME=adaptive_test
GROQ_API_KEY=your_groq_api_key
```

> **Where to get these:**
> - `MONGODB_URI` → [MongoDB Atlas](https://www.mongodb.com/atlas) — create a free cluster and grab your connection string
> - `GROQ_API_KEY` → [Groq Console](https://console.groq.com) — sign up for a free API key

### 5 · Seed the database

```bash
python seed.py
```

### 6 · Start the server

```bash
uvicorn app:app --reload
```

### 7 · Explore the API docs

Open your browser and visit:

```
http://127.0.0.1:8000/docs
```

FastAPI's interactive Swagger UI will be waiting for you. ✨

<br/>

---

## 📡 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/start-session` | Initialize a new student test session |
| `GET` | `/next-question?session_id=` | Fetch the next adaptively selected question |
| `POST` | `/submit-answer` | Submit an answer and update ability estimate |
| `GET` | `/study-plan?session_id=` | Retrieve AI-generated study plan *(after 10 Qs)* |
| `GET` | `/` | Health check |

<br/>

---

## 🧮 Adaptive Algorithm — How It Works

The engine uses a **1D IRT-inspired adaptive algorithm** to model and update a student's latent ability in real time.

<br/>

**Starting Point**

Every student begins with a neutral baseline:

```
ability₀ = 0.5     (scale: 0.1 → 1.0)
```

<br/>

**Question Selection**

At each step, MongoDB is queried for the question whose difficulty is *closest* to the student's current ability score — using an efficient aggregation pipeline:

```
question = argmin |difficulty - ability|
```

<br/>

**Ability Update Formula**

After each response, the ability score shifts toward the truth:

```
✅ Correct:    ability += 0.1 × (1 - ability) × difficulty
❌ Incorrect:  ability -= 0.1 × ability × (1 - difficulty)
```

This bounded update rule ensures:
- Scores **never exceed** the `[0.1, 1.0]` range
- Progress **converges** naturally — large jumps early, fine-tuning later
- Difficulty and correctness **both influence** the update magnitude

<br/>

**Session Completion**

After **10 questions**, the session is marked complete and the `/study-plan` endpoint becomes available.

<br/>

---

## 🤖 AI-Generated Study Plan

Once a session concludes, the following data is packaged and sent to **Groq's LLaMA 3.3 70B**:

- Final ability score
- Overall accuracy
- Topics where the student answered incorrectly

The model returns a **structured 3-step study plan** that directly targets the student's weak areas — not a generic one-size-fits-all guide.

```
Example output:

  Step 1 → Focus on [Weak Topic A]: practice 20 questions per day
           with emphasis on elimination strategies.

  Step 2 → Review [Weak Topic B] fundamentals using...

  Step 3 → Simulate timed conditions by...
```

<br/>

---

## 🗂️ Project Structure

```
adaptive-diagnostic-engine/
│
├── app.py              # FastAPI application & route definitions
├── adaptive.py         # IRT-based ability estimation logic
├── ai_insights.py      # Groq LLM integration & prompt engineering
├── database.py         # MongoDB Atlas connection & queries
├── models.py           # Pydantic data models
├── seed.py             # Database seeding script
├── test_db.py          # Database connection tests
├── test_run.py         # End-to-end test runner
├── requirements.txt    # Python dependencies
└── .env                # Environment variables (not committed)
```

<br/>

---

<div align="center">

<br/>

**Built with curiosity and caffeine by [Mona Agrawal](https://github.com/Mona-Agrawall)**

<br/>

*If this helped you, consider leaving a ⭐ on the repo!*

<br/>

</div>
