from app.clients.supabase import create_supabase_admin_client


def find_material(user_id: str, content_hash: str) -> dict | None:
    response = (
        create_supabase_admin_client()
        .table("materials")
        .select("*")
        .eq("user_id", user_id)
        .eq("content_hash", content_hash)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def get_material(user_id: str, material_id: str) -> dict | None:
    response = (
        create_supabase_admin_client()
        .table("materials")
        .select("*")
        .eq("user_id", user_id)
        .eq("id", material_id)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def create_material(data: dict) -> dict:
    return create_supabase_admin_client().table("materials").insert(data).execute().data[0]
