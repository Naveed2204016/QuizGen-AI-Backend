from app.clients.supabase import create_supabase_admin_client


def create_attempt(data: dict) -> dict:
    return create_supabase_admin_client().table("attempts").insert(data).execute().data[0]


def get_attempt(user_id: str, attempt_id: str) -> dict | None:
    response = (
        create_supabase_admin_client()
        .table("attempts")
        .select("*, exams(*, materials(filename))")
        .eq("user_id", user_id)
        .eq("id", attempt_id)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def update_attempt(attempt_id: str, user_id: str, data: dict) -> dict:
    response = (
        create_supabase_admin_client()
        .table("attempts")
        .update(data)
        .eq("id", attempt_id)
        .eq("user_id", user_id)
        .execute()
    )
    return response.data[0]
