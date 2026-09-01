SYSTEM_PROMPT = """You create rigorous exams using only the supplied study material.
Return one valid JSON object and no markdown. Cover the most important distinct topics across the material.
Preserve mathematical notation in plain text/LaTeX and include calculation or application questions when the source supports them.
Every question must be answerable from its cited source. Avoid ambiguity, trivia, duplicates, and excluded prior questions.
MCQs need exactly four plausible options and one exact correct_answer matching an option.
Short answers need a concise reference answer containing every fact needed for grading.
Use source IDs exactly as provided, such as S3.
JSON shape: {"questions":[{"type":"mcq|short","question":"...","options":["..."] or null,"correct_answer":"...","explanation":"...","source_id":"S1","marks":1}]}"""


def build_generation_prompt(context: list[dict], mcq_count: int, short_count: int, previous: list[str]) -> str:
    sources = "\n\n".join(
        f"[{item['source_id']}] {item['source']}\n{item['text']}" for item in context
    )
    exclusions = "\n".join(f"- {question}" for question in previous[-40:]) or "None"
    total = mcq_count + short_count
    candidate_count = min(max(total + 4, total * 2), total + 12)
    return f"""Create {candidate_count} candidate questions so the application can remove near-duplicates.
At least {mcq_count} must be MCQ and at least {short_count} must be short-answer.
Use varied cognitive styles and prioritize broad important-topic coverage.

Previously used questions to avoid:
{exclusions}

Study sources:
{sources}"""
