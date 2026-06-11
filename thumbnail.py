"""
thumbnail.py — Generates a YouTube-optimised thumbnail (1280×720) using Pillow.
Creates a clean, bold design: dark gradient + tool name + category badge + verdict text.
"""
import os
import logging
from PIL import Image, ImageDraw, ImageFont

log = logging.getLogger(__name__)

THUMB_W, THUMB_H = 1280, 720

# Category → accent colour mapping
CATEGORY_COLORS = {
    "AI Tools & Models":   "#6366f1",   # indigo
    "Developer Tools":     "#10b981",   # emerald
    "SaaS Web Apps":       "#3b82f6",   # blue
    "Mobile Apps":         "#f59e0b",   # amber
    "Hardware & Gadgets":  "#ef4444",   # red
    "Tech":                "#8b5cf6",   # purple (default)
}

FONT_PATH_BOLD   = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_PATH_NORMAL = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def _load_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def _draw_gradient(draw: ImageDraw.Draw, w: int, h: int, top: tuple, bottom: tuple):
    """Render a vertical gradient from top colour to bottom colour."""
    for y in range(h):
        t = y / h
        r = int(top[0] + (bottom[0] - top[0]) * t)
        g = int(top[1] + (bottom[1] - top[1]) * t)
        b = int(top[2] + (bottom[2] - top[2]) * t)
        draw.line([(0, y), (w, y)], fill=(r, g, b))


def _hex_to_rgb(hex_color: str) -> tuple:
    h = hex_color.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def create_thumbnail(
    tool_name: str,
    thumbnail_text: str,
    category: str,
    output_path: str,
    rating: float | None = None,
) -> str:
    """
    Create and save a YouTube thumbnail.

    Args:
        tool_name:       Product name (large text).
        thumbnail_text:  Short punchy overlay (e.g. "Worth It?" / "GAME CHANGER").
        category:        Used to pick accent colour.
        output_path:     Where to save the .jpg file.
        rating:          Optional numeric rating to display (e.g. 8.5).

    Returns:
        output_path on success.
    """
    accent_hex = CATEGORY_COLORS.get(category, CATEGORY_COLORS["Tech"])
    accent_rgb = _hex_to_rgb(accent_hex)

    img  = Image.new("RGB", (THUMB_W, THUMB_H))
    draw = ImageDraw.Draw(img)

    # ── Background gradient (dark navy → slightly lighter) ──────────────────
    _draw_gradient(draw, THUMB_W, THUMB_H, (10, 14, 36), (22, 30, 64))

    # ── Accent stripe on left ────────────────────────────────────────────────
    draw.rectangle([0, 0, 10, THUMB_H], fill=accent_rgb)

    # ── Large diagonal accent shape (subtle) ────────────────────────────────
    overlay = Image.new("RGBA", (THUMB_W, THUMB_H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.polygon([(800, 0), (THUMB_W, 0), (THUMB_W, THUMB_H), (620, THUMB_H)],
               fill=(*accent_rgb, 18))
    img.paste(Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB"))
    draw = ImageDraw.Draw(img)

    # ── Tool name ─────────────────────────────────────────────────────────────
    font_title = _load_font(FONT_PATH_BOLD, 108)
    # Shrink font if name is too long
    while True:
        bbox = draw.textbbox((0, 0), tool_name, font=font_title)
        if (bbox[2] - bbox[0]) < THUMB_W - 160 or font_title.size <= 48:
            break
        font_title = _load_font(FONT_PATH_BOLD, font_title.size - 8)

    draw.text((80, 150), tool_name, fill="white", font=font_title)

    # ── Thumbnail text (punchy tagline) ───────────────────────────────────────
    font_tag = _load_font(FONT_PATH_BOLD, 62)
    draw.text((82, 310), thumbnail_text, fill=accent_hex, font=font_tag)

    # ── Category badge ────────────────────────────────────────────────────────
    font_cat = _load_font(FONT_PATH_NORMAL, 32)
    cat_text = f"  {category.upper()}  "
    cat_bbox = draw.textbbox((0, 0), cat_text, font=font_cat)
    cat_w = cat_bbox[2] - cat_bbox[0] + 24
    draw.rounded_rectangle([80, 430, 80 + cat_w, 476], radius=6, fill=accent_rgb)
    draw.text((92, 436), category.upper(), fill="white", font=font_cat)

    # ── Rating badge (top-right) ──────────────────────────────────────────────
    if rating is not None:
        font_rating_big   = _load_font(FONT_PATH_BOLD, 72)
        font_rating_label = _load_font(FONT_PATH_NORMAL, 28)
        draw.rounded_rectangle([1070, 30, 1250, 160], radius=12, fill=accent_rgb)
        draw.text((1090, 38),  str(rating), fill="white", font=font_rating_big)
        draw.text((1098, 120), "/ 10",      fill="white", font=font_rating_label)

    # ── "REVIEW" pill in top-left corner ─────────────────────────────────────
    font_review = _load_font(FONT_PATH_BOLD, 28)
    draw.rounded_rectangle([28, 24, 180, 62], radius=6, fill=(220, 38, 38))
    draw.text((42, 30), "REVIEW", fill="white", font=font_review)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img.save(output_path, "JPEG", quality=95, optimize=True)
    log.info(f"Thumbnail saved → {output_path}")
    return output_path
