SYSTEM_PROMPT = """You create rigorous exams using only the supplied study material.
Return one valid JSON object and no markdown, commentary, or code fences. Cover the most important distinct topics across the material.
Preserve mathematical notation in plain text/LaTeX and include calculation or application questions when the source supports them.
Every question must be answerable from its cited source. Avoid ambiguity, trivia, duplicates, and excluded prior questions.
Never use outside knowledge to fill gaps. If the supplied sources do not contain enough information, return fewer questions or an empty questions array instead of inventing content.
MCQs need exactly four plausible options and one exact correct_answer matching an option.
Short answers must use null for options and need a concise reference answer containing every fact needed for grading.
Use source IDs exactly as provided, such as S3.
The only top-level key is "questions". Each question must have exactly these fields: type, question, options, correct_answer, explanation, source_id, and marks.
Valid MCQ example: {"type":"mcq","question":"...","options":["A","B","C","D"],"correct_answer":"A","explanation":"...","source_id":"S1","marks":1}.
Valid short-answer example: {"type":"short","question":"...","options":null,"correct_answer":"...","explanation":"...","source_id":"S1","marks":1}."""


def build_generation_prompt(context: list[dict], mcq_count: int, short_count: int, previous: list[str]) -> str:
    sources = "\n\n".join(
        f"[{item['source_id']}] {item['source']}\n{item['text']}" for item in context
    )
    exclusions = "\n".join(f"- {question}" for question in previous[-40:]) or "None"
    total = mcq_count + short_count
    candidate_count = min(max(total + 4, total * 2), total + 12)
    return f"""Create exactly {candidate_count} candidate questions so the application can remove near-duplicates.
Include at least {mcq_count} questions whose type is exactly "mcq" and at least {short_count} whose type is exactly "short".
Use varied cognitive styles and prioritize broad important-topic coverage.

Previously used questions to avoid:
{exclusions}

Study sources:
{sources}"""
