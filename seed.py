from database import questions_collection
import uuid

questions = [
    {"question_id": str(uuid.uuid4()), "question_text": "What is the value of x if 2x + 5 = 15?", "options": ["3", "5", "7", "10"], "correct_answer": "5", "difficulty": 0.2, "topic": "Algebra", "tags": ["linear equations", "basic"]},
    {"question_id": str(uuid.uuid4()), "question_text": "If a train travels 60 miles in 1.5 hours, what is its speed?", "options": ["30 mph", "40 mph", "45 mph", "90 mph"], "correct_answer": "40 mph", "difficulty": 0.3, "topic": "Algebra", "tags": ["speed", "rate"]},
    {"question_id": str(uuid.uuid4()), "question_text": "What is the area of a circle with radius 7?", "options": ["49π", "14π", "7π", "21π"], "correct_answer": "49π", "difficulty": 0.3, "topic": "Geometry", "tags": ["circle", "area"]},
    {"question_id": str(uuid.uuid4()), "question_text": "Which word is closest in meaning to 'BENEVOLENT'?", "options": ["Cruel", "Kind", "Angry", "Lazy"], "correct_answer": "Kind", "difficulty": 0.2, "topic": "Vocabulary", "tags": ["synonyms", "basic"]},
    {"question_id": str(uuid.uuid4()), "question_text": "Solve: 3x² - 12 = 0", "options": ["x=2", "x=±2", "x=4", "x=±4"], "correct_answer": "x=±2", "difficulty": 0.5, "topic": "Algebra", "tags": ["quadratic", "intermediate"]},
    {"question_id": str(uuid.uuid4()), "question_text": "What is the sum of interior angles of a hexagon?", "options": ["540°", "620°", "720°", "360°"], "correct_answer": "720°", "difficulty": 0.5, "topic": "Geometry", "tags": ["polygons", "angles"]},
    {"question_id": str(uuid.uuid4()), "question_text": "Which word is closest in meaning to 'EPHEMERAL'?", "options": ["Permanent", "Temporary", "Ancient", "Solid"], "correct_answer": "Temporary", "difficulty": 0.5, "topic": "Vocabulary", "tags": ["synonyms", "intermediate"]},
    {"question_id": str(uuid.uuid4()), "question_text": "If f(x) = x² + 3x, what is f(4)?", "options": ["28", "24", "20", "16"], "correct_answer": "28", "difficulty": 0.4, "topic": "Algebra", "tags": ["functions", "substitution"]},
    {"question_id": str(uuid.uuid4()), "question_text": "A rectangle has perimeter 40 and length 12. What is its width?", "options": ["6", "7", "8", "10"], "correct_answer": "8", "difficulty": 0.3, "topic": "Geometry", "tags": ["perimeter", "rectangle"]},
    {"question_id": str(uuid.uuid4()), "question_text": "Which word is closest in meaning to 'LOQUACIOUS'?", "options": ["Silent", "Talkative", "Aggressive", "Timid"], "correct_answer": "Talkative", "difficulty": 0.4, "topic": "Vocabulary", "tags": ["synonyms"]},
    {"question_id": str(uuid.uuid4()), "question_text": "What is the slope of the line passing through (2,3) and (4,7)?", "options": ["1", "2", "3", "4"], "correct_answer": "2", "difficulty": 0.5, "topic": "Algebra", "tags": ["slope", "coordinate geometry"]},
    {"question_id": str(uuid.uuid4()), "question_text": "Solve: log₂(64) = ?", "options": ["4", "5", "6", "8"], "correct_answer": "6", "difficulty": 0.6, "topic": "Algebra", "tags": ["logarithms", "advanced"]},
    {"question_id": str(uuid.uuid4()), "question_text": "Which word is closest in meaning to 'PERFIDIOUS'?", "options": ["Loyal", "Treacherous", "Brave", "Humble"], "correct_answer": "Treacherous", "difficulty": 0.7, "topic": "Vocabulary", "tags": ["synonyms", "advanced"]},
    {"question_id": str(uuid.uuid4()), "question_text": "What is the volume of a sphere with radius 3?", "options": ["36π", "12π", "9π", "27π"], "correct_answer": "36π", "difficulty": 0.6, "topic": "Geometry", "tags": ["sphere", "volume"]},
    {"question_id": str(uuid.uuid4()), "question_text": "If 5x - 3y = 10 and x = 2, what is y?", "options": ["0", "1", "2", "3"], "correct_answer": "0", "difficulty": 0.4, "topic": "Algebra", "tags": ["substitution", "linear"]},
    {"question_id": str(uuid.uuid4()), "question_text": "What is the probability of rolling an even number on a die?", "options": ["1/6", "1/3", "1/2", "2/3"], "correct_answer": "1/2", "difficulty": 0.3, "topic": "Statistics", "tags": ["probability", "basic"]},
    {"question_id": str(uuid.uuid4()), "question_text": "Which word is closest in meaning to 'OBFUSCATE'?", "options": ["Clarify", "Confuse", "Simplify", "Illuminate"], "correct_answer": "Confuse", "difficulty": 0.8, "topic": "Vocabulary", "tags": ["synonyms", "hard"]},
    {"question_id": str(uuid.uuid4()), "question_text": "Find the determinant of [[2,3],[1,4]]", "options": ["5", "8", "11", "14"], "correct_answer": "5", "difficulty": 0.8, "topic": "Algebra", "tags": ["matrices", "hard"]},
    {"question_id": str(uuid.uuid4()), "question_text": "What is the standard deviation concept used to measure?", "options": ["Central tendency", "Data spread", "Sample size", "Correlation"], "correct_answer": "Data spread", "difficulty": 0.6, "topic": "Statistics", "tags": ["statistics", "intermediate"]},
    {"question_id": str(uuid.uuid4()), "question_text": "In a right triangle, if one angle is 30°, what is the other non-right angle?", "options": ["30°", "45°", "60°", "90°"], "correct_answer": "60°", "difficulty": 0.2, "topic": "Geometry", "tags": ["triangles", "angles", "basic"]},
]

def seed():
    questions_collection.drop()
    questions_collection.insert_many(questions)
    print(f"Seeded {len(questions)} questions successfully!")

if __name__ == "__main__":
    seed()