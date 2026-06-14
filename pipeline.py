"""
pipeline.py — Orchestrator for the immersive scenario video pipeline.

Usage:
  python pipeline.py                        # Auto-discover 2 topics
  python pipeline.py --n 5                  # Produce 5 videos
  python pipeline.py --topic "Your Life as a Viking"
  python pipeline.py --queued               # Process Airtable queue
"""
import os, sys, logging, argparse, tempfile, time

import config as cfg
from discover         import discover_topics
from script_writer    import generate_script
from voice_gen        import generate_voiceover
from visuals          import generate_scene_images
from assembler        import assemble_video
from thumbnail        import create_thumbnail
from music_manager    import get_music, setup_music_dirs
from uploader         import upload_video
from airtable_tracker import (create_video_record, update_status,
                               get_reviewed_tools, get_pending_topics)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("pipeline.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)


def run_single(topic: dict, record_id: str = None):
    title = topic["title"]
    log.info(f"\n{'━'*55}\n  🎬  {title}\n{'━'*55}")
    if not record_id:
        record_id = create_video_record(title, topic.get("topic_type", "general"))

    with tempfile.TemporaryDirectory(prefix="scenario_") as tmp:
        try:
            # 1. Script ────────────────────────────────────────────────────
            log.info("[1/7] Writing immersive script...")
            update_status(record_id, "Scripting")
            script = generate_script(topic)
            update_status(record_id, "Scripted",
                          **{"YouTube Title": script["yt_title"],
                             "Script": script["voiceover_script"]})

            # 2. Voiceover ─────────────────────────────────────────────────
            log.info("[2/7] Generating voiceover...")
            update_status(record_id, "Voicing")
            audio_path = os.path.join(tmp, "voice.mp3")
            generate_voiceover(script["voiceover_script"], audio_path)

            # 3. Scene images ──────────────────────────────────────────────
            log.info(f"[3/7] Generating {len(script['scenes'])} scene images...")
            update_status(record_id, "Generating Images")
            img_dir = os.path.join(tmp, "images")
            scenes  = generate_scene_images(script["scenes"], img_dir)

            # 4. Background music (optional) ───────────────────────────────
            log.info("[4/7] Selecting background music...")
            music_path = get_music(script.get("music_style", "orchestral_documentary"))

            # 5. Thumbnail ─────────────────────────────────────────────────
            log.info("[5/7] Creating thumbnail...")
            thumb_path = os.path.join(tmp, "thumbnail.jpg")
            create_thumbnail(
                title=script["yt_title"],
                thumbnail_text=script.get("thumbnail_text", "WATCH THIS"),
                topic_type=script.get("topic_type", "ancient_history"),
                output_path=thumb_path,
                thumbnail_danger=script.get("thumbnail_danger", ""),
            )

            # 6. Assemble video ─────────────────────────────────────────────
            log.info("[6/7] Assembling video with Ken Burns animation...")
            update_status(record_id, "Assembling")
            video_path = os.path.join(tmp, "final.mp4")
            assemble_video(
                audio_path=audio_path,
                scenes=scenes,
                script_data=script,
                output_path=video_path,
                music_path=music_path,
            )

            # ── Save a persistent copy before the temp dir is cleaned up ──
            import shutil, re as _re
            _safe = _re.sub(r"[^\w\s-]", "", script["yt_title"])[:60].strip().replace(" ", "_")
            _ts   = time.strftime("%Y%m%d_%H%M")
            outputs_dir  = os.path.join(os.path.dirname(__file__), "outputs")
            os.makedirs(outputs_dir, exist_ok=True)
            saved_video = os.path.join(outputs_dir, f"{_ts}_{_safe}.mp4")
            saved_thumb = os.path.join(outputs_dir, f"{_ts}_{_safe}_thumb.jpg")
            shutil.copy2(video_path, saved_video)
            shutil.copy2(thumb_path, saved_thumb)
            log.info(f"💾  Video saved → {saved_video}")
            log.info(f"💾  Thumb saved → {saved_thumb}")

            # 7. Upload ────────────────────────────────────────────────────
            log.info("[7/7] Uploading to YouTube...")
            update_status(record_id, "Uploading")
            result = upload_video(
                video_path=video_path,
                title=script["yt_title"],
                description=script["yt_description"],
                tags=script.get("yt_tags", []),
                thumbnail_path=thumb_path,
            )
            update_status(record_id, "Published",
                          **{"YouTube URL": result["url"],
                             "YouTube ID":  result["video_id"]})
            log.info(f"✅  Published: {result['url']}")
            return result

        except Exception as exc:
            log.error(f"❌  Failed: {exc}", exc_info=True)
            update_status(record_id, "Error", **{"Error Notes": str(exc)[:500]})
            return None


def run_batch(topics: list, delay: int = 15):
    results = []
    for i, topic in enumerate(topics, 1):
        log.info(f"\n📽  Video {i}/{len(topics)}")
        results.append(run_single(topic))
        if i < len(topics):
            log.info(f"Cooling down {delay}s...")
            time.sleep(delay)
    return results


def main():
    parser = argparse.ArgumentParser(description="Immersive Scenario Video Pipeline")
    parser.add_argument("--n",     type=int, default=2, help="Videos to auto-produce")
    parser.add_argument("--topic", nargs="+", help="Specific topic title(s)")
    parser.add_argument("--queued",action="store_true", help="Process Airtable queue")
    args = parser.parse_args()

    try: cfg.validate()
    except EnvironmentError as e:
        log.error(f"Config error: {e}"); sys.exit(1)

    setup_music_dirs()   # create music/ folder structure if missing

    if args.queued:
        topics = get_pending_topics()
        if not topics:
            log.info("No queued topics in Airtable."); sys.exit(0)
        for t in topics:
            rid = t.pop("record_id", None)
            # Convert 'name' field to 'title' for compatibility
            if "name" in t and "title" not in t:
                t["title"] = t.pop("name")
            run_single(t, record_id=rid)

    elif args.topic:
        topics = [{"title": t, "topic_type": "general", "hook": "",
                   "setting": "", "music_style": "orchestral_documentary"}
                  for t in args.topic]
        run_batch(topics)

    else:
        already = get_reviewed_tools()
        topics  = discover_topics(n_topics=args.n, already_done=already)
        run_batch(topics)


if __name__ == "__main__":
    main()
