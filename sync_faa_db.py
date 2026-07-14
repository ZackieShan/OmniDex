#!/usr/bin/env python3
"""Download and import the FAA aircraft registration database.

The FAA publishes a monthly update at:
  https://www.faa.gov/aircraft/air_cert/aircraft_registry/releasable_aircraft_download

This script:
  1. Downloads ReleasableAircraft.zip
  2. Extracts MASTER.txt (aircraft) and ACFTREF.txt (reference data)
  3. Imports into SQLite for fast local lookups

Run manually:
    python3 sync_faa_db.py

Or add to crontab for monthly auto-update:
    0 3 1 * * cd ~/skydex && python3 sync_faa_db.py >> /tmp/skydex_faa_sync.log 2>&1
"""

from __future__ import annotations

import csv
import io
import logging
import os
import sqlite3
import sys
import urllib.request
import zipfile
from pathlib import Path

logger = logging.getLogger("faa_sync")

# FAA Registration Database URL
FAA_URL = "https://registry.faa.gov/database/ReleasableAircraft.zip"

# Default output path
DEFAULT_DB_PATH = os.path.expanduser("~/.skydex/faa_registry.db")


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def download_zip(url: str, timeout: int = 60) -> bytes:
    """Download the FAA zip file into memory."""
    logger.info("Downloading FAA registry from %s ...", url)
    req = urllib.request.Request(url, headers={"User-Agent": "SkyDex/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
    logger.info("Downloaded %d bytes", len(data))
    return data


def extract_csv(zip_data: bytes, filename: str) -> list:
    """Extract a CSV file from the zip and return list of dicts."""
    logger.info("Extracting %s from zip...", filename)
    with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
        # The zip contains files like MASTER.txt, ACFTREF.txt, ENGINE.txt, etc.
        # Find the file matching the name
        names = zf.namelist()
        target = None
        for n in names:
            if n.upper().endswith(filename.upper()):
                target = n
                break
        if not target:
            raise FileNotFoundError(f"{filename} not found in zip. Contents: {names}")

        with zf.open(target) as f:
            # FAA releasable files are comma-delimited CSV. Column names and
            # values are padded with trailing spaces, so strip the headers and
            # every value on import.
            content = f.read().decode("latin-1")
            reader = csv.DictReader(content.splitlines(), delimiter=",")
            if reader.fieldnames:
                reader.fieldnames = [name.strip() for name in reader.fieldnames]
            rows = list(reader)
            logger.info("  %s: %d rows", filename, len(rows))
            return rows


def create_tables(conn: sqlite3.Connection) -> None:
    """Create the FAA registry tables."""
    conn.executescript("""
        DROP TABLE IF EXISTS faa_master;
        DROP TABLE IF EXISTS faa_acftref;

        CREATE TABLE faa_master (
            n_number TEXT PRIMARY KEY,
            serial_number TEXT,
            mfr_mdl_code TEXT,
            eng_mfr_mdl TEXT,
            year_mfr TEXT,
            type_registrant TEXT,
            name TEXT,
            street TEXT,
            street2 TEXT,
            city TEXT,
            state TEXT,
            zip_code TEXT,
            region TEXT,
            county TEXT,
            country TEXT,
            last_action_date TEXT,
            cert_issue_date TEXT,
            certification TEXT,
            type_aircraft TEXT,
            type_engine TEXT,
            status_code TEXT,
            mode_s_code TEXT,
            fract_owner TEXT,
            air_worth_date TEXT,
            other_name_1 TEXT,
            other_name_2 TEXT,
            other_name_3 TEXT,
            other_name_4 TEXT,
            other_name_5 TEXT,
            expiration_date TEXT,
            unique_id TEXT,
            kit_mfr TEXT,
            kit_model TEXT,
            mode_s_code_hex TEXT
        );

        CREATE TABLE faa_acftref (
            code TEXT PRIMARY KEY,
            mfr TEXT,
            model TEXT,
            type_acft TEXT,
            type_eng TEXT,
            ac_cat TEXT,
            build_cert_ind TEXT,
            no_eng TEXT,
            no_seats TEXT,
            ac_weight TEXT,
            speed TEXT
        );

        CREATE INDEX idx_faa_master_hex ON faa_master(mode_s_code_hex);
        CREATE INDEX idx_faa_master_mfr ON faa_master(mfr_mdl_code);
        CREATE INDEX idx_faa_acftref_code ON faa_acftref(code);
    """)
    conn.commit()


def import_master(conn: sqlite3.Connection, rows: list) -> int:
    """Import MASTER.txt into faa_master table."""
    cursor = conn.cursor()
    inserted = 0
    for row in rows:
        try:
            cursor.execute("""
                INSERT INTO faa_master VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
            """, (
                row.get("N-NUMBER", "").strip(),
                row.get("SERIAL NUMBER", "").strip(),
                row.get("MFR MDL CODE", "").strip(),
                row.get("ENG MFR MDL", "").strip(),
                row.get("YEAR MFR", "").strip(),
                row.get("TYPE REGISTRANT", "").strip(),
                row.get("NAME", "").strip(),
                row.get("STREET", "").strip(),
                row.get("STREET2", "").strip(),
                row.get("CITY", "").strip(),
                row.get("STATE", "").strip(),
                row.get("ZIP CODE", "").strip(),
                row.get("REGION", "").strip(),
                row.get("COUNTY", "").strip(),
                row.get("COUNTRY", "").strip(),
                row.get("LAST ACTION DATE", "").strip(),
                row.get("CERT ISSUE DATE", "").strip(),
                row.get("CERTIFICATION", "").strip(),
                row.get("TYPE AIRCRAFT", "").strip(),
                row.get("TYPE ENGINE", "").strip(),
                row.get("STATUS CODE", "").strip(),
                row.get("MODE S CODE", "").strip(),
                row.get("FRACT OWNER", "").strip(),
                row.get("AIR WORTH DATE", "").strip(),
                row.get("OTHER NAME(1)", "").strip(),
                row.get("OTHER NAME(2)", "").strip(),
                row.get("OTHER NAME(3)", "").strip(),
                row.get("OTHER NAME(4)", "").strip(),
                row.get("OTHER NAME(5)", "").strip(),
                row.get("EXPIRATION DATE", "").strip(),
                row.get("UNIQUE ID", "").strip(),
                row.get("KIT MFR", "").strip(),
                row.get("KIT MODEL", "").strip(),
                row.get("MODE S CODE HEX", "").strip().upper(),
            ))
            inserted += 1
        except Exception as e:
            logger.debug("Skip row: %s", e)
            continue
    conn.commit()
    return inserted


def import_acftref(conn: sqlite3.Connection, rows: list) -> int:
    """Import ACFTREF.txt into faa_acftref table."""
    cursor = conn.cursor()
    inserted = 0
    for row in rows:
        try:
            cursor.execute("""
                INSERT INTO faa_acftref VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                row.get("CODE", "").strip(),
                row.get("MFR", "").strip(),
                row.get("MODEL", "").strip(),
                row.get("TYPE-ACFT", "").strip(),
                row.get("TYPE-ENG", "").strip(),
                row.get("AC-CAT", "").strip(),
                row.get("BUILD-CERT-IND", "").strip(),
                row.get("NO-ENG", "").strip(),
                row.get("NO-SEATS", "").strip(),
                row.get("AC-WEIGHT", "").strip(),
                row.get("SPEED", "").strip(),
            ))
            inserted += 1
        except Exception as e:
            logger.debug("Skip row: %s", e)
            continue
    conn.commit()
    return inserted


def lookup_hex(db_path: str, hex_code: str) -> dict:
    """Look up aircraft by ICAO 24-bit hex. Returns enrichment dict."""
    hex_code = hex_code.upper().strip()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT m.*, r.mfr as manufacturer, r.model as model_name
        FROM faa_master m
        LEFT JOIN faa_acftref r ON m.mfr_mdl_code = r.code
        WHERE m.mode_s_code_hex = ?
    """, (hex_code,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return {}

    return {
        "registration": row["n_number"],
        "model": row["model_name"] or row["kit_model"],
        "manufacturer": row["manufacturer"] or row["kit_mfr"],
        "year_mfr": row["year_mfr"] or None,
        "type_code": row["type_aircraft"],
        "operator": row["name"],
        "status": row["status_code"],
        "source": "faa_registry",
    }


def main() -> None:
    setup_logging()

    db_path = os.environ.get("FAA_DB_PATH", DEFAULT_DB_PATH)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    logger.info("=" * 50)
    logger.info("FAA Registration DB Sync")
    logger.info("Database: %s", db_path)
    logger.info("=" * 50)

    try:
        # Download
        zip_data = download_zip(FAA_URL)

        # Extract
        master_rows = extract_csv(zip_data, "MASTER.txt")
        acftref_rows = extract_csv(zip_data, "ACFTREF.txt")

        # Import
        conn = sqlite3.connect(db_path)
        create_tables(conn)

        master_count = import_master(conn, master_rows)
        acftref_count = import_acftref(conn, acftref_rows)

        conn.close()

        logger.info("=" * 50)
        logger.info("Import complete:")
        logger.info("  faa_master:  %d aircraft", master_count)
        logger.info("  faa_acftref: %d reference entries", acftref_count)
        logger.info("=" * 50)

        # Quick test lookup
        import random
        test_conn = sqlite3.connect(db_path)
        test_cursor = test_conn.cursor()
        test_cursor.execute("SELECT mode_s_code_hex FROM faa_master WHERE mode_s_code_hex != '' LIMIT 1")
        test_row = test_cursor.fetchone()
        test_conn.close()
        if test_row:
            logger.info("Sample lookup for hex %s:", test_row[0])
            result = lookup_hex(db_path, test_row[0])
            for k, v in result.items():
                logger.info("  %s: %s", k, v)

    except Exception as e:
        logger.error("Sync failed: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
