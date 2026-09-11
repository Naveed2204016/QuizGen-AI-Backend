import json
import logging
import math
import re
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from time import perf_counter

from fastapi import HTTPException
from google.genai.errors import APIError

from app.clients.gemini import generate_json
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
    system_instruction = "\n\n".join(
        str(message["content"]) for message in messages if message["role"] == "system"
    )
    prompt = "\n\n".join(
        str(message["content"]) for message in messages if message["role"] != "system"
    )
    content = generate_json(
        system_instruction=system_instruction,
        prompt=prompt,
        max_output_tokens=5000,
    )
    parsed = _parse_json_object(content)
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
    started = perf_counter()
    labeled = [{**item, "source_id": f"S{index}"} for index, item in enumerate(context, 1)]
    accepted: list[dict] = []
    last_error: Exception | None = None

    total_requested = mcq_count + short_count
    planned_batches = max(1, math.ceil(total_requested / GENERATION_BATCH_SIZE))
    max_attempts = planned_batches + 3

    # Independent initial batches overlap provider latency. Merge and deduplicate
    # in order, then request only deficits using all accepted questions.
    def request(batch_context, mcqs, shorts, exclusions):
        return _request_candidates([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_generation_prompt(batch_context, mcqs, shorts, exclusions)},
        ])

    plans = []
    remaining_mcqs, remaining_shorts = mcq_count, short_count
    for index in range(planned_batches):
        total = min(GENERATION_BATCH_SIZE, remaining_mcqs + remaining_shorts)
        mcqs = min(remaining_mcqs, round(total * remaining_mcqs / (remaining_mcqs + remaining_shorts)))
        shorts = min(remaining_shorts, total - mcqs)
        mcqs = min(remaining_mcqs, total - shorts)
        plans.append((_context_window(labeled, index, planned_batches), mcqs, shorts))
        remaining_mcqs -= mcqs
        remaining_shorts -= shorts
    initial = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(request, ctx, m, s, previous) for ctx, m, s in plans]
        for future in futures:
            try:
                initial.append(future.result())
            except (APIError, json.JSONDecodeError, AttributeError, TypeError, ValueError) as exc:
                initial.append(exc)

    # Small batches avoid truncated JSON for larger exams. Each batch receives a
    # different section of the document so questions cover beginning through end.
    for attempt in range(1, max_attempts + 1):
        mcqs = [q for q in accepted if q["type"] == "mcq"]
        shorts = [q for q in accepted if q["type"] == "short"]
        missing_mcqs = mcq_count - len(mcqs)
        missing_shorts = short_count - len(shorts)
        if missing_mcqs <= 0 and missing_shorts <= 0:
            logger.info("Generation completed in %.2fs", perf_counter() - started)
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
            if attempt <= planned_batches:
                batch_context, batch_mcqs, batch_shorts = plans[attempt - 1]
                candidates = initial[attempt - 1]
                if isinstance(candidates, Exception):
                    raise candidates
            else:
                candidates = request(batch_context, batch_mcqs, batch_shorts, exclusions)
        except (APIError, json.JSONDecodeError, AttributeError, TypeError, ValueError) as exc:
            last_error = exc
            logger.warning("Question generation attempt %s failed: %s", attempt, exc)
            continue

        valid_candidates = []
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            prepared = _prepare_candidate(candidate, {item["source_id"]: item for item in batch_context}, labeled[0])
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

    mcqs = [q for q in accepted if q["type"] == "mcq"]
    shorts = [q for q in accepted if q["type"] == "short"]
    if len(mcqs) == mcq_count and len(shorts) == short_count:
        logger.info("Generation completed in %.2fs", perf_counter() - started)
        return mcqs + shorts
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
        or not all(isinstance(option, str) and option.strip() for option in options)
        or len({option.strip().casefold() for option in options}) != 4
        or candidate.get("correct_answer") not in options
    ):
        return None
    if not all(isinstance(candidate.get(key), str) and candidate[key].strip() for key in ("question", "correct_answer", "explanation")):
        return None
    source = source_map.get(candidate.get("source_id"))
    if source is None:
        return None
    return {
        **candidate,
        "type": question_type,
        "id": str(uuid4()),
        "source": source["source"],
        "source_text": source["text"],
        "marks": 1,
        "options": options if question_type == "mcq" else None,
    }
