SYSTEM_PROMPT = """Grade short answers strictly from the supplied reference answer and study source.
Judge factual correctness separately from semantic coverage. Penalize contradictions even if wording is similar.
Return one valid JSON object and no markdown.
JSON shape: {"evaluations":[{"question_id":"uuid","factual_score":0.0,"feedback":"brief explanation"}]}.
factual_score must be between 0 and 1."""


def build_evaluation_prompt(items: list[dict]) -> str:
    blocks = []
    for item in items:
        blocks.append(
            "\n".join(
                [
                    f"Question ID: {item['question_id']}",
                    f"Question: {item['question']}",
                    f"Student answer: {item['user_answer'] or '[not answered]'}",
                    f"Reference answer: {item['correct_answer']}",
                    f"Source: {item['source_text']}",
                ]
            )
        )
    return "Grade these answers:\n\n" + "\n\n---\n\n".join(blocks)
