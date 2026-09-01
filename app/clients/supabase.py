from supabase import Client, create_client

from app.core.config import get_settings


def create_supabase_client() -> Client:
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_publishable_key)


def create_supabase_admin_client() -> Client:
    settings = get_settings()
    if not settings.supabase_secret_key:
        raise RuntimeError("SUPABASE_SECRET_KEY is required")
    return create_client(settings.supabase_url, settings.supabase_secret_key)
