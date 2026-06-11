"""
youtube_auth.py — Run this ONCE to get your YouTube OAuth2 refresh token.
After running, paste the refresh token into your .env file.

Usage:
  python youtube_auth.py
"""
import os
import json
import webbrowser
import requests
from urllib.parse import urlencode
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID     = os.getenv("YOUTUBE_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET", "")
SCOPE         = "https://www.googleapis.com/auth/youtube.upload"
REDIRECT_URI  = "urn:ietf:wg:oauth:2.0:oob"

if not CLIENT_ID or not CLIENT_SECRET:
    print("ERROR: Set YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET in .env first.")
    exit(1)

auth_url = (
    "https://accounts.google.com/o/oauth2/v2/auth?"
    + urlencode({
        "client_id":     CLIENT_ID,
        "redirect_uri":  REDIRECT_URI,
        "response_type": "code",
        "scope":         SCOPE,
        "access_type":   "offline",
        "prompt":        "consent",
    })
)

print("\n🔑  YouTube OAuth2 Setup\n")
print("Opening your browser to authorise the app...")
print("If it doesn't open, visit this URL manually:\n")
print(auth_url)
print()
webbrowser.open(auth_url)

code = input("Paste the authorisation code Google gave you: ").strip()

resp = requests.post(
    "https://oauth2.googleapis.com/token",
    data={
        "code":          code,
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri":  REDIRECT_URI,
        "grant_type":    "authorization_code",
    },
)
resp.raise_for_status()
tokens = resp.json()

refresh_token = tokens.get("refresh_token")
if not refresh_token:
    print("ERROR: No refresh token returned. Make sure you set prompt=consent.")
    exit(1)

print(f"\n✅  Success! Add this to your .env file:\n")
print(f"YOUTUBE_REFRESH_TOKEN={refresh_token}\n")
