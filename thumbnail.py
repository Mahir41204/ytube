"""
thumbnail.py — Creates dramatic "YOU + DANGER + QUESTION" thumbnails.
Style: dark cinematic background + bold title + danger element + dramatic text.
Background image: FLUX.1-schnell via HF Inference API, falling back to
Pexels stock photo search, then a solid dark background.
"""
import os, logging, random, re, requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from config import (
    HF_TOKEN, HF_IMAGE_API_URL, HF_GEN_WIDTH, HF_GEN_HEIGHT,
    PEXELS_API_KEY, PEXELS_SEARCH_URL,
)
from visuals import _hf_flux_image_bytes, _pexels_image_bytes, _simplify_query

log = logging.getLogger(__name__)

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
    Uses Gemini (or a Pexels stock photo) to generate a background image, then overlays text.
    Falls back to a painted dark background if image generation fails.
    """
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    accent = CATEGORY_COLORS.get(topic_type, "#c0392b")
    accent_rgb = _hex_rgb(accent)

    # ── Background: FLUX.1-schnell → Pexels → solid dark ──────────────────
    bg_prompt = (
        f"dramatic cinematic thumbnail background, {title}, "
        f"{thumbnail_danger or 'epic dramatic scene'}, "
        "dark moody lighting, no text, no watermark, widescreen, "
        "cinematic digital painting, high contrast, dramatic atmosphere"
    )

    image_bytes = _hf_flux_image_bytes(bg_prompt, seed=random.randint(1, 99999), retries=3)

    if image_bytes is None:
        query = _simplify_query(f"{title} {thumbnail_danger}")
        log.info(f"FLUX unavailable — trying Pexels for thumbnail: '{query}'")
        image_bytes = _pexels_image_bytes(query, seed=random.randint(0, 7))

    if image_bytes is not None:
        bg = Image.open(BytesIO(image_bytes)).convert("RGB").resize((1280, 720))
        # Darken it so text stands out
        overlay = Image.new("RGB", (1280, 720), (0, 0, 0))
        bg = Image.blend(bg, overlay, 0.45)
    else:
        log.warning("No background image available — using solid bg")
        bg = Image.new("RGB", (1280, 720), (12, 12, 25))

    draw = ImageDraw.Draw(bg)

    # ── Left accent bar ────────────────────────────────────────────────────
    draw.rectangle([0, 0, 10, 720], fill=accent_rgb)

    # ── Bottom gradient for text readability ──────────────────────────────
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
    pill_text = "WATCH THIS"
    pad_x, pad_y = 18, 10
    bb = draw.textbbox((0, 0), pill_text, font=font_pill)
    text_w, text_h = bb[2] - bb[0], bb[3] - bb[1]
    pill_right  = 1258
    pill_left   = pill_right - (text_w + pad_x * 2)
    pill_top    = 22
    pill_bottom = pill_top + (text_h + pad_y * 2)
    draw.rounded_rectangle([pill_left, pill_top, pill_right, pill_bottom],
                           radius=8, fill=accent_rgb)
    draw.text((pill_left + pad_x, pill_top + pad_y - bb[1]), pill_text,
              fill="white", font=font_pill)

    bg.save(output_path, "JPEG", quality=95)
    log.info(f"Thumbnail saved → {output_path}")
    return output_path
