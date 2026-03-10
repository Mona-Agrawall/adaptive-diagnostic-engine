import requests

BASE = "http://127.0.0.1:8000"
session_id = "531bc31a-2121-4996-8915-bbfd36f8ed83"

for i in range(9):
    q = requests.get(f"{BASE}/next-question", params={"session_id": session_id}).json()
    if "error" in q or "detail" in q:
        print("Done or error:", q)
        break
    print(f"Q{i+2}: {q['question_text']} -> Answering: {q['options'][0]}")
    ans = requests.post(f"{BASE}/submit-answer", json={
        "session_id": session_id,
        "question_id": q["question_id"],
        "answer": q["options"][0]
    }).json()
    print(f"Result: correct={ans['correct']}, ability={ans['new_ability_score']}, completed={ans['completed']}")
    if ans["completed"]:
        break

print("Done! Now call /study-plan")