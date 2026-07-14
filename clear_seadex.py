#!/usr/bin/env python3
"""Wipe SeaDex (vessel) data only — leaves SkyDex (aircraft) completely untouched.

Usage (stop the service first so nothing is writing):
    sudo systemctl stop skydex
    cd ~/skydex
    python3 clear_seadex.py            # clear vessels + vessel_sightings
    python3 clear_seadex.py --photos   # also delete cached vessel photos
    sudo systemctl start skydex

Dex numbering restarts at 1 automatically the next time vessels are seen.
"""

import shutil
import sqlite3
import sys
from pathlib import Path

from config import SkyDexConfig


def main() -> None:
    cfg = SkyDexConfig()
    db_path = Path(cfg.db_path).expanduser()
    if not db_path.exists():
        print(f"No database found at {db_path} — nothing to clear.")
        return

    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        # Be defensive in case the tables don't exist yet.
        def _count(table: str) -> int:
            try:
                return cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            except sqlite3.OperationalError:
                return 0

        n_vessels = _count("vessels")
        n_sightings = _count("vessel_sightings")

        for table in ("vessel_sightings", "vessels"):
            try:
                cur.execute(f"DELETE FROM {table}")
            except sqlite3.OperationalError:
                pass
        # Reset the autoincrement id counter for vessel_sightings (cosmetic).
        try:
            cur.execute("DELETE FROM sqlite_sequence WHERE name IN ('vessel_sightings','vessels')")
        except sqlite3.OperationalError:
            pass
        conn.commit()
        try:
            cur.execute("VACUUM")
        except sqlite3.OperationalError as e:
            print(f"(skipped VACUUM: {e} — is skydex still running?)")
        print(f"Cleared {n_vessels} vessels and {n_sightings} vessel sightings.")
        print("SkyDex (aircraft) data left untouched.")
    finally:
        conn.close()

    if "--photos" in sys.argv:
        photo_dir = Path(cfg.photo_cache_dir).expanduser() / "vessel"
        if photo_dir.exists():
            shutil.rmtree(photo_dir, ignore_errors=True)
            print(f"Removed cached vessel photos at {photo_dir}")


if __name__ == "__main__":
    main()
