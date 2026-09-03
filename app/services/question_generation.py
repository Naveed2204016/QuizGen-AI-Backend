import json
import logging
import math
import re
from uuid import uuid4

from fastapi import HTTPException
from groq import APIError, BadRequestError

from app.clients.groq import get_groq_client
from app.core.config import get_settings
from app.prompts.question_generation import SYSTEM_PROMPT, build_generation_prompt
from app.services.duplicate_detection import filter_duplicates

logger = logging.getLogger(__name__)
GENERATION_BATCH_SIZE = 6


def _parse_json_object(content: str) -> dict:
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
    if not isinstance(parsed, dict):
        raise ValueError("AI response must be a JSON object")
    return parsed


def _request_candidates(messages: list[dict]) -> list:
    request = {
        "model": get_settings().groq_model,
        "messages": messages,
        "response_format": {"type": "json_object"},
        "reasoning_effort": "none",
        "temperature": 0.45,
        "max_completion_tokens": 5000,
    }
    try:
        response = get_groq_client().chat.completions.create(**request)
    except BadRequestError:
        # Some Groq models intermittently reject otherwise valid generations in
        # JSON Object Mode. The prompt still requires JSON, and we validate it.
        request.pop("response_format")
        response = get_groq_client().chat.completions.create(**request)
    parsed = _parse_json_object(response.choices[0].message.content or "{}")
    candidates = parsed.get("questions", [])
    if not isinstance(candidates, list):
        raise ValueError("questions must be a list")
    return candidates


def _context_window(context: list[dict], batch_index: int, batch_count: int) -> list[dict]:
    if batch_count <= 1 or len(context) <= batch_count:
        return context
    window_index = batch_index % batch_count
    start = window_index * len(context) // batch_count
    end = (window_index + 1) * len(context) // batch_count
    return context[start:end] or context


def generate_questions(
    context: list[dict], mcq_count: int, short_count: int, previous: list[str]
) -> list[dict]:
    if not context:
        raise HTTPException(status_code=422, detail="No material context is available")
    labeled = [{**item, "source_id": f"S{index}"} for index, item in enumerate(context, 1)]
    source_map = {item["source_id"]: item for item in labeled}
    accepted: list[dict] = []
    last_error: Exception | None = None

    total_requested = mcq_count + short_count
    planned_batches = max(1, math.ceil(total_requested / GENERATION_BATCH_SIZE))
    max_attempts = planned_batches + 3

    # Small batches avoid truncated JSON for larger exams. Each batch receives a
    # different section of the document so questions cover beginning through end.
    for attempt in range(1, max_attempts + 1):
        mcqs = [q for q in accepted if q["type"] == "mcq"]
        shorts = [q for q in accepted if q["type"] == "short"]
        missing_mcqs = mcq_count - len(mcqs)
        missing_shorts = short_count - len(shorts)
        if missing_mcqs <= 0 and missing_shorts <= 0:
            return mcqs[:mcq_count] + shorts[:short_count]

        remaining = missing_mcqs + missing_shorts
        batch_total = min(GENERATION_BATCH_SIZE, remaining)
        batch_mcqs = min(
            missing_mcqs,
            round(batch_total * missing_mcqs / remaining),
        )
        batch_shorts = min(missing_shorts, batch_total - batch_mcqs)
        batch_mcqs = min(missing_mcqs, batch_total - batch_shorts)
        batch_context = _context_window(labeled, attempt - 1, planned_batches)
        exclusions = previous + [q["question"] for q in accepted]
        try:
            candidates = _request_candidates(
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": build_generation_prompt(
                            batch_context, batch_mcqs, batch_shorts, exclusions
                        ),
                    },
                ]
            )
        except (APIError, json.JSONDecodeError, AttributeError, TypeError, ValueError) as exc:
            last_error = exc
            logger.warning("Question generation attempt %s failed: %s", attempt, exc)
            continue

        valid_candidates = []
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            prepared = _prepare_candidate(candidate, source_map, labeled[0])
            if prepared:
                valid_candidates.append(prepared)

        new_mcqs = filter_duplicates(
            [q for q in valid_candidates if q["type"] == "mcq"], exclusions, batch_mcqs
        )
        short_exclusions = exclusions + [q["question"] for q in new_mcqs]
        new_shorts = filter_duplicates(
            [q for q in valid_candidates if q["type"] == "short"],
            short_exclusions,
            batch_shorts,
        )
        accepted.extend(new_mcqs)
        accepted.extend(new_shorts)
        logger.info(
            "Question generation attempt %s: received=%s valid=%s accepted_mcq=%s/%s "
            "accepted_short=%s/%s",
            attempt,
            len(candidates),
            len(valid_candidates),
            len([q for q in accepted if q["type"] == "mcq"]),
            mcq_count,
            len([q for q in accepted if q["type"] == "short"]),
            short_count,
        )

    detail = (
        f"AI generated {len([q for q in accepted if q['type'] == 'mcq'])}/{mcq_count} MCQs "
        f"and {len([q for q in accepted if q['type'] == 'short'])}/{short_count} short questions"
    )
    if not accepted and last_error:
        detail = "The AI provider could not return valid question data"
    raise HTTPException(status_code=502, detail=detail)


def _prepare_candidate(candidate: dict, source_map: dict, fallback_source: dict) -> dict | None:
    raw_type = str(candidate.get("type", "")).strip().lower().replace("_", "-")
    type_aliases = {
        "mcq": "mcq",
        "multiple-choice": "mcq",
        "multiple choice": "mcq",
        "short": "short",
        "short-answer": "short",
        "short answer": "short",
    }
    question_type = type_aliases.get(raw_type)
    options = candidate.get("options")
    if question_type == "mcq" and isinstance(options, dict):
        option_keys = [key for key in ("A", "B", "C", "D") if key in options]
        if len(option_keys) == 4:
            answer = str(candidate.get("correct_answer", "")).strip().upper()
            candidate["correct_answer"] = options.get(answer, candidate.get("correct_answer"))
            options = [options[key] for key in option_keys]
    if question_type == "mcq" and isinstance(options, list):
        answer = str(candidate.get("correct_answer", "")).strip().upper()
        if answer in {"A", "B", "C", "D"}:
            index = ord(answer) - ord("A")
            if index < len(options):
                candidate["correct_answer"] = options[index]
    if question_type not in {"mcq", "short"}:
        return None
    if question_type == "mcq" and (
        not isinstance(options, list)
        or len(options) != 4
        or candidate.get("correct_answer") not in options
    ):
        return None
    if not all(candidate.get(key) for key in ("question", "correct_answer", "explanation")):
        return None
    source = source_map.get(candidate.get("source_id"), fallback_source)
    return {
        **candidate,
        "type": question_type,
        "id": str(uuid4()),
        "source": source["source"],
        "source_text": source["text"],
        "marks": 1,
        "options": options if question_type == "mcq" else None,
    }
