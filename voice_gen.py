"""
voice_gen.py — Converts voiceover scripts to speech using Gemini 2.5 Flash TTS.
Uses the same GEMINI_API_KEY as the rest of the pipeline.

Gemini TTS produces natural, expressive, documentary-quality narration —
a massive upgrade from gTTS's robotic monotone.

The model outputs raw PCM (s16le, 24000 Hz, mono).
Long scripts are split into sentence-aware chunks to preserve audio quality
(Gemini TTS quality drifts on very long single outputs), and the PCM from
all chunks is concatenated into one seamless WAV, then converted to MP3.
"""
import os, logging, subprocess, tempfile, wave, time, re
from google import genai
from google.genai import types
from config import GEMINI_API_KEY, GEMINI_TTS_MODEL, GEMINI_TTS_VOICE

log = logging.getLogger(__name__)
client = genai.Client(api_key=GEMINI_API_KEY)

# PCM audio constants (Gemini TTS output format)
_SAMPLE_RATE  = 24000
_CHANNELS     = 1
_SAMPLE_WIDTH = 2   # 16-bit PCM = 2 bytes

# Max words per chunk. Gemini TTS quality drifts for very long outputs;
# splitting at ~350 words (~2 min audio) keeps each call well within limits.
_MAX_CHUNK_WORDS = 350

# Performance prompt sent before every chunk of transcript.
# Gemini TTS uses this to set the narrator's character, tone, and pacing.
_NARRATOR_PROMPT = """\
# AUDIO PROFILE: Documentary Narrator — "The Witness"

## THE SCENE
A soundproofed voiceover studio. The narrator is reading a second-person
immersive experience script for a cinematic YouTube video. The listener is
the main character — they are living the story, not watching it. The tone
is gripping, intimate, and dramatic — like a premium nature documentary
crossed with a survival thriller.

### DIRECTOR'S NOTES

Style:
- Deep gravitas with warmth. Be the trusted guide pulling the viewer through
  a dangerous or extraordinary world.
- Lean into sensory words — pause fractionally on "cold", "dark", "silence",
  "burning", "weight". These are what make the listener feel present.
- Short punchy sentences during danger: deliver them fast, clipped, urgent.
- Longer wonder sentences: slow down, let them breathe, give them scale.
- The final line of any section should always land with quiet weight —
  never rush the outro.

Pacing: Moderate documentary pace. Natural, engaging, never rushed.
Build speed on action beats; near-whisper on final reflective lines.

Accent: Clear, neutral American English. No regional accent.

### TRANSCRIPT
"""


def _split_into_chunks(text: str, max_words: int) -> list:
    """Split narration at sentence boundaries into chunks of at most
    max_words words. Preserves sentence integrity throughout."""
    sentences = re.split(r'(?<=[.!?…])\s+', text.strip())
    chunks, current, count = [], [], 0
    for s in sentences:
        w = len(s.split())
        if count + w > max_words and current:
            chunks.append(" ".join(current))
            current, count = [], 0
        current.append(s)
        count += w
    if current:
        chunks.append(" ".join(current))
    return chunks or [text]


def _generate_chunk_pcm(chunk_text: str, retries: int = 3) -> bytes:
    """Call Gemini TTS for a single text chunk. Returns raw PCM bytes."""
    prompt = _NARRATOR_PROMPT + chunk_text

    for attempt in range(1, retries + 1):
        try:
            response = client.models.generate_content(
                model=GEMINI_TTS_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=GEMINI_TTS_VOICE,
                            )
                        )
                    ),
                ),
            )
            pcm = response.candidates[0].content.parts[0].inline_data.data
            if not pcm:
                raise ValueError("Empty audio data returned")
            return pcm

        except Exception as exc:
            log.warning(f"  TTS chunk attempt {attempt} failed: {exc}")
            if attempt < retries:
                time.sleep(5 * attempt)
            else:
                raise RuntimeError(
                    f"Gemini TTS failed after {retries} attempts: {exc}"
                ) from exc


def _pcm_to_wav(pcm_bytes: bytes, path: str):
    """Write concatenated PCM bytes to a WAV file."""
    with wave.open(path, "wb") as wf:
        wf.setnchannels(_CHANNELS)
        wf.setsampwidth(_SAMPLE_WIDTH)
        wf.setframerate(_SAMPLE_RATE)
        wf.writeframes(pcm_bytes)


def _wav_to_mp3(wav_path: str, mp3_path: str):
    """Convert WAV → MP3 via ffmpeg."""
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", wav_path,
         "-codec:a", "libmp3lame", "-q:a", "2", mp3_path],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg WAV→MP3 conversion failed:\n{result.stderr[-2000:]}")


def generate_voiceover(script_text: str, output_path: str) -> str:
    """
    Convert the full voiceover script to speech and save as MP3.

    Long scripts are split into sentence-aware chunks; each chunk is sent
    to Gemini TTS separately and the resulting PCM audio is concatenated
    before saving, producing one seamless MP3.

    Args:
        script_text:  The full voiceover script (plain text, no markup).
        output_path:  Where to save the final .mp3 file.

    Returns:
        output_path on success.
    """
    word_count = len(script_text.split())
    chunks = _split_into_chunks(script_text, _MAX_CHUNK_WORDS)
    log.info(
        f"Generating voiceover with Gemini TTS — "
        f"{word_count} words across {len(chunks)} chunks "
        f"(voice: {GEMINI_TTS_VOICE}, model: {GEMINI_TTS_MODEL})"
    )

    all_pcm = b""
    for i, chunk in enumerate(chunks, 1):
        log.info(f"  TTS chunk {i}/{len(chunks)} ({len(chunk.split())} words)...")
        all_pcm += _generate_chunk_pcm(chunk)
        if i < len(chunks):
            time.sleep(1)   # small cooldown between chunks

    # Write WAV → MP3
    fd, wav_path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        _pcm_to_wav(all_pcm, wav_path)
        _wav_to_mp3(wav_path, output_path)
    finally:
        if os.path.exists(wav_path):
            os.remove(wav_path)

    size_kb = os.path.getsize(output_path) // 1024
    log.info(f"Voiceover saved → {output_path} ({size_kb} KB)")
    return output_path
