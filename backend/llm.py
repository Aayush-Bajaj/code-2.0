import os
import json
import time
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional
try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

from backend.config import settings

# Maximum retry attempts and default timeout in seconds
MAX_RETRIES = 3
TIMEOUT_SECONDS = 30.0


def _compute_cache_key(model: str, prompt: str, images: Optional[List[bytes]] = None) -> str:
    """Compute deterministic SHA-256 cache key based on model, prompt, and image bytes."""
    hasher = hashlib.sha256()
    hasher.update(model.encode("utf-8"))
    hasher.update(prompt.encode("utf-8"))
    if images:
        for img in images:
            hasher.update(img)
    return hasher.hexdigest()


def _get_cache_path(cache_key: str) -> Path:
    settings.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return settings.CACHE_DIR / f"{cache_key}.json"


def _read_cache(cache_key: str) -> Optional[str]:
    path = _get_cache_path(cache_key)
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("response")
        except Exception:
            return None
    return None


def _write_cache(cache_key: str, response_text: str) -> None:
    path = _get_cache_path(cache_key)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"response": response_text, "timestamp": time.time()}, f, indent=2)
    except Exception:
        pass


def _load_mock_fixture(prompt: str) -> str:
    """Load mock JSON or text fixture based on prompt context."""
    settings.FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    fixture_path = settings.FIXTURES_DIR / "llm_default_mock.json"
    if fixture_path.exists():
        with open(fixture_path, "r", encoding="utf-8") as f:
            return f.read()
    return json.dumps({
        "status": "mock",
        "message": "Mocked response from tests/fixtures",
        "extracted": {"supplier": "Test Supplier", "amount_inr": 1000.0, "quantity": 100.0, "unit": "kWh"}
    })


def _get_client() -> Any:
    if genai is None:
        raise ImportError("google-genai package is not installed. Install via requirements.txt.")
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set. Provide it in .env or enable MOCK_LLM=1.")
    return genai.Client(api_key=api_key)


def _call_gemini_api(prompt: str, images: Optional[List[bytes]] = None) -> str:
    """Direct client call with 30s timeout configured."""
    client = _get_client()
    contents: List[Any] = []
    if images:
        for img in images:
            contents.append(types.Part.from_bytes(data=img, mime_type="image/jpeg"))
    contents.append(prompt)

    # genai Client generate_content call
    response = client.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            # Request timeout can be handled or rely on client default
        ),
    )
    if not response or not response.text:
        raise RuntimeError("Received empty response from Gemini API.")
    return response.text


def _call_with_retry_and_cache(prompt: str, images: Optional[List[bytes]] = None) -> str:
    """Handles MOCK_LLM, DEMO_OFFLINE, SHA-256 cache, timeout, and exponential backoff retries."""
    cache_key = _compute_cache_key(settings.GEMINI_MODEL, prompt, images)

    # 1. Check offline switches & Cache
    cached_val = _read_cache(cache_key)
    if cached_val is not None:
        return cached_val

    if settings.DEMO_OFFLINE:
        raise RuntimeError(
            f"DEMO_OFFLINE=1 is enabled, but no cached response was found for key {cache_key}. "
            "Please pre-warm the cache in data/cache/ or disable DEMO_OFFLINE."
        )

    if settings.MOCK_LLM:
        mock_resp = _load_mock_fixture(prompt)
        _write_cache(cache_key, mock_resp)
        return mock_resp

    # 2. Live API call with retries and exponential backoff
    last_err = None
    delay = 1.0
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp_text = _call_gemini_api(prompt, images)
            _write_cache(cache_key, resp_text)
            return resp_text
        except Exception as e:
            last_err = e
            if attempt < MAX_RETRIES:
                time.sleep(delay)
                delay *= 2.0

    raise RuntimeError(f"Gemini API failed after {MAX_RETRIES} attempts. Error: {last_err}")


def generate_text(prompt: str) -> str:
    """Generate text from Gemini via robust cached wrapper."""
    return _call_with_retry_and_cache(prompt=prompt, images=None)


def generate_json(prompt: str, images: Optional[List[bytes]] = None) -> Dict[str, Any]:
    """Generate and parse JSON with automatic strip and one repair retry."""
    raw_text = _call_with_retry_and_cache(prompt=prompt, images=images)

    def _clean_and_parse(text: str) -> Optional[Dict[str, Any]]:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()
        try:
            return json.loads(cleaned)
        except Exception:
            return None

    parsed = _clean_and_parse(raw_text)
    if parsed is not None:
        return parsed

    # JSON repair retry with Gemini if parsing failed
    repair_prompt = (
        "The following text was supposed to be valid JSON but failed to parse. "
        "Output ONLY the corrected, valid JSON string and nothing else:\n\n"
        f"{raw_text}"
    )
    try:
        repaired_text = _call_with_retry_and_cache(prompt=repair_prompt, images=None)
        repaired_parsed = _clean_and_parse(repaired_text)
        if repaired_parsed is not None:
            return repaired_parsed
    except Exception:
        pass

    raise ValueError(f"Failed to parse valid JSON from LLM response after repair attempt. Raw text:\n{raw_text[:500]}")
