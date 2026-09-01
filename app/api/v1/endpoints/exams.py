from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_current_user
from app.repositories.exams import create_exam, get_exam, history, previous_question_texts
from app.repositories.materials import get_material
from app.schemas.exam import GenerateExamRequest
from app.services.question_generation import generate_questions
from app.services.retrieval import retrieve_generation_context

router = APIRouter(prefix="/exams", tags=["Exams"])


@router.post("/generate")
def generate_exam(payload: GenerateExamRequest, user=Depends(get_current_user)):
    user_id = str(user.id)
    material = get_material(user_id, payload.material_id)
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    context = retrieve_generation_context(user_id, payload.material_id)
    previous = previous_question_texts(user_id, payload.material_id)
    questions = generate_questions(context, payload.mcq_count, payload.short_count, previous)
    exam = create_exam(
        {
            "id": str(uuid4()),
            "user_id": user_id,
            "material_id": payload.material_id,
            "mcq_count": payload.mcq_count,
            "short_count": payload.short_count,
            "duration_minutes": payload.duration_minutes,
            "questions": questions,
            "status": "ready",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    return {"id": exam["id"], "material": material["filename"], "question_count": len(questions), "duration_minutes": payload.duration_minutes}


@router.get("/history")
def exam_history(user=Depends(get_current_user)):
    rows = history(str(user.id))
    exams = []
    for row in rows:
        completed = [attempt for attempt in (row.get("attempts") or []) if attempt.get("status") == "completed"]
        if not completed:
            continue
        latest = max(completed, key=lambda item: item.get("submitted_at") or "")
        exams.append(
            {
                "id": row["id"],
                "material": (row.get("materials") or {}).get("filename", "Study material"),
                "score": float(latest.get("score") or 0),
                "date": latest.get("submitted_at") or row["created_at"],
                "status": "Completed",
            }
        )
    scores = [item["score"] for item in exams]
    return {
        "total_exams": len(exams),
        "average_score": round(sum(scores) / len(scores), 1) if scores else 0,
        "best_score": max(scores) if scores else 0,
        "exams": exams,
    }


@router.get("/{exam_id}")
def exam_detail(exam_id: str, user=Depends(get_current_user)):
    exam = get_exam(str(user.id), exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    return exam
