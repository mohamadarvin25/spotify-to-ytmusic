"""Transfer tracks from playlist_tracks.json into a new YouTube Music playlist.

Tracks are added in the order they appear in the JSON (sorted by added_at asc).
Uses batch add (50 per request) — fast but ordering within a batch can be slightly
off. Use add_ordered.py if you need strict ordering.

Usage:
    python -m src.transfer "<New Playlist Name>" [description]
"""

import json
import sys
import time

from ytmusicapi import YTMusic

from .common import (
    BROWSER_HEADERS_FILE,
    NOT_FOUND_FILE,
    PLAYLIST_TRACKS_FILE,
    TRANSFER_LOG_FILE,
    search_ytmusic,
    setup_utf8_stdout,
)


BATCH_SIZE = 50
PRIVACY = "PUBLIC"  # one of PRIVATE, PUBLIC, UNLISTED


def main():
    setup_utf8_stdout()

    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    name = sys.argv[1]
    description = sys.argv[2] if len(sys.argv) > 2 else "Transferred from Spotify"

    tracks = json.load(open(PLAYLIST_TRACKS_FILE, encoding="utf-8"))
    print(f"Loaded {len(tracks)} tracks from {PLAYLIST_TRACKS_FILE.name}")

    yt = YTMusic(str(BROWSER_HEADERS_FILE))

    print(f'Creating playlist: "{name}" ({PRIVACY})')
    pid = yt.create_playlist(name, description, privacy_status=PRIVACY)
    print(f"Playlist id: {pid}")

    matched: list[str] = []
    not_found: list[str] = []
    log_lines: list[str] = []

    for i, t in enumerate(tracks, 1):
        label = f'{t["name"]} - {", ".join(t["artists"])}'
        print(f"[{i}/{len(tracks)}] {label}")
        vid = search_ytmusic(yt, t)
        if vid:
            matched.append(vid)
            log_lines.append(f"OK\t{vid}\t{label}")
        else:
            not_found.append(label)
            log_lines.append(f"MISS\t-\t{label}")
        time.sleep(0.2)

    print(f"\nMatched {len(matched)}/{len(tracks)}")
    if not_found:
        print(f"{len(not_found)} not found -> {NOT_FOUND_FILE.name}")

    print("Adding tracks (in order)...")
    for i in range(0, len(matched), BATCH_SIZE):
        chunk = matched[i:i + BATCH_SIZE]
        try:
            yt.add_playlist_items(pid, chunk, duplicates=True)
            print(f"  added {i + len(chunk)}/{len(matched)}")
        except Exception as e:
            print(f"  error at batch {i}: {e}")
        time.sleep(1.0)

    TRANSFER_LOG_FILE.write_text("\n".join(log_lines), encoding="utf-8")
    if not_found:
        NOT_FOUND_FILE.write_text("\n".join(not_found), encoding="utf-8")

    print(f"\nDone. https://music.youtube.com/playlist?list={pid}")


if __name__ == "__main__":
    main()
