"""config.py — Central config for the immersive scenario video pipeline."""
import os
from dotenv import load_dotenv
load_dotenv()

# ── Google Gemini ──────────────────────────────────────────────────────────
GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL    = "gemini-2.5-flash"

# ── Gemini TTS voiceover ───────────────────────────────────────────────────
# Uses the same GEMINI_API_KEY as the script writer.
# Model: gemini-2.5-flash-preview-tts (fast, high-quality, natural pacing)
GEMINI_TTS_MODEL = "gemini-2.5-flash-preview-tts"
# Voice options: Charon (Informative) | Fenrir (Excitable) | Orus (Firm)
# | Algieba (Smooth) | Gacrux (Mature) | Sulafat (Warm)
GEMINI_TTS_VOICE = os.getenv("GEMINI_TTS_VOICE", "Charon")

# Gemini TTS speaks at roughly 150 wpm in documentary-narrator mode.
# The assembler uses this to calculate per-scene image durations.
SPEAKING_WPM        = 150

# ── Hugging Face — FLUX.1-schnell image generation (free) ─────────────────
# Get a free token at https://huggingface.co/settings/tokens (read access only)
# Free tier: ~few hundred requests/hour — plenty for this pipeline.
HF_TOKEN          = os.getenv("HF_TOKEN", "")
HF_IMAGE_MODEL    = "black-forest-labs/FLUX.1-schnell"
HF_IMAGE_API_URL  = f"https://api-inference.huggingface.co/models/{HF_IMAGE_MODEL}"
IMAGE_WIDTH       = 1920
IMAGE_HEIGHT      = 1080
# Native generation size (HF inference); upscaled to IMAGE_WIDTH x IMAGE_HEIGHT
# using LANCZOS. 16:9 native keeps quality high without asking for 1920x1080.
HF_GEN_WIDTH      = 1024
HF_GEN_HEIGHT     = 576

# ── Pexels stock photo search (free fallback for images) ───────────────────
PEXELS_API_KEY      = os.getenv("PEXELS_API_KEY", "")
PEXELS_SEARCH_URL   = "https://api.pexels.com/v1/search"

# ── Video settings ─────────────────────────────────────────────────────────
VIDEO_FPS           = 30
SCENE_MIN_DURATION  = 4.0             # seconds per image minimum
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
    if not HF_TOKEN:
        import logging
        logging.getLogger(__name__).warning(
            "HF_TOKEN not set — image generation will fall back to Pexels only. "
            "Get a free token at https://huggingface.co/settings/tokens"
        )
