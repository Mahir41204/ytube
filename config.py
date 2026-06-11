"""
config.py — Central configuration for the Tech Review Video Pipeline.
All secrets are loaded from environment variables (set in .env).
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── Google Gemini (free tier: 1,500 req/day) ───────────────────────────────
# Get key at: https://aistudio.google.com/app/apikey  (no credit card needed)
GEMINI_API_KEY      = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL        = "gemini-1.5-flash"

# ── gTTS (Google Text-to-Speech) ────────────────────────────────────────────
# No API key needed — uses Google Translate TTS endpoint, completely free
GTTS_LANGUAGE       = "en"
GTTS_TLD            = "com"   # accent: com=US, co.uk=British, com.au=Australian

# ── Pexels ─────────────────────────────────────────────────────────────────
PEXELS_API_KEY      = os.getenv("PEXELS_API_KEY", "")

# ── YouTube Data API ───────────────────────────────────────────────────────
YT_CLIENT_ID        = os.getenv("YOUTUBE_CLIENT_ID", "")
YT_CLIENT_SECRET    = os.getenv("YOUTUBE_CLIENT_SECRET", "")
YT_REFRESH_TOKEN    = os.getenv("YOUTUBE_REFRESH_TOKEN", "")
YT_CATEGORY_ID      = "28"   # Science & Technology
YT_DEFAULT_PRIVACY  = "public"

# ── Airtable ───────────────────────────────────────────────────────────────
AIRTABLE_API_TOKEN  = os.getenv("AIRTABLE_API_TOKEN", "")
AIRTABLE_BASE_ID    = os.getenv("AIRTABLE_BASE_ID", "")
AIRTABLE_TABLE_NAME = "Video Queue"

# ── Video output settings ──────────────────────────────────────────────────
VIDEO_RESOLUTION    = "1920x1080"
VIDEO_FPS           = 30
INTRO_DURATION_SEC  = 4
OUTRO_DURATION_SEC  = 4
TEMP_DIR            = "/tmp/pipeline"

# ── Review categories to discover ─────────────────────────────────────────
REVIEW_CATEGORIES = [
    "AI Tools & Models",
    "Developer Tools",
    "SaaS Web Apps",
    "Mobile Apps",
    "Hardware & Gadgets",
]

def validate():
    """Raise if any required key is missing."""
    required = {
        "GEMINI_API_KEY": GEMINI_API_KEY,
        "PEXELS_API_KEY": PEXELS_API_KEY,
        "YOUTUBE_CLIENT_ID": YT_CLIENT_ID,
        "YOUTUBE_CLIENT_SECRET": YT_CLIENT_SECRET,
        "YOUTUBE_REFRESH_TOKEN": YT_REFRESH_TOKEN,
        "AIRTABLE_API_TOKEN": AIRTABLE_API_TOKEN,
        "AIRTABLE_BASE_ID": AIRTABLE_BASE_ID,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise EnvironmentError(f"Missing required env vars: {', '.join(missing)}")
