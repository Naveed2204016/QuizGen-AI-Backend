from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

from app.api.v1.router import api_router
from app.core.config import get_settings

settings = get_settings()
app = FastAPI(title=settings.app_name)

@app.exception_handler(Exception)
async def unexpected_error(request, exc):
    logging.getLogger(__name__).error("Unhandled API error", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "The backend encountered an internal error. Please retry; see backend logs for details."})

app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/")
def root():
    return {"message": settings.app_name}


# Wrap the complete application so even unhandled 500 responses carry CORS
# headers and the frontend can read their actual error message.
app = CORSMiddleware(
    app,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
