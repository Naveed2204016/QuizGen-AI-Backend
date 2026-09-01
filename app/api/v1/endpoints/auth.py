from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_current_user
from app.clients.supabase import create_supabase_client
from app.schemas.user import AuthResponse, LoginRequest, RefreshRequest, RegisterRequest, UserResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


def serialize_user(user) -> UserResponse:
    metadata = user.user_metadata or {}
    return UserResponse(
        id=str(user.id),
        email=user.email or "",
        full_name=metadata.get("full_name") or (user.email or "User").split("@")[0],
        created_at=str(user.created_at) if user.created_at else None,
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest):
    try:
        result = create_supabase_client().auth.sign_up(
            {
                "email": payload.email,
                "password": payload.password,
                "options": {"data": {"full_name": payload.full_name}},
            }
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not result.user:
        raise HTTPException(status_code=400, detail="Account could not be created")

    return AuthResponse(
        user=serialize_user(result.user),
        access_token=result.session.access_token if result.session else None,
        refresh_token=result.session.refresh_token if result.session else None,
        message=None if result.session else "Check your email to confirm your account, then sign in.",
    )


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest):
    try:
        result = create_supabase_client().auth.sign_in_with_password(payload.model_dump(mode="json"))
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid email or password") from exc

    if not result.user or not result.session:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    return AuthResponse(
        user=serialize_user(result.user),
        access_token=result.session.access_token,
        refresh_token=result.session.refresh_token,
    )


@router.post("/refresh", response_model=AuthResponse)
def refresh(payload: RefreshRequest):
    try:
        result = create_supabase_client().auth.refresh_session(payload.refresh_token)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Session expired") from exc
    if not result.user or not result.session:
        raise HTTPException(status_code=401, detail="Session expired")
    return AuthResponse(
        user=serialize_user(result.user),
        access_token=result.session.access_token,
        refresh_token=result.session.refresh_token,
    )


@router.get("/me", response_model=UserResponse)
def me(user=Depends(get_current_user)):
    return serialize_user(user)
