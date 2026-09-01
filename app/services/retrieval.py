from uuid import uuid4

from qdrant_client.models import Distance, FieldCondition, Filter, MatchValue, PointStruct, VectorParams

from app.clients.qdrant import get_qdrant_client
from app.core.config import get_settings
from app.services.embeddings import embed_texts


def _filter(user_id: str, material_id: str) -> Filter:
    return Filter(
        must=[
            FieldCondition(key="user_id", match=MatchValue(value=user_id)),
            FieldCondition(key="material_id", match=MatchValue(value=material_id)),
        ]
    )


def index_chunks(user_id: str, material_id: str, chunks: list[dict]) -> None:
    client = get_qdrant_client()
    settings = get_settings()
    vectors = embed_texts([chunk["text"] for chunk in chunks])
    if not client.collection_exists(settings.qdrant_collection):
        client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=VectorParams(size=len(vectors[0]), distance=Distance.COSINE),
        )
    points = [
        PointStruct(
            id=str(uuid4()),
            vector=vector,
            payload={"user_id": user_id, "material_id": material_id, **chunk},
        )
        for chunk, vector in zip(chunks, vectors)
    ]
    client.upsert(collection_name=settings.qdrant_collection, points=points, wait=True)


def retrieve_generation_context(user_id: str, material_id: str, limit: int = 18) -> list[dict]:
    client = get_qdrant_client()
    settings = get_settings()
    queries = [
        "important definitions, core concepts, conclusions and comparisons",
        "important formulas, equations, calculations, worked examples and problem solving",
        "key facts, processes, causes, effects and applications",
    ]
    selected: dict[str, dict] = {}
    for query in queries:
        response = client.query_points(
            collection_name=settings.qdrant_collection,
            query=embed_texts([query])[0],
            query_filter=_filter(user_id, material_id),
            limit=max(6, limit // len(queries)),
            with_payload=True,
        )
        for point in response.points:
            payload = dict(point.payload or {})
            selected[str(point.id)] = payload
    return sorted(selected.values(), key=lambda item: (item.get("section_number", 0), item.get("part", 0)))[:limit]
