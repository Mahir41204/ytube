"""
discover.py — Generates "Your Life as..." scenario topics.
Uses Gemini + Product Hunt trends for inspiration,
but all topics are crafted around immersive first-person scenarios.
"""
import json, logging
from google import genai
from google.genai import types
from config import GEMINI_API_KEY, GEMINI_MODEL, TOPIC_TYPES, MUSIC_STYLES

log = logging.getLogger(__name__)
client = genai.Client(api_key=GEMINI_API_KEY)

SYSTEM = """You generate viral YouTube video topics for an immersive first-person scenario channel.
Every topic follows the format: "Your Life as [X]", "Your Life on [X]", or "A Day as [X]".
The viewer IS the main character. They experience it, not learn about it.

Respond ONLY with a valid JSON array. Each element:
{
  "title": "Your Life as a Roman Soldier",
  "topic_type": "ancient_history",
  "hook": "One shocking fact that instantly creates curiosity (max 20 words)",
  "setting": "Brief vivid setting description for the script writer (2-3 sentences)",
  "music_style": "orchestral_documentary"
}

topic_type must be one of:
  ancient_history | space_science | nature_creature |
  disaster_survival | historical_era | extreme_environment

music_style must be one of:
  orchestral_documentary | ambient_scifi | cinematic_tension | atmospheric_adventure"""

VIRAL_EXAMPLES = [
    "Your Life as a Roman Soldier",
    "Your Life on Mars",
    "Your Life During the Black Death",
    "Your Life as an Ant",
    "Your Life as a Viking",
    "Your Life in Ancient Egypt",
    "Your Life During the Ice Age",
    "Your Life as a Deep Sea Fish",
    "Your Life on Jupiter",
    "Your Life During Pompeii",
    "Your Life in Medieval England",
    "Your Life as a Samurai",
    "Your Life During WWI Trenches",
    "Your Life as a T-Rex",
]


def _extract_json_payload(raw: str):
    raw = raw.strip()
    if "```" in raw:
        parts = [part.strip() for part in raw.split("```") if part.strip()]
        for part in parts:
            if part.startswith("json"):
                raw = part[4:].strip()
                break
        else:
            raw = parts[0]

    start_candidates = [raw.find("["), raw.find("{")]
    start_candidates = [idx for idx in start_candidates if idx != -1]
    if start_candidates:
        raw = raw[min(start_candidates):]

    return json.loads(raw)


def discover_topics(n_topics: int = 3, already_done=None) -> list:
    skip = ", ".join(already_done) if already_done else "none"

    prompt = (
        f"Generate {n_topics} fresh video topics for a 'Your Life as...' YouTube channel.\n\n"
        f"Already done (skip these): {skip}\n\n"
        "Rules:\n"
        "- Mix topic_types for variety (don't do all ancient_history)\n"
        "- Topics must create strong curiosity AND visceral first-person experience\n"
        "- Think: Familiar concept + Unknown daily reality = Viral\n"
        f"- Examples of great topics: {', '.join(VIRAL_EXAMPLES[:6])}\n\n"
        f"Return a JSON array of exactly {n_topics} fresh topic objects."
    )

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM,
            temperature=0.95,   # higher creativity for topic variety
            max_output_tokens=1024,
            response_mime_type="application/json",
        ),
    )
    topics = _extract_json_payload(response.text)
    # Ensure music_style is set correctly
    for t in topics:
        if "music_style" not in t:
            t["music_style"] = MUSIC_STYLES.get(t.get("topic_type", ""), "orchestral_documentary")
    log.info(f"Discovered topics: {[t['title'] for t in topics]}")
    return topics
