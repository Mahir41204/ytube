"""
airtable_tracker.py — Tracks every video through the pipeline in Airtable.

Key fixes applied:
  - typecast=True on all writes → Airtable auto-creates new select options (fixes 422)
  - All functions wrapped in try/except → 4xx/5xx never crash the pipeline
  - _AIRTABLE_ENABLED flag → disables after first failure, no repeated warnings
"""
import logging
import requests
from urllib.parse import quote
from config import AIRTABLE_API_TOKEN, AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME

log = logging.getLogger(__name__)

_TABLE_ENCODED = quote(AIRTABLE_TABLE_NAME, safe="")
_BASE    = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{_TABLE_ENCODED}"
_HEADERS = {
    "Authorization": f"Bearer {AIRTABLE_API_TOKEN}",
    "Content-Type":  "application/json",
}

_AIRTABLE_ENABLED = True   # flipped to False on first failure to silence repeat warnings


def _disable(reason: str):
    global _AIRTABLE_ENABLED
    if _AIRTABLE_ENABLED:
        log.warning(f"Airtable disabled ({reason}) — pipeline continues without tracking.")
    _AIRTABLE_ENABLED = False


# ── Write helpers ──────────────────────────────────────────────────────────

def create_video_record(title: str, category: str) -> str:
    """
    Create a new Airtable row at the start of the pipeline.
    typecast=True means Airtable will auto-create the select option if it
    doesn't exist yet — fixes the 422 error from mismatched category values.
    Returns the record ID (e.g. 'recXXXXXXXXXXXXXX'), or '' on any failure.
    """
    if not AIRTABLE_API_TOKEN or not AIRTABLE_BASE_ID:
        _disable("missing AIRTABLE_API_TOKEN or AIRTABLE_BASE_ID in env")
        return ""
    if not _AIRTABLE_ENABLED:
        return ""
    try:
        resp = requests.post(
            _BASE,
            headers=_HEADERS,
            json={
                "records": [{"fields": {
                    "Tool Name": title,     # field name kept as-is from original base
                    "Category":  category,
                    "Status":    "Queued",
                }}],
                "typecast": True,           # ← auto-creates new select options
            },
            timeout=15,
        )
        resp.raise_for_status()
        record_id = resp.json()["records"][0]["id"]
        log.info(f"Airtable record created: {record_id}")
        return record_id
    except Exception as exc:
        _disable(str(exc))
        return ""


def update_status(record_id: str, status: str, **extra_fields) -> dict:
    """
    Update a record's Status and any extra fields.
    Silently skips if record_id is empty or Airtable has been disabled.
    """
    if not record_id or not _AIRTABLE_ENABLED:
        return {}
    try:
        resp = requests.patch(
            f"{_BASE}/{record_id}",
            headers=_HEADERS,
            json={
                "fields":   {"Status": status, **extra_fields},
                "typecast": True,           # ← auto-creates new select options
            },
            timeout=15,
        )
        resp.raise_for_status()
        log.debug(f"Airtable {record_id} → {status}")
        return resp.json()
    except Exception as exc:
        log.warning(f"Airtable update skipped ({status}): {exc}")
        return {}


# ── Read helpers ───────────────────────────────────────────────────────────

def get_reviewed_tools() -> list:
    """
    Return all video titles already tracked in Airtable (used to skip duplicates).
    Returns [] silently if Airtable is unavailable — pipeline still runs fine.
    """
    if not AIRTABLE_API_TOKEN or not AIRTABLE_BASE_ID:
        _disable("missing env vars")
        return []
    if not _AIRTABLE_ENABLED:
        return []
    try:
        tools, offset = [], None
        while True:
            params = {"fields[]": "Tool Name", "pageSize": 100}
            if offset:
                params["offset"] = offset
            resp = requests.get(_BASE, headers=_HEADERS, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            for r in data.get("records", []):
                name = r.get("fields", {}).get("Tool Name")
                if name:
                    tools.append(name)
            offset = data.get("offset")
            if not offset:
                break
        log.info(f"Airtable: {len(tools)} existing videos found (dedup active).")
        return tools
    except Exception as exc:
        _disable(str(exc))
        return []


def get_pending_topics() -> list:
    """
    Return records with Status == 'Queued' for manual queue mode.
    Returns [] if Airtable is unreachable.
    """
    if not AIRTABLE_API_TOKEN or not AIRTABLE_BASE_ID:
        _disable("missing env vars")
        return []
    if not _AIRTABLE_ENABLED:
        return []
    try:
        resp = requests.get(
            _BASE,
            headers=_HEADERS,
            params={
                "filterByFormula": "{Status} = 'Queued'",
                "fields[]": ["Tool Name", "Category", "Notes"],
            },
            timeout=15,
        )
        resp.raise_for_status()
        topics = []
        for r in resp.json().get("records", []):
            f = r.get("fields", {})
            topics.append({
                "record_id":      r["id"],
                "title":          f.get("Tool Name", ""),
                "topic_type":     f.get("Category", "general"),
                "search_context": f.get("Notes", ""),
                "hook":           "",
                "setting":        "",
                "music_style":    "orchestral_documentary",
            })
        return topics
    except Exception as exc:
        _disable(str(exc))
        return []
