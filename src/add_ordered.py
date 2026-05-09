"""Add videoIds (from transfer_log.txt) to a YouTube Music playlist
ONE-BY-ONE with delay, to preserve strict order.

Resumable: writes progress to .add_progress so re-runs continue where
they left off (useful when cookies expire mid-run).

Usage:
    python -m src.add_ordered <playlist_id>            # resume or start
    python -m src.add_ordered <playlist_id> --reset    # start from track 0
"""

import sys
import time

from ytmusicapi import YTMusic

from .common import (
    ADD_PROGRESS_FILE,
    BROWSER_HEADERS_FILE,
    TRANSFER_LOG_FILE,
    setup_utf8_stdout,
)


DELAY_SECONDS = 1.2


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
    reset = "--reset" in sys.argv

    video_ids = load_video_ids()
    print(f"Total tracks to add: {len(video_ids)}")

    start = 0
    if ADD_PROGRESS_FILE.exists() and not reset:
        try:
            start = int(ADD_PROGRESS_FILE.read_text().strip())
            print(f"Resuming from track {start}")
        except Exception:
            start = 0
    elif reset and ADD_PROGRESS_FILE.exists():
        ADD_PROGRESS_FILE.unlink()

    yt = YTMusic(str(BROWSER_HEADERS_FILE))

    for i in range(start, len(video_ids)):
        vid = video_ids[i]
        try:
            yt.add_playlist_items(pid, [vid], duplicates=True)
        except Exception as e:
            print(f"  [{i+1}/{len(video_ids)}] FAIL on {vid}: {e}")
            ADD_PROGRESS_FILE.write_text(str(i))
            print(f"\nProgress saved. Re-run after refreshing cookies:")
            print(f"  python -m src.add_ordered {pid}")
            sys.exit(1)

        if (i + 1) % 25 == 0 or i + 1 == len(video_ids):
            print(f"  added {i+1}/{len(video_ids)}")
            ADD_PROGRESS_FILE.write_text(str(i + 1))

        time.sleep(DELAY_SECONDS)

    if ADD_PROGRESS_FILE.exists():
        ADD_PROGRESS_FILE.unlink()

    print(f"\nDone. {len(video_ids) - start} tracks added.")
    print(f"https://music.youtube.com/playlist?list={pid}")


if __name__ == "__main__":
    main()
