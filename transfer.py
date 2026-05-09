"""
Transfer a Spotify playlist to YouTube Music, preserving the order
in which tracks were added to the Spotify playlist (oldest first).

Usage:
    python transfer.py <spotify_playlist_url_or_id> "<new_ytmusic_playlist_name>"

Example:
    python transfer.py https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M "My Transferred Playlist"
"""

import os
import re
import sys
import time
import json
from pathlib import Path

import spotipy
from spotipy.oauth2 import SpotifyOAuth
from ytmusicapi import YTMusic


HERE = Path(__file__).parent
CONFIG_FILE = HERE / "config.json"
HEADERS_FILE = HERE / "browser.json"
LOG_FILE = HERE / "transfer_log.txt"
NOT_FOUND_FILE = HERE / "not_found.txt"


def load_config():
    if not CONFIG_FILE.exists():
        print(f"ERROR: {CONFIG_FILE} not found. See README.md.")
        sys.exit(1)
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_playlist_id(url_or_id: str) -> str:
    m = re.search(r"playlist[/:]([a-zA-Z0-9]+)", url_or_id)
    if m:
        return m.group(1)
    return url_or_id.strip()


def get_spotify_client(cfg):
    auth = SpotifyOAuth(
        client_id=cfg["spotify_client_id"],
        client_secret=cfg["spotify_client_secret"],
        redirect_uri=cfg.get("spotify_redirect_uri", "http://127.0.0.1:8888/callback"),
        scope="playlist-read-private playlist-read-collaborative",
        cache_path=str(HERE / ".spotify_cache"),
        open_browser=True,
    )
    return spotipy.Spotify(auth_manager=auth)


def fetch_spotify_tracks(sp, playlist_id):
    """Return list of {name, artists, album, added_at, duration_ms} sorted by added_at ascending."""
    tracks = []
    results = sp.playlist_items(
        playlist_id,
        additional_types=("track",),
        fields="items(added_at,track(name,artists(name),album(name),duration_ms,is_local)),next",
        limit=100,
    )
    while results:
        for item in results["items"]:
            t = item.get("track")
            if not t or t.get("is_local"):
                continue
            tracks.append({
                "name": t["name"],
                "artists": [a["name"] for a in t["artists"]],
                "album": t["album"]["name"] if t.get("album") else "",
                "added_at": item["added_at"],
                "duration_ms": t.get("duration_ms", 0),
            })
        if results.get("next"):
            results = sp.next(results)
        else:
            break

    tracks.sort(key=lambda x: x["added_at"])
    return tracks


def search_ytmusic(yt: YTMusic, track) -> str | None:
    """Return videoId of best match or None."""
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

    target_ms = track.get("duration_ms", 0)
    best = None
    best_score = -1.0

    name_lower = track["name"].lower()
    artist_lower = primary_artist.lower()

    for r in results:
        vid = r.get("videoId")
        if not vid:
            continue
        title = (r.get("title") or "").lower()
        artists_field = r.get("artists") or []
        artists_text = " ".join((a.get("name") or "").lower() for a in artists_field)

        score = 0.0
        if name_lower and name_lower in title:
            score += 2.0
        if artist_lower and (artist_lower in artists_text or artist_lower in title):
            score += 2.0

        dur = r.get("duration_seconds")
        if dur and target_ms:
            diff = abs(dur * 1000 - target_ms)
            if diff <= 3000:
                score += 1.5
            elif diff <= 8000:
                score += 0.5

        if score > best_score:
            best_score = score
            best = vid

    return best or results[0].get("videoId")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    playlist_arg = sys.argv[1]
    new_playlist_name = sys.argv[2]
    description = sys.argv[3] if len(sys.argv) > 3 else "Transferred from Spotify"

    cfg = load_config()
    if not HEADERS_FILE.exists():
        print(f"ERROR: {HEADERS_FILE} not found. Run: ytmusicapi browser")
        sys.exit(1)

    playlist_id = extract_playlist_id(playlist_arg)
    print(f"Spotify playlist id: {playlist_id}")

    print("Authenticating with Spotify...")
    sp = get_spotify_client(cfg)

    print("Fetching tracks (sorted by added_at ascending)...")
    tracks = fetch_spotify_tracks(sp, playlist_id)
    print(f"Found {len(tracks)} tracks.")

    if not tracks:
        print("Nothing to transfer.")
        return

    print("Authenticating with YouTube Music...")
    yt = YTMusic(str(HEADERS_FILE))

    print(f'Creating YouTube Music playlist: "{new_playlist_name}"')
    yt_playlist_id = yt.create_playlist(new_playlist_name, description, privacy_status="PRIVATE")
    print(f"Created playlist id: {yt_playlist_id}")

    matched_video_ids = []
    not_found = []
    log_lines = []

    for i, track in enumerate(tracks, 1):
        label = f'{track["name"]} - {", ".join(track["artists"])}'
        print(f"[{i}/{len(tracks)}] {label}")
        vid = search_ytmusic(yt, track)
        if vid:
            matched_video_ids.append(vid)
            log_lines.append(f"OK\t{vid}\t{label}")
        else:
            not_found.append(label)
            log_lines.append(f"MISS\t-\t{label}")
        time.sleep(0.25)

    print(f"\nMatched {len(matched_video_ids)} / {len(tracks)} tracks.")
    if not_found:
        print(f"{len(not_found)} not found, written to {NOT_FOUND_FILE.name}")

    print("Adding tracks to YouTube Music playlist (in order)...")
    BATCH = 50
    for i in range(0, len(matched_video_ids), BATCH):
        chunk = matched_video_ids[i:i + BATCH]
        try:
            yt.add_playlist_items(yt_playlist_id, chunk, duplicates=True)
            print(f"  added {i + len(chunk)} / {len(matched_video_ids)}")
        except Exception as e:
            print(f"  error adding batch starting at {i}: {e}")
        time.sleep(1.0)

    LOG_FILE.write_text("\n".join(log_lines), encoding="utf-8")
    if not_found:
        NOT_FOUND_FILE.write_text("\n".join(not_found), encoding="utf-8")

    print("\nDone.")
    print(f"Playlist URL: https://music.youtube.com/playlist?list={yt_playlist_id}")


if __name__ == "__main__":
    main()
