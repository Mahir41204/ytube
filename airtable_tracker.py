"""
airtable_tracker.py — Tracks every video through the pipeline in Airtable.
Uses the Airtable REST API directly (no MCP needed from the script).

Status progression:
  Queued → Scripting → Scripted → Voicing → Fetching Visuals
  → Assembling → Uploading → Published   (or → Error)
"""
import logging
import requests
from urllib.parse import quote
from config import AIRTABLE_API_TOKEN, AIRTABLE_BASE_ID, AIRTABLE_TABLE_NAME

log = logging.getLogger(__name__)

# URL-encode the table name so spaces ("Video Queue" → "Video%20Queue") don't break the request
_TABLE_ENCODED = quote(AIRTABLE_TABLE_NAME, safe="")
_BASE = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{_TABLE_ENCODED}"
_HEADERS = {
    "Authorization": f"Bearer {AIRTABLE_API_TOKEN}",
    "Content-Type":  "application/json",
}


# ── Write helpers ──────────────────────────────────────────────────────────

def create_video_record(tool_name: str, category: str) -> str:
    """Create a new Airtable record. Returns record ID, or empty string on failure."""
    try:
        payload = {
            "records": [{
                "fields": {
                    "Tool Name": tool_name,
                    "Category":  category,
                    "Status":    "Queued",
                }
            }]
        }
        resp = requests.post(_BASE, headers=_HEADERS, json=payload, timeout=15)
        resp.raise_for_status()
        record_id = resp.json()["records"][0]["id"]
        log.info(f"Airtable record created for '{tool_name}': {record_id}")
        return record_id
    except Exception as exc:
        log.warning(f"Airtable tracking disabled: {exc}")
        return ""


def update_status(record_id: str, status: str, **extra_fields) -> dict:
    """Update a record's Status field. Silently skips if record_id is empty."""
    if not record_id:
        return {}
    try:
        fields = {"Status": status, **extra_fields}
        resp = requests.patch(
            f"{_BASE}/{record_id}",
            headers=_HEADERS,
            json={"fields": fields},
            timeout=15,
        )
        resp.raise_for_status()
        log.debug(f"Airtable {record_id} → {status}")
        return resp.json()
    except Exception as exc:
        log.warning(f"Airtable update failed ({status}): {exc}")
        return {}


# ── Read helpers ───────────────────────────────────────────────────────────

def get_reviewed_tools() -> list[str]:
    """
    Return a list of tool names already in Airtable (any status).
    Used by discover.py to avoid re-reviewing the same tool.
    """
    tools = []
    offset = None

    while True:
        params: dict = {"fields[]": "Tool Name", "pageSize": 100}
        if offset:
            params["offset"] = offset

        resp = requests.get(_BASE, headers=_HEADERS, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        for record in data.get("records", []):
            name = record.get("fields", {}).get("Tool Name")
            if name:
                tools.append(name)

        offset = data.get("offset")
        if not offset:
            break

    log.info(f"Found {len(tools)} already-reviewed tools in Airtable.")
    return tools


def get_pending_topics() -> list[dict]:
    """
    Fetch records with Status == 'Queued' so the pipeline can pick up
    manually added topics from Airtable.
    """
    params = {
        "filterByFormula": "{Status} = 'Queued'",
        "fields[]": ["Tool Name", "Category", "Notes"],
    }
    resp = requests.get(_BASE, headers=_HEADERS, params=params, timeout=15)
    resp.raise_for_status()
    records = resp.json().get("records", [])

    topics = []
    for r in records:
        f = r.get("fields", {})
        topics.append({
            "record_id":    r["id"],
            "name":         f.get("Tool Name", ""),
            "category":     f.get("Category", "Tech"),
            "search_context": f.get("Notes", ""),
        })
    return topics
