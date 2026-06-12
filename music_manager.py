"""
music_manager.py — Selects background music for each video.
Place royalty-free .mp3 files in music/{style}/ folders.
If no music found, video runs voiceover-only (still works fine).

Recommended free music sources:
  - pixabay.com/music  (free, no attribution, search "cinematic")
  - freemusicarchive.org (CC-licensed)
  - incompetech.com  (CC-BY, Kevin MacLeod)

Folder structure:
  music/
    orchestral_documentary/  ← ancient history, historical era
    ambient_scifi/           ← space, science
    cinematic_tension/       ← disaster, survival, danger
    atmospheric_adventure/   ← nature, creatures, exploration
"""
import os, random, logging
from config import MUSIC_DIR

log = logging.getLogger(__name__)


def get_music(music_style: str) -> str:
    """
    Return a random .mp3 path for the given style, or None if no files found.
    """
    style_dir = os.path.join(MUSIC_DIR, music_style)
    if not os.path.isdir(style_dir):
        log.info(f"No music folder found for style '{music_style}' — skipping music.")
        return None

    tracks = [f for f in os.listdir(style_dir) if f.lower().endswith(".mp3")]
    if not tracks:
        log.info(f"Music folder '{style_dir}' is empty — skipping music.")
        return None

    chosen = os.path.join(style_dir, random.choice(tracks))
    log.info(f"Background music: {chosen}")
    return chosen


def setup_music_dirs():
    """Create the music directory structure if it doesn't exist."""
    styles = ["orchestral_documentary", "ambient_scifi",
              "cinematic_tension", "atmospheric_adventure"]
    for s in styles:
        os.makedirs(os.path.join(MUSIC_DIR, s), exist_ok=True)
    log.info(f"Music directories ready at: {MUSIC_DIR}")

    readme = os.path.join(MUSIC_DIR, "README.md")
    if not os.path.exists(readme):
        with open(readme, "w") as f:
            f.write("""# Background Music Setup

Place royalty-free .mp3 files in the correct subfolder based on mood.

## Free sources (no attribution required):
- **Pixabay Music**: pixabay.com/music — search "cinematic", "orchestral", "ambient space"
- **Free Music Archive**: freemusicarchive.org — filter by CC0 license

## Folders:
| Folder | Used for | Search terms |
|--------|----------|--------------|
| orchestral_documentary/ | Ancient history, medieval | "orchestral documentary", "epic historical" |
| ambient_scifi/ | Space, science | "ambient space", "sci-fi drone" |
| cinematic_tension/ | Disaster, survival, danger | "cinematic tension", "dark suspense" |
| atmospheric_adventure/ | Nature, creatures | "atmospheric adventure", "nature documentary" |

Download 2-3 tracks per folder for variety. Videos without music still work fine.
""")
