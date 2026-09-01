import re

from app.services.embeddings import cosine_similarity, embed_texts


def normalize_question(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def filter_duplicates(candidates: list[dict], previous: list[str], needed: int) -> list[dict]:
    accepted: list[dict] = []
    comparison_texts = [text for text in previous if text]
    comparison_vectors = embed_texts(comparison_texts) if comparison_texts else []
    exact = {normalize_question(text) for text in comparison_texts}

    for candidate in candidates:
        text = candidate.get("question", "").strip()
        normalized = normalize_question(text)
        if not text or normalized in exact:
            continue
        vector = embed_texts([text])[0]
        if any(cosine_similarity(vector, old) >= 0.92 for old in comparison_vectors):
            continue
        accepted.append(candidate)
        exact.add(normalized)
        comparison_vectors.append(vector)
        if len(accepted) == needed:
            break
    return accepted
