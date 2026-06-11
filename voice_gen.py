"""
voice_gen.py — Converts review scripts to speech using gTTS (Google TTS).
Completely free, no API key, no account needed.
pip install gTTS
"""
import logging
from gtts import gTTS
from config import GTTS_LANGUAGE, GTTS_TLD

log = logging.getLogger(__name__)

# Available TLD accents:
#   com       → US English
#   co.uk     → British English
#   com.au    → Australian English
#   co.in     → Indian English
#   ca        → Canadian English


def generate_voiceover(script_text: str, output_path: str) -> str:
    """
    Convert text to speech and save as MP3.

    Args:
        script_text:  The full voiceover script.
        output_path:  Where to save the .mp3 file.

    Returns:
        output_path on success.
    """
    log.info(f"Generating voiceover with gTTS ({len(script_text)} chars)...")
    tts = gTTS(text=script_text, lang=GTTS_LANGUAGE, tld=GTTS_TLD, slow=False)
    tts.save(output_path)
    log.info(f"Voiceover saved → {output_path}")
    return output_path


def set_accent(tld: str):
    """
    Quick helper to change accent at runtime.
    Pass one of: com | co.uk | com.au | co.in | ca
    """
    import config
    config.GTTS_TLD = tld
    log.info(f"gTTS accent set to: {tld}")
