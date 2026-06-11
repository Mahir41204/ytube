"""
script_writer.py — Generates full review scripts using Google Gemini.
Free tier: 1,500 requests/day, no credit card required.
"""
import json
import logging
from google import genai
from google.genai import types
from config import GEMINI_API_KEY, GEMINI_MODEL

log = logging.getLogger(__name__)
client = genai.Client(api_key=GEMINI_API_KEY)

SCRIPT_SYSTEM = """You are a professional tech YouTuber who writes punchy, honest review scripts.
Your videos are direct, skip filler, and always have a clear opinion.

Respond with ONLY a valid JSON object — no markdown fences, no extra text:
{
  "title": "YouTube title (max 60 chars, SEO-optimised and compelling)",
  "description": "YouTube description (250-300 words). Include: hook, what the tool does, 3 key points, verdict, timestamps [00:00 Intro | 01:00 Features | 02:30 Verdict], 3-5 hashtags at end",
  "tags": ["tag1", "tag2"],
  "thumbnail_text": "Short punchy thumbnail overlay (max 18 chars, e.g. 'Worth It?' or 'GAME CHANGER')",
  "rating": 7.5,
  "script": "Full voiceover — conversational, no stage directions, no headings. Just the words to speak. 350-450 words.",
  "visual_queries": ["pexels video search term 1", "pexels video search term 2"],
  "key_points": ["Point 1 (max 6 words)", "Point 2", "Point 3", "Point 4"],
  "duration_estimate": 200
}

Script structure (woven naturally into narration):
1. Hook — bold claim or question (15 sec)
2. What it is and who it's for (30 sec)
3. 3-4 key features, honest take (75 sec)
4. Pricing (15 sec)
5. Pros and cons — blunt (30 sec)
6. Verdict + rating out of 10 (20 sec)
7. Like and subscribe CTA (10 sec)

visual_queries: 5-7 Pexels search terms matching the review content
key_points: short lower-third text overlays (4-6 items, max 6 words each)"""


def generate_script(
    tool_name: str,
    category: str,
    search_context: str = "",
    why_review_now: str = "",
) -> dict:
    """Generate a full review script for a tool using Gemini."""
    prompt = f"Write a complete YouTube review script for: **{tool_name}**\nCategory: {category}\n"
    if why_review_now:
        prompt += f"Why it's relevant now: {why_review_now}\n"
    if search_context:
        prompt += f"Known facts: {search_context}\n"
    prompt += (
        "\nBe specific about features and pricing. "
        "Return the JSON object as specified in your instructions."
    )

    log.info(f"Generating script for '{tool_name}' with Gemini...")
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SCRIPT_SYSTEM,
            temperature=0.8,
            max_output_tokens=4096,
        ),
    )

    raw = response.text.strip()
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    data = json.loads(raw.strip())
    data["tags"] = data.get("tags", [])[:15]
    log.info(f"Script ready for '{tool_name}' (~{data.get('duration_estimate', '?')}s)")
    return data
