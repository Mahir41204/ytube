"""config.py — Central config for the immersive scenario video pipeline."""
import os
from dotenv import load_dotenv
load_dotenv()

# ── Google Gemini ──────────────────────────────────────────────────────────
GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL    = "gemini-2.5-flash"

# ── gTTS voiceover ─────────────────────────────────────────────────────────
GTTS_LANGUAGE   = "en"
GTTS_TLD        = os.getenv("GTTS_TLD", "com")   # com=US | co.uk=British

# ── Google Gemini image generation ─────────────────────────────────────────
# Uses the same GEMINI_API_KEY as the script writer.
GEMINI_IMAGE_MODEL  = "gemini-2.5-flash-image"
IMAGE_WIDTH         = 1920
IMAGE_HEIGHT        = 1080

# ── Video settings ─────────────────────────────────────────────────────────
VIDEO_FPS           = 30
SCENE_MIN_DURATION  = 3.5             # seconds per image minimum
SPEAKING_WPM        = 130             # words per minute for timing estimation
TRANSITION_DURATION = 0.4             # crossfade between scenes (seconds)

# ── Music ─────────────────────────────────────────────────────────────────
MUSIC_DIR           = os.path.join(os.path.dirname(__file__), "music")
MUSIC_VOLUME        = 0.18            # background music volume (0-1)

# ── YouTube ────────────────────────────────────────────────────────────────
YT_CLIENT_ID        = os.getenv("YOUTUBE_CLIENT_ID", "")
YT_CLIENT_SECRET    = os.getenv("YOUTUBE_CLIENT_SECRET", "")
YT_REFRESH_TOKEN    = os.getenv("YOUTUBE_REFRESH_TOKEN", "")
YT_CATEGORY_ID      = "27"            # 27 = Education (fits this niche better)
YT_DEFAULT_PRIVACY  = "public"

# ── Airtable ───────────────────────────────────────────────────────────────
AIRTABLE_API_TOKEN  = os.getenv("AIRTABLE_API_TOKEN", "")
AIRTABLE_BASE_ID    = os.getenv("AIRTABLE_BASE_ID", "")
AIRTABLE_TABLE_NAME = "Video Queue"

# ── Topic categories ───────────────────────────────────────────────────────
TOPIC_TYPES = [
    "ancient_history",
    "space_science",
    "nature_creature",
    "disaster_survival",
    "historical_era",
    "extreme_environment",
]

MUSIC_STYLES = {
    "ancient_history":    "orchestral_documentary",
    "space_science":      "ambient_scifi",
    "nature_creature":    "atmospheric_adventure",
    "disaster_survival":  "cinematic_tension",
    "historical_era":     "orchestral_documentary",
    "extreme_environment":"cinematic_tension",
}

def validate():
    missing = [k for k, v in {
        "GEMINI_API_KEY":      GEMINI_API_KEY,
        "YOUTUBE_CLIENT_ID":   YT_CLIENT_ID,
        "YOUTUBE_CLIENT_SECRET": YT_CLIENT_SECRET,
        "YOUTUBE_REFRESH_TOKEN": YT_REFRESH_TOKEN,
    }.items() if not v]
    if missing:
        raise EnvironmentError(f"Missing env vars: {', '.join(missing)}")
