from groq import Groq
from dotenv import load_dotenv
import os

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def generate_study_plan(session: dict) -> str:
    total = session["correct_answers"] + session["incorrect_answers"]
    accuracy = round((session["correct_answers"] / total) * 100, 1) if total > 0 else 0
    topics_missed = session["topics_missed"] if session["topics_missed"] else ["None"]
    ability = session["ability_score"]

    prompt = f"""
    A student just completed an adaptive GRE diagnostic test. Here are their results:

    - Final Ability Score: {ability} (scale 0.1 to 1.0)
    - Total Questions Answered: {total}
    - Correct Answers: {session["correct_answers"]}
    - Incorrect Answers: {session["incorrect_answers"]}
    - Accuracy: {accuracy}%
    - Topics where they made mistakes: {", ".join(topics_missed)}

    Based on this performance, generate a personalized 3-step study plan to help them improve.
    Be specific, practical, and encouraging. Format it clearly as Step 1, Step 2, Step 3.
    """

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content