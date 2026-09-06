from functools import lru_cache

from google import genai
from google.genai import types

from app.core.config import get_settings


@lru_cache
def get_gemini_client() -> genai.Client:
    settings = get_settings()
    return genai.Client(
        api_key=settings.gemini_api_key,
        http_options=types.HttpOptions(
            timeout=int(settings.gemini_timeout_seconds * 1000),
        ),
    )


def generate_json(
    *, system_instruction: str, prompt: str, max_output_tokens: int
) -> str:
    settings = get_settings()
    response = get_gemini_client().models.generate_content(
        model=settings.gemini_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            max_output_tokens=max_output_tokens,
        ),
    )
    return response.text or "{}"
