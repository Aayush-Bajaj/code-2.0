import os
import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv
load_dotenv(BASE_DIR / ".env")

REQUIRED_ENV_VARS = [
    "GEMINI_API_KEY",
    "GEMINI_MODEL",
    "MOCK_LLM",
    "MOCK_VISION",
    "DEMO_OFFLINE",
]

REQUIRED_PYTHON = (3, 12)


def check_python_version() -> bool:
    print("--- Python Version Check ---")
    major, minor = sys.version_info.major, sys.version_info.minor
    version_str = f"{major}.{minor}.{sys.version_info.micro}"
    print(f"  Python version: {version_str}")
    if (major, minor) != REQUIRED_PYTHON:
        print(
            f"  WARNING: Carbon Passport requires Python "
            f"{REQUIRED_PYTHON[0]}.{REQUIRED_PYTHON[1]}, "
            f"but you are running {version_str}. "
            "Please switch to the .venv created with Python 3.12."
        )
        return False
    print("  Python 3.12: OK")
    return True


DEPENDENCIES = [
    ("fastapi", "fastapi"),
    ("uvicorn", "uvicorn"),
    ("sqlmodel", "sqlmodel"),
    ("pydantic", "pydantic"),
    ("multipart", "multipart"),
    ("dotenv", "dotenv"),
    ("cv2", "opencv-python-headless"),
    ("numpy", "numpy"),
    ("PIL", "pillow"),
    ("easyocr", "easyocr"),
    ("ultralytics", "ultralytics"),
    ("google.genai", "google-genai"),
    ("chromadb", "chromadb"),
    ("sentence_transformers", "sentence-transformers"),
    ("reportlab", "reportlab"),
    ("yaml", "pyyaml"),
    ("pytest", "pytest"),
    ("httpx", "httpx"),
    ("tqdm", "tqdm"),
    ("requests", "requests"),
]


def check_env_vars() -> bool:
    print("--- Environment Variables Check ---")
    all_ok = True
    for var in REQUIRED_ENV_VARS:
        val = os.getenv(var)
        if val is not None and len(val.strip()) > 0:
            print(f"  {var}: present")
        else:
            print(f"  {var}: missing")
            if var == "GEMINI_API_KEY":
                # In mock/offline mode missing api key is tolerable
                mock_mode = os.getenv("MOCK_LLM", "0") in ("1", "true") or os.getenv("DEMO_OFFLINE", "0") in ("1", "true")
                if not mock_mode:
                    all_ok = False
    return all_ok


def check_dependencies() -> bool:
    print("\n--- Dependencies Import Check ---")
    all_ok = True
    for mod_name, pkg_name in DEPENDENCIES:
        try:
            __import__(mod_name)
            print(f"  {pkg_name} ({mod_name}): OK")
        except ImportError as e:
            print(f"  {pkg_name} ({mod_name}): FAILED (ImportError: {e})")
            all_ok = False
        except Exception as e:
            print(f"  {pkg_name} ({mod_name}): FAILED ({e})")
            all_ok = False
    return all_ok


def test_gemini_call() -> bool:
    print("\n--- Gemini LLM Call Check ---")
    try:
        from backend.llm import generate_text
        response = generate_text("Ping! Respond with 'pong'.")
        print(f"  Gemini call result: SUCCESS (response: {response.strip()[:60]})")
        return True
    except Exception as e:
        print(f"  Gemini call result: FAILED (Reason: {e})")
        return False


def main():
    print("=== Carbon Passport Environment & System Check ===\n")
    from backend.config import settings

    py_ok = check_python_version()
    env_ok = check_env_vars()
    deps_ok = check_dependencies()
    llm_ok = test_gemini_call()

    print("\n==================================================")
    if py_ok and env_ok and deps_ok and llm_ok:
        print("OVERALL STATUS: OK")
        sys.exit(0)
    else:
        print("OVERALL STATUS: FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
