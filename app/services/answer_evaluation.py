import json
import logging
import re

from groq import APIError

from app.clients.groq import get_groq_client
from app.core.config import get_settings
from app.prompts.answer_evaluation import SYSTEM_PROMPT, build_evaluation_prompt
from app.services.embeddings import cosine_similarity, embed_texts

logger = logging.getLogger(__name__)
EVALUATION_BATCH_SIZE = 5


def _parse_evaluations(content: str) -> list[dict]:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise
        parsed = json.loads(text[start : end + 1])
    evaluations = parsed.get("evaluations", []) if isinstance(parsed, dict) else []
    if not isinstance(evaluations, list):
        raise ValueError("evaluations must be a list")
    return [item for item in evaluations if isinstance(item, dict)]


def _evaluate_short_batch(items: list[dict]) -> list[dict]:
    request = {
        "model": get_settings().groq_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_evaluation_prompt(items)},
        ],
        "response_format": {"type": "json_object"},
        "reasoning_effort": "none",
        "temperature": 0,
        "max_completion_tokens": 2400,
    }
    try:
        response = get_groq_client().chat.completions.create(**request)
    except APIError:
        request.pop("response_format")
        response = get_groq_client().chat.completions.create(**request)
    return _parse_evaluations(response.choices[0].message.content or "{}")


def _semantic_score(answer: str, reference: str) -> float:
    try:
        vectors = embed_texts([answer, reference])
        return max(0.0, min(1.0, cosine_similarity(vectors[0], vectors[1])))
    except Exception as exc:
        logger.warning("Embedding evaluation failed; using word-overlap fallback: %s", exc)
        answer_words = set(re.findall(r"[a-z0-9]+", answer.casefold()))
        reference_words = set(re.findall(r"[a-z0-9]+", reference.casefold()))
        return len(answer_words & reference_words) / max(1, len(reference_words))


def _score_value(value: object, fallback: float) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return fallback


def evaluate_answers(questions: list[dict], submitted: dict[str, str]) -> list[dict]:
    short_items: list[dict] = []
    for question in questions:
        answer = submitted.get(question["id"], "").strip()
        if question["type"] == "short" and answer:
            short_items.append(
                {
                    "question_id": question["id"],
                    "question": question["question"],
                    "user_answer": answer,
                    "correct_answer": question["correct_answer"],
                    "source_text": question["source_text"],
                }
            )

    factual_by_id: dict[str, dict] = {}
    for start in range(0, len(short_items), EVALUATION_BATCH_SIZE):
        batch = short_items[start : start + EVALUATION_BATCH_SIZE]
        try:
            evaluations = _evaluate_short_batch(batch)
            expected_ids = {item["question_id"] for item in batch}
            for item in evaluations:
                question_id = item.get("question_id")
                if question_id in expected_ids:
                    factual_by_id[question_id] = item
        except (APIError, json.JSONDecodeError, AttributeError, TypeError, ValueError) as exc:
            logger.warning("AI evaluation batch failed; retrying answers individually: %s", exc)
            for item in batch:
                try:
                    for evaluation in _evaluate_short_batch([item]):
                        if evaluation.get("question_id") == item["question_id"]:
                            factual_by_id[item["question_id"]] = evaluation
                            break
                except (
                    APIError,
                    json.JSONDecodeError,
                    AttributeError,
                    TypeError,
                    ValueError,
                ) as item_exc:
                    logger.warning(
                        "AI evaluation failed for question %s; using local fallback: %s",
                        item["question_id"],
                        item_exc,
                    )

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
                semantic = _semantic_score(answer, question["correct_answer"])
                evaluation = factual_by_id.get(question["id"], {})
                if evaluation:
                    factual = _score_value(evaluation.get("factual_score"), semantic)
                    score = 0.35 * semantic + 0.65 * factual
                    feedback = evaluation.get("feedback", "Answer evaluated against the source.")
                else:
                    factual = semantic
                    score = semantic
                    feedback = "AI grading was unavailable; semantic fallback grading was used."
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
