#!/usr/bin/env python3
"""Download and import the OpenSky aircraft database.

OpenSky provides a bulk aircraft metadata file that maps ICAO24 -> type, registration, operator.
This script downloads it and imports into SQLite for fast local enrichment.

Run manually:
    python3 sync_opensky_db.py

Or add to crontab for weekly auto-update:
    0 4 * * 0 cd ~/skydex && python3 sync_opensky_db.py >> /tmp/skydex_opensky_sync.log 2>&1
"""

from __future__ import annotations

import csv
import json
import logging
import os
import sqlite3
import sys
import urllib.request
from pathlib import Path

logger = logging.getLogger("opensky_sync")

# OpenSky OAuth2 credentials — read from the environment / .env, never
# hardcoded. (Only needed for REST API calls; the bulk CSV is public.)
OPENSKY_CLIENT_ID = os.environ.get("SKYDEX_OPENSKY_CLIENT_ID", "")
OPENSKY_CLIENT_SECRET = os.environ.get("SKYDEX_OPENSKY_CLIENT_SECRET", "")

# OpenSky aircraft database — try API first, fallback to static dataset
OPENSKY_API_URL = "https://opensky-network.org/api/metadata/aircraft/icao/"
# Alternative: bulk download list
OPENSKY_BULK_URL = "https://opensky-network.org/datasets/metadata/aircraftDatabase.csv"

DEFAULT_DB_PATH = os.path.expanduser("~/.skydex/opensky_aircraft.db")


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def download_bulk_csv(timeout: int = 120) -> str:
    """Download the OpenSky aircraft database CSV.

    The bulk metadata CSV is a static dataset download and does not use the
    OpenSky REST API auth (which is now OAuth2-only). We fetch it directly.
    """
    logger.info("Downloading OpenSky aircraft database from %s ...", OPENSKY_BULK_URL)
    req = urllib.request.Request(OPENSKY_BULK_URL, headers={"User-Agent": "SkyDex/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read().decode("utf-8")
    logger.info("Downloaded %d bytes", len(data))
    return data


def create_tables(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        DROP TABLE IF EXISTS opensky_aircraft;

        CREATE TABLE opensky_aircraft (
            icao24 TEXT PRIMARY KEY,
            registration TEXT,
            manufacturericao TEXT,
            manufacturername TEXT,
            model TEXT,
            typecode TEXT,
            serialnumber TEXT,
            linenumber TEXT,
            icaoaircrafttype TEXT,
            operator TEXT,
            operatorcallsign TEXT,
            operatoricao TEXT,
            operatoriata TEXT,
            owner TEXT,
            testreg TEXT,
            registered TEXT,
            reguntil TEXT,
            status TEXT,
            built TEXT,
            firstflightdate TEXT,
            seatconfiguration TEXT,
            engines TEXT
        );

        CREATE INDEX idx_opensky_reg ON opensky_aircraft(registration);
        CREATE INDEX idx_opensky_type ON opensky_aircraft(typecode);
        CREATE INDEX idx_opensky_operator ON opensky_aircraft(operator);
    """)
    conn.commit()


def import_csv(conn: sqlite3.Connection, csv_text: str) -> int:
    """Import the CSV into SQLite."""
    import io
    reader = csv.DictReader(io.StringIO(csv_text))
    cursor = conn.cursor()
    inserted = 0
    skipped = 0

    for row in reader:
        try:
            cursor.execute("""
                INSERT INTO opensky_aircraft VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
            """, (
                row.get("icao24", "").upper().strip(),
                row.get("registration", "").strip() or None,
                row.get("manufacturericao", "").strip() or None,
                row.get("manufacturername", "").strip() or None,
                row.get("model", "").strip() or None,
                row.get("typecode", "").strip() or None,
                row.get("serialnumber", "").strip() or None,
                row.get("linenumber", "").strip() or None,
                row.get("icaoaircrafttype", "").strip() or None,
                row.get("operator", "").strip() or None,
                row.get("operatorcallsign", "").strip() or None,
                row.get("operatoricao", "").strip() or None,
                row.get("operatoriata", "").strip() or None,
                row.get("owner", "").strip() or None,
                row.get("testreg", "").strip() or None,
                row.get("registered", "").strip() or None,
                row.get("reguntil", "").strip() or None,
                row.get("status", "").strip() or None,
                row.get("built", "").strip() or None,
                row.get("firstflightdate", "").strip() or None,
                row.get("seatconfiguration", "").strip() or None,
                row.get("engines", "").strip() or None,
            ))
            inserted += 1
        except Exception as e:
            skipped += 1
            if skipped <= 3:
                logger.debug("Skip row %s: %s", row.get("icao24"), e)

    conn.commit()
    logger.info("Inserted %d rows, skipped %d", inserted, skipped)
    return inserted


def lookup_hex(db_path: str, hex_code: str) -> dict:
    """Look up aircraft by ICAO 24-bit hex. Returns enrichment dict."""
    hex_code = hex_code.upper().strip()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM opensky_aircraft WHERE icao24 = ?", (hex_code,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return {}

    return {
        "registration": row["registration"],
        "model": row["model"],
        "manufacturer": row["manufacturername"],
        "type_code": row["typecode"],
        "operator": row["operator"],
        "operator_icao": row["operatoricao"],
        "serial_number": row["serialnumber"],
        "year_built": row["built"],
        "source": "opensky_db",
    }


def main() -> None:
    setup_logging()

    db_path = os.environ.get("OPENSKY_DB_PATH", DEFAULT_DB_PATH)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    logger.info("=" * 50)
    logger.info("OpenSky Aircraft DB Sync")
    logger.info("Database: %s", db_path)
    logger.info("=" * 50)

    try:
        csv_text = download_bulk_csv()

        conn = sqlite3.connect(db_path)
        create_tables(conn)
        count = import_csv(conn, csv_text)
        conn.close()

        logger.info("=" * 50)
        logger.info("Import complete: %d aircraft", count)
        logger.info("=" * 50)

        # Verify
        verify_conn = sqlite3.connect(db_path)
        verify_cursor = verify_conn.cursor()
        verify_cursor.execute("SELECT COUNT(*) FROM opensky_aircraft")
        total = verify_cursor.fetchone()[0]
        verify_cursor.execute("SELECT COUNT(*) FROM opensky_aircraft WHERE model IS NOT NULL")
        with_model = verify_cursor.fetchone()[0]
        verify_conn.close()
        logger.info("Total: %d | With model: %d | Without: %d", total, with_model, total - with_model)

    except Exception as e:
        logger.error("Sync failed: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
