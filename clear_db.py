#!/usr/bin/env python3
"""Clear the SkyDex database to start fresh.

Usage:
    python3 clear_db.py           # Clear database after confirmation
    python3 clear_db.py --force   # Skip confirmation
"""

import os
import sqlite3
import sys
from pathlib import Path

def get_db_path():
    # Default path from config
    default = os.path.expanduser("~/.skydex/skydex.db")
    if os.path.exists(default):
        return default
    # Check alternate locations
    for alt in ["./skydex.db", "~/.skydex.db", "/tmp/skydex.db"]:
        p = os.path.expanduser(alt)
        if os.path.exists(p):
            return p
    return default

def main():
    db_path = get_db_path()

    if not os.path.exists(db_path):
        print(f"No database found at {db_path}")
        print("Already clean - nothing to do.")
        return

    print(f"Database: {db_path}")
    print(f"Size:     {os.path.getsize(db_path):,} bytes")

    if "--force" not in sys.argv:
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Count records
            cursor.execute("SELECT COUNT(*) FROM airframes")
            airframes = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM detections")
            detections = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM badges")
            badges = conn.execute("SELECT COUNT(*) FROM badges").fetchone()[0]
            conn.close()

            print(f"Records:  {airframes} airframes, {detections} detections, {badges} badges")
            print("")
            resp = input("Delete ALL data and start fresh? (yes/no): ")
            if resp.lower().strip() != "yes":
                print("Cancelled.")
                return
        except Exception as e:
            print(f"Warning: could not read stats: {e}")
            resp = input("Delete database? (yes/no): ")
            if resp.lower().strip() != "yes":
                print("Cancelled.")
                return

    # Delete the DB plus its WAL/SHM sidecars (SQLite runs in WAL mode).
    removed = []
    for suffix in ("", "-wal", "-shm"):
        p = db_path + suffix
        if os.path.exists(p):
            os.remove(p)
            removed.append(p)
    for p in removed:
        print(f"Deleted:  {p}")
    print("Database cleared. Restart SkyDex to start fresh.")

if __name__ == "__main__":
    main()
