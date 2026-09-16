import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

# ── API Keys ─────────────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GROQ_API_KEY   = os.getenv("GROQ_API_KEY", "")

# ── Models ───────────────────────────────────────────────────────
GPT4V_MODEL  = os.getenv("GPT4V_MODEL", "gpt-4o")
GROQ_MODEL   = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

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
]

# ── Ensure output dir exists ──────────────────────────────────────
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(PAPERS_DIR, exist_ok=True)
os.makedirs(GT_DIR, exist_ok=True)

def validate_api_keys():
    missing = [name for name, value in (("OPENAI_API_KEY", OPENAI_API_KEY), ("GROQ_API_KEY", GROQ_API_KEY)) if not value.strip()]
    if missing:
        raise ValueError("Missing API keys in .env: " + ", ".join(missing))
