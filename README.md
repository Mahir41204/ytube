# 🎬 Automated Tech Review Video Pipeline

Fully automated end-to-end system that discovers trending software tools, writes and narrates a review script, assembles a video with stock footage and text overlays, and publishes it to YouTube — zero manual work required.

---

## How It Works

```
Web search → Claude script → ElevenLabs voice → Pexels footage → FFmpeg assembly → YouTube
```

Every video that goes through the pipeline is tracked in Airtable. n8n runs the schedule.

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
sudo apt-get install ffmpeg          # Ubuntu/Debian
# brew install ffmpeg                # macOS
```

### 2. Configure API keys

```bash
cp .env.example .env
# Edit .env and fill in all keys (see instructions below)
```

### 3. Authorise YouTube (one-time)

```bash
python youtube_auth.py
# Follow the browser prompt, paste the code, copy the refresh token into .env
```

### 4. Run the pipeline

```bash
# Auto-discover 3 trending tools and produce videos
python pipeline.py

# Discover and produce 5 videos
python pipeline.py --n 5

# Review specific tools
python pipeline.py --tool "Cursor AI" "v0.dev" "Perplexity"

# Pick up topics you queued manually in Airtable
python pipeline.py --queued
```

---

## API Keys You Need

Every service used is **completely free** — no credit card required for any of them.

| Service | Where to get it | Cost | Used for |
|---------|----------------|------|----------|
| **Google Gemini** | aistudio.google.com/app/apikey | Free (1,500 req/day) | Scripts + topic discovery |
| **gTTS** | Built-in, no key needed | Free, unlimited | Voiceover narration |
| **Pexels** | pexels.com/api | Free, unlimited | Stock footage |
| **YouTube Data API** | Google Cloud Console | Free (6 uploads/day) | Publishing |
| **Airtable** | airtable.com/create/tokens | Free tier | Pipeline tracking |

---

## YouTube API Setup (detailed)

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project (e.g. "Tech Review Bot")
3. Enable **YouTube Data API v3** (APIs & Services → Library)
4. Create credentials → **OAuth 2.0 Client ID** → Desktop App
5. Download the credentials JSON — copy `client_id` and `client_secret` to `.env`
6. Run `python youtube_auth.py` and follow the prompts to get your refresh token

---

## Airtable Base Structure

The pipeline creates a base called **Tech Review Pipeline** with a **Video Queue** table:

| Field | Type | Description |
|-------|------|-------------|
| Tool Name | Text | Primary key — name of the product |
| Category | Select | AI Tools, Dev Tools, SaaS, Mobile, Hardware |
| Status | Select | Queued → Scripting → … → Published / Error |
| YouTube Title | Text | Auto-generated SEO title |
| Script | Long text | Full voiceover script |
| Estimated Duration | Number | Seconds |
| YouTube URL | URL | Published video link |
| YouTube ID | Text | Video ID (e.g. dQw4w9WgXcQ) |
| Error Notes | Long text | Failure reason if status = Error |

**To manually queue a video:** Add a row in Airtable with Tool Name, Category, and Status = "Queued". Then run `python pipeline.py --queued`.

---

## n8n Schedule

The pipeline runs automatically via an n8n workflow:
- **Daily at 09:00** — discovers 2 trending tools and produces videos
- **Weekly on Monday** — produces 5 videos for the week ahead
- You can also trigger it manually from the n8n dashboard

The n8n workflow calls the pipeline as an HTTP webhook. To activate it:
1. Set your server's webhook URL in the n8n workflow
2. Deploy `pipeline.py` on any server that has Python + FFmpeg installed
3. Start the HTTP listener: `python webhook_server.py` (see below)

---

## File Structure

```
tech-review-pipeline/
├── pipeline.py          # Main orchestrator — run this
├── config.py            # API keys & settings (loads from .env)
├── discover.py          # Finds trending tools via Claude + web search
├── script_writer.py     # Generates review scripts via Claude API
├── voice_gen.py         # ElevenLabs text-to-speech
├── visuals.py           # Pexels stock footage downloader
├── assembler.py         # FFmpeg video assembly
├── thumbnail.py         # PIL thumbnail generator
├── uploader.py          # YouTube Data API uploader
├── airtable_tracker.py  # Airtable progress tracker
├── youtube_auth.py      # One-time OAuth2 setup helper
├── requirements.txt
└── .env.example
```

---

## Typical Video Output

- **Duration:** 3–5 minutes
- **Resolution:** 1920×1080 @ 30fps
- **Structure:** Intro title card → Stock footage + voiceover + lower-thirds → Outro
- **Thumbnail:** 1280×720 JPEG with tool name, punchy tagline, category badge, rating

---

## Cost Per Video

**$0.00** — every component is free.

| Step | Service | Cost |
|------|---------|------|
| Topic discovery | Product Hunt RSS + Gemini | $0 |
| Script writing | Gemini 1.5 Flash | $0 |
| Voiceover | gTTS | $0 |
| Stock footage | Pexels API | $0 |
| Video assembly | FFmpeg | $0 |
| YouTube upload | YouTube Data API | $0 |
| **Total** | | **$0 / video** |
