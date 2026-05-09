"""Shared utilities used by multiple scripts."""

import re
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent

# Local-only files (gitignored). Always reference via these constants
# so paths stay consistent if the layout changes.
PLAYLIST_TRACKS_FILE = PROJECT_ROOT / "playlist_tracks.json"
TRANSFER_LOG_FILE = PROJECT_ROOT / "transfer_log.txt"
NOT_FOUND_FILE = PROJECT_ROOT / "not_found.txt"
ADD_PROGRESS_FILE = PROJECT_ROOT / ".add_progress"

BROWSER_HEADERS_FILE = PROJECT_ROOT / "browser.json"
SPOTIFY_AUTH_FILE = PROJECT_ROOT / "spotify_auth.json"
SPOTIFY_CONFIG_FILE = PROJECT_ROOT / "config.json"
SPOTIFY_OAUTH_CACHE = PROJECT_ROOT / ".spotify_cache"


def setup_utf8_stdout():
    """Force UTF-8 stdout on Windows so non-Latin track titles don't crash prints."""
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def extract_playlist_id(url_or_id: str) -> str:
    """Accept either a full Spotify playlist URL/URI or a bare ID."""
    m = re.search(r"playlist[/:]([a-zA-Z0-9]+)", url_or_id)
    return m.group(1) if m else url_or_id.strip()


def score_ytmusic_result(result: dict, target_name: str, target_artist: str, target_duration_ms: int) -> float:
    """Score how well a YT Music search result matches a Spotify track.

    Higher is better. Combines title match, artist match, and duration proximity.
    """
    name_lower = target_name.lower()
    artist_lower = target_artist.lower()
    title = (result.get("title") or "").lower()
    artists_text = " ".join((a.get("name") or "").lower() for a in (result.get("artists") or []))

    score = 0.0
    if name_lower and name_lower in title:
        score += 2.0
    if artist_lower and (artist_lower in artists_text or artist_lower in title):
        score += 2.0

    dur = result.get("duration_seconds")
    if dur and target_duration_ms:
        diff_ms = abs(dur * 1000 - target_duration_ms)
        if diff_ms <= 3000:
            score += 1.5
        elif diff_ms <= 8000:
            score += 0.5

    return score


def search_ytmusic(yt, track: dict) -> str | None:
    """Find the best videoId for a Spotify-style track dict.

    Track dict must have: name (str), artists (list[str]), duration_ms (int).
    Returns videoId or None if nothing usable found.
    """
    primary_artist = track["artists"][0] if track["artists"] else ""
    query = f'{track["name"]} {primary_artist}'.strip()

    try:
        results = yt.search(query, filter="songs", limit=5)
    except Exception as e:
        print(f"  search error: {e}")
        return None

    if not results:
        try:
            results = yt.search(query, filter="videos", limit=5)
        except Exception as e:
            print(f"  fallback search error: {e}")
            return None

    if not results:
        return None

    best_vid = None
    best_score = -1.0
    for r in results:
        vid = r.get("videoId")
        if not vid:
            continue
        score = score_ytmusic_result(r, track["name"], primary_artist, track.get("duration_ms", 0))
        if score > best_score:
            best_score = score
            best_vid = vid

    return best_vid or results[0].get("videoId")
