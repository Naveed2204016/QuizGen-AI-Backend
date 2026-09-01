import json

from app.clients.groq import get_groq_client
from app.core.config import get_settings
from app.prompts.answer_evaluation import SYSTEM_PROMPT, build_evaluation_prompt
from app.services.embeddings import cosine_similarity, embed_texts


def evaluate_answers(questions: list[dict], submitted: dict[str, str]) -> list[dict]:
    short_items: list[dict] = []
    for question in questions:
        if question["type"] == "short":
            short_items.append(
                {
                    "question_id": question["id"],
                    "question": question["question"],
                    "user_answer": submitted.get(question["id"], "").strip(),
                    "correct_answer": question["correct_answer"],
                    "source_text": question["source_text"],
                }
            )

    factual_by_id: dict[str, dict] = {}
    if short_items:
        response = get_groq_client().chat.completions.create(
            model=get_settings().groq_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_evaluation_prompt(short_items)},
            ],
            response_format={"type": "json_object"},
            temperature=0,
            max_completion_tokens=1800,
        )
        parsed = json.loads(response.choices[0].message.content or "{}")
        factual_by_id = {item["question_id"]: item for item in parsed.get("evaluations", [])}

    results: list[dict] = []
    for question in questions:
        answer = submitted.get(question["id"], "").strip()
        if question["type"] == "mcq":
            score = 1.0 if answer == question["correct_answer"] else 0.0
            semantic = score
            factual = score
            feedback = "Correct." if score else "Review the explanation and cited source."
        else:
            if answer:
                vectors = embed_texts([answer, question["correct_answer"]])
                semantic = max(0.0, min(1.0, cosine_similarity(vectors[0], vectors[1])))
                evaluation = factual_by_id.get(question["id"], {})
                factual = max(0.0, min(1.0, float(evaluation.get("factual_score", 0))))
                score = 0.35 * semantic + 0.65 * factual
                feedback = evaluation.get("feedback", "Answer evaluated against the source.")
            else:
                semantic = factual = score = 0.0
                feedback = "Not answered."
        results.append(
            {
                "question_id": question["id"],
                "type": question["type"],
                "question": question["question"],
                "options": question.get("options"),
                "user_answer": answer,
                "correct_answer": question["correct_answer"],
                "explanation": question["explanation"],
                "source": question["source"],
                "semantic_score": round(semantic, 3),
                "factual_score": round(factual, 3),
                "awarded_marks": round(score, 2),
                "max_marks": 1,
                "correct": score >= 0.7,
                "feedback": feedback,
            }
        )
    return results
