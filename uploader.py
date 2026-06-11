"""
uploader.py — Uploads the final video and thumbnail to YouTube via the Data API v3.
Uses OAuth2 refresh-token flow (no browser interaction required after first setup).
"""
import os
import logging
import requests
from config import YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN, YT_CATEGORY_ID, YT_DEFAULT_PRIVACY

log = logging.getLogger(__name__)

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
YT_UPLOAD_URL    = "https://www.googleapis.com/upload/youtube/v3/videos"
YT_THUMB_URL     = "https://www.googleapis.com/upload/youtube/v3/thumbnails/set"
CHUNK_SIZE       = 8 * 1024 * 1024   # 8 MB resumable-upload chunks


def _get_access_token() -> str:
    """Exchange refresh token for a short-lived access token."""
    resp = requests.post(GOOGLE_TOKEN_URL, data={
        "client_id":     YT_CLIENT_ID,
        "client_secret": YT_CLIENT_SECRET,
        "refresh_token": YT_REFRESH_TOKEN,
        "grant_type":    "refresh_token",
    }, timeout=15)
    resp.raise_for_status()
    return resp.json()["access_token"]


def _init_resumable_upload(access_token: str, metadata: dict, file_size: int) -> str:
    """Request a resumable-upload URI from YouTube."""
    resp = requests.post(
        f"{YT_UPLOAD_URL}?uploadType=resumable&part=snippet,status",
        headers={
            "Authorization":           f"Bearer {access_token}",
            "Content-Type":            "application/json; charset=UTF-8",
            "X-Upload-Content-Type":   "video/mp4",
            "X-Upload-Content-Length": str(file_size),
        },
        json=metadata,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.headers["Location"]


def _upload_file(upload_uri: str, video_path: str, file_size: int) -> dict:
    """Stream the video file to YouTube in chunks."""
    uploaded = 0
    with open(video_path, "rb") as fh:
        while uploaded < file_size:
            chunk = fh.read(CHUNK_SIZE)
            end   = uploaded + len(chunk) - 1
            resp  = requests.put(
                upload_uri,
                headers={
                    "Content-Type":  "video/mp4",
                    "Content-Range": f"bytes {uploaded}-{end}/{file_size}",
                },
                data=chunk,
                timeout=300,
            )
            if resp.status_code in (200, 201):
                log.info("Upload complete.")
                return resp.json()
            elif resp.status_code == 308:
                # Resumable incomplete — continue
                uploaded = end + 1
                pct = uploaded / file_size * 100
                log.info(f"  Uploading… {pct:.0f}%")
            else:
                resp.raise_for_status()
    raise RuntimeError("Upload loop exited without completion.")


def upload_video(
    video_path: str,
    title: str,
    description: str,
    tags: list[str],
    thumbnail_path: str | None = None,
    privacy: str | None = None,
    category_id: str | None = None,
) -> dict:
    """
    Upload a video to YouTube.

    Args:
        video_path:      Path to the .mp4 file.
        title:           Video title (max 100 chars).
        description:     Video description.
        tags:            List of keyword tags.
        thumbnail_path:  Optional .jpg thumbnail (1280×720 recommended).
        privacy:         "public" | "unlisted" | "private" (defaults to config).
        category_id:     YouTube category ID (defaults to Science & Technology).

    Returns:
        {"video_id": "...", "url": "https://www.youtube.com/watch?v=..."}
    """
    access_token = _get_access_token()
    file_size    = os.path.getsize(video_path)

    metadata = {
        "snippet": {
            "title":       title[:100],
            "description": description,
            "tags":        tags,
            "categoryId":  category_id or YT_CATEGORY_ID,
        },
        "status": {
            "privacyStatus":          privacy or YT_DEFAULT_PRIVACY,
            "selfDeclaredMadeForKids": False,
            "madeForKids":             False,
        },
    }

    log.info(f"Initiating YouTube upload: '{title}' ({file_size / 1_048_576:.1f} MB)")
    upload_uri = _init_resumable_upload(access_token, metadata, file_size)
    video_data = _upload_file(upload_uri, video_path, file_size)
    video_id   = video_data["id"]

    # Upload custom thumbnail if provided
    if thumbnail_path and os.path.exists(thumbnail_path):
        log.info(f"Uploading thumbnail for video {video_id}...")
        with open(thumbnail_path, "rb") as tf:
            thumb_resp = requests.post(
                f"{YT_THUMB_URL}?videoId={video_id}&uploadType=media",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type":  "image/jpeg",
                },
                data=tf,
                timeout=60,
            )
        if thumb_resp.ok:
            log.info("Thumbnail uploaded.")
        else:
            log.warning(f"Thumbnail upload failed: {thumb_resp.text}")

    result = {
        "video_id": video_id,
        "url":      f"https://www.youtube.com/watch?v={video_id}",
    }
    log.info(f"Published → {result['url']}")
    return result


def get_oauth_setup_url() -> str:
    """
    Helper: print the URL a user visits once to authorise the app and get
    their refresh token. Call this interactively the first time you set up.
    """
    return (
        "https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={YT_CLIENT_ID}"
        "&redirect_uri=urn:ietf:wg:oauth:2.0:oob"
        "&response_type=code"
        "&scope=https://www.googleapis.com/auth/youtube.upload"
        "&access_type=offline"
        "&prompt=consent"
    )
