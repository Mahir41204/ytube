"""
visuals.py — Generates cinematic scene images using Google Gemini
(gemini-2.5-flash-image, aka "Nano Banana"). Uses the same GEMINI_API_KEY
as script_writer.py.
"""
import os, time, logging, random
from io import BytesIO
from PIL import Image
from google import genai
from google.genai import types
from config import GEMINI_API_KEY, IMAGE_WIDTH, IMAGE_HEIGHT, GEMINI_IMAGE_MODEL

log = logging.getLogger(__name__)
client = genai.Client(api_key=GEMINI_API_KEY)

# Appended to every prompt for consistent cinematic style
STYLE_SUFFIX = (
    "semi realistic digital painting, cinematic lighting, high detail, "
    "storytelling illustration, immersive perspective, documentary style, "
    "dramatic atmosphere, professional concept art, 16:9 widescreen"
)

# Styles to explicitly avoid
NEGATIVE_HINT = "no anime, no cartoon, no pixar, no comic book, no modern elements"


def _fit_to_canvas(img: Image.Image, width: int, height: int) -> Image.Image:
    """Resize/crop an image to exactly width x height, preserving aspect ratio
    (center-crop any overflow)."""
    img = img.convert("RGB")
    src_ratio = img.width / img.height
    dst_ratio = width / height

    if src_ratio > dst_ratio:
        # Source is wider than target — match height, crop width
        new_height = height
        new_width = int(round(new_height * src_ratio))
    else:
        # Source is taller than target — match width, crop height
        new_width = width
        new_height = int(round(new_width / src_ratio))

    img = img.resize((new_width, new_height), Image.LANCZOS)

    left = (new_width - width) // 2
    top = (new_height - height) // 2
    return img.crop((left, top, left + width, top + height))


def generate_scene_image(
    prompt: str,
    output_path: str,
    seed: int = None,
    retries: int = 3,
) -> str:
    """
    Generate a single 1920×1080 image for a scene via Google Gemini.

    Args:
        prompt:       Scene description (image_prompt from script).
        output_path:  Where to save the .jpg file.
        seed:         Fixed seed for reproducibility (random if None).
        retries:      How many times to retry on failure.

    Returns:
        output_path on success.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    full_prompt = f"{prompt}, {STYLE_SUFFIX}. Avoid: {NEGATIVE_HINT}."
    seed = seed or random.randint(1, 999999)

    for attempt in range(1, retries + 1):
        try:
            log.info(f"  Generating image (attempt {attempt}): {prompt[:60]}...")
            response = client.models.generate_content(
                model=GEMINI_IMAGE_MODEL,
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["Text", "Image"],
                    image_config=types.ImageConfig(aspect_ratio="16:9"),
                    seed=seed,
                ),
            )

            image_bytes = None
            for part in response.candidates[0].content.parts:
                if getattr(part, "inline_data", None) is not None:
                    image_bytes = part.inline_data.data
                    break

            if image_bytes is None:
                raise ValueError("Response did not contain image data")

            img = Image.open(BytesIO(image_bytes))
            img = _fit_to_canvas(img, IMAGE_WIDTH, IMAGE_HEIGHT)
            img.save(output_path, "JPEG", quality=92)

            log.info(f"  Image saved: {output_path} ({os.path.getsize(output_path)//1024} KB)")
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
        # Small delay to avoid hammering the API
        time.sleep(2)

    return scenes
