"""
script_writer.py — Writes immersive second-person scenario scripts.
The viewer is always "You". Never "Roman soldiers usually..." — always "You wake up..."

Output includes the full narration split into timed scenes,
each with a cinematic image prompt for image generation.
"""
import json, logging
from google import genai
from google.genai import types
from config import GEMINI_API_KEY, GEMINI_MODEL

log = logging.getLogger(__name__)
client = genai.Client(api_key=GEMINI_API_KEY)

SYSTEM = """You write immersive first-person YouTube video scripts.
The VIEWER is the main character. Always use "You", never "they" or third person.
Never say "Roman soldiers usually..." — say "You wake up before sunrise."

Respond ONLY with valid JSON — no markdown, no extra text:
{
  "yt_title": "Your Life as a Roman Soldier (60 chars max, include 'Your Life')",
  "yt_description": "Compelling YT description, 200 words, end with 5 hashtags",
  "yt_tags": ["tag1", "tag2"],
  "thumbnail_text": "CAN YOU SURVIVE? (max 20 chars, dramatic question or statement)",
  "thumbnail_danger": "One-line danger element for thumbnail art direction",
  "voiceover_script": "The COMPLETE narration as one continuous text block. Pure speech — no [brackets], no scene labels, no directions. This is exactly what gets spoken.",
  "scenes": [
    {
      "narration": "Exact portion of voiceover_script for this scene.",
      "image_prompt": "Detailed cinematic image-generation prompt (see rules below)",
      "animation": "slow_zoom_in",
      "camera": "first_person"
    }
  ]
}

SCRIPT STRUCTURE (weave naturally, no headings):
1. Hook (0-15s): Drop viewer INTO the scenario immediately. Danger, urgency, strangeness.
2. Arrival (15-40s): Where and when. What you see, smell, feel first.
3. First Problem (40-80s): Something immediately threatens you or confuses you.
4. Learning (80-130s): You figure out how to survive the basics. Daily reality.
5. Major Threat (130-180s): Something big goes wrong. Life is in danger.
6. Survival (180-220s): How you cope. Decisions. Consequences.
7. Climax (220-250s): Peak moment of the scenario.
8. Outcome + Final Reflection (250-270s): Fast forward. How it ends. What it meant.

SCENE RULES:
- 12-18 scenes total
- Each scene narration: 2-4 sentences max
- voiceover_script must be ALL scene narrations joined together (nothing omitted)

IMAGE PROMPT RULES (critical for quality):
- Style suffix always: "semi realistic digital painting, cinematic lighting, high detail, storytelling illustration, documentary style, dramatic atmosphere, 16:9"
- camera "first_person": describe what viewer's hands/feet/tools look like in frame
- camera "over_shoulder": viewer sees back of character's head in scene
- camera "wide_cinematic": epic establishing or battle shot
- Be specific: time of day, weather, clothing, environment details
- No modern elements for historical topics

animation must be one of: slow_zoom_in | slow_zoom_out | pan_right | pan_left | static"""

SCRIPT_FORMULA = """
Script formula reminders:
- Problem → Decision → Consequence → New Problem (repeat)
- Viewer must FEEL they are there, not learn facts
- Use sensory details: cold, hunger, smell of smoke, weight of armour
- Vary sentence length: short punchy lines for danger, longer for wonder
- End each scene on a mini-cliffhanger or revelation when possible
"""


def generate_script(topic: dict) -> dict:
    """
    Generate a full immersive script for a 'Your Life as...' topic.
    Returns the JSON with voiceover_script, scenes, and YouTube metadata.
    """
    prompt = (
        f"Write a complete immersive video script for: **{topic['title']}**\n\n"
        f"Topic type: {topic.get('topic_type', 'general')}\n"
        f"Hook idea: {topic.get('hook', '')}\n"
        f"Setting context: {topic.get('setting', '')}\n\n"
        f"{SCRIPT_FORMULA}\n"
        "Generate 12-16 scenes covering the full experience from arrival to outcome.\n"
        "The voiceover_script must be gripping, immersive, and feel like a journey.\n"
        "Return only the JSON object."
    )

    log.info(f"Writing immersive script for '{topic['title']}'...")

    last_error = None
    for attempt in range(1, 3):
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM,
                temperature=0.85,
                max_output_tokens=16384,
                response_mime_type="application/json",
                # gemini-2.5-flash spends part of max_output_tokens on
                # "thinking" by default, which can truncate the JSON
                # output. Disable it so the full budget goes to the script.
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )

        raw = (response.text or "").strip()
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        try:
            data = json.loads(raw)
            break
        except json.JSONDecodeError as exc:
            last_error = exc
            log.warning(f"  Attempt {attempt}: model returned invalid JSON ({exc}). "
                        f"Retrying..." if attempt == 1 else "Giving up.")
    else:
        raise ValueError(f"Model did not return valid JSON after retries: {last_error}")

    data["yt_tags"] = data.get("yt_tags", [])[:15]
    data["topic_type"] = topic.get("topic_type", "general")
    data["music_style"] = topic.get("music_style", "orchestral_documentary")

    log.info(f"Script ready: {len(data.get('scenes', []))} scenes, "
             f"{len(data.get('voiceover_script', '').split())} words")
    return data
