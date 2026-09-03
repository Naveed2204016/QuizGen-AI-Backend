import hashlib
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.api.dependencies import get_current_user
from app.core.config import get_settings
from app.repositories.materials import create_material, find_material
from app.services.chunking import chunk_sections
from app.services.document_parser import extract_document
from app.services.retrieval import index_chunks

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

    content_hash = hashlib.sha256(content).hexdigest()
    try:
        sections = extract_document(content, extension)
        chunks = chunk_sections(sections)
        existing = find_material(str(user.id), content_hash)
        if existing:
            return {
                "id": existing["id"],
                "filename": existing["filename"],
                "page_count": existing["page_count"],
                "reused": True,
            }
        material_id = str(uuid4())
        index_chunks(str(user.id), material_id, chunks)
        material = create_material(
            {
                "id": material_id,
                "user_id": str(user.id),
                "filename": file.filename,
                "content_hash": content_hash,
                "mime_type": file.content_type,
                "page_count": len(sections),
                "chunk_count": len(chunks),
            }
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Material processing failed") from exc

    return {"id": material["id"], "filename": material["filename"], "page_count": material["page_count"], "reused": False}
