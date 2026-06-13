"""
thumbnail.py — Creates dramatic "YOU + DANGER + QUESTION" thumbnails.
Style: dark cinematic background + bold title + danger element + dramatic text.
Background image generated via Google Gemini (gemini-2.5-flash-image).
"""
import os, logging, random
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from google import genai
from google.genai import types
from config import GEMINI_API_KEY, GEMINI_IMAGE_MODEL

log = logging.getLogger(__name__)
client = genai.Client(api_key=GEMINI_API_KEY)

FONT_BOLD   = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_NORMAL = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

CATEGORY_COLORS = {
    "ancient_history":    "#c0392b",
    "space_science":      "#2980b9",
    "nature_creature":    "#27ae60",
    "disaster_survival":  "#e67e22",
    "historical_era":     "#8e44ad",
    "extreme_environment":"#16a085",
}

def _load(path, size):
    try: return ImageFont.truetype(path, size)
    except: return ImageFont.load_default()

def _hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2],16) for i in (0,2,4))


def create_thumbnail(
    title: str,
    thumbnail_text: str,
    topic_type: str,
    output_path: str,
    thumbnail_danger: str = "",
) -> str:
    """
    Creates a 1280×720 dramatic thumbnail.
    Uses Pollinations.ai to generate a background image, then overlays text.
    Falls back to a painted dark background if image generation fails.
    """
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    accent = CATEGORY_COLORS.get(topic_type, "#c0392b")
    accent_rgb = _hex_rgb(accent)

    # ── Background image via Gemini ────────────────────────────────────────
    bg_prompt = (
        f"dramatic cinematic thumbnail background, {title}, "
        f"{thumbnail_danger or 'epic dramatic scene'}, "
        "dark moody lighting, no text, widescreen, semi realistic digital painting, "
        "high contrast, cinematic atmosphere, 16:9"
    )
    bg = None
    try:
        response = client.models.generate_content(
            model=GEMINI_IMAGE_MODEL,
            contents=bg_prompt,
            config=types.GenerateContentConfig(
                response_modalities=["Text", "Image"],
                image_config=types.ImageConfig(aspect_ratio="16:9"),
                seed=random.randint(1, 99999),
            ),
        )
        image_bytes = None
        for part in response.candidates[0].content.parts:
            if getattr(part, "inline_data", None) is not None:
                image_bytes = part.inline_data.data
                break
        if image_bytes is None:
            raise ValueError("Response did not contain image data")

        bg = Image.open(BytesIO(image_bytes)).convert("RGB").resize((1280, 720))
        # Darken it so text stands out
        overlay = Image.new("RGB", (1280, 720), (0, 0, 0))
        bg = Image.blend(bg, overlay, 0.45)
    except Exception as e:
        log.warning(f"Thumbnail background generation failed: {e} — using solid bg")
        bg = Image.new("RGB", (1280, 720), (12, 12, 25))

    draw = ImageDraw.Draw(bg)

    # ── Left accent bar ────────────────────────────────────────────────────
    draw.rectangle([0, 0, 10, 720], fill=accent_rgb)

    # ── Bottom gradient for text readability ──────────────────────────────
    for y in range(350, 720):
        alpha = int((y - 350) / 370 * 200)
        r = max(0, int(bg.getpixel((640, y))[0]) - alpha // 3)
        draw.line([(0,y),(1280,y)], fill=(0, 0, 0, 0))
    grad = Image.new("RGBA", (1280, 370), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for y in range(370):
        a = int(y / 370 * 180)
        gd.line([(0, y), (1280, y)], fill=(0, 0, 0, a))
    bg = bg.convert("RGBA")
    bg.paste(grad, (0, 350), grad)
    bg = bg.convert("RGB")
    draw = ImageDraw.Draw(bg)

    # ── Main title (large, white) ─────────────────────────────────────────
    font_title = _load(FONT_BOLD, 92)
    # Shrink if needed
    while font_title.size > 40:
        bb = draw.textbbox((0,0), title, font=font_title)
        if bb[2] - bb[0] < 1160: break
        font_title = _load(FONT_BOLD, font_title.size - 6)
    draw.text((70, 400), title, fill="white", font=font_title)

    # ── Dramatic thumbnail text (accent colour) ───────────────────────────
    font_tag = _load(FONT_BOLD, 68)
    draw.text((72, 560), thumbnail_text, fill=accent, font=font_tag)

    # ── "WATCH THIS" pill in top-right ────────────────────────────────────
    font_pill = _load(FONT_BOLD, 30)
    draw.rounded_rectangle([1060, 22, 1258, 66], radius=8, fill=accent_rgb)
    draw.text((1078, 31), "WATCH THIS", fill="white", font=font_pill)

    bg.save(output_path, "JPEG", quality=95)
    log.info(f"Thumbnail saved → {output_path}")
    return output_path
