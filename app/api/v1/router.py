from fastapi import APIRouter

from app.api.v1.endpoints import attempts, auth, exams, materials

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(materials.router)
api_router.include_router(exams.router)
api_router.include_router(attempts.router)


@api_router.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}
