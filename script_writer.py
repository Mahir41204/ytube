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

SYSTEM = """You write immersive first-person YouTube video scripts that read like
a gripping short story, not a documentary voiceover.
The VIEWER is the main character. Always use "You", never "they" or third person.
Never say "Roman soldiers usually..." — say "You wake up before sunrise, and
your hands are already shaking from the cold."

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

LENGTH — THIS IS CRITICAL:
- The voiceover_script MUST be a long-form narrative of 1,800-2,200 words.
  Short scripts are treated as a failure. Do not summarize or rush — slow down,
  add more beats, more sensory detail, more internal thought, more dialogue
  (spoken aloud by other characters you encounter).
- Generate 24-30 scenes total, each one a meaningful narrative beat.
- voiceover_script must be ALL scene narrations joined together (nothing omitted,
  nothing added that isn't in a scene).

STORYTELLING CRAFT (this is what separates a good video from a great one):
- Open mid-action — never with throat-clearing or scene-setting. Something is
  already happening to "you" in sentence one.
- Give the viewer a CLEAR EMOTIONAL ARC: curiosity → unease → fear/excitement →
  desperation → a turning point → relief or awe → a haunting final thought.
- Layer in at least 3-4 distinct escalating problems/obstacles, not just one.
  Each should complicate or build on the last (a small mistake early on should
  matter later — plant it, then pay it off).
- Use vivid, specific sensory detail in nearly every scene: temperature,
  smell, texture, sound, taste, the weight of objects, how your body feels.
- Include moments of dialogue or other voices/sounds ("Someone shouts...",
  "A voice crackles...") to break up pure narration — but it's still spoken
  by the narrator, describing what is heard.
- Use second-person present or near-present tense ("You feel...", "Your
  fingers find...") to keep immediacy.
- Vary rhythm deliberately: short, punchy sentences during danger or shock.
  Longer, flowing sentences for wonder, scale, or reflection.
- Every scene should end on a hook, image, or small revelation that pulls the
  viewer into the next one — avoid flat, informational sentences.
- Build toward a genuine CLIMAX around scene 22-26 — the highest-stakes
  moment of the whole experience — followed by a resolution and a final
  reflective line that lingers (something the viewer will think about after
  the video ends).
- Avoid repeating the same words/phrases (e.g. don't open multiple scenes
  with "Suddenly" or "Now"). Vary vocabulary and sentence openings throughout.
- Treat this as narrative non-fiction storytelling — the goal is for the
  viewer to feel they LIVED something, not that they read a Wikipedia summary.

SCRIPT STRUCTURE (expand each phase with multiple scenes — weave naturally,
no headings, no explicit timestamps in the output):
1. Cold open / Hook — drop the viewer straight into a vivid, disorienting,
   or tense moment. Raise an immediate question.
2. Orientation — what/when/where you are, through sensation, not exposition.
   Plant a small detail that will matter later.
3. First friction — an early problem, mistake, or threat that forces you to
   adapt and learn the "rules" of this world.
4. Daily reality — the rhythm of this life, its small dangers and small
   wonders, deepening immersion (this can be 2-4 scenes of texture).
5. Rising complication — a second, bigger problem emerges, connected to or
   worsened by something from earlier.
6. Major threat — life is genuinely in danger; stakes peak.
7. Desperate decision — you must choose, act, or sacrifice something.
8. Climax — the single most intense moment of the entire scenario.
9. Aftermath — immediate consequences, how you (and others) are changed.
10. Outcome + final reflection — fast-forward to how this life/scenario
   resolves, and end on one resonant, thought-provoking final line.

IMAGE PROMPT RULES (critical for quality):
- Style suffix always: "semi realistic digital painting, cinematic lighting, high detail, storytelling illustration, documentary style, dramatic atmosphere, 16:9"
- camera "first_person": describe what viewer's hands/feet/tools look like in frame
- camera "over_shoulder": viewer sees back of character's head in scene
- camera "wide_cinematic": epic establishing or battle shot
- Be specific: time of day, weather, clothing, environment details
- No modern elements for historical topics
- Vary compositions across scenes — avoid repeating the same camera angle or
  framing back-to-back.

animation must be one of: slow_zoom_in | slow_zoom_out | pan_right | pan_left | static"""

SCRIPT_FORMULA = """
Storytelling formula reminders:
- Plant → Develop → Pay Off (repeat across the whole script)
- Problem → Decision → Consequence → Worse Problem (the spiral drives momentum)
- Viewer must FEEL they are there — not learn facts about history/nature
- Use ALL five senses, not just sight. Smell is the most immersive and most forgotten.
- Vary sentence length deliberately. Short sentences = danger, shock, action.
  Long sentences = wonder, scale, dread building slowly.
- End every scene on a hook, image, or question that pulls forward
- At least once, address the viewer's inner thought directly
  ("You tell yourself it's fine. You know it isn't.")
- The final line of the entire script must be a single, haunting, resonant
  sentence the viewer will still be thinking about ten minutes later.
"""


def generate_script(topic: dict) -> dict:
    """
    Generate a full immersive script for a 'Your Life as...' topic.
    Returns the JSON with voiceover_script, scenes, and YouTube metadata.
    Target: 1,800-2,200 word narration across 24-30 scenes → ~7-8 min video
    at 1.5x playback speed.
    """
    prompt = (
        f"Write a complete immersive video script for: **{topic['title']}**\n\n"
        f"Topic type: {topic.get('topic_type', 'general')}\n"
        f"Hook idea: {topic.get('hook', '')}\n"
        f"Setting context: {topic.get('setting', '')}\n\n"
        f"{SCRIPT_FORMULA}\n\n"
        "MANDATORY LENGTH: The voiceover_script must be 1,800-2,200 words of rich, "
        "immersive narrative — NOT a short summary. Generate 24-30 scenes. "
        "Each scene's narration should be 3-6 sentences of vivid, specific prose. "
        "A short script is a failed script.\n\n"
        "The voiceover_script must be the complete joined narration of ALL scenes — "
        "every word that will be spoken, nothing more, nothing less.\n\n"
        "Return only the JSON object, no markdown fences."
    )

    log.info(f"Writing immersive script for '{topic['title']}'...")

    last_error = None
    for attempt in range(1, 4):
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM,
                temperature=0.90,
                max_output_tokens=16384,
                response_mime_type="application/json",
                # Disable thinking tokens so the full budget goes to the script.
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
            if attempt < 3:
                log.warning(f"  Attempt {attempt}: invalid JSON ({exc}). Retrying...")
            else:
                log.warning(f"  Attempt {attempt}: invalid JSON ({exc}). Giving up.")
    else:
        raise ValueError(f"Model did not return valid JSON after 3 attempts: {last_error}")

    # Validate length — warn if the model came up short
    word_count = len(data.get("voiceover_script", "").split())
    scene_count = len(data.get("scenes", []))
    if word_count < 1200:
        log.warning(f"  Script is short ({word_count} words). Consider re-running.")
    else:
        log.info(f"  Script quality: {word_count} words, {scene_count} scenes ✓")

    data["yt_tags"]    = data.get("yt_tags", [])[:15]
    data["topic_type"] = topic.get("topic_type", "general")
    data["music_style"]= topic.get("music_style", "orchestral_documentary")

    log.info(f"Script ready: {scene_count} scenes, {word_count} words")
    return data
