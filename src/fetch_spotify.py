"""Fetch a Spotify playlist via the public web-player API (pathfinder).

No OAuth or Spotify Developer App needed. Reads auth tokens from
`spotify_auth.json` (see examples/spotify_auth.example.json).

Output: playlist_tracks.json — sorted by added_at ascending (oldest first).

Usage:
    python -m src.fetch_spotify <playlist_url_or_id>
"""

import json
import sys
import time

import requests

from .common import (
    PLAYLIST_TRACKS_FILE,
    SPOTIFY_AUTH_FILE,
    extract_playlist_id,
    setup_utf8_stdout,
)


PATHFINDER_URL = "https://api-partner.spotify.com/pathfinder/v2/query"

# Persisted query hash for the "fetchPlaylist" GraphQL operation. Spotify
# rotates these when they ship a new web bundle. If you get
# "PersistedQueryNotFound", re-grab this from DevTools (see README).
FETCH_PLAYLIST_HASH = "a65e12194ed5fc443a1cdebed5fabe33ca5b07b987185d63c72483867ad13cb4"


def load_auth() -> dict:
    if not SPOTIFY_AUTH_FILE.exists():
        print(f"ERROR: {SPOTIFY_AUTH_FILE.name} not found. See README for how to grab tokens.")
        sys.exit(1)
    with open(SPOTIFY_AUTH_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def fetch_playlist(playlist_id: str, auth: dict, page_size: int = 100) -> list[dict]:
    headers = {
        "authorization": auth["authorization"],
        "client-token": auth["client_token"],
        "accept": "application/json",
        "accept-language": "en",
        "app-platform": "WebPlayer",
        "content-type": "application/json;charset=UTF-8",
        "origin": "https://open.spotify.com",
        "referer": "https://open.spotify.com/",
        "spotify-app-version": "1.2.69.460",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    }

    all_tracks: list[dict] = []
    offset = 0
    total: int | None = None

    while True:
        body = {
            "variables": {
                "uri": f"spotify:playlist:{playlist_id}",
                "offset": offset,
                "limit": page_size,
                "enableWatchFeedEntrypoint": True,
                "includeEpisodeContentRatingsV2": False,
            },
            "operationName": "fetchPlaylist",
            "extensions": {
                "persistedQuery": {
                    "version": 1,
                    "sha256Hash": FETCH_PLAYLIST_HASH,
                }
            },
        }

        r = requests.post(PATHFINDER_URL, headers=headers, json=body, timeout=30)
        if r.status_code != 200:
            print(f"HTTP {r.status_code}: {r.text[:500]}")
            r.raise_for_status()

        data = r.json()
        if "errors" in data:
            print("API error:", json.dumps(data["errors"], indent=2)[:1000])
            sys.exit(1)

        playlist = data.get("data", {}).get("playlistV2") or data.get("data", {}).get("playlist")
        if not playlist:
            print("Unexpected payload:", json.dumps(data, indent=2)[:1000])
            sys.exit(1)

        content = playlist.get("content") or {}
        items = content.get("items") or []
        total = content.get("totalCount", total)

        for item in items:
            added_at = item.get("addedAt", {}).get("isoString") or item.get("addedAt") or ""
            track = item.get("itemV2", {}).get("data") or item.get("item", {}).get("data") or {}
            if not track:
                continue
            duration_ms = (track.get("trackDuration") or {}).get("totalMilliseconds", 0)
            if not duration_ms:
                duration_ms = track.get("duration", {}).get("totalMilliseconds", 0)
            artists_field = track.get("artists", {}).get("items", [])
            artists = [a.get("profile", {}).get("name", "") for a in artists_field if a]
            all_tracks.append({
                "name": track.get("name", ""),
                "artists": [a for a in artists if a],
                "album": (track.get("albumOfTrack") or {}).get("name", ""),
                "added_at": added_at,
                "duration_ms": duration_ms,
            })

        offset += len(items)
        print(f"  fetched {offset}/{total or '?'}")
        if total is not None and offset >= total:
            break
        if not items:
            break
        time.sleep(0.3)

    all_tracks.sort(key=lambda x: x["added_at"])
    return all_tracks


def main():
    setup_utf8_stdout()

    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    playlist_id = extract_playlist_id(sys.argv[1])
    print(f"Fetching playlist {playlist_id}...")

    auth = load_auth()
    tracks = fetch_playlist(playlist_id, auth)
    print(f"\nTotal tracks fetched: {len(tracks)}")

    with open(PLAYLIST_TRACKS_FILE, "w", encoding="utf-8") as f:
        json.dump(tracks, f, ensure_ascii=False, indent=2)
    print(f"Saved to {PLAYLIST_TRACKS_FILE.name}")


if __name__ == "__main__":
    main()
