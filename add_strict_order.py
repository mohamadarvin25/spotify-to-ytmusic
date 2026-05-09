"""
Add videoIds (from transfer_log.txt) to a YouTube Music playlist
ONE-BY-ONE with delay, to preserve strict order.

Resumable: writes progress to .add_progress so you can re-run if cookies expire.

Usage:
    python add_strict_order.py <playlist_id>     # resume or start
    python add_strict_order.py <playlist_id> --reset   # start from track 0
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
PROGRESS = HERE / ".add_progress"

DELAY_SECONDS = 1.2


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    pid = sys.argv[1]
    reset = "--reset" in sys.argv

    video_ids = []
    for line in LOG.read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and parts[0] == "OK":
            video_ids.append(parts[1])
    print(f"Total tracks to add: {len(video_ids)}")

    start = 0
    if PROGRESS.exists() and not reset:
        try:
            start = int(PROGRESS.read_text().strip())
            print(f"Resuming from track {start}")
        except Exception:
            start = 0
    elif reset and PROGRESS.exists():
        PROGRESS.unlink()

    yt = YTMusic(str(HEADERS))

    for i in range(start, len(video_ids)):
        vid = video_ids[i]
        try:
            yt.add_playlist_items(pid, [vid], duplicates=True)
        except Exception as e:
            print(f"  [{i+1}/{len(video_ids)}] FAIL on {vid}: {e}")
            PROGRESS.write_text(str(i))
            print(f"\nProgress saved. Re-run after refreshing cookies:")
            print(f"  python add_strict_order.py {pid}")
            sys.exit(1)

        if (i + 1) % 25 == 0 or i + 1 == len(video_ids):
            print(f"  added {i+1}/{len(video_ids)}")
            PROGRESS.write_text(str(i + 1))

        time.sleep(DELAY_SECONDS)

    if PROGRESS.exists():
        PROGRESS.unlink()

    print(f"\nDone. {len(video_ids) - start} tracks added.")
    print(f"https://music.youtube.com/playlist?list={pid}")


if __name__ == "__main__":
    main()
