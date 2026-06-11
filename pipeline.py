"""
pipeline.py — Main orchestrator for the automated tech review video pipeline.

Typical usage:
  python pipeline.py                     # Auto-discover 3 topics & run
  python pipeline.py --n 5               # Discover 5 topics
  python pipeline.py --tool "Cursor AI"  # Review one specific tool
  python pipeline.py --queued            # Process tools added manually in Airtable
"""
import os
import sys
import logging
import argparse
import tempfile
import time
from pathlib import Path

import config as cfg
from discover         import discover_topics
from script_writer    import generate_script
from voice_gen        import generate_voiceover
from visuals          import fetch_stock_videos
from assembler        import assemble_video
from thumbnail        import create_thumbnail
from uploader         import upload_video
from airtable_tracker import (
    create_video_record,
    update_status,
    get_reviewed_tools,
    get_pending_topics,
)

# ── Logging ────────────────────────────────────────────────────────────────
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


# ── Single-video pipeline ──────────────────────────────────────────────────

def run_single(topic: dict, record_id: str | None = None):
    """
    Process one topic end-to-end:
      Discover → Script → Voice → Visuals → Assemble → Thumbnail → Upload
    """
    tool_name = topic["name"]
    category  = topic.get("category", "Tech")

    log.info(f"━━━  Starting pipeline for: {tool_name}  ━━━")

    # Create Airtable record (skip if already created from get_pending_topics)
    if not record_id:
        record_id = create_video_record(tool_name, category)

    with tempfile.TemporaryDirectory(prefix="review_") as tmpdir:
        try:
            # ── 1. Script ─────────────────────────────────────────────────
            log.info(f"[1/6] Generating script for '{tool_name}'...")
            update_status(record_id, "Scripting")
            script = generate_script(
                tool_name=tool_name,
                category=category,
                search_context=topic.get("search_context", topic.get("tagline", "")),
                why_review_now=topic.get("why_review_now", ""),
            )
            update_status(
                record_id, "Scripted",
                **{
                    "YouTube Title":       script["title"],
                    "Script":              script["script"],
                    "Estimated Duration":  script.get("duration_estimate", 0),
                }
            )

            # ── 2. Voiceover ──────────────────────────────────────────────
            log.info(f"[2/6] Generating voiceover...")
            update_status(record_id, "Voicing")
            audio_path = os.path.join(tmpdir, "voiceover.mp3")
            generate_voiceover(script["script"], audio_path)

            # ── 3. Stock footage ──────────────────────────────────────────
            log.info(f"[3/6] Fetching stock footage...")
            update_status(record_id, "Fetching Visuals")
            clip_dir = os.path.join(tmpdir, "clips")
            clips = fetch_stock_videos(
                queries=script["visual_queries"],
                download_dir=clip_dir,
            )
            if not clips:
                raise RuntimeError("No video clips downloaded — cannot assemble.")

            # ── 4. Thumbnail ──────────────────────────────────────────────
            log.info(f"[4/6] Creating thumbnail...")
            thumb_path = os.path.join(tmpdir, "thumbnail.jpg")
            create_thumbnail(
                tool_name=tool_name,
                thumbnail_text=script.get("thumbnail_text", "Watch This"),
                category=category,
                output_path=thumb_path,
                rating=script.get("rating"),
            )

            # ── 5. Assemble video ─────────────────────────────────────────
            log.info(f"[5/6] Assembling video...")
            update_status(record_id, "Assembling")
            video_path = os.path.join(tmpdir, "final_video.mp4")
            assemble_video(
                audio_path=audio_path,
                video_clips=clips,
                tool_name=tool_name,
                key_points=script.get("key_points", []),
                output_path=video_path,
            )

            # ── 6. Upload to YouTube ──────────────────────────────────────
            log.info(f"[6/6] Uploading to YouTube...")
            update_status(record_id, "Uploading")
            result = upload_video(
                video_path=video_path,
                title=script["title"],
                description=script["description"],
                tags=script["tags"],
                thumbnail_path=thumb_path,
            )

            # ── Done ──────────────────────────────────────────────────────
            update_status(
                record_id, "Published",
                **{
                    "YouTube URL": result["url"],
                    "YouTube ID":  result["video_id"],
                }
            )
            log.info(f"✅  Published: {result['url']}")
            return result

        except Exception as exc:
            log.error(f"❌  Pipeline failed for '{tool_name}': {exc}", exc_info=True)
            update_status(record_id, "Error", **{"Error Notes": str(exc)[:500]})
            return None


# ── Batch runner ───────────────────────────────────────────────────────────

def run_batch(topics: list[dict], delay_between: int = 10):
    """Run the pipeline for a list of topics, pausing between each."""
    results = []
    for i, topic in enumerate(topics, 1):
        log.info(f"\n🎬  Video {i}/{len(topics)}: {topic['name']}\n")
        result = run_single(topic)
        results.append(result)
        if i < len(topics):
            log.info(f"Pausing {delay_between}s before next video...")
            time.sleep(delay_between)
    return results


# ── Entry point ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Automated Tech Review Video Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python pipeline.py                     # Auto-discover 3 topics
  python pipeline.py --n 5               # Discover & produce 5 videos
  python pipeline.py --tool "Cursor AI"  # Review one specific tool
  python pipeline.py --tool "Cursor AI" "Windsurf" "Zed"  # Multiple specific tools
  python pipeline.py --queued            # Process items queued in Airtable
        """,
    )
    parser.add_argument("--n",       type=int,   default=3,
                        help="Number of topics to auto-discover (default: 3)")
    parser.add_argument("--tool",    nargs="+",
                        help="One or more specific tool names to review")
    parser.add_argument("--queued",  action="store_true",
                        help="Process topics manually queued in Airtable")
    parser.add_argument("--category", default=None,
                        help="Filter discovery to one category")
    args = parser.parse_args()

    # Validate API keys before starting
    try:
        cfg.validate()
    except EnvironmentError as e:
        log.error(f"Configuration error: {e}")
        log.error("Copy .env.example to .env and fill in your API keys.")
        sys.exit(1)

    # Determine topics
    if args.queued:
        topics = get_pending_topics()
        if not topics:
            log.info("No queued topics found in Airtable. Add rows with Status='Queued'.")
            sys.exit(0)
        log.info(f"Found {len(topics)} queued topics in Airtable.")
        results = []
        for t in topics:
            rec_id = t.pop("record_id", None)
            result = run_single(t, record_id=rec_id)
            results.append(result)

    elif args.tool:
        topics = [{"name": t, "category": "Tech"} for t in args.tool]
        run_batch(topics)

    else:
        cats = [args.category] if args.category else None
        already = get_reviewed_tools()
        topics  = discover_topics(categories=cats, n_topics=args.n, already_reviewed=already)
        run_batch(topics)


if __name__ == "__main__":
    main()
