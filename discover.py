"""
discover.py — Finds trending software tools to review.

Sources (all free, no auth):
  1. Product Hunt RSS feed — real trending launches
  2. Google Gemini — selects & enriches the best picks
"""
import json
import logging
import xml.etree.ElementTree as ET
import requests
from google import genai
from google.genai import types
from config import GEMINI_API_KEY, GEMINI_MODEL, REVIEW_CATEGORIES

log = logging.getLogger(__name__)
client = genai.Client(api_key=GEMINI_API_KEY)

PH_RSS_URL = "https://www.producthunt.com/feed"

DISCOVER_SYSTEM = """You are a tech content researcher.
Respond with ONLY a valid JSON array — no markdown, no extra text.
Each element must match this schema exactly:
{
  "name": "Exact product name",
  "category": "One of: AI Tools & Models | Developer Tools | SaaS Web Apps | Mobile Apps | Hardware & Gadgets",
  "tagline": "One sentence: what it does",
  "why_review_now": "Why this is worth reviewing now (max 20 words)",
  "search_context": "Key facts: pricing tier, main features, target user"
}"""


def _fetch_product_hunt(limit: int = 20) -> list[str]:
    """Scrape Product Hunt RSS for recently featured products."""
    try:
        resp = requests.get(PH_RSS_URL, timeout=10,
                            headers={"User-Agent": "TechReviewBot/1.0"})
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        items = root.findall(".//item")
        titles = [item.findtext("title", "").strip() for item in items[:limit]]
        titles = [t for t in titles if t]
        log.info(f"Fetched {len(titles)} products from Product Hunt RSS")
        return titles
    except Exception as exc:
        log.warning(f"Product Hunt RSS failed: {exc} — falling back to Gemini knowledge")
        return []


def discover_topics(
    categories=None,
    n_topics: int = 5,
    already_reviewed=None,
) -> list[dict]:
    """Return a list of trending tools to review."""
    cats  = categories or REVIEW_CATEGORIES
    skip  = ", ".join(already_reviewed) if already_reviewed else "none"
    ph    = _fetch_product_hunt(30)

    if ph:
        ph_block = "Recently trending on Product Hunt:\n" + "\n".join(f"- {t}" for t in ph)
        prompt = (
            f"From this list of recently trending products, pick the {n_topics} best candidates "
            f"that fit these categories: {', '.join(cats)}.\n\n"
            f"{ph_block}\n\n"
            f"Skip these already reviewed: {skip}\n\n"
            f"If the list doesn't have enough suitable candidates, add well-known tools "
            f"from your knowledge that would make great review videos right now.\n\n"
            f"Return a JSON array with exactly {n_topics} objects."
        )
    else:
        prompt = (
            f"Suggest {n_topics} software tools that would make excellent review videos "
            f"right now, in these categories: {', '.join(cats)}.\n\n"
            f"Focus on: recent launches, viral tools, or widely discussed products.\n"
            f"Skip these: {skip}\n\n"
            f"Return a JSON array with exactly {n_topics} objects."
        )

    log.info("Selecting topics with Gemini...")
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=DISCOVER_SYSTEM,
            temperature=0.7,
            max_output_tokens=2048,
        ),
    )

    raw = response.text.strip()
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    topics = json.loads(raw.strip())
    log.info(f"Discovered {len(topics)} topics: {[t['name'] for t in topics]}")
    return topics
