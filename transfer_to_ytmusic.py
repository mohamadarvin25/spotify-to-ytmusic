"""
Transfer tracks from playlist_tracks.json (Spotify) to a new YouTube Music playlist.
Tracks are added in the order they appear in the file (already sorted by added_at asc).

Usage:
    python transfer_to_ytmusic.py "<New Playlist Name>" [description]
"""

import json
import sys
import time
from pathlib import Path

# Force UTF-8 stdout on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from ytmusicapi import YTMusic


HERE = Path(__file__).parent
TRACKS_FILE = HERE / "playlist_tracks.json"
HEADERS_FILE = HERE / "browser.json"
LOG_FILE = HERE / "transfer_log.txt"
NOT_FOUND_FILE = HERE / "not_found.txt"


def search_ytmusic(yt: YTMusic, track) -> str | None:
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
    name_lower = track["name"].lower()
    artist_lower = primary_artist.lower()

    best = None
    best_score = -1.0
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
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    name = sys.argv[1]
    desc = sys.argv[2] if len(sys.argv) > 2 else "Transferred from Spotify"

    tracks = json.load(open(TRACKS_FILE, encoding="utf-8"))
    print(f"Loaded {len(tracks)} tracks from {TRACKS_FILE.name}")

    yt = YTMusic(str(HEADERS_FILE))

    print(f'Creating playlist: "{name}"')
    pid = yt.create_playlist(name, desc, privacy_status="PUBLIC")
    print(f"Playlist id: {pid}")

    matched = []
    not_found = []
    log = []

    for i, t in enumerate(tracks, 1):
        label = f'{t["name"]} - {", ".join(t["artists"])}'
        print(f"[{i}/{len(tracks)}] {label}")
        vid = search_ytmusic(yt, t)
        if vid:
            matched.append(vid)
            log.append(f"OK\t{vid}\t{label}")
        else:
            not_found.append(label)
            log.append(f"MISS\t-\t{label}")
        time.sleep(0.2)

    print(f"\nMatched {len(matched)}/{len(tracks)}")
    if not_found:
        print(f"{len(not_found)} not found -> {NOT_FOUND_FILE.name}")

    print("Adding tracks (in order)...")
    BATCH = 50
    for i in range(0, len(matched), BATCH):
        chunk = matched[i:i + BATCH]
        try:
            yt.add_playlist_items(pid, chunk, duplicates=True)
            print(f"  added {i + len(chunk)}/{len(matched)}")
        except Exception as e:
            print(f"  error at batch {i}: {e}")
        time.sleep(1.0)

    LOG_FILE.write_text("\n".join(log), encoding="utf-8")
    if not_found:
        NOT_FOUND_FILE.write_text("\n".join(not_found), encoding="utf-8")

    print(f"\nDone. https://music.youtube.com/playlist?list={pid}")


if __name__ == "__main__":
    main()
