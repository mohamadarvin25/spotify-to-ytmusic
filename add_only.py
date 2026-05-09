"""
Add already-matched videoIds (from transfer_log.txt) into an existing
YouTube Music playlist. Use this if the search step succeeded but the
add step failed (e.g. cookies expired mid-run).

Usage:
    python add_only.py <playlist_id>
"""

import sys
import time
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from ytmusicapi import YTMusic

HERE = Path(__file__).parent
LOG = HERE / "transfer_log.txt"
HEADERS = HERE / "browser.json"


def main():
    if len(sys.argv) < 2:
        print("Usage: python add_only.py <playlist_id>")
        sys.exit(1)
    pid = sys.argv[1]

    video_ids = []
    for line in LOG.read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and parts[0] == "OK":
            video_ids.append(parts[1])
    print(f"Loaded {len(video_ids)} videoIds from log")

    yt = YTMusic(str(HEADERS))

    BATCH = 50
    added = 0
    for i in range(0, len(video_ids), BATCH):
        chunk = video_ids[i:i + BATCH]
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
