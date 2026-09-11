import logging
from time import perf_counter

from google import genai
from google.genai import types

from app.core.config import get_settings


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
    started = perf_counter()
    # Keep the owning Client alive throughout the request. Concurrent cache
    # misses can otherwise create temporary Clients whose destructors close
    # the transport while a bound Models method is still using it.
    with get_gemini_client() as client:
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                max_output_tokens=max_output_tokens,
            ),
        )
    logging.getLogger(__name__).info("Gemini request completed in %.2fs", perf_counter() - started)
    return response.text or "{}"
