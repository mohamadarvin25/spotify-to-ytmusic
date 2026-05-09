"""[DEPRECATED] All-in-one transfer using Spotify's official Web API.

Since late 2024, Spotify requires the Developer App owner to have an active
Premium subscription. If your account is free, this mode returns 403 and you
should use the scraping pipeline instead:

    python -m src.fetch_spotify <playlist_url>
    python -m src.transfer "<New Playlist Name>"

Usage (if you have Premium):
    python -m src.transfer_official <playlist_url_or_id> "<New Playlist Name>"
"""

import json
import sys
import time

import spotipy
from spotipy.oauth2 import SpotifyOAuth
from ytmusicapi import YTMusic

from .common import (
    BROWSER_HEADERS_FILE,
    NOT_FOUND_FILE,
    SPOTIFY_CONFIG_FILE,
    SPOTIFY_OAUTH_CACHE,
    TRANSFER_LOG_FILE,
    extract_playlist_id,
    search_ytmusic,
    setup_utf8_stdout,
)


def load_config() -> dict:
    if not SPOTIFY_CONFIG_FILE.exists():
        print(f"ERROR: {SPOTIFY_CONFIG_FILE.name} not found. See README.md.")
        sys.exit(1)
    with open(SPOTIFY_CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def get_spotify_client(cfg):
    auth = SpotifyOAuth(
        client_id=cfg["spotify_client_id"],
        client_secret=cfg["spotify_client_secret"],
        redirect_uri=cfg.get("spotify_redirect_uri", "http://127.0.0.1:8888/callback"),
        scope="playlist-read-private playlist-read-collaborative",
        cache_path=str(SPOTIFY_OAUTH_CACHE),
        open_browser=True,
    )
    return spotipy.Spotify(auth_manager=auth)


def fetch_spotify_tracks(sp, playlist_id):
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


def main():
    setup_utf8_stdout()

    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    playlist_id = extract_playlist_id(sys.argv[1])
    new_playlist_name = sys.argv[2]
    description = sys.argv[3] if len(sys.argv) > 3 else "Transferred from Spotify"

    cfg = load_config()
    if not BROWSER_HEADERS_FILE.exists():
        print(f"ERROR: {BROWSER_HEADERS_FILE.name} not found. See README.")
        sys.exit(1)

    print(f"Spotify playlist id: {playlist_id}")
    print("Authenticating with Spotify...")
    sp = get_spotify_client(cfg)

    print("Fetching tracks...")
    tracks = fetch_spotify_tracks(sp, playlist_id)
    print(f"Found {len(tracks)} tracks.")
    if not tracks:
        return

    yt = YTMusic(str(BROWSER_HEADERS_FILE))

    print(f'Creating YouTube Music playlist: "{new_playlist_name}"')
    pid = yt.create_playlist(new_playlist_name, description, privacy_status="PRIVATE")
    print(f"Created playlist id: {pid}")

    matched: list[str] = []
    not_found: list[str] = []
    log_lines: list[str] = []

    for i, track in enumerate(tracks, 1):
        label = f'{track["name"]} - {", ".join(track["artists"])}'
        print(f"[{i}/{len(tracks)}] {label}")
        vid = search_ytmusic(yt, track)
        if vid:
            matched.append(vid)
            log_lines.append(f"OK\t{vid}\t{label}")
        else:
            not_found.append(label)
            log_lines.append(f"MISS\t-\t{label}")
        time.sleep(0.25)

    print(f"\nMatched {len(matched)} / {len(tracks)} tracks.")
    if not_found:
        print(f"{len(not_found)} not found, written to {NOT_FOUND_FILE.name}")

    print("Adding tracks to YouTube Music playlist (in order)...")
    BATCH = 50
    for i in range(0, len(matched), BATCH):
        chunk = matched[i:i + BATCH]
        try:
            yt.add_playlist_items(pid, chunk, duplicates=True)
            print(f"  added {i + len(chunk)} / {len(matched)}")
        except Exception as e:
            print(f"  error adding batch starting at {i}: {e}")
        time.sleep(1.0)

    TRANSFER_LOG_FILE.write_text("\n".join(log_lines), encoding="utf-8")
    if not_found:
        NOT_FOUND_FILE.write_text("\n".join(not_found), encoding="utf-8")

    print(f"\nDone. https://music.youtube.com/playlist?list={pid}")


if __name__ == "__main__":
    main()
