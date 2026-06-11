"""
visuals.py — Fetches and downloads stock video clips from Pexels.
Clips are downloaded to a temp directory, ready for FFmpeg assembly.
"""
import os
import logging
import requests
from config import PEXELS_API_KEY

log = logging.getLogger(__name__)

PEXELS_VIDEO_URL = "https://api.pexels.com/videos/search"
PREFERRED_QUALITY = ("hd", "sd")   # Try HD first, fall back to SD
MIN_CLIP_DURATION  = 8             # seconds — skip clips shorter than this


def _best_file(video_files: list[dict]) -> dict | None:
    """Pick the best available video file (HD > SD, 1080p > 720p)."""
    for quality in PREFERRED_QUALITY:
        candidates = [f for f in video_files if f.get("quality") == quality]
        if candidates:
            # Prefer 1080p within quality tier
            hd = [f for f in candidates if f.get("height", 0) >= 1080]
            return (hd or candidates)[0]
    return video_files[0] if video_files else None


def fetch_stock_videos(
    queries: list[str],
    clips_per_query: int = 1,
    download_dir: str = "/tmp/pipeline/clips",
) -> list[str]:
    """
    Search Pexels for each query and download the best matching clip.

    Args:
        queries:         List of search terms (from script_writer visual_queries).
        clips_per_query: How many clips to download per query.
        download_dir:    Where to save .mp4 files.

    Returns:
        List of local file paths for downloaded clips.
    """
    os.makedirs(download_dir, exist_ok=True)
    headers = {"Authorization": PEXELS_API_KEY}
    paths = []

    for query in queries:
        log.info(f"Fetching Pexels clip for: '{query}'")
        try:
            resp = requests.get(
                PEXELS_VIDEO_URL,
                headers=headers,
                params={
                    "query": query,
                    "per_page": clips_per_query + 3,   # fetch a few extras to filter
                    "orientation": "landscape",
                    "size": "medium",
                },
                timeout=20,
            )
            resp.raise_for_status()
            videos = resp.json().get("videos", [])

            # Filter out very short clips
            videos = [v for v in videos if v.get("duration", 0) >= MIN_CLIP_DURATION]

            downloaded = 0
            for video in videos:
                if downloaded >= clips_per_query:
                    break

                file_info = _best_file(video.get("video_files", []))
                if not file_info:
                    continue

                video_url = file_info["link"]
                safe_query = query.replace(" ", "_")[:40]
                local_path = os.path.join(download_dir, f"{safe_query}_{video['id']}.mp4")

                if os.path.exists(local_path):
                    log.info(f"  Clip already cached: {local_path}")
                    paths.append(local_path)
                    downloaded += 1
                    continue

                log.info(f"  Downloading clip {video['id']} ({file_info.get('quality','?')})")
                dl = requests.get(video_url, stream=True, timeout=60)
                dl.raise_for_status()
                with open(local_path, "wb") as f:
                    for chunk in dl.iter_content(chunk_size=65536):
                        f.write(chunk)

                paths.append(local_path)
                downloaded += 1

        except Exception as exc:
            log.warning(f"  Failed to fetch clip for '{query}': {exc}")
            continue

    log.info(f"Downloaded {len(paths)} clips total.")
    return paths
