from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_current_user
from app.repositories.attempts import create_attempt, get_attempt, update_attempt
from app.repositories.exams import get_exam
from app.schemas.attempt import SubmitAttemptRequest
from app.services.answer_evaluation import evaluate_answers

router = APIRouter(tags=["Attempts"])


def _public_question(question: dict) -> dict:
    return {key: question.get(key) for key in ("id", "type", "question", "options", "marks")}


@router.post("/exams/{exam_id}/attempts")
def start_attempt(exam_id: str, user=Depends(get_current_user)):
    user_id = str(user.id)
    exam = get_exam(user_id, exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    started_at = datetime.now(timezone.utc)
    expires_at = started_at + timedelta(minutes=exam["duration_minutes"])
    attempt = create_attempt(
        {
            "id": str(uuid4()),
            "exam_id": exam_id,
            "user_id": user_id,
            "started_at": started_at.isoformat(),
            "expires_at": expires_at.isoformat(),
            "status": "in_progress",
            "answers": {},
        }
    )
    return {
        "attempt_id": attempt["id"],
        "exam_id": exam_id,
        "material": (exam.get("materials") or {}).get("filename", "Study material"),
        "expires_at": expires_at.isoformat(),
        "questions": [_public_question(question) for question in exam["questions"]],
    }


@router.post("/attempts/{attempt_id}/submit")
def submit_attempt(attempt_id: str, payload: SubmitAttemptRequest, user=Depends(get_current_user)):
    user_id = str(user.id)
    attempt = get_attempt(user_id, attempt_id)
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
    if attempt["status"] == "completed":
        return attempt["results"]

    now = datetime.now(timezone.utc)
    expires_at = datetime.fromisoformat(attempt["expires_at"].replace("Z", "+00:00"))
    too_late = now > expires_at + timedelta(seconds=15)
    submitted = {} if too_late else {item.question_id: item.answer for item in payload.answers}
    questions = attempt["exams"]["questions"]
    valid_question_ids = {question["id"] for question in questions}
    if any(question_id not in valid_question_ids for question_id in submitted):
        raise HTTPException(status_code=400, detail="Submission contains an invalid question ID")
    results = evaluate_answers(questions, submitted)
    awarded = sum(item["awarded_marks"] for item in results)
    maximum = sum(item["max_marks"] for item in results) or 1
    score = round(awarded / maximum * 100, 1)
    result_payload = {
        "attempt_id": attempt_id,
        "material": (attempt["exams"].get("materials") or {}).get("filename", "Study material"),
        "score": score,
        "awarded_marks": round(awarded, 2),
        "max_marks": maximum,
        "correct_count": sum(1 for item in results if item["correct"]),
        "total_questions": len(results),
        "auto_submitted": payload.auto_submitted or too_late,
        "submitted_at": now.isoformat(),
        "results": results,
    }
    update_attempt(
        attempt_id,
        user_id,
        {
            "answers": submitted,
            "results": result_payload,
            "score": score,
            "status": "completed",
            "auto_submitted": payload.auto_submitted or too_late,
            "submitted_at": now.isoformat(),
        },
    )
    return result_payload


@router.get("/attempts/{attempt_id}/result")
def attempt_result(attempt_id: str, user=Depends(get_current_user)):
    attempt = get_attempt(str(user.id), attempt_id)
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
    if attempt["status"] != "completed":
        raise HTTPException(status_code=409, detail="Attempt has not been submitted")
    return attempt["results"]
