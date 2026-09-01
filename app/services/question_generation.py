import json
from uuid import uuid4

from fastapi import HTTPException

from app.clients.groq import get_groq_client
from app.core.config import get_settings
from app.prompts.question_generation import SYSTEM_PROMPT, build_generation_prompt
from app.services.duplicate_detection import filter_duplicates


def generate_questions(
    context: list[dict], mcq_count: int, short_count: int, previous: list[str]
) -> list[dict]:
    if not context:
        raise HTTPException(status_code=422, detail="No material context is available")
    labeled = [{**item, "source_id": f"S{index}"} for index, item in enumerate(context, 1)]
    source_map = {item["source_id"]: item for item in labeled}
    response = get_groq_client().chat.completions.create(
        model=get_settings().groq_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_generation_prompt(labeled, mcq_count, short_count, previous)},
        ],
        response_format={"type": "json_object"},
        temperature=0.75,
        max_completion_tokens=5000,
    )
    try:
        candidates = json.loads(response.choices[0].message.content or "{}").get("questions", [])
    except (json.JSONDecodeError, AttributeError) as exc:
        raise HTTPException(status_code=502, detail="The AI returned invalid question data") from exc

    valid_candidates = []
    for candidate in candidates:
        question_type = candidate.get("type")
        options = candidate.get("options")
        if question_type not in {"mcq", "short"}:
            continue
        if question_type == "mcq" and (
            not isinstance(options, list)
            or len(options) != 4
            or candidate.get("correct_answer") not in options
        ):
            continue
        if not all(candidate.get(key) for key in ("question", "correct_answer", "explanation")):
            continue
        source = source_map.get(candidate.get("source_id"), labeled[0])
        candidate["id"] = str(uuid4())
        candidate["source"] = source["source"]
        candidate["source_text"] = source["text"]
        candidate["marks"] = 1
        if candidate.get("type") == "short":
            candidate["options"] = None
        valid_candidates.append(candidate)

    mcqs = filter_duplicates([q for q in valid_candidates if q.get("type") == "mcq"], previous, mcq_count)
    used = previous + [q["question"] for q in mcqs]
    shorts = filter_duplicates([q for q in valid_candidates if q.get("type") == "short"], used, short_count)
    if len(mcqs) < mcq_count or len(shorts) < short_count:
        raise HTTPException(status_code=502, detail="AI could not create enough distinct questions; please retry")
    return mcqs[:mcq_count] + shorts[:short_count]
