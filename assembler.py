"""
assembler.py — Assembles the final immersive scenario video.

Pipeline:
  1. Calculate per-scene duration from word count
  2. Apply Ken Burns animation to each image (zoom / pan)
  3. Add subtitle overlay (scene narration at bottom)
  4. Crossfade between scenes
  5. Mux voiceover + optional background music
"""
import os, json, math, random, logging, subprocess, textwrap
from config import VIDEO_FPS, SCENE_MIN_DURATION, SPEAKING_WPM, TRANSITION_DURATION, MUSIC_VOLUME

log = logging.getLogger(__name__)

FONT      = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


# ── Helpers ────────────────────────────────────────────────────────────────

def _run(cmd, label="ffmpeg"):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg [{label}] failed:\n{result.stderr[-3000:]}")

def _duration(path):
    r = subprocess.run(
        ["ffprobe","-v","quiet","-print_format","json","-show_format", path],
        capture_output=True, text=True, check=True)
    return float(json.loads(r.stdout)["format"]["duration"])

def _words(text):
    return len(text.split())

def _escape(t):
    return (t.replace("\\","\\\\")
             .replace("'", "\u2019")
             .replace(":", "\\:")
             .replace("%","\\%")
             .replace("[","\\[").replace("]","\\]"))

def _wrap(text, width=60):
    """Word-wrap text for subtitle display."""
    lines = textwrap.wrap(text, width=width)
    return "\\n".join(_escape(l) for l in lines[:3])  # max 3 lines


# ── Ken Burns animations ───────────────────────────────────────────────────

def _ken_burns_filter(animation: str, duration: float, w=1920, h=1080) -> str:
    d = max(1, int(duration * VIDEO_FPS))
    if animation == "slow_zoom_in":
        return (f"zoompan=z='min(zoom+0.0008,1.3)':d={d}:"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={w}x{h}:fps={VIDEO_FPS}")
    elif animation == "slow_zoom_out":
        return (f"zoompan=z='if(eq(on,1),1.3,max(1.001,zoom-0.0008))':d={d}:"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={w}x{h}:fps={VIDEO_FPS}")
    elif animation == "pan_right":
        return (f"zoompan=z='1.2':d={d}:"
                f"x='on/{d}*(iw-iw/1.2)':y='(ih-ih/1.2)/2':s={w}x{h}:fps={VIDEO_FPS}")
    elif animation == "pan_left":
        return (f"zoompan=z='1.2':d={d}:"
                f"x='(iw-iw/1.2)-on/{d}*(iw-iw/1.2)':y='(ih-ih/1.2)/2':s={w}x{h}:fps={VIDEO_FPS}")
    else:  # static with slight zoom
        return (f"zoompan=z='1.05':d={d}:"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={w}x{h}:fps={VIDEO_FPS}")


ANIMATIONS = ["slow_zoom_in", "slow_zoom_out", "pan_right", "pan_left"]

def _build_scene_clip(scene: dict, workdir: str, idx: int) -> str:
    """Render one image → Ken Burns animated clip with subtitle."""
    img       = scene["image_path"]
    duration  = scene["duration"]
    anim      = scene.get("animation", random.choice(ANIMATIONS))
    narration = scene.get("narration", "")
    out       = os.path.join(workdir, f"scene_{idx:03d}.mp4")

    kb_filter = _ken_burns_filter(anim, duration)
    sub_text  = _wrap(narration, width=55)

    # Fade in/out alpha for subtitle
    fade_in  = 0.3
    fade_out = max(0, duration - 0.4)

    subtitle_filter = (
        # Dark bar behind text
        f"drawbox=x=0:y=ih-160:w=iw:h=160:color=black@0.55:t=fill,"
        # Subtitle text
        f"drawtext=text='{sub_text}':"
        f"fontfile={FONT}:fontsize=38:fontcolor=white:"
        f"x=(w-text_w)/2:y=h-130:"
        f"alpha='if(lt(t,{fade_in}),t/{fade_in},"
              f"if(gt(t,{fade_out}),({duration}-t)/{(duration-fade_out) or 0.1},1))'"
    )

    fade_filter = f"fade=t=in:st=0:d={min(0.4,duration*0.1)},fade=t=out:st={duration-0.35}:d=0.35"

    full_vf = f"{kb_filter},{subtitle_filter},{fade_filter},format=yuv420p"

    _run([
        "ffmpeg", "-y",
        "-loop", "1", "-i", img,
        "-t", str(duration),
        "-vf", full_vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-an", out,
    ], f"scene_{idx}")
    return out


# ── Scene timing ───────────────────────────────────────────────────────────

def _assign_durations(scenes: list, total_audio_duration: float) -> list:
    """
    Distribute audio duration across scenes proportional to word count.
    Every scene gets at least SCENE_MIN_DURATION seconds.
    """
    counts  = [max(1, _words(s.get("narration", ""))) for s in scenes]
    total_w = sum(counts)

    for i, scene in enumerate(scenes):
        scene["duration"] = max(
            SCENE_MIN_DURATION,
            total_audio_duration * counts[i] / total_w
        )
    # Normalise so total matches audio exactly
    ratio = total_audio_duration / sum(s["duration"] for s in scenes)
    for s in scenes:
        s["duration"] = max(SCENE_MIN_DURATION, s["duration"] * ratio)

    log.info(f"Scene durations: {[round(s['duration'],1) for s in scenes]}")
    return scenes


# ── Concat + mix ───────────────────────────────────────────────────────────

def _concat_clips(clips: list, out: str) -> str:
    lst = out + ".txt"
    with open(lst, "w") as f:
        for c in clips:
            f.write(f"file '{c}'\n")
    _run(["ffmpeg","-y","-f","concat","-safe","0","-i",lst,"-c","copy", out], "concat")
    os.remove(lst)
    return out


def _mux_with_audio(video: str, voiceover: str, music_path: str, out: str) -> str:
    """Combine silent video with voiceover and optional background music."""
    if music_path and os.path.exists(music_path):
        music_dur = _duration(music_path)
        video_dur = _duration(video)
        # Loop music if shorter than video
        loop = math.ceil(video_dur / music_dur) if music_dur < video_dur else 1

        _run([
            "ffmpeg", "-y",
            "-i", video,
            "-i", voiceover,
            "-stream_loop", str(loop), "-i", music_path,
            "-filter_complex",
                f"[1:a]volume=1.0[vo];"
                f"[2:a]volume={MUSIC_VOLUME},atrim=0:{video_dur}[bg];"
                f"[vo][bg]amix=inputs=2:duration=first[a]",
            "-map", "0:v", "-map", "[a]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-shortest", out,
        ], "mux_music")
    else:
        _run([
            "ffmpeg", "-y",
            "-i", video, "-i", voiceover,
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-shortest", out,
        ], "mux_voice")
    return out


# ── Public API ─────────────────────────────────────────────────────────────

def assemble_video(
    audio_path: str,
    scenes: list,
    script_data: dict,
    output_path: str,
    music_path: str = None,
) -> str:
    """
    Full assembly: Ken Burns clips → concat → mux with voice + music.

    Args:
        audio_path:   Path to voiceover .mp3
        scenes:       List of scene dicts with 'image_path' added by visuals.py
        script_data:  Full script dict (title, topic_type, etc.)
        output_path:  Final .mp4 destination
        music_path:   Optional background music .mp3

    Returns:
        output_path
    """
    workdir = os.path.join(os.path.dirname(output_path), "_asm")
    os.makedirs(workdir, exist_ok=True)

    audio_dur = _duration(audio_path)
    log.info(f"Audio duration: {audio_dur:.1f}s  |  Scenes: {len(scenes)}")

    # 1. Assign per-scene durations
    scenes = _assign_durations(scenes, audio_dur)

    # 2. Render each scene as an animated clip
    scene_clips = []
    for i, scene in enumerate(scenes):
        log.info(f"  Rendering scene {i+1}/{len(scenes)} ({scene['duration']:.1f}s)...")
        clip = _build_scene_clip(scene, workdir, i)
        scene_clips.append(clip)

    # 3. Concatenate
    log.info("Concatenating scenes...")
    concat_path = os.path.join(workdir, "concat.mp4")
    _concat_clips(scene_clips, concat_path)

    # 4. Mux with voice + music
    log.info("Mixing audio...")
    _mux_with_audio(concat_path, audio_path, music_path, output_path)

    log.info(f"Video assembled → {output_path}")
    return output_path
