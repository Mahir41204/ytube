"""
visuals.py — Generates cinematic scene images using FLUX.1-schnell via the
Hugging Face Serverless Inference API (free tier, ~few hundred req/hour).

Primary:  FLUX.1-schnell (Black Forest Labs) — best-in-class open source
          image model, excellent at cinematic/painterly styles with rich prompts.
Fallback: Pexels stock photo search if HF is unavailable or token not set.
"""
import os, time, logging, random, re, requests
from io import BytesIO
from PIL import Image
from config import (
    HF_TOKEN, HF_IMAGE_API_URL, HF_GEN_WIDTH, HF_GEN_HEIGHT,
    IMAGE_WIDTH, IMAGE_HEIGHT,
    PEXELS_API_KEY, PEXELS_SEARCH_URL,
)

log = logging.getLogger(__name__)

# Style suffix tuned for FLUX.1 — natural language works better than SD tags
STYLE_SUFFIX = (
    "cinematic digital painting, dramatic lighting, hyper-detailed, "
    "storytelling composition, documentary atmosphere, rich color grading, "
    "16:9 widescreen, professional concept art"
)

# Words to strip when building a Pexels fallback search query
_STOPWORDS = {
    "a","an","the","you","your","is","are","of","in","on","with","and","to",
    "at","as","semi","realistic","digital","painting","cinematic","lighting",
    "high","detail","storytelling","illustration","immersive","perspective",
    "documentary","style","dramatic","atmosphere","professional","concept",
    "art","widescreen","16:9","shot","scene","view","camera","rich","color",
    "grading","hyper","detailed","composition","no","not","without",
}


def _fit_to_canvas(img: Image.Image, width: int, height: int) -> Image.Image:
    """Resize/crop image to exactly width×height, preserving aspect ratio."""
    img = img.convert("RGB")
    src_ratio = img.width / img.height
    dst_ratio = width / height
    if src_ratio > dst_ratio:
        new_h = height
        new_w = int(round(new_h * src_ratio))
    else:
        new_w = width
        new_h = int(round(new_w / src_ratio))
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - width) // 2
    top  = (new_h - height) // 2
    return img.crop((left, top, left + width, top + height))


def _hf_flux_image_bytes(prompt: str, seed: int, retries: int = 4) -> bytes | None:
    """
    Call HF Serverless Inference API to generate an image with FLUX.1-schnell.
    Handles model cold-start (503) and rate-limit (429) automatically.
    Returns raw image bytes, or None on permanent failure.
    """
    if not HF_TOKEN:
        log.warning("  HF_TOKEN not set — skipping FLUX generation")
        return None

    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    payload = {
        "inputs": prompt,
        "parameters": {
            "width":               HF_GEN_WIDTH,
            "height":              HF_GEN_HEIGHT,
            "num_inference_steps": 4,     # schnell is distilled — 4 steps is plenty
            "guidance_scale":      0.0,   # schnell doesn't use CFG
            "seed":                seed,
        },
    }

    for attempt in range(1, retries + 1):
        try:
            resp = requests.post(
                HF_IMAGE_API_URL, headers=headers,
                json=payload, timeout=120,
            )

            # 503 = model warming up — wait the estimated time and retry
            if resp.status_code == 503:
                try:
                    wait = float(resp.json().get("estimated_time", 20))
                except Exception:
                    wait = 20
                log.info(f"  FLUX model warming up, waiting {wait:.0f}s... "
                         f"(attempt {attempt}/{retries})")
                time.sleep(min(wait + 2, 60))
                continue

            # 429 = rate limited — back off
            if resp.status_code == 429:
                wait = 15 * attempt
                log.warning(f"  HF rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue

            resp.raise_for_status()

            # Success — response body is raw image bytes
            if resp.content and len(resp.content) > 1000:
                return resp.content
            log.warning(f"  FLUX response too small ({len(resp.content)} bytes), retrying...")

        except requests.exceptions.Timeout:
            log.warning(f"  FLUX request timed out (attempt {attempt})")
        except Exception as exc:
            log.warning(f"  FLUX attempt {attempt} error: {exc}")

        if attempt < retries:
            time.sleep(5 * attempt)

    log.warning("  FLUX generation failed after all retries")
    return None


def _simplify_query(prompt: str, max_words: int = 5) -> str:
    """Extract the most meaningful keywords from a scene prompt for Pexels."""
    first_clause = prompt.split(",")[0]
    words = re.findall(r"[A-Za-z]+", first_clause.lower())
    keywords = [w for w in words if w not in _STOPWORDS and len(w) > 2]
    return " ".join(keywords[:max_words]) or "cinematic landscape"


def _pexels_image_bytes(query: str, seed: int = 0) -> bytes | None:
    """Search Pexels for a landscape photo. Returns raw image bytes or None."""
    if not PEXELS_API_KEY:
        log.warning("  PEXELS_API_KEY not set — cannot use Pexels fallback")
        return None
    try:
        headers = {"Authorization": PEXELS_API_KEY}
        params  = {"query": query, "orientation": "landscape", "per_page": 8}
        resp = requests.get(PEXELS_SEARCH_URL, headers=headers,
                            params=params, timeout=30)
        resp.raise_for_status()
        photos = resp.json().get("photos", [])
        if not photos:
            log.warning(f"  Pexels: no results for '{query}'")
            return None
        photo   = photos[seed % len(photos)]
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
    retries: int = 4,
) -> str:
    """
    Generate a single 1920×1080 scene image.

    1. FLUX.1-schnell via HF Serverless Inference API (free, AI-generated)
    2. Pexels stock photo search (free, real photo fallback)

    Returns output_path on success, raises RuntimeError if both fail.
    """
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    seed = seed or random.randint(1, 999999)
    full_prompt = f"{prompt}, {STYLE_SUFFIX}"

    image_bytes = None
    source = None

    # ── 1. FLUX.1-schnell (HF Serverless Inference API) ───────────────────
    log.info(f"  Generating via FLUX.1-schnell: {prompt[:65]}...")
    image_bytes = _hf_flux_image_bytes(full_prompt, seed=seed, retries=retries)
    if image_bytes:
        source = "flux"

    # ── 2. Pexels stock photo fallback ────────────────────────────────────
    if not image_bytes:
        query = _simplify_query(prompt)
        log.info(f"  Falling back to Pexels: '{query}'")
        image_bytes = _pexels_image_bytes(query, seed=seed)
        if image_bytes:
            source = "pexels"

    if not image_bytes:
        raise RuntimeError(
            f"All image sources failed for: {prompt[:80]}"
        )

    img = Image.open(BytesIO(image_bytes))
    img = _fit_to_canvas(img, IMAGE_WIDTH, IMAGE_HEIGHT)
    img.save(output_path, "JPEG", quality=92)
    log.info(f"  Saved ({source}): {output_path} "
             f"({os.path.getsize(output_path)//1024} KB)")
    return output_path


def generate_scene_images(scenes: list, output_dir: str) -> list:
    """
    Generate one image per scene, with caching for reruns.
    Adds 'image_path' key to each scene dict.
    """
    os.makedirs(output_dir, exist_ok=True)
    base_seed = random.randint(1000, 9000)

    for i, scene in enumerate(scenes):
        out_path = os.path.join(output_dir, f"scene_{i:03d}.jpg")

        if os.path.exists(out_path) and os.path.getsize(out_path) > 10_000:
            log.info(f"  Scene {i+1}: using cached image")
            scene["image_path"] = out_path
            continue

        scene["image_path"] = generate_scene_image(
            prompt=scene["image_prompt"],
            output_path=out_path,
            seed=base_seed + i,
        )
        time.sleep(1)   # small cooldown between requests

    return scenes
