import hashlib
from pathlib import Path
from uuid import uuid4
import logging
from time import perf_counter

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.repositories.materials import create_material, find_material
from app.services.chunking import chunk_sections
from app.services.document_parser import extract_document
from app.services.retrieval import has_material_index, index_chunks

router = APIRouter(prefix="/materials", tags=["Materials"])


@router.post("/upload")
async def upload_material(file: UploadFile = File(...), user=Depends(get_current_user)):
    extension = Path(file.filename or "").suffix.lower()
    if extension not in {".pdf", ".pptx"}:
        raise HTTPException(status_code=415, detail="Only PDF and PPTX files are supported")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="The uploaded file is empty")
    if len(content) > get_settings().max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail="The uploaded file is too large")

    return await run_in_threadpool(_process_material, content, extension, file.filename, file.content_type, str(user.id))


def _process_material(content: bytes, extension: str, filename: str, mime_type: str, user_id: str):
    started = perf_counter()
    content_hash = hashlib.sha256(content).hexdigest()
    try:
        existing = find_material(user_id, content_hash)
        if existing and has_material_index(user_id, existing["id"], existing["chunk_count"]):
            logging.getLogger(__name__).info("Material index reused in %.2fs", perf_counter() - started)
            return {**{key: existing[key] for key in ("id", "filename", "page_count")}, "reused": True}
        sections = extract_document(content, extension)
        chunks = chunk_sections(sections)
        if existing:
            # The Supabase material can outlive the machine-local Qdrant index.
            # Rebuild its chunks on upload so the returned material ID always
            # has generation context available locally.
            index_chunks(user_id, existing["id"], chunks)
            return {
                "id": existing["id"],
                "filename": existing["filename"],
                "page_count": existing["page_count"],
                "reused": True,
            }
        material_id = str(uuid4())
        index_chunks(user_id, material_id, chunks)
        material = create_material(
            {
                "id": material_id,
                "user_id": user_id,
                "filename": filename,
                "content_hash": content_hash,
                "mime_type": mime_type,
                "page_count": len(sections),
                "chunk_count": len(chunks),
            }
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Material processing failed") from exc

    logging.getLogger(__name__).info("Material processing completed in %.2fs", perf_counter() - started)
    return {"id": material["id"], "filename": material["filename"], "page_count": material["page_count"], "reused": False}
