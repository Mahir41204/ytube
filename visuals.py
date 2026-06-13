"""
visuals.py — Generates cinematic scene images.

Primary:  Google Gemini (gemini-2.5-flash-image, "Nano Banana"), using the
          same GEMINI_API_KEY as script_writer.py.
Fallback: If Gemini has no image-generation credits/quota (or any other
          error), automatically search Pexels for a free stock photo that
          matches the scene instead.
"""
import os, time, logging, random, re, requests
from io import BytesIO
from PIL import Image
from google import genai
from google.genai import types
from config import (
    GEMINI_API_KEY, IMAGE_WIDTH, IMAGE_HEIGHT, GEMINI_IMAGE_MODEL,
    PEXELS_API_KEY, PEXELS_SEARCH_URL,
)

log = logging.getLogger(__name__)
client = genai.Client(api_key=GEMINI_API_KEY)

# Appended to every Gemini prompt for consistent cinematic style
STYLE_SUFFIX = (
    "semi realistic digital painting, cinematic lighting, high detail, "
    "storytelling illustration, immersive perspective, documentary style, "
    "dramatic atmosphere, professional concept art, 16:9 widescreen"
)

# Styles to explicitly avoid
NEGATIVE_HINT = "no anime, no cartoon, no pixar, no comic book, no modern elements"

# Common cinematic/style words that make poor stock-photo search queries
_STOPWORDS = {
    "a", "an", "the", "you", "your", "is", "are", "of", "in", "on", "with",
    "and", "to", "at", "as", "your's", "semi", "realistic", "digital",
    "painting", "cinematic", "lighting", "high", "detail", "storytelling",
    "illustration", "immersive", "perspective", "documentary", "style",
    "dramatic", "atmosphere", "professional", "concept", "art", "widescreen",
    "16:9", "shot", "scene", "view", "camera",
}


def _fit_to_canvas(img: Image.Image, width: int, height: int) -> Image.Image:
    """Resize/crop an image to exactly width x height, preserving aspect ratio
    (center-crop any overflow)."""
    img = img.convert("RGB")
    src_ratio = img.width / img.height
    dst_ratio = width / height

    if src_ratio > dst_ratio:
        new_height = height
        new_width = int(round(new_height * src_ratio))
    else:
        new_width = width
        new_height = int(round(new_width / src_ratio))

    img = img.resize((new_width, new_height), Image.LANCZOS)

    left = (new_width - width) // 2
    top = (new_height - height) // 2
    return img.crop((left, top, left + width, top + height))


def _gemini_image_bytes(prompt: str, seed: int) -> bytes | None:
    """Try to generate an image with Gemini. Returns raw image bytes, or
    None if generation isn't available (no credits, quota, etc.)."""
    try:
        response = client.models.generate_content(
            model=GEMINI_IMAGE_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["Text", "Image"],
                image_config=types.ImageConfig(aspect_ratio="16:9"),
                seed=seed,
            ),
        )
        for part in response.candidates[0].content.parts:
            if getattr(part, "inline_data", None) is not None:
                return part.inline_data.data
        log.warning("  Gemini response contained no image data")
    except Exception as exc:
        log.warning(f"  Gemini image generation unavailable: {exc}")
    return None


def _simplify_query(prompt: str, max_words: int = 6) -> str:
    """Turn a long cinematic image prompt into a short keyword query
    suitable for a stock-photo search engine."""
    # Use only the first clause (before the first comma), which usually
    # holds the actual subject of the scene.
    first_clause = prompt.split(",")[0]
    words = re.findall(r"[A-Za-z]+", first_clause.lower())
    keywords = [w for w in words if w not in _STOPWORDS]
    if not keywords:
        keywords = words
    return " ".join(keywords[:max_words]) or "cinematic landscape"


def _pexels_image_bytes(query: str, seed: int = 0) -> bytes | None:
    """Search Pexels for a landscape stock photo matching `query` and
    return the raw image bytes, or None if nothing was found / on error."""
    if not PEXELS_API_KEY:
        log.warning("  PEXELS_API_KEY not set — cannot search for stock images")
        return None
    try:
        headers = {"Authorization": PEXELS_API_KEY}
        params = {"query": query, "orientation": "landscape", "per_page": 8}
        resp = requests.get(PEXELS_SEARCH_URL, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        photos = resp.json().get("photos", [])
        if not photos:
            return None

        photo = photos[seed % len(photos)]
        img_url = photo["src"].get("original") or photo["src"]["large2x"]
        img_resp = requests.get(img_url, timeout=60)
        img_resp.raise_for_status()
        return img_resp.content
    except Exception as exc:
        log.warning(f"  Pexels search failed for '{query}': {exc}")
        return None


def generate_scene_image(
    prompt: str,
    output_path: str,
    seed: int = None,
    retries: int = 3,
) -> str:
    """
    Generate (or find) a single 1920×1080 image for a scene.

    Tries Gemini image generation first; if that fails (e.g. no billing /
    no quota), falls back to a Pexels stock photo search based on the
    scene's image prompt.

    Args:
        prompt:       Scene description (image_prompt from script).
        output_path:  Where to save the .jpg file.
        seed:         Fixed seed for reproducibility (random if None).
        retries:      How many times to retry Gemini before falling back.

    Returns:
        output_path on success.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    full_prompt = f"{prompt}, {STYLE_SUFFIX}. Avoid: {NEGATIVE_HINT}."
    seed = seed or random.randint(1, 999999)

    image_bytes = None
    source = None

    # ── 1. Try Gemini image generation (free tier if available) ───────────
    for attempt in range(1, retries + 1):
        log.info(f"  Generating image via Gemini (attempt {attempt}): {prompt[:60]}...")
        image_bytes = _gemini_image_bytes(full_prompt, seed)
        if image_bytes:
            source = "gemini"
            break
        if attempt < retries:
            time.sleep(5)
            seed = random.randint(1, 999999)

    # ── 2. Fall back to a Pexels stock photo search ────────────────────────
    if not image_bytes:
        query = _simplify_query(prompt)
        log.info(f"  Falling back to Pexels stock photo search: '{query}'")
        image_bytes = _pexels_image_bytes(query, seed=seed)
        if image_bytes:
            source = "pexels"

    if not image_bytes:
        raise RuntimeError(
            f"Failed to obtain an image (Gemini + Pexels) for: {prompt[:80]}"
        )

    img = Image.open(BytesIO(image_bytes))
    img = _fit_to_canvas(img, IMAGE_WIDTH, IMAGE_HEIGHT)
    img.save(output_path, "JPEG", quality=92)

    log.info(f"  Image saved ({source}): {output_path} "
             f"({os.path.getsize(output_path)//1024} KB)")
    return output_path


def generate_scene_images(scenes: list, output_dir: str) -> list:
    """
    Generate one image per scene.

    Args:
        scenes:     List of scene dicts from script_writer (must have 'image_prompt').
        output_dir: Directory to save images.

    Returns:
        scenes list with 'image_path' added to each scene.
    """
    os.makedirs(output_dir, exist_ok=True)
    base_seed = random.randint(1000, 9000)

    for i, scene in enumerate(scenes):
        out_path = os.path.join(output_dir, f"scene_{i:03d}.jpg")

        # Reuse cached image if it exists (useful for reruns)
        if os.path.exists(out_path) and os.path.getsize(out_path) > 10_000:
            log.info(f"  Scene {i+1}: using cached image")
            scene["image_path"] = out_path
            continue

        scene["image_path"] = generate_scene_image(
            prompt=scene["image_prompt"],
            output_path=out_path,
            seed=base_seed + i,
        )
        # Small delay to avoid hammering APIs
        time.sleep(2)

    return scenes
