from app.clients.supabase import create_supabase_admin_client


def create_exam(data: dict) -> dict:
    return create_supabase_admin_client().table("exams").insert(data).execute().data[0]


def get_exam(user_id: str, exam_id: str) -> dict | None:
    response = (
        create_supabase_admin_client()
        .table("exams")
        .select("*, materials(filename)")
        .eq("user_id", user_id)
        .eq("id", exam_id)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def previous_question_texts(user_id: str, material_id: str) -> list[str]:
    response = (
        create_supabase_admin_client()
        .table("exams")
        .select("questions")
        .eq("user_id", user_id)
        .eq("material_id", material_id)
        .order("created_at", desc=True)
        .limit(10)
        .execute()
    )
    return [
        question.get("question", "")
        for exam in response.data
        for question in (exam.get("questions") or [])
    ]


def history(user_id: str) -> list[dict]:
    response = (
        create_supabase_admin_client()
        .table("exams")
        .select("id,status,created_at,materials(filename),attempts(score,submitted_at,status)")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return response.data
