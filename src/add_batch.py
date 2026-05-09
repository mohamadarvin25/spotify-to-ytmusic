"""Add already-matched videoIds (from transfer_log.txt) to an existing
YouTube Music playlist using batch requests.

Use this when the search step already finished but the add step failed
mid-run (e.g. cookies expired). Faster than add_ordered but ordering
within each batch can be slightly off.

Usage:
    python -m src.add_batch <playlist_id>
"""

import sys
import time

from ytmusicapi import YTMusic

from .common import BROWSER_HEADERS_FILE, TRANSFER_LOG_FILE, setup_utf8_stdout


BATCH_SIZE = 50


def load_video_ids() -> list[str]:
    video_ids: list[str] = []
    for line in TRANSFER_LOG_FILE.read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and parts[0] == "OK":
            video_ids.append(parts[1])
    return video_ids


def main():
    setup_utf8_stdout()

    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    pid = sys.argv[1]

    video_ids = load_video_ids()
    print(f"Loaded {len(video_ids)} videoIds from {TRANSFER_LOG_FILE.name}")

    yt = YTMusic(str(BROWSER_HEADERS_FILE))

    added = 0
    for i in range(0, len(video_ids), BATCH_SIZE):
        chunk = video_ids[i:i + BATCH_SIZE]
        try:
            yt.add_playlist_items(pid, chunk, duplicates=True)
            added += len(chunk)
            print(f"  added {added}/{len(video_ids)}")
        except Exception as e:
            print(f"  error at batch {i}: {e}")
            sys.exit(1)
        time.sleep(1.0)

    print(f"\nDone. {added} tracks added.")
    print(f"https://music.youtube.com/playlist?list={pid}")


if __name__ == "__main__":
    main()
