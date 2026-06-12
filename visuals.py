"""
visuals.py — Generates cinematic scene images using Pollinations.ai.
Completely free, no API key required. Uses the Flux model.
"""
import os, time, logging, random, requests
from urllib.parse import quote
from config import POLLINATIONS_URL, IMAGE_WIDTH, IMAGE_HEIGHT, IMAGE_MODEL

log = logging.getLogger(__name__)

# Appended to every prompt for consistent cinematic style
STYLE_SUFFIX = (
    "semi realistic digital painting, cinematic lighting, high detail, "
    "storytelling illustration, immersive perspective, documentary style, "
    "dramatic atmosphere, professional concept art, 16:9 widescreen"
)

# Styles to explicitly avoid
NEGATIVE_HINT = "no anime, no cartoon, no pixar, no comic book, no modern elements"


def generate_scene_image(
    prompt: str,
    output_path: str,
    seed: int = None,
    retries: int = 3,
) -> str:
    """
    Generate a single 1920×1080 image for a scene via Pollinations.ai.

    Args:
        prompt:       Scene description (image_prompt from script).
        output_path:  Where to save the .jpg file.
        seed:         Fixed seed for reproducibility (random if None).
        retries:      How many times to retry on failure.

    Returns:
        output_path on success.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    full_prompt = f"{prompt}, {STYLE_SUFFIX}"
    seed = seed or random.randint(1, 999999)

    params = {
        "width":  IMAGE_WIDTH,
        "height": IMAGE_HEIGHT,
        "model":  IMAGE_MODEL,
        "nologo": "true",
        "seed":   seed,
    }
    url = f"{POLLINATIONS_URL}/{quote(full_prompt)}"

    for attempt in range(1, retries + 1):
        try:
            log.info(f"  Generating image (attempt {attempt}): {prompt[:60]}...")
            resp = requests.get(url, params=params, timeout=120)
            resp.raise_for_status()

            # Verify it's actually an image
            if not resp.content[:4] in (b'\xff\xd8\xff\xe0', b'\xff\xd8\xff\xe1',
                                         b'\x89PNG', b'GIF8'):
                # Pollinations sometimes returns an error page — retry
                raise ValueError("Response is not a valid image")

            with open(output_path, "wb") as f:
                f.write(resp.content)
            log.info(f"  Image saved: {output_path} ({len(resp.content)//1024} KB)")
            return output_path

        except Exception as exc:
            log.warning(f"  Image generation attempt {attempt} failed: {exc}")
            if attempt < retries:
                wait = 10 * attempt
                log.info(f"  Retrying in {wait}s...")
                time.sleep(wait)
                seed = random.randint(1, 999999)   # try a different seed

    raise RuntimeError(f"Failed to generate image after {retries} attempts: {prompt[:80]}")


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
        # Small delay to be respectful to the free API
        time.sleep(2)

    return scenes
