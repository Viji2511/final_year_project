import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

# ── API Keys ─────────────────────────────────────────────────────
# NOTE: OPENAI_API_KEY is retained in config for legacy compatibility.
# Stage 2A no longer uses OpenAI; it uses Groq Vision instead.
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GROQ_API_KEY   = os.getenv("GROQ_API_KEY", "")

# ── Models ───────────────────────────────────────────────────────
# Legacy / unused variables kept for backward compatibility:
GPT4V_MODEL  = os.getenv("GPT4V_MODEL", "gpt-4o")       # No longer used by Stage 2A

# GROQ_MODEL is an alias for GROQ_CODE_MODEL for backward compatibility.
# Stage 3 and Stage 4 both use this for text/code generation.
GROQ_MODEL       = os.getenv("GROQ_CODE_MODEL",  os.getenv("GROQ_MODEL", ""))
GROQ_CODE_MODEL  = GROQ_MODEL   # explicit alias — Stage 4 code generation

# Stage 2A — Groq Vision model for figure understanding.
# Must be verified as vision-capable at startup.
GROQ_VISION_MODEL = os.getenv("GROQ_VISION_MODEL", "")

# Vision image max-dimension (resize before sending to API)
GROQ_VISION_MAX_DIM    = int(os.getenv("GROQ_VISION_MAX_DIM", "512"))
GROQ_VISION_MAX_TOKENS = int(os.getenv("GROQ_VISION_MAX_TOKENS", "1500"))

GROQ_PLANNER_MAX_TOKENS = int(os.getenv("GROQ_PLANNER_MAX_TOKENS", "1000"))
GROQ_CODEGEN_MAX_TOKENS = int(os.getenv("GROQ_CODEGEN_MAX_TOKENS", "4000"))

# ── Pipeline settings ────────────────────────────────────────────
PIPELINE_MODE = os.getenv("PIPELINE_MODE", "generate_only").strip().lower()
if PIPELINE_MODE not in {"generate_only", "full"}:
    raise ValueError("PIPELINE_MODE must be generate_only or full")

MAX_RETRIES        = 3
FIDELITY_TOLERANCE = 0.05   # 5% numeric tolerance
SSIM_THRESHOLD     = 0.85
DOCKER_CPU         = 4
DOCKER_RAM         = "16g"
DOCKER_TIMEOUT     = 14400  # 4 hours in seconds

# ── Paths ────────────────────────────────────────────────────────
BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
MREP_BENCH_DIR  = os.path.join(BASE_DIR, "mrep_bench")
PAPERS_DIR      = os.path.join(MREP_BENCH_DIR, "papers")
GT_DIR          = os.path.join(MREP_BENCH_DIR, "ground_truth")
OUTPUT_DIR      = os.path.join(BASE_DIR, "outputs")
SANDBOX_DIR     = os.path.join(BASE_DIR, "sandbox")

# ── Supported figure types ────────────────────────────────────────
SUPPORTED_FIGURE_TYPES = [
    "line_chart",
    "bar_chart",
    "confusion_matrix",
    "training_curve",
    "other",  # Groq Vision may return 'other' for complex figures
]

# ── Ensure output dir exists ──────────────────────────────────────
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(PAPERS_DIR, exist_ok=True)
os.makedirs(GT_DIR, exist_ok=True)


def validate_api_keys():
    """
    Validate that GROQ_API_KEY and GROQ_CODE_MODEL are configured.
    Does NOT require OPENAI_API_KEY — Stage 2A now uses Groq Vision.
    """
    if not GROQ_API_KEY.strip():
        raise ValueError("Missing API keys in .env: GROQ_API_KEY")

    if not GROQ_CODE_MODEL.strip():
        raise ValueError("Missing GROQ_CODE_MODEL (or GROQ_MODEL) in .env")

    # Validate that GROQ_CODE_MODEL is available
    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        models = client.models.list()
        available_models = [m.id for m in models.data]
        if GROQ_CODE_MODEL not in available_models:
            raise ValueError(
                f"The configured GROQ_CODE_MODEL '{GROQ_CODE_MODEL}' is not available. "
                f"Available models: {', '.join(available_models)}"
            )
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Failed to validate Groq code model: {e}")


def validate_vision_model():
    """
    Validate that GROQ_VISION_MODEL is configured and available.
    Called by Stage 2A before executing figure parsing.

    Raises structured errors:
      - GROQ_VISION_MODEL_UNAVAILABLE  — model not in models.list()
      - GROQ_VISION_AUTH_FAILED        — API key rejected
      - GROQ_VISION_REQUEST_FAILED     — generic connectivity issue
    """
    if not GROQ_API_KEY.strip():
        raise ValueError("[GROQ_VISION_AUTH_FAILED] GROQ_API_KEY is missing or empty.")

    if not GROQ_VISION_MODEL.strip():
        raise ValueError(
            "[GROQ_VISION_MODEL_UNAVAILABLE] GROQ_VISION_MODEL is not set in .env. "
            "Please set GROQ_VISION_MODEL to a vision-capable Groq model."
        )

    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        models = client.models.list()
        available_models = [m.id for m in models.data]
    except Exception as e:
        error_str = str(e).lower()
        if "auth" in error_str or "401" in error_str or "api key" in error_str:
            raise ValueError(f"[GROQ_VISION_AUTH_FAILED] Groq API authentication failed: {e}")
        raise ValueError(f"[GROQ_VISION_REQUEST_FAILED] Could not reach Groq API to validate vision model: {e}")

    if GROQ_VISION_MODEL not in available_models:
        raise ValueError(
            f"[GROQ_VISION_MODEL_UNAVAILABLE] The configured GROQ_VISION_MODEL "
            f"'{GROQ_VISION_MODEL}' is not available for this API key. "
            f"Available models: {', '.join(available_models)}"
        )
    # Model is present; vision capability was verified empirically (see probe_qwen_vision.py)
    # for qwen/qwen3.8-27b — it accepts image_url content with resized base64 PNG.
