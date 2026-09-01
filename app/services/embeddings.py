import math
from functools import lru_cache

from fastembed import TextEmbedding

from app.core.config import get_settings


@lru_cache
def get_embedding_model() -> TextEmbedding:
    return TextEmbedding(model_name=get_settings().embedding_model)


def embed_texts(texts: list[str]) -> list[list[float]]:
    return [vector.tolist() for vector in get_embedding_model().embed(texts)]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right))
    denominator = math.sqrt(sum(a * a for a in left)) * math.sqrt(sum(b * b for b in right))
    return numerator / denominator if denominator else 0.0
