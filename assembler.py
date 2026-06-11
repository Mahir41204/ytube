"""
assembler.py — Assembles the final review video using FFmpeg.

Structure:
  [Intro card 4s] → [Stock footage + voiceover + text overlays] → [Outro card 4s]

All clips are normalised to 1920×1080@30fps before concatenation.
"""
import os
import json
import logging
import subprocess
import tempfile
from config import VIDEO_FPS, INTRO_DURATION_SEC, OUTRO_DURATION_SEC

log = logging.getLogger(__name__)

FONT_BOLD   = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_NORMAL = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


# ── Helpers ────────────────────────────────────────────────────────────────

def _run(cmd: list[str], label: str = "ffmpeg"):
    """Run an FFmpeg command, raising on failure with captured stderr."""
    log.debug(f"[{label}] {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"FFmpeg failed ({label}):\n{result.stderr[-2000:]}"
        )


def get_duration(path: str) -> float:
    """Return the duration of a media file in seconds."""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", path],
        capture_output=True, text=True, check=True,
    )
    info = json.loads(result.stdout)
    return float(info["format"]["duration"])


def _escape(text: str) -> str:
    """Escape special characters for FFmpeg drawtext."""
    return (
        text.replace("\\", "\\\\")
            .replace("'",  "\u2019")   # curly apostrophe — avoids shell quoting hell
            .replace(":",  "\\:")
            .replace("%",  "\\%")
    )


# ── Stage builders ─────────────────────────────────────────────────────────

def create_title_card(
    title: str,
    duration: float,
    output_path: str,
    subtitle: str = "Full Review",
    bg_color: str = "0x0f172a",
) -> str:
    """Render an animated title card (fade-in text on dark background)."""
    title_esc    = _escape(title)
    subtitle_esc = _escape(subtitle)
    fade_expr    = f"if(lt(t,0.6),t/0.6,if(gt(t,{duration}-0.5),({duration}-t)/0.5,1))"

    vf = (
        # Title
        f"drawtext=text='{title_esc}'"
        f":fontfile={FONT_BOLD}:fontsize=88:fontcolor=white"
        f":x=(w-text_w)/2:y=(h-text_h)/2-55:alpha='{fade_expr}',"
        # Subtitle
        f"drawtext=text='{subtitle_esc}'"
        f":fontfile={FONT_NORMAL}:fontsize=40:fontcolor=#94a3b8"
        f":x=(w-text_w)/2:y=(h-text_h)/2+60:alpha='{fade_expr}'"
    )

    _run([
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"color=c={bg_color}:size=1920x1080:rate={VIDEO_FPS}:duration={duration}",
        "-vf", vf, "-an",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        output_path,
    ], "title_card")
    return output_path


def normalise_clip(src: str, duration: float, output_path: str) -> str:
    """
    Scale and loop/trim a video clip to 1920×1080 @ fps, exactly `duration` seconds.
    Strips original audio.
    """
    _run([
        "ffmpeg", "-y",
        "-stream_loop", "-1",
        "-i", src,
        "-t", str(duration),
        "-vf", "scale=1920:1080:force_original_aspect_ratio=increase,"
               "crop=1920:1080,"
               f"fps={VIDEO_FPS}",
        "-an",
        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        output_path,
    ], "normalise")
    return output_path


def add_lower_third(
    src: str,
    text: str,
    appear_at: float,
    show_for: float,
    output_path: str,
) -> str:
    """Overlay a lower-third text box on a video segment."""
    text_esc  = _escape(text)
    enable    = f"between(t,{appear_at},{appear_at + show_for})"
    alpha_in  = f"if(lt(t-{appear_at},0.3),(t-{appear_at})/0.3,1)"
    alpha_out = (
        f"if(gt(t,{appear_at + show_for - 0.3}),"
        f"({appear_at + show_for}-t)/0.3,1)"
    )
    alpha = f"min({alpha_in},{alpha_out})"

    vf = (
        # Semi-transparent dark bar
        f"drawbox=x=0:y=ih-110:w=iw:h=110:color=black@0.55:t=fill:enable='{enable}',"
        # Text
        f"drawtext=text='{text_esc}'"
        f":fontfile={FONT_BOLD}:fontsize=34:fontcolor=white"
        f":x=50:y=h-72:alpha='{alpha}'"
    )

    _run([
        "ffmpeg", "-y", "-i", src,
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-an", output_path,
    ], "lower_third")
    return output_path


def concat_silent_clips(paths: list[str], output_path: str) -> str:
    """Concatenate video-only clips (no audio) using the concat demuxer."""
    list_file = output_path + ".txt"
    with open(list_file, "w") as f:
        for p in paths:
            f.write(f"file '{p}'\n")

    _run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", list_file,
        "-c", "copy",
        output_path,
    ], "concat")
    os.remove(list_file)
    return output_path


def mux_audio(video_path: str, audio_path: str, output_path: str) -> str:
    """Combine the silent assembled video with the voiceover audio."""
    _run([
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", audio_path,
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "copy",
        "-c:a", "aac",
        "-ar", "44100",
        "-ac", "2",
        "-b:a", "192k",
        "-shortest",
        output_path,
    ], "mux_audio")
    return output_path

# ── Main assembler ─────────────────────────────────────────────────────────

def assemble_video(
    audio_path: str,
    video_clips: list[str],
    tool_name: str,
    key_points: list[str],
    output_path: str,
) -> str:
    """
    Full pipeline: intro → stock clips with overlays → outro, muxed with voiceover.

    Args:
        audio_path:   Path to the ElevenLabs .mp3 file.
        video_clips:  List of downloaded Pexels .mp4 clip paths.
        tool_name:    Used for the intro title card.
        key_points:   Short phrases shown as lower-thirds during the review.
        output_path:  Where to save the final .mp4.

    Returns:
        output_path on success.
    """
    workdir = os.path.join(os.path.dirname(output_path), "asm_work")
    os.makedirs(workdir, exist_ok=True)

    if not video_clips:
        raise ValueError("No video clips provided — cannot assemble video.")

    # ── Measure voiceover duration ────────────────────────────────────────
    audio_duration = get_duration(audio_path)
    log.info(f"Voiceover duration: {audio_duration:.1f}s")

    # ── Intro title card ──────────────────────────────────────────────────
    intro_path = os.path.join(workdir, "intro.mp4")
    create_title_card(tool_name, INTRO_DURATION_SEC, intro_path)

    # ── Outro card ────────────────────────────────────────────────────────
    outro_path = os.path.join(workdir, "outro.mp4")
    create_title_card(
        "Like & Subscribe",
        OUTRO_DURATION_SEC,
        outro_path,
        subtitle="for more tech reviews",
    )

    # ── Prepare stock footage body ────────────────────────────────────────
    # Divide the voiceover time evenly across available clips
    n_clips = len(video_clips)
    clip_dur = audio_duration / n_clips

    processed_clips = []
    for idx, clip_src in enumerate(video_clips):
        norm_path    = os.path.join(workdir, f"norm_{idx:02d}.mp4")
        overlay_path = os.path.join(workdir, f"ovl_{idx:02d}.mp4")

        # Normalise
        normalise_clip(clip_src, clip_dur, norm_path)

        # Add lower-third if we have a key point for this slot
        if idx < len(key_points):
            add_lower_third(
                norm_path,
                key_points[idx],
                appear_at=1.5,
                show_for=min(4.5, clip_dur - 2),
                output_path=overlay_path,
            )
            processed_clips.append(overlay_path)
        else:
            processed_clips.append(norm_path)

    # ── Concatenate body clips ────────────────────────────────────────────
    body_path = os.path.join(workdir, "body.mp4")
    concat_silent_clips(processed_clips, body_path)

    # ── Mux body with voiceover ───────────────────────────────────────────
    # ── Debug durations ───────────────────────────────────────────────────
log.info(f"Body duration: {get_duration(body_path):.1f}s")
log.info(f"Audio duration: {audio_duration:.1f}s")

# ── Normalize voiceover audio ─────────────────────────────────────────
voice_fixed = os.path.join(workdir, "voice_fixed.wav")

_run([
    "ffmpeg", "-y",
    "-i", audio_path,
    "-ar", "44100",
    "-ac", "2",
    "-c:a", "pcm_s16le",
    voice_fixed,
], "normalize_audio")

# ── Mux body with normalized voiceover ────────────────────────────────
body_audio_path = os.path.join(workdir, "body_audio.mp4")
mux_audio(body_path, voice_fixed, body_audio_path)

    # ── Final concatenation: intro + body(+audio) + outro ────────────────
    # Intro and outro need silent audio tracks so they concat cleanly
    intro_silent = os.path.join(workdir, "intro_s.mp4")
    outro_silent = os.path.join(workdir, "outro_s.mp4")

    for src, dst in [(intro_path, intro_silent), (outro_path, outro_silent)]:
        _run([
            "ffmpeg", "-y", "-i", src,
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo:d=4",,
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-shortest", dst,
        ], "add_silent_audio")

    final_list = os.path.join(workdir, "final.txt")
    with open(final_list, "w") as f:
        for p in [intro_silent, body_audio_path, outro_silent]:
            f.write(f"file '{p}'\n")

    _run([
    "ffmpeg", "-y",
    "-f", "concat",
    "-safe", "0",
    "-i", final_list,
    "-c:v", "libx264",
    "-preset", "medium",
    "-crf", "18",
    "-c:a", "aac",
    "-ar", "44100",
    "-ac", "2",
    "-b:a", "192k",
    "-movflags", "+faststart",
    output_path,
], "final_render")

    log.info(f"Video assembled → {output_path}")
    return output_path
