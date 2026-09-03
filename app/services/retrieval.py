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
    else:
        # Re-uploading a material refreshes its local index without accumulating
        # duplicate chunks. This also repairs an index deleted between API runs.
        client.delete(
            collection_name=settings.qdrant_collection,
            points_selector=_filter(user_id, material_id),
            wait=True,
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
    if limit <= 0:
        return []
    client = get_qdrant_client()
    settings = get_settings()
    points, _ = client.scroll(
        collection_name=settings.qdrant_collection,
        scroll_filter=_filter(user_id, material_id),
        limit=10_000,
        with_payload=True,
        with_vectors=False,
    )
    chunks = sorted(
        (dict(point.payload or {}) for point in points),
        key=lambda item: (item.get("section_number", 0), item.get("part", 0)),
    )
    if len(chunks) <= limit:
        return chunks
    if limit == 1:
        return [chunks[len(chunks) // 2]]

    # Generation needs broad document coverage, not the chunks most similar to
    # a few generic queries. Sample uniformly from beginning through end.
    indices = {
        round(index * (len(chunks) - 1) / (limit - 1))
        for index in range(limit)
    }
    return [chunks[index] for index in sorted(indices)]
