"""SkyDex SQLite database — schema, migrations, and CRUD.

Tables mirror the spec exactly:
  airframes, detections, aircraft_types, predictions,
  weather_snapshots, badges
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema DDL
# ---------------------------------------------------------------------------

_SCHEMA = """
-- Core airframe table: one row per unique ICAO 24-bit address ever seen
CREATE TABLE IF NOT EXISTS airframes (
    hex                 TEXT PRIMARY KEY,         -- ICAO 24-bit, e.g. "A18B13"
    dex_number          INTEGER UNIQUE,           -- catch order, 1-based
    registration        TEXT,                     -- N-number or foreign
    type_code           TEXT,                     -- ICAO type code, e.g. "B738"
    model               TEXT,                     -- human model name
    manufacturer        TEXT,
    operator            TEXT,
    is_military         INTEGER DEFAULT 0,        -- boolean 0/1
    first_seen          REAL,                     -- Unix timestamp
    last_seen           REAL,                     -- Unix timestamp
    detection_count     INTEGER DEFAULT 0,
    rarity              TEXT DEFAULT 'Common',    -- Common|Uncommon|Rare|Epic|Legendary
    evolution_tier      TEXT DEFAULT 'Spotted',   -- Spotted|Tracked|Tagged|Bonded
    photo_url           TEXT,
    photo_checked       INTEGER DEFAULT 0,        -- 1 once we've tried to find a photo
    photo_credit        TEXT,                     -- photographer attribution
    year_built          TEXT,                     -- year of manufacture (if known)
    emergency_seen      REAL,                     -- last time seen squawking 7x00
    primary_type        TEXT,                     -- classified behavioral type (Jet/Rotor/...)
    facts_json          TEXT DEFAULT '{}',        -- free-form JSON
    types_json          TEXT DEFAULT '[]',        -- assigned behavioral types
    created_at          REAL DEFAULT (unixepoch())
);

-- Every single detection event (one row per sighting)
CREATE TABLE IF NOT EXISTS detections (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    hex                 TEXT NOT NULL,
    timestamp           REAL DEFAULT (unixepoch()),
    lat                 REAL,
    lon                 REAL,
    altitude            REAL,                     -- feet
    ground_speed        REAL,                     -- knots
    track               REAL,                     -- degrees true
    callsign            TEXT,
    origin_airport      TEXT,
    dest_airport        TEXT,
    distance_miles      REAL,
    contrail_likely     INTEGER DEFAULT 0,        -- boolean 0/1
    is_shiny            INTEGER DEFAULT 0,        -- boolean 0/1
    FOREIGN KEY (hex) REFERENCES airframes(hex)
);

-- One row per "sighting" (a continuous appearance in range). A new sighting
-- starts only after the aircraft has been gone longer than the session gap, so
-- a trainer doing laps is one sighting and a return trip later is another.
CREATE TABLE IF NOT EXISTS sightings (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    hex                 TEXT NOT NULL,
    started_at          REAL,                     -- Unix timestamp (session start)
    ended_at            REAL,                     -- Unix timestamp (last seen)
    callsign            TEXT,
    origin_airport      TEXT,                     -- ICAO of departure (if known)
    dest_airport        TEXT,                     -- ICAO of destination (if known)
    FOREIGN KEY (hex) REFERENCES airframes(hex)
);

-- SeaDex: one row per unique vessel (by MMSI). Fully separate from airframes.
CREATE TABLE IF NOT EXISTS vessels (
    mmsi            TEXT PRIMARY KEY,
    dex_number      INTEGER UNIQUE,
    name            TEXT,
    callsign        TEXT,
    ship_type       INTEGER,
    category        TEXT,                          -- Cargo/Tanker/Sailing/...
    flag            TEXT,                          -- ISO country (from MMSI)
    length          REAL,                          -- metres
    destination     TEXT,
    first_seen      REAL,
    last_seen       REAL,
    detection_count INTEGER DEFAULT 0,
    rarity          TEXT DEFAULT 'Common',
    nav_status      INTEGER,                       -- last-known AIS nav status code
    min_distance    REAL,                          -- closest approach ever (miles)
    last_lat        REAL,                          -- last-seen position (anchor check)
    last_lon        REAL,
    imo             INTEGER,                        -- IMO number (for Commons photo lookup)
    photo_url       TEXT,
    photo_credit    TEXT,                           -- photographer / source attribution
    photo_checked   INTEGER DEFAULT 0,
    created_at      REAL DEFAULT (unixepoch())
);

-- SeaDex: one row per vessel sighting (continuous appearance in range)
CREATE TABLE IF NOT EXISTS vessel_sightings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    mmsi        TEXT NOT NULL,
    started_at  REAL,
    ended_at    REAL,
    destination TEXT
);

-- Emergency squawk events (7500 hijack, 7600 radio fail, 7700 general)
CREATE TABLE IF NOT EXISTS emergencies (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    hex                 TEXT NOT NULL,
    squawk              TEXT,
    callsign            TEXT,
    timestamp           REAL DEFAULT (unixepoch())
);

-- Aircraft type reference (B738 → Boeing 737-800)
CREATE TABLE IF NOT EXISTS aircraft_types (
    type_code           TEXT PRIMARY KEY,         -- e.g. "B738", "C172"
    name                TEXT,                     -- human name
    manufacturer        TEXT,
    role                TEXT,                     -- narrowbody, GA, rotor, etc.
    facts_json          TEXT DEFAULT '{}',        -- fun facts about this type
    image_url           TEXT,
    wikipedia_url       TEXT
);

-- Predictions: commuter schedules, type confidences
CREATE TABLE IF NOT EXISTS predictions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    key                 TEXT NOT NULL,            -- callsign or hex
    key_type            TEXT NOT NULL,            -- 'callsign' | 'hex'
    predicted_type      TEXT NOT NULL,            -- Commuter|Trainer|Sentinel|...
    confidence          REAL DEFAULT 0.0,         -- 0.0-1.0
    schedule_json       TEXT DEFAULT '{}',        -- day/hour histograms
    next_expected       TEXT,                     -- human-readable prediction
    next_expected_ts    REAL,                     -- Unix timestamp of next expected
    created_at          REAL DEFAULT (unixepoch()),
    updated_at          REAL DEFAULT (unixepoch())
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_predictions_key_type
    ON predictions(key, key_type, predicted_type);

-- Weather snapshots (from NWS or BME280)
CREATE TABLE IF NOT EXISTS weather_snapshots (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp           REAL DEFAULT (unixepoch()),
    temp_f              REAL,
    wind_speed_kt       REAL,
    wind_dir_deg        REAL,
    pressure_inhg       REAL,
    humidity_pct        REAL,
    condition           TEXT,
    source              TEXT DEFAULT 'api'        -- 'api' | 'bme280'
);

-- Badges earned
CREATE TABLE IF NOT EXISTS badges (
    badge_id            TEXT PRIMARY KEY,
    earned_at           REAL DEFAULT (unixepoch()),
    description         TEXT
);

-- AtmoDex: logged satellite passes (predicted, deduped by minute) — a history.
CREATE TABLE IF NOT EXISTS satellite_passes (
    norad         INTEGER NOT NULL,
    start_at      REAL NOT NULL,        -- minute-aligned epoch (dedupe key)
    peak_at       REAL,
    end_at        REAL,
    max_elevation REAL,
    logged_at     REAL DEFAULT (unixepoch()),
    UNIQUE(norad, start_at)
);

-- When each achievement was first unlocked (achievements themselves are
-- computed live; this just remembers the date for the detail popup).
CREATE TABLE IF NOT EXISTS achievement_unlocks (
    id        TEXT PRIMARY KEY,
    earned_at REAL DEFAULT (unixepoch())
);

-- LandDex: Amtrak trains that passed within range (the Traindex). Train
-- numbers repeat daily like commuter flights, so times_seen builds regulars.
CREATE TABLE IF NOT EXISTS trains (
    train_num   TEXT PRIMARY KEY,
    route       TEXT,
    rarity      TEXT DEFAULT 'Common',
    first_seen  REAL,
    last_seen   REAL,
    times_seen  INTEGER DEFAULT 0,
    max_speed   REAL
);

-- StormDex: notable weather "catches" — record breakers, extreme alerts,
-- named storms. Kept forever: this is the almanac your kids look back on.
CREATE TABLE IF NOT EXISTS weather_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_date  TEXT NOT NULL,     -- YYYY-MM-DD local
    kind        TEXT NOT NULL,     -- record_high/record_low/near_record/alert/named_storm
    title       TEXT,
    detail      TEXT,
    stats_json  TEXT,
    severity    TEXT,
    logged_at   REAL DEFAULT (unixepoch()),
    UNIQUE(event_date, kind, title)
);

-- EtherDex: RF/Bluetooth devices heard (devices, never people — 90-day prune)
CREATE TABLE IF NOT EXISTS ether_devices (
    device_key  TEXT PRIMARY KEY,   -- rf:Model#id  or  bt:MAC
    kind        TEXT,               -- weather/tpms/doorbell/remote/alarm/mystery/bt
    name        TEXT,
    rarity      TEXT DEFAULT 'Common',
    first_seen  REAL,
    last_seen   REAL,
    times_seen  INTEGER DEFAULT 0,
    meta_json   TEXT
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_detections_hex     ON detections(hex);
CREATE INDEX IF NOT EXISTS idx_detections_ts      ON detections(timestamp);
CREATE INDEX IF NOT EXISTS idx_sightings_hex      ON sightings(hex);
CREATE INDEX IF NOT EXISTS idx_sightings_started  ON sightings(started_at);
CREATE INDEX IF NOT EXISTS idx_vessels_count      ON vessels(detection_count DESC);
CREATE INDEX IF NOT EXISTS idx_vsight_mmsi        ON vessel_sightings(mmsi);
CREATE INDEX IF NOT EXISTS idx_vsight_started     ON vessel_sightings(started_at);
CREATE INDEX IF NOT EXISTS idx_airframes_count    ON airframes(detection_count DESC);
CREATE INDEX IF NOT EXISTS idx_airframes_rarity   ON airframes(rarity);
"""


# ---------------------------------------------------------------------------
# Connection pool (thread-safe)
# ---------------------------------------------------------------------------

class Database:
    """Thread-safe SQLite database manager."""

    def __init__(self, db_path: str = "~/.skydex/skydex.db"):
        self.path = Path(db_path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_db()

    # -- connection management ----------------------------------------------

    def _conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(str(self.path), check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA synchronous=NORMAL")
        return self._local.conn

    def _init_db(self) -> None:
        with self._transaction() as conn:
            conn.executescript(_SCHEMA)
            # Lightweight migrations: add newer columns to older airframes tables.
            cols = {r[1] for r in conn.execute("PRAGMA table_info(airframes)").fetchall()}
            for col, ddl in (
                ("photo_checked", "INTEGER DEFAULT 0"),
                ("photo_credit", "TEXT"),
                ("year_built", "TEXT"),
                ("emergency_seen", "REAL"),
                ("primary_type", "TEXT"),
            ):
                if col not in cols:
                    conn.execute(f"ALTER TABLE airframes ADD COLUMN {col} {ddl}")

            # SeaDex vessels: newer columns for the water-native stats.
            vcols = {r[1] for r in conn.execute("PRAGMA table_info(vessels)").fetchall()}
            for col, ddl in (("nav_status", "INTEGER"), ("min_distance", "REAL"),
                             ("last_lat", "REAL"), ("last_lon", "REAL"),
                             ("imo", "INTEGER"), ("photo_credit", "TEXT")):
                if col not in vcols:
                    conn.execute(f"ALTER TABLE vessels ADD COLUMN {col} {ddl}")

            # EtherDex: resident tracking (the NVIDIA Shield problem).
            ecols = {r[1] for r in conn.execute("PRAGMA table_info(ether_devices)").fetchall()}
            for col, ddl in (("hits", "INTEGER DEFAULT 0"), ("resident", "INTEGER DEFAULT 0")):
                if col not in ecols:
                    conn.execute(f"ALTER TABLE ether_devices ADD COLUMN {col} {ddl}")

            # Spotter credits — who called the rare catch (family leaderboard).
            conn.execute("""CREATE TABLE IF NOT EXISTS spotter_credits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL, kind TEXT, ident TEXT,
                spotted_at REAL DEFAULT (unixepoch()))""")

            # Journeys — craft tagged with "Follow" tracked beyond the home
            # radius (planes via ADS-B aggregators, boats via AISStream MMSI).
            conn.execute("""CREATE TABLE IF NOT EXISTS followed_craft (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL,               -- 'air' | 'sea'
                craft_id TEXT NOT NULL,           -- ICAO hex (air) or MMSI (sea)
                name TEXT, added_at REAL, active INTEGER DEFAULT 1,
                last_lat REAL, last_lon REAL, last_alt REAL, last_speed REAL,
                last_seen REAL, last_source TEXT, callsign TEXT,
                UNIQUE(kind, craft_id))""")
            conn.execute("""CREATE TABLE IF NOT EXISTS journey_points (
                follow_id INTEGER NOT NULL,
                ts REAL NOT NULL, lat REAL, lon REAL, alt REAL, speed REAL)""")
            conn.execute("""CREATE INDEX IF NOT EXISTS idx_journey_pts
                ON journey_points(follow_id, ts)""")

            # Trainer cards + games arcade: per-kid avatars, game scores
            # (top-3 kept per game), and the daily weather-guess game.
            conn.execute("""CREATE TABLE IF NOT EXISTS profiles (
                name TEXT PRIMARY KEY, avatar TEXT,
                created_at REAL DEFAULT (unixepoch()))""")
            conn.execute("""CREATE TABLE IF NOT EXISTS kid_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL, game TEXT NOT NULL,
                score REAL NOT NULL, played_at REAL DEFAULT (unixepoch()))""")
            conn.execute("""CREATE TABLE IF NOT EXISTS wx_guesses (
                target_date TEXT NOT NULL, name TEXT NOT NULL, guess REAL,
                resolved INTEGER DEFAULT 0, won INTEGER DEFAULT 0, actual REAL,
                UNIQUE(target_date, name))""")

            # One-time migrations keyed on PRAGMA user_version.
            ver = conn.execute("PRAGMA user_version").fetchone()[0]
            if ver < 1:
                # A new photo source (Planespotters) was added — re-try the
                # backfill for any airframe that still has no photo.
                conn.execute(
                    "UPDATE airframes SET photo_checked = 0 "
                    "WHERE photo_url IS NULL OR photo_url = ''"
                )
                conn.execute("PRAGMA user_version = 1")
            if ver < 2:
                # Purge EtherDex "devices" that were really bluetoothctl property
                # lines swallowed by the old parser (ManufacturerData, RSSI…).
                conn.execute(
                    """DELETE FROM ether_devices WHERE
                       name LIKE 'ManufacturerData%' OR name LIKE 'ServiceData%'
                       OR name LIKE 'RSSI%' OR name LIKE 'TxPower%'
                       OR name LIKE 'UUIDs%' OR name LIKE 'AdvertisingFlags%'
                       OR name LIKE 'Name:%' OR name LIKE 'Alias:%'
                       OR name LIKE '%Key: 0x%' OR name LIKE '%Value:%'""")
                conn.execute("PRAGMA user_version = 2")
            if ver < 3:
                # Merge duplicate Bluetooth entries: gadgets rotate randomized
                # MACs, so one Shield became a dozen rows. Collapse by name
                # into a name-keyed row with summed counts.
                rows = conn.execute(
                    """SELECT LOWER(TRIM(name)) AS lname, MIN(first_seen) AS fs,
                              MAX(last_seen) AS ls, SUM(times_seen) AS ts,
                              SUM(COALESCE(hits,0)) AS h, MAX(resident) AS res,
                              MAX(kind) AS kind, MAX(name) AS disp,
                              MAX(rarity) AS rar, MAX(meta_json) AS mj
                       FROM ether_devices
                       WHERE device_key LIKE 'bt%' AND name IS NOT NULL AND name != ''
                       GROUP BY lname"""
                ).fetchall()
                for r in rows:
                    conn.execute(
                        """INSERT INTO ether_devices (device_key, kind, name, rarity,
                           first_seen, last_seen, times_seen, hits, resident, meta_json)
                           VALUES (?,?,?,?,?,?,?,?,?,?)
                           ON CONFLICT(device_key) DO UPDATE SET
                             times_seen = excluded.times_seen,
                             hits = excluded.hits,
                             first_seen = excluded.first_seen,
                             last_seen = excluded.last_seen,
                             resident = MAX(resident, excluded.resident)""",
                        (f"btn:{r['lname'][:40]}", r["kind"], r["disp"], r["rar"],
                         r["fs"], r["ls"], r["ts"], r["h"], r["res"], r["mj"]))
                conn.execute("DELETE FROM ether_devices WHERE device_key LIKE 'bt:%'")
                conn.execute("PRAGMA user_version = 3")
        logger.info("Database initialized at %s", self.path)

    @contextmanager
    def _transaction(self):
        conn = self._conn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    # -- airframes ----------------------------------------------------------

    def get_airframe(self, hex_code: str) -> Optional[Dict[str, Any]]:
        with self._transaction() as conn:
            row = conn.execute(
                "SELECT * FROM airframes WHERE hex = ?", (hex_code.upper(),)
            ).fetchone()
            return dict(row) if row else None

    def get_or_create_airframe(self, hex_code: str) -> Dict[str, Any]:
        """Get existing airframe or create a new one with the next dex_number."""
        hex_code = hex_code.upper().strip()
        existing = self.get_airframe(hex_code)
        if existing:
            return existing

        with self._transaction() as conn:
            # Get next dex_number
            row = conn.execute(
                "SELECT COALESCE(MAX(dex_number), 0) + 1 FROM airframes"
            ).fetchone()
            dex_number = row[0] if row else 1

            now = time.time()
            conn.execute(
                """INSERT INTO airframes
                   (hex, dex_number, first_seen, last_seen, detection_count)
                   VALUES (?, ?, ?, ?, 0)""",
                (hex_code, dex_number, now, now),
            )

        return self.get_airframe(hex_code)

    # Columns that enrichment is allowed to write to (guards against
    # enrichment dicts carrying extra keys like icao24/source/year).
    _AIRFRAME_COLUMNS = {
        "registration", "type_code", "model", "manufacturer", "operator",
        "is_military", "first_seen", "last_seen", "detection_count", "rarity",
        "evolution_tier", "photo_url", "photo_checked", "photo_credit",
        "year_built", "emergency_seen", "primary_type", "facts_json", "types_json",
    }

    def update_airframe(self, hex_code: str, **fields: Any) -> None:
        hex_code = hex_code.upper().strip()
        fields["last_seen"] = time.time()

        # Filter out None values (don't overwrite good data with nulls) and any
        # keys that aren't real airframe columns.
        set_clauses = []
        values = []
        for key, value in fields.items():
            if value is not None and key in self._AIRFRAME_COLUMNS:
                set_clauses.append(f"{key} = ?")
                values.append(value)

        if not set_clauses:
            return

        values.append(hex_code)
        with self._transaction() as conn:
            conn.execute(
                f"UPDATE airframes SET {', '.join(set_clauses)} WHERE hex = ?",
                values,
        )

    def increment_detection_count(self, hex_code: str) -> int:
        hex_code = hex_code.upper().strip()
        with self._transaction() as conn:
            conn.execute(
                """UPDATE airframes
                   SET detection_count = detection_count + 1,
                       last_seen = ?
                   WHERE hex = ?""",
                (time.time(), hex_code),
            )
            row = conn.execute(
                "SELECT detection_count FROM airframes WHERE hex = ?", (hex_code,)
            ).fetchone()
            return row[0] if row else 0

    def list_airframes(
        self,
        order_by: str = "detection_count DESC",
        limit: int = 100,
        rarity: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        # detection_count > 0 = actually caught inside the pokeball. Airframe
        # rows also exist for fly-bys that were only *seen* (wide visible range)
        # or whose detail card was opened — those don't belong in the dex.
        query = "SELECT * FROM airframes WHERE detection_count > 0"
        params: Tuple = ()
        if rarity:
            query += " AND rarity = ?"
            params = (rarity,)
        query += f" ORDER BY {order_by} LIMIT ?"
        params += (limit,)

        with self._transaction() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def get_top_airframes(self, n: int = 10) -> List[Dict[str, Any]]:
        return self.list_airframes(order_by="detection_count DESC", limit=n)

    def get_airframes_needing_photo(self, limit: int = 1) -> List[Dict[str, Any]]:
        """Logged airframes that have no photo and haven't been checked yet,
        most-seen first (so popular regulars get pictures soonest)."""
        with self._transaction() as conn:
            rows = conn.execute(
                """SELECT hex, registration FROM airframes
                   WHERE (photo_url IS NULL OR photo_url = '')
                     AND COALESCE(photo_checked, 0) = 0
                   ORDER BY detection_count DESC LIMIT ?""",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_photo_for_type(self, type_code: str) -> Optional[str]:
        """A representative photo URL for a type — the most-seen airframe of
        that type that has a photo. Used as a generic 'model' image fallback."""
        if not type_code:
            return None
        with self._transaction() as conn:
            row = conn.execute(
                """SELECT photo_url FROM airframes
                   WHERE type_code = ? AND photo_url IS NOT NULL AND photo_url != ''
                   ORDER BY detection_count DESC LIMIT 1""",
                (type_code.upper().strip(),),
            ).fetchone()
            return row[0] if row else None

    def get_airframe_count(self) -> int:
        with self._transaction() as conn:
            row = conn.execute("SELECT COUNT(*) FROM airframes WHERE detection_count > 0").fetchone()
            return row[0] if row else 0

    # -- detections ---------------------------------------------------------

    def log_detection(self, hex_code: str, **fields: Any) -> int:
        """Log a detection event. Returns the detection row id."""
        hex_code = hex_code.upper().strip()
        columns = ["hex"]
        values = [hex_code]
        for key, value in fields.items():
            if value is not None:
                columns.append(key)
                values.append(value)

        with self._transaction() as conn:
            cursor = conn.execute(
                f"INSERT INTO detections ({', '.join(columns)}) VALUES ({', '.join('?' * len(values))})",
                values,
            )
            return cursor.lastrowid

    # -- sightings (sessions) ----------------------------------------------

    def start_sighting(
        self, hex_code: str, started_at: float,
        callsign: Optional[str] = None,
        origin: Optional[str] = None, dest: Optional[str] = None,
    ) -> int:
        """Open a new sighting (continuous-appearance session). Returns its id."""
        hex_code = hex_code.upper().strip()
        with self._transaction() as conn:
            cursor = conn.execute(
                """INSERT INTO sightings (hex, started_at, ended_at, callsign, origin_airport, dest_airport)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (hex_code, started_at, started_at, callsign or None, origin or None, dest or None),
            )
            return cursor.lastrowid

    def update_sighting(
        self, sighting_id: int, ended_at: float,
        callsign: Optional[str] = None,
        origin: Optional[str] = None, dest: Optional[str] = None,
    ) -> None:
        """Extend an open sighting; fill callsign/route once they become known."""
        with self._transaction() as conn:
            conn.execute(
                """UPDATE sightings SET
                       ended_at = ?,
                       callsign = COALESCE(NULLIF(callsign, ''), ?),
                       origin_airport = COALESCE(NULLIF(origin_airport, ''), ?),
                       dest_airport = COALESCE(NULLIF(dest_airport, ''), ?)
                   WHERE id = ?""",
                (ended_at, callsign or None, origin or None, dest or None, sighting_id),
            )

    def get_route_counts(self, which: str, limit: int = 40) -> List[Dict[str, Any]]:
        """Top departure ('origin') or arrival ('dest') airports by sighting
        count. Returns [{code, count}, ...]. Cities are resolved in the API."""
        col = "origin_airport" if which == "origin" else "dest_airport"
        with self._transaction() as conn:
            rows = conn.execute(
                f"""SELECT {col} AS code, COUNT(*) AS c FROM sightings
                    WHERE {col} IS NOT NULL AND {col} != ''
                    GROUP BY {col} ORDER BY c DESC LIMIT ?""",
                (limit,),
            ).fetchall()
            return [{"code": r["code"], "count": r["c"]} for r in rows]

    def get_model_counts(self, limit: int = 8) -> List[Dict[str, Any]]:
        """Most-seen aircraft models (by total sightings)."""
        with self._transaction() as conn:
            rows = conn.execute(
                """SELECT model AS label, SUM(detection_count) AS c FROM airframes
                   WHERE model IS NOT NULL AND model != ''
                   GROUP BY model ORDER BY c DESC LIMIT ?""",
                (limit,),
            ).fetchall()
            return [{"label": r["label"], "count": r["c"] or 0} for r in rows]

    def get_operator_counts(self, limit: int = 8) -> List[Dict[str, Any]]:
        """Most-seen operators / owners (by total sightings)."""
        with self._transaction() as conn:
            rows = conn.execute(
                """SELECT operator AS label, SUM(detection_count) AS c FROM airframes
                   WHERE operator IS NOT NULL AND operator != ''
                   GROUP BY operator ORDER BY c DESC LIMIT ?""",
                (limit,),
            ).fetchall()
            return [{"label": r["label"], "count": r["c"] or 0} for r in rows]

    def get_sightings_dow(self) -> List[Tuple[str, int]]:
        """(hex, day-of-week) for every sighting (0=Sun..6=Sat, local time).

        Used to build the 'activity by fleet type by day' chart — the fleet type
        is resolved per-hex in the API layer (it needs the classifier)."""
        with self._transaction() as conn:
            rows = conn.execute(
                """SELECT hex,
                          CAST(strftime('%w', started_at, 'unixepoch', 'localtime') AS INTEGER) AS dow
                   FROM sightings WHERE started_at IS NOT NULL"""
            ).fetchall()
            return [(r["hex"], r["dow"]) for r in rows]

    def get_last_sighting(self, hex_code: str) -> Optional[Dict[str, Any]]:
        """Most recent sighting for an airframe (used to resume across restarts)."""
        with self._transaction() as conn:
            row = conn.execute(
                "SELECT * FROM sightings WHERE hex = ? ORDER BY started_at DESC LIMIT 1",
                (hex_code.upper(),),
            ).fetchone()
            return dict(row) if row else None

    def get_sightings_for_airframe(
        self, hex_code: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        with self._transaction() as conn:
            rows = conn.execute(
                """SELECT * FROM sightings WHERE hex = ?
                   ORDER BY started_at DESC LIMIT ?""",
                (hex_code.upper(), limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_airframe_route_stats(self, hex_code: str, limit: int = 5) -> Dict[str, Any]:
        """Top departure / arrival airports for a single airframe (its regulars)."""
        h = hex_code.upper()
        with self._transaction() as conn:
            origins = conn.execute(
                """SELECT origin_airport AS code, COUNT(*) AS c FROM sightings
                   WHERE hex = ? AND origin_airport IS NOT NULL AND origin_airport != ''
                   GROUP BY origin_airport ORDER BY c DESC LIMIT ?""",
                (h, limit),
            ).fetchall()
            dests = conn.execute(
                """SELECT dest_airport AS code, COUNT(*) AS c FROM sightings
                   WHERE hex = ? AND dest_airport IS NOT NULL AND dest_airport != ''
                   GROUP BY dest_airport ORDER BY c DESC LIMIT ?""",
                (h, limit),
            ).fetchall()
            return {
                "origins": [{"code": r["code"], "count": r["c"]} for r in origins],
                "dests": [{"code": r["code"], "count": r["c"]} for r in dests],
            }

    # -- vessels (SeaDex) ---------------------------------------------------

    _VESSEL_COLUMNS = {
        "name", "callsign", "ship_type", "category", "flag", "length",
        "destination", "first_seen", "last_seen", "detection_count", "rarity",
        "nav_status", "min_distance", "last_lat", "last_lon", "imo",
        "photo_url", "photo_credit", "photo_checked",
    }

    def get_vessel(self, mmsi: str) -> Optional[Dict[str, Any]]:
        with self._transaction() as conn:
            row = conn.execute("SELECT * FROM vessels WHERE mmsi = ?", (str(mmsi).strip(),)).fetchone()
            return dict(row) if row else None

    def get_or_create_vessel(self, mmsi: str) -> Dict[str, Any]:
        mmsi = str(mmsi).strip()
        existing = self.get_vessel(mmsi)
        if existing:
            return existing
        with self._transaction() as conn:
            row = conn.execute("SELECT COALESCE(MAX(dex_number), 0) + 1 FROM vessels").fetchone()
            dex_number = row[0] if row else 1
            now = time.time()
            conn.execute(
                "INSERT INTO vessels (mmsi, dex_number, first_seen, last_seen, detection_count) VALUES (?, ?, ?, ?, 0)",
                (mmsi, dex_number, now, now),
            )
        return self.get_vessel(mmsi)

    def update_vessel(self, mmsi: str, **fields: Any) -> None:
        mmsi = str(mmsi).strip()
        fields["last_seen"] = time.time()
        sets, vals = [], []
        for k, v in fields.items():
            if v is not None and k in self._VESSEL_COLUMNS:
                sets.append(f"{k} = ?")
                vals.append(v)
        if not sets:
            return
        vals.append(mmsi)
        with self._transaction() as conn:
            conn.execute(f"UPDATE vessels SET {', '.join(sets)} WHERE mmsi = ?", vals)

    def increment_vessel_count(self, mmsi: str) -> int:
        mmsi = str(mmsi).strip()
        with self._transaction() as conn:
            conn.execute(
                "UPDATE vessels SET detection_count = detection_count + 1, last_seen = ? WHERE mmsi = ?",
                (time.time(), mmsi),
            )
            row = conn.execute("SELECT detection_count FROM vessels WHERE mmsi = ?", (mmsi,)).fetchone()
            return row[0] if row else 0

    def list_vessels(self, order_by: str = "detection_count DESC", limit: int = 1000) -> List[Dict[str, Any]]:
        with self._transaction() as conn:
            rows = conn.execute(f"SELECT * FROM vessels ORDER BY {order_by} LIMIT ?", (limit,)).fetchall()
            return [dict(r) for r in rows]

    def start_vessel_sighting(self, mmsi: str, started_at: float, destination: Optional[str] = None) -> int:
        with self._transaction() as conn:
            cur = conn.execute(
                "INSERT INTO vessel_sightings (mmsi, started_at, ended_at, destination) VALUES (?, ?, ?, ?)",
                (str(mmsi).strip(), started_at, started_at, destination or None),
            )
            return cur.lastrowid

    def update_vessel_sighting(self, sighting_id: int, ended_at: float, destination: Optional[str] = None) -> None:
        with self._transaction() as conn:
            conn.execute(
                "UPDATE vessel_sightings SET ended_at = ?, destination = COALESCE(NULLIF(destination,''), ?) WHERE id = ?",
                (ended_at, destination or None, sighting_id),
            )

    def get_last_vessel_sighting(self, mmsi: str) -> Optional[Dict[str, Any]]:
        with self._transaction() as conn:
            row = conn.execute(
                "SELECT * FROM vessel_sightings WHERE mmsi = ? ORDER BY started_at DESC LIMIT 1",
                (str(mmsi).strip(),),
            ).fetchone()
            return dict(row) if row else None

    def get_vessel_sightings(self, mmsi: str, limit: int = 12) -> List[Dict[str, Any]]:
        with self._transaction() as conn:
            rows = conn.execute(
                "SELECT * FROM vessel_sightings WHERE mmsi = ? ORDER BY started_at DESC LIMIT ?",
                (str(mmsi).strip(), limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_vessel_stats(self) -> Dict[str, Any]:
        """Totals + breakdowns for the SeaDex Stats/Graphs pages."""
        with self._transaction() as conn:
            total_vessels = conn.execute("SELECT COUNT(*) FROM vessels").fetchone()[0]
            total_sightings = conn.execute("SELECT COUNT(*) FROM vessel_sightings").fetchone()[0]

            cat = {r[0]: r[1] for r in conn.execute(
                "SELECT category, COUNT(*) FROM vessels WHERE category IS NOT NULL GROUP BY category").fetchall()}
            rarity = {r[0]: r[1] for r in conn.execute(
                "SELECT rarity, COUNT(*) FROM vessels GROUP BY rarity").fetchall()}
            top = [dict(r) for r in conn.execute(
                "SELECT mmsi, dex_number, name, category, detection_count FROM vessels ORDER BY detection_count DESC LIMIT 3").fetchall()]

            dow = conn.execute(
                """SELECT CAST(strftime('%w', started_at,'unixepoch','localtime') AS INTEGER) AS d, COUNT(*) c
                   FROM vessel_sightings GROUP BY d ORDER BY c DESC LIMIT 1""").fetchone()
            hour = conn.execute(
                """SELECT CAST(strftime('%H', started_at,'unixepoch','localtime') AS INTEGER) AS h, COUNT(*) c
                   FROM vessel_sightings GROUP BY h ORDER BY c DESC LIMIT 1""").fetchone()

            hour_arr = [0] * 24
            for r in conn.execute(
                """SELECT CAST(strftime('%H', started_at,'unixepoch','localtime') AS INTEGER) AS h, COUNT(*) c
                   FROM vessel_sightings WHERE date(started_at,'unixepoch','localtime') = date('now','localtime')
                   GROUP BY h""").fetchall():
                if r["h"] is not None and 0 <= r["h"] <= 23:
                    hour_arr[r["h"]] = r["c"]

            dests = [{"label": r[0], "count": r[1]} for r in conn.execute(
                """SELECT destination, COUNT(*) FROM vessel_sightings
                   WHERE destination IS NOT NULL AND destination != ''
                   GROUP BY destination ORDER BY COUNT(*) DESC LIMIT 8""").fetchall()]
            flags = [{"label": r[0], "count": r[1]} for r in conn.execute(
                """SELECT flag, SUM(detection_count) FROM vessels
                   WHERE flag IS NOT NULL AND flag != ''
                   GROUP BY flag ORDER BY SUM(detection_count) DESC LIMIT 8""").fetchall()]

            # Nav-status distribution (last-known per vessel) — uniquely maritime.
            nav = {r[0]: r[1] for r in conn.execute(
                "SELECT nav_status, COUNT(*) FROM vessels WHERE nav_status IS NOT NULL GROUP BY nav_status").fetchall()}

            # Size: biggest vessels seen + a length distribution.
            biggest = [dict(r) for r in conn.execute(
                """SELECT mmsi, dex_number, name, category, length FROM vessels
                   WHERE length IS NOT NULL AND length > 0 ORDER BY length DESC LIMIT 5""").fetchall()]
            size_buckets = {"< 50 m": 0, "50–100 m": 0, "100–200 m": 0, "200 m+": 0}
            for (ln,) in conn.execute("SELECT length FROM vessels WHERE length IS NOT NULL AND length > 0").fetchall():
                if ln < 50:
                    size_buckets["< 50 m"] += 1
                elif ln < 100:
                    size_buckets["50–100 m"] += 1
                elif ln < 200:
                    size_buckets["100–200 m"] += 1
                else:
                    size_buckets["200 m+"] += 1

            # Closest approach ever, and the longest single visit (dwell).
            closest = conn.execute(
                """SELECT mmsi, name, category, min_distance FROM vessels
                   WHERE min_distance IS NOT NULL ORDER BY min_distance ASC LIMIT 1""").fetchone()
            dwell = conn.execute(
                """SELECT s.mmsi, v.name, v.category,
                          (s.ended_at - s.started_at) AS secs
                   FROM vessel_sightings s LEFT JOIN vessels v ON s.mmsi = v.mmsi
                   WHERE s.ended_at IS NOT NULL AND s.started_at IS NOT NULL
                   ORDER BY secs DESC LIMIT 1""").fetchone()

            return {
                "total_vessels": total_vessels,
                "total_sightings": total_sightings,
                "category_distribution": cat,
                "rarity_distribution": rarity,
                "top_vessels": top,
                "busiest_dow": dow["d"] if dow else None,
                "busiest_dow_count": dow["c"] if dow else 0,
                "busiest_hour": hour["h"] if hour else None,
                "busiest_hour_count": hour["c"] if hour else 0,
                "activity_by_hour_today": hour_arr,
                "top_destinations": dests,
                "top_flags": flags,
                "nav_status_distribution": nav,
                "biggest_vessels": biggest,
                "size_distribution": size_buckets,
                "closest_approach": dict(closest) if closest else None,
                "longest_dwell": dict(dwell) if dwell else None,
            }

    def get_vessel_category_dow(self) -> List[Tuple[str, int]]:
        """(category, day-of-week) per vessel sighting, for the activity chart."""
        with self._transaction() as conn:
            rows = conn.execute(
                """SELECT v.category AS cat,
                          CAST(strftime('%w', s.started_at,'unixepoch','localtime') AS INTEGER) AS dow
                   FROM vessel_sightings s LEFT JOIN vessels v ON s.mmsi = v.mmsi
                   WHERE s.started_at IS NOT NULL"""
            ).fetchall()
            return [((r["cat"] or "Other"), r["dow"]) for r in rows]

    # -- day summary (combined air + sea report for today) ------------------

    def get_day_summary(self) -> Dict[str, Any]:
        """A rich summary of *today's* traffic — both aircraft and vessels.

        Today = the local calendar day. Aircraft telemetry (speed/altitude/
        routes) comes from the `detections` log; counts/new-vs-repeat come from
        the per-session `sightings` / `vessel_sightings` tables.
        """
        with self._transaction() as conn:
            return {
                "air": self._air_day_summary(conn),
                "sea": self._sea_day_summary(conn),
            }

    def _air_day_summary(self, conn) -> Dict[str, Any]:
        TODAY_S = "date(started_at,'unixepoch','localtime')=date('now','localtime')"
        TODAY_T = "date(timestamp,'unixepoch','localtime')=date('now','localtime')"

        visits = conn.execute(f"SELECT COUNT(*) FROM sightings WHERE {TODAY_S}").fetchone()[0]
        unique = conn.execute(f"SELECT COUNT(DISTINCT hex) FROM sightings WHERE {TODAY_S}").fetchone()[0]
        new = conn.execute(
            f"""SELECT COUNT(*) FROM airframes
                WHERE date(first_seen,'unixepoch','localtime')=date('now','localtime')
                  AND hex IN (SELECT DISTINCT hex FROM sightings WHERE {TODAY_S})"""
        ).fetchone()[0]

        def _extreme(col):
            r = conn.execute(
                f"""SELECT d.{col} AS val, a.model, a.registration, a.operator, d.callsign, d.hex
                    FROM detections d LEFT JOIN airframes a ON d.hex=a.hex
                    WHERE {TODAY_T} AND d.{col} IS NOT NULL
                    ORDER BY d.{col} DESC LIMIT 1"""
            ).fetchone()
            return dict(r) if r else None

        by_type = {(r["t"] or "Aircraft"): r["c"] for r in conn.execute(
            f"""SELECT a.primary_type AS t, COUNT(DISTINCT s.hex) AS c
                FROM sightings s LEFT JOIN airframes a ON s.hex=a.hex
                WHERE {TODAY_S} GROUP BY a.primary_type""").fetchall()}

        top_models = [{"label": r[0], "count": r[1]} for r in conn.execute(
            f"""SELECT COALESCE(NULLIF(a.model,''), a.type_code, 'Unknown') AS m, COUNT(DISTINCT s.hex) AS c
                FROM sightings s LEFT JOIN airframes a ON s.hex=a.hex
                WHERE {TODAY_S} GROUP BY m ORDER BY c DESC LIMIT 8""").fetchall()]

        top_routes = [{"origin": r[0], "dest": r[1], "count": r[2]} for r in conn.execute(
            f"""SELECT origin_airport, dest_airport, COUNT(DISTINCT hex) AS c
                FROM detections
                WHERE {TODAY_T} AND origin_airport IS NOT NULL AND origin_airport!=''
                  AND dest_airport IS NOT NULL AND dest_airport!=''
                GROUP BY origin_airport, dest_airport ORDER BY c DESC LIMIT 8""").fetchall()]

        hours = [0] * 24
        for r in conn.execute(
            f"""SELECT CAST(strftime('%H', started_at,'unixepoch','localtime') AS INTEGER) AS h, COUNT(*) c
                FROM sightings WHERE {TODAY_S} GROUP BY h""").fetchall():
            if r["h"] is not None and 0 <= r["h"] <= 23:
                hours[r["h"]] = r["c"]
        busiest_hour = max(range(24), key=lambda h: hours[h]) if any(hours) else None

        emergencies = [dict(r) for r in conn.execute(
            f"""SELECT e.hex, e.squawk, e.callsign, e.timestamp, a.model, a.registration
                FROM emergencies e LEFT JOIN airframes a ON e.hex=a.hex
                WHERE date(e.timestamp,'unixepoch','localtime')=date('now','localtime')
                ORDER BY e.timestamp DESC""").fetchall()]

        roster = [dict(r) for r in conn.execute(
            f"""SELECT s.hex, COUNT(*) AS visits, a.model, a.registration, a.operator,
                       a.primary_type, a.rarity, a.detection_count, dt.max_alt, dt.max_spd,
                       CASE WHEN date(a.first_seen,'unixepoch','localtime')=date('now','localtime')
                            THEN 1 ELSE 0 END AS is_new
                FROM sightings s
                LEFT JOIN airframes a ON s.hex=a.hex
                LEFT JOIN (SELECT hex, MAX(altitude) max_alt, MAX(ground_speed) max_spd
                           FROM detections WHERE {TODAY_T} GROUP BY hex) dt ON dt.hex=s.hex
                WHERE {TODAY_S}
                GROUP BY s.hex ORDER BY visits DESC, dt.max_spd DESC LIMIT 60""").fetchall()]

        return {
            "visits": visits, "unique": unique, "new": new, "repeat": max(0, unique - new),
            "fastest": _extreme("ground_speed"), "highest": _extreme("altitude"),
            "by_type": by_type, "top_models": top_models, "top_routes": top_routes,
            "activity_by_hour": hours, "busiest_hour": busiest_hour,
            "emergencies": emergencies, "roster": roster,
        }

    def _sea_day_summary(self, conn) -> Dict[str, Any]:
        TODAY = "date(started_at,'unixepoch','localtime')=date('now','localtime')"

        visits = conn.execute(f"SELECT COUNT(*) FROM vessel_sightings WHERE {TODAY}").fetchone()[0]
        unique = conn.execute(f"SELECT COUNT(DISTINCT mmsi) FROM vessel_sightings WHERE {TODAY}").fetchone()[0]
        new = conn.execute(
            f"""SELECT COUNT(*) FROM vessels
                WHERE date(first_seen,'unixepoch','localtime')=date('now','localtime')
                  AND mmsi IN (SELECT DISTINCT mmsi FROM vessel_sightings WHERE {TODAY})"""
        ).fetchone()[0]

        biggest = conn.execute(
            f"""SELECT v.length AS val, v.name, v.mmsi, v.category FROM vessels v
                WHERE v.length IS NOT NULL
                  AND v.mmsi IN (SELECT DISTINCT mmsi FROM vessel_sightings WHERE {TODAY})
                ORDER BY v.length DESC LIMIT 1""").fetchone()

        by_category = {(r["c"] or "Other"): r["n"] for r in conn.execute(
            f"""SELECT v.category AS c, COUNT(DISTINCT s.mmsi) AS n
                FROM vessel_sightings s LEFT JOIN vessels v ON s.mmsi=v.mmsi
                WHERE {TODAY} GROUP BY v.category""").fetchall()}

        top_destinations = [{"label": r[0], "count": r[1]} for r in conn.execute(
            f"""SELECT destination, COUNT(*) AS c FROM vessel_sightings
                WHERE {TODAY} AND destination IS NOT NULL AND destination!=''
                GROUP BY destination ORDER BY c DESC LIMIT 8""").fetchall()]

        top_flags = [{"label": r[0], "count": r[1]} for r in conn.execute(
            f"""SELECT v.flag, COUNT(DISTINCT s.mmsi) AS c
                FROM vessel_sightings s LEFT JOIN vessels v ON s.mmsi=v.mmsi
                WHERE {TODAY} AND v.flag IS NOT NULL AND v.flag!=''
                GROUP BY v.flag ORDER BY c DESC LIMIT 8""").fetchall()]

        roster = [dict(r) for r in conn.execute(
            f"""SELECT s.mmsi, COUNT(*) AS visits, v.name, v.category, v.length, v.flag,
                       v.rarity, v.destination, v.detection_count,
                       CASE WHEN date(v.first_seen,'unixepoch','localtime')=date('now','localtime')
                            THEN 1 ELSE 0 END AS is_new
                FROM vessel_sightings s LEFT JOIN vessels v ON s.mmsi=v.mmsi
                WHERE {TODAY}
                GROUP BY s.mmsi ORDER BY visits DESC, v.length DESC LIMIT 60""").fetchall()]

        return {
            "visits": visits, "unique": unique, "new": new, "repeat": max(0, unique - new),
            "biggest": dict(biggest) if biggest else None,
            "by_category": by_category, "top_destinations": top_destinations,
            "top_flags": top_flags, "roster": roster,
        }

    # -- emergencies --------------------------------------------------------

    def log_emergency(self, hex_code: str, squawk: str, callsign: Optional[str] = None) -> None:
        with self._transaction() as conn:
            conn.execute(
                "INSERT INTO emergencies (hex, squawk, callsign) VALUES (?, ?, ?)",
                (hex_code.upper(), squawk, callsign or None),
            )

    def get_emergencies(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._transaction() as conn:
            rows = conn.execute(
                "SELECT * FROM emergencies ORDER BY timestamp DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_emergency_counts(self) -> Dict[str, int]:
        with self._transaction() as conn:
            rows = conn.execute(
                "SELECT squawk, COUNT(*) AS c FROM emergencies GROUP BY squawk"
            ).fetchall()
            return {r["squawk"]: r["c"] for r in rows}

    def get_detections_for_airframe(
        self, hex_code: str, limit: int = 500
    ) -> List[Dict[str, Any]]:
        with self._transaction() as conn:
            rows = conn.execute(
                """SELECT * FROM detections WHERE hex = ?
                   ORDER BY timestamp DESC LIMIT ?""",
                (hex_code.upper(), limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_recent_detections(self, since: float) -> List[Dict[str, Any]]:
        with self._transaction() as conn:
            rows = conn.execute(
                "SELECT * FROM detections WHERE timestamp > ? ORDER BY timestamp DESC",
                (since,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_detection_count(self) -> int:
        with self._transaction() as conn:
            row = conn.execute("SELECT COUNT(*) FROM detections").fetchone()
            return row[0] if row else 0

    # -- aircraft types -----------------------------------------------------

    def get_aircraft_type(self, type_code: str) -> Optional[Dict[str, Any]]:
        with self._transaction() as conn:
            row = conn.execute(
                "SELECT * FROM aircraft_types WHERE type_code = ?",
                (type_code.upper(),),
            ).fetchone()
            return dict(row) if row else None

    def upsert_aircraft_type(self, type_code: str, **fields: Any) -> None:
        type_code = type_code.upper().strip()
        existing = self.get_aircraft_type(type_code)

        if existing:
            set_clauses = []
            values = []
            for key, value in fields.items():
                if value is not None:
                    set_clauses.append(f"{key} = ?")
                    values.append(value)
            if set_clauses:
                values.append(type_code)
                with self._transaction() as conn:
                    conn.execute(
                        f"UPDATE aircraft_types SET {', '.join(set_clauses)} WHERE type_code = ?",
                        values,
                    )
        else:
            columns = ["type_code"]
            values = [type_code]
            for key, value in fields.items():
                if value is not None:
                    columns.append(key)
                    values.append(value)
            with self._transaction() as conn:
                conn.execute(
                    f"INSERT INTO aircraft_types ({', '.join(columns)}) VALUES ({', '.join('?' * len(values))})",
                    values,
                )

    # -- predictions --------------------------------------------------------

    def get_predictions(self, key: str, key_type: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._transaction() as conn:
            if key_type:
                rows = conn.execute(
                    "SELECT * FROM predictions WHERE key = ? AND key_type = ? ORDER BY confidence DESC",
                    (key, key_type),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM predictions WHERE key = ? ORDER BY confidence DESC",
                    (key,),
                ).fetchall()
            return [dict(r) for r in rows]

    def upsert_prediction(
        self, key: str, key_type: str, predicted_type: str,
        confidence: float = 0.0, schedule_json: str = "{}",
        next_expected: Optional[str] = None, next_expected_ts: Optional[float] = None,
    ) -> None:
        now = time.time()
        with self._transaction() as conn:
            existing = conn.execute(
                "SELECT id FROM predictions WHERE key = ? AND key_type = ? AND predicted_type = ?",
                (key, key_type, predicted_type),
            ).fetchone()

            if existing:
                conn.execute(
                    """UPDATE predictions SET
                        confidence = ?, schedule_json = ?,
                        next_expected = ?, next_expected_ts = ?, updated_at = ?
                       WHERE id = ?""",
                    (confidence, schedule_json, next_expected, next_expected_ts, now, existing["id"]),
                )
            else:
                conn.execute(
                    """INSERT INTO predictions
                        (key, key_type, predicted_type, confidence, schedule_json,
                         next_expected, next_expected_ts, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (key, key_type, predicted_type, confidence, schedule_json,
                     next_expected, next_expected_ts, now, now),
                )

    # -- weather ------------------------------------------------------------

    def get_latest_weather(self) -> Optional[Dict[str, Any]]:
        with self._transaction() as conn:
            row = conn.execute(
                "SELECT * FROM weather_snapshots ORDER BY timestamp DESC LIMIT 1"
            ).fetchone()
            return dict(row) if row else None

    def save_weather(self, **fields: Any) -> None:
        columns = []
        values = []
        for key, value in fields.items():
            if value is not None:
                columns.append(key)
                values.append(value)
        if not columns:
            return
        with self._transaction() as conn:
            conn.execute(
                f"INSERT INTO weather_snapshots ({', '.join(columns)}) VALUES ({', '.join('?' * len(values))})",
                values,
            )

    # -- badges -------------------------------------------------------------

    def has_badge(self, badge_id: str) -> bool:
        with self._transaction() as conn:
            row = conn.execute(
                "SELECT 1 FROM badges WHERE badge_id = ?", (badge_id,)
            ).fetchone()
            return row is not None

    def award_badge(self, badge_id: str, description: str = "") -> bool:
        """Award a badge. Returns True if newly awarded, False if already had."""
        if self.has_badge(badge_id):
            return False
        with self._transaction() as conn:
            conn.execute(
                "INSERT INTO badges (badge_id, description) VALUES (?, ?)",
                (badge_id, description),
            )
        logger.info("Badge awarded: %s", badge_id)
        return True

    def list_badges(self) -> List[Dict[str, Any]]:
        with self._transaction() as conn:
            rows = conn.execute("SELECT * FROM badges ORDER BY earned_at DESC").fetchall()
            return [dict(r) for r in rows]

    # -- satellite passes (AtmoDex history) ---------------------------------

    def log_satellite_pass(self, norad: int, start: float, peak: Optional[float],
                           end: Optional[float], max_elevation: Optional[float]) -> None:
        start_min = int(round(start / 60.0) * 60)
        with self._transaction() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO satellite_passes (norad, start_at, peak_at, end_at, max_elevation) "
                "VALUES (?, ?, ?, ?, ?)",
                (int(norad), start_min, peak, end, max_elevation),
            )

    def get_satellite_passes(self, norad: int, limit: int = 20) -> List[Dict[str, Any]]:
        with self._transaction() as conn:
            rows = conn.execute(
                "SELECT * FROM satellite_passes WHERE norad = ? ORDER BY start_at DESC LIMIT ?",
                (int(norad), limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_satellite_pass_count(self, norad: int) -> int:
        with self._transaction() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM satellite_passes WHERE norad = ?", (int(norad),)
            ).fetchone()[0]

    # -- stats --------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        with self._transaction() as conn:
            total_airframes = conn.execute("SELECT COUNT(*) FROM airframes WHERE detection_count > 0").fetchone()[0]
            total_detections = conn.execute("SELECT COUNT(*) FROM detections").fetchone()[0]
            total_badges = conn.execute("SELECT COUNT(*) FROM badges").fetchone()[0]

            # Type distribution
            type_counts = {}
            rows = conn.execute(
                "SELECT rarity, COUNT(*) FROM airframes WHERE detection_count > 0 GROUP BY rarity"
            ).fetchall()
            for row in rows:
                type_counts[row[0]] = row[1]

            # Top airframe
            top = conn.execute(
                "SELECT hex, dex_number, detection_count, model FROM airframes ORDER BY detection_count DESC LIMIT 1"
            ).fetchone()

            # Sightings = sessions (one continuous appearance each). All the
            # pattern stats below count per sighting, so a daily regular bumps
            # its airport every day, while a trainer doing laps counts once.
            total_visits = conn.execute("SELECT COUNT(*) FROM sightings").fetchone()[0]

            # Busiest day-of-week / hour (local time), by sighting start time.
            dow = conn.execute(
                """SELECT CAST(strftime('%w', started_at, 'unixepoch', 'localtime') AS INTEGER) AS dow,
                          COUNT(*) AS c
                   FROM sightings GROUP BY dow ORDER BY c DESC LIMIT 1"""
            ).fetchone()
            hour = conn.execute(
                """SELECT CAST(strftime('%H', started_at, 'unixepoch', 'localtime') AS INTEGER) AS hr,
                          COUNT(*) AS c
                   FROM sightings GROUP BY hr ORDER BY c DESC LIMIT 1"""
            ).fetchone()

            # Most common departure / destination — per sighting.
            origin = conn.execute(
                """SELECT origin_airport AS code, COUNT(*) AS c FROM sightings
                   WHERE origin_airport IS NOT NULL AND origin_airport != ''
                   GROUP BY origin_airport ORDER BY c DESC LIMIT 1"""
            ).fetchone()
            dest = conn.execute(
                """SELECT dest_airport AS code, COUNT(*) AS c FROM sightings
                   WHERE dest_airport IS NOT NULL AND dest_airport != ''
                   GROUP BY dest_airport ORDER BY c DESC LIMIT 1"""
            ).fetchone()

            # Rarest (least-seen) departure / destination.
            origin_lo = conn.execute(
                """SELECT origin_airport AS code, COUNT(*) AS c FROM sightings
                   WHERE origin_airport IS NOT NULL AND origin_airport != ''
                   GROUP BY origin_airport ORDER BY c ASC, code ASC LIMIT 1"""
            ).fetchone()
            dest_lo = conn.execute(
                """SELECT dest_airport AS code, COUNT(*) AS c FROM sightings
                   WHERE dest_airport IS NOT NULL AND dest_airport != ''
                   GROUP BY dest_airport ORDER BY c ASC, code ASC LIMIT 1"""
            ).fetchone()

            # Activity by hour for TODAY (local), as a 24-slot array.
            hour_arr = [0] * 24
            for r in conn.execute(
                """SELECT CAST(strftime('%H', started_at, 'unixepoch', 'localtime') AS INTEGER) AS hr,
                          COUNT(*) AS c
                   FROM sightings
                   WHERE date(started_at, 'unixepoch', 'localtime') = date('now', 'localtime')
                   GROUP BY hr"""
            ).fetchall():
                if r["hr"] is not None and 0 <= r["hr"] <= 23:
                    hour_arr[r["hr"]] = r["c"]

            return {
                "total_airframes": total_airframes,
                "total_detections": total_detections,  # raw telemetry rows
                "total_visits": total_visits,           # cooldown-based visits
                "total_badges": total_badges,
                "rarity_distribution": type_counts,
                "top_airframe": dict(top) if top else None,
                "busiest_dow": dow["dow"] if dow else None,
                "busiest_dow_count": dow["c"] if dow else 0,
                "busiest_hour": hour["hr"] if hour else None,
                "busiest_hour_count": hour["c"] if hour else 0,
                "top_origin": {"code": origin["code"], "count": origin["c"]} if origin else None,
                "top_dest": {"code": dest["code"], "count": dest["c"]} if dest else None,
                "bottom_origin": {"code": origin_lo["code"], "count": origin_lo["c"]} if origin_lo else None,
                "bottom_dest": {"code": dest_lo["code"], "count": dest_lo["c"]} if dest_lo else None,
                "activity_by_hour_today": hour_arr,
            }

    # =======================================================================
    # Maintenance (nightly) — retention pruning + WAL checkpoint
    # =======================================================================

    def run_maintenance(self, retention_days: int = 30) -> Dict[str, Any]:
        """Prune old raw telemetry and checkpoint the WAL. Airframes, vessels,
        sightings, and aggregates are kept forever — only the high-volume raw
        rows (detections, weather snapshots) are pruned."""
        cutoff = time.time() - retention_days * 86400
        result: Dict[str, Any] = {"retention_days": retention_days}
        with self._transaction() as conn:
            cur = conn.execute("DELETE FROM detections WHERE timestamp < ?", (cutoff,))
            result["detections_pruned"] = cur.rowcount
            cur = conn.execute("DELETE FROM weather_snapshots WHERE timestamp < ?", (cutoff,))
            result["weather_pruned"] = cur.rowcount
            # EtherDex privacy rule: devices unheard for 90 days are forgotten.
            cur = conn.execute("DELETE FROM ether_devices WHERE last_seen < ?",
                               (time.time() - 90 * 86400,))
            result["ether_pruned"] = cur.rowcount
            # Journeys: cap each trail at ~4000 breadcrumbs, and forget trails
            # of craft unfollowed for 60+ days.
            conn.execute(
                """DELETE FROM journey_points WHERE rowid IN (
                     SELECT p.rowid FROM journey_points p
                     JOIN (SELECT follow_id, COUNT(*) AS n FROM journey_points
                           GROUP BY follow_id HAVING n > 4000) big
                       ON big.follow_id = p.follow_id
                     WHERE p.ts < (SELECT ts FROM journey_points q
                                   WHERE q.follow_id = p.follow_id
                                   ORDER BY ts DESC LIMIT 1 OFFSET 3999))""")
            cur = conn.execute(
                """DELETE FROM journey_points WHERE follow_id IN (
                     SELECT id FROM followed_craft
                     WHERE active = 0 AND COALESCE(last_seen, added_at) < ?)""",
                (time.time() - 60 * 86400,))
            result["journeys_pruned"] = cur.rowcount
        try:
            conn = self._conn()
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except sqlite3.Error as e:
            result["checkpoint_error"] = str(e)
        result["db_size_bytes"] = self.get_db_size_bytes()
        logger.info("DB maintenance: pruned %s detections, %s weather rows (db=%.1f MB)",
                    result.get("detections_pruned"), result.get("weather_pruned"),
                    result["db_size_bytes"] / 1e6)
        return result

    def get_db_size_bytes(self) -> int:
        total = 0
        for suffix in ("", "-wal", "-shm"):
            try:
                total += os.path.getsize(str(self.path) + suffix)
            except OSError:
                pass
        return total

    # =======================================================================
    # Hall of Fame — all-time records (air + sea, kept strictly separate)
    # =======================================================================

    def get_records(self) -> Dict[str, Any]:
        """All-time records for the Records view. Every entry carries enough
        identity (hex/mmsi + name) for the frontend to link into the Dex."""
        with self._transaction() as conn:
            def one(sql: str, args: tuple = ()) -> Optional[Dict[str, Any]]:
                row = conn.execute(sql, args).fetchone()
                return dict(row) if row else None

            air: Dict[str, Any] = {}
            air["fastest"] = one(
                """SELECT d.hex, d.ground_speed AS value, d.timestamp, a.registration, a.model, d.callsign
                   FROM detections d JOIN airframes a ON a.hex = d.hex
                   WHERE d.ground_speed IS NOT NULL AND d.ground_speed < 1200
                   ORDER BY d.ground_speed DESC LIMIT 1""")
            air["highest"] = one(
                """SELECT d.hex, d.altitude AS value, d.timestamp, a.registration, a.model, d.callsign
                   FROM detections d JOIN airframes a ON a.hex = d.hex
                   WHERE d.altitude IS NOT NULL AND d.altitude < 60000
                   ORDER BY d.altitude DESC LIMIT 1""")
            air["closest"] = one(
                """SELECT d.hex, d.distance_miles AS value, d.timestamp, a.registration, a.model, d.callsign
                   FROM detections d JOIN airframes a ON a.hex = d.hex
                   WHERE d.distance_miles IS NOT NULL AND d.distance_miles > 0
                   ORDER BY d.distance_miles ASC LIMIT 1""")
            air["most_seen"] = one(
                """SELECT hex, detection_count AS value, registration, model, operator
                   FROM airframes WHERE detection_count > 0
                   ORDER BY detection_count DESC LIMIT 1""")
            air["oldest"] = one(
                """SELECT hex, year_built AS value, registration, model
                   FROM airframes
                   WHERE detection_count > 0
                     AND year_built IS NOT NULL AND year_built != '' AND CAST(year_built AS INTEGER) > 1900
                   ORDER BY CAST(year_built AS INTEGER) ASC LIMIT 1""")
            air["first_catch"] = one(
                """SELECT hex, first_seen AS value, registration, model
                   FROM airframes WHERE first_seen IS NOT NULL AND detection_count > 0
                   ORDER BY first_seen ASC LIMIT 1""")
            air["busiest_day"] = one(
                """SELECT date(started_at, 'unixepoch', 'localtime') AS day, COUNT(*) AS value
                   FROM sightings GROUP BY day ORDER BY value DESC LIMIT 1""")
            row = conn.execute("SELECT COUNT(*) AS c FROM emergencies").fetchone()
            air["emergencies"] = row["c"] if row else 0
            row = conn.execute(
                """SELECT COUNT(*) AS c FROM airframes
                   WHERE is_military = 1 AND detection_count > 0""").fetchone()
            air["military_count"] = row["c"] if row else 0

            sea: Dict[str, Any] = {}
            sea["longest"] = one(
                """SELECT mmsi, length AS value, name, category, flag
                   FROM vessels WHERE length IS NOT NULL AND length > 0
                   ORDER BY length DESC LIMIT 1""")
            sea["most_seen"] = one(
                """SELECT mmsi, detection_count AS value, name, category, flag
                   FROM vessels ORDER BY detection_count DESC LIMIT 1""")
            sea["closest"] = one(
                """SELECT mmsi, min_distance AS value, name, category, flag
                   FROM vessels WHERE min_distance IS NOT NULL AND min_distance > 0
                   ORDER BY min_distance ASC LIMIT 1""")
            sea["first_catch"] = one(
                """SELECT mmsi, first_seen AS value, name, category
                   FROM vessels WHERE first_seen IS NOT NULL
                   ORDER BY first_seen ASC LIMIT 1""")
            sea["busiest_day"] = one(
                """SELECT date(started_at, 'unixepoch', 'localtime') AS day, COUNT(*) AS value
                   FROM vessel_sightings GROUP BY day ORDER BY value DESC LIMIT 1""")
            row = conn.execute(
                "SELECT COUNT(DISTINCT flag) AS c FROM vessels WHERE flag IS NOT NULL AND flag != ''").fetchone()
            sea["flag_count"] = row["c"] if row else 0
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM vessels WHERE category = 'Superyacht'").fetchone()
            sea["superyachts"] = row["c"] if row else 0

            air["longest_visit"] = one(
                """SELECT s.hex, (s.ended_at - s.started_at) AS value, s.callsign,
                          a.registration, a.model
                   FROM sightings s JOIN airframes a ON a.hex = s.hex
                   WHERE s.ended_at IS NOT NULL AND (s.ended_at - s.started_at) BETWEEN 60 AND 43200
                   ORDER BY value DESC LIMIT 1""")

            rail: Dict[str, Any] = {}
            rail["fastest"] = one(
                """SELECT train_num, route, max_speed AS value FROM trains
                   WHERE max_speed > 0 ORDER BY max_speed DESC LIMIT 1""")
            rail["most_seen"] = one(
                """SELECT train_num, route, times_seen AS value FROM trains
                   ORDER BY times_seen DESC LIMIT 1""")
            row = conn.execute("SELECT COUNT(*) AS c FROM trains").fetchone()
            rail["total"] = row["c"] if row else 0

            return {"air": air, "sea": sea, "rail": rail}

    def get_achievement_stats(self) -> Dict[str, Any]:
        """Raw counters that achievements.py turns into unlocked/locked badges."""
        with self._transaction() as conn:
            def scalar(sql: str, args: tuple = ()) -> Any:
                row = conn.execute(sql, args).fetchone()
                return row[0] if row and row[0] is not None else 0

            return {
                "airframes": scalar("SELECT COUNT(*) FROM airframes WHERE detection_count > 0"),
                "vessels": scalar("SELECT COUNT(*) FROM vessels"),
                "air_types": scalar(
                    """SELECT COUNT(DISTINCT primary_type) FROM airframes
                       WHERE primary_type IS NOT NULL AND detection_count > 0"""),
                "heavies": scalar("SELECT COUNT(*) FROM airframes WHERE primary_type = 'Heavy' AND detection_count > 0"),
                "rotors": scalar("SELECT COUNT(*) FROM airframes WHERE primary_type = 'Rotor' AND detection_count > 0"),
                "military": scalar("SELECT COUNT(*) FROM airframes WHERE is_military = 1 AND detection_count > 0"),
                "emergencies": scalar("SELECT COUNT(*) FROM emergencies"),
                "night_catches": scalar(
                    """SELECT COUNT(*) FROM sightings
                       WHERE CAST(strftime('%H', started_at, 'unixepoch', 'localtime') AS INTEGER) < 5
                          OR CAST(strftime('%H', started_at, 'unixepoch', 'localtime') AS INTEGER) >= 23"""),
                "legendaries": scalar(
                    "SELECT COUNT(*) FROM airframes WHERE LOWER(rarity) = 'legendary' AND detection_count > 0"),
                "bonded": scalar(
                    "SELECT COUNT(*) FROM airframes WHERE evolution_tier = 'Bonded' AND detection_count > 0"),
                "sea_flags": scalar(
                    "SELECT COUNT(DISTINCT flag) FROM vessels WHERE flag IS NOT NULL AND flag != ''"),
                "superyachts": scalar(
                    "SELECT COUNT(*) FROM vessels WHERE category = 'Superyacht'"),
                "sailing": scalar(
                    "SELECT COUNT(*) FROM vessels WHERE category = 'Sailing'"),
                "sea_categories": scalar(
                    "SELECT COUNT(DISTINCT category) FROM vessels WHERE category IS NOT NULL"),
                "best_day_air": scalar(
                    """SELECT MAX(c) FROM (SELECT COUNT(*) AS c FROM sightings
                       GROUP BY date(started_at, 'unixepoch', 'localtime'))"""),
                "best_day_sea": scalar(
                    """SELECT MAX(c) FROM (SELECT COUNT(*) AS c FROM vessel_sightings
                       GROUP BY date(started_at, 'unixepoch', 'localtime'))"""),
                "iss_passes": scalar("SELECT COUNT(*) FROM satellite_passes"),
                "trains": scalar("SELECT COUNT(*) FROM trains"),
                "acelas": scalar("SELECT COUNT(*) FROM trains WHERE route LIKE '%Acela%'"),
                "train_passes": scalar("SELECT COALESCE(SUM(times_seen),0) FROM trains"),
                "train_routes": scalar(
                    "SELECT COUNT(DISTINCT route) FROM trains WHERE route IS NOT NULL AND route != ''"),
                # --- deeper air ---
                "epics": scalar(
                    "SELECT COUNT(*) FROM airframes WHERE LOWER(rarity) = 'epic' AND detection_count > 0"),
                "air_models": scalar(
                    """SELECT COUNT(DISTINCT type_code) FROM airframes
                       WHERE type_code IS NOT NULL AND type_code != '' AND detection_count > 0"""),
                "air_operators": scalar(
                    """SELECT COUNT(DISTINCT operator) FROM airframes
                       WHERE operator IS NOT NULL AND operator != '' AND detection_count > 0"""),
                "vintage_air": scalar(
                    """SELECT COUNT(*) FROM airframes
                       WHERE detection_count > 0 AND year_built IS NOT NULL AND year_built != ''
                         AND CAST(year_built AS INTEGER) BETWEEN 1903 AND 1979"""),
                "new_metal": scalar(
                    """SELECT COUNT(*) FROM airframes
                       WHERE detection_count > 0 AND year_built = strftime('%Y','now')"""),
                "foreign_reg": scalar(
                    """SELECT COUNT(*) FROM airframes
                       WHERE detection_count > 0 AND registration IS NOT NULL
                         AND registration != '' AND registration NOT LIKE 'N%'"""),
                "air_sightings": scalar("SELECT COUNT(*) FROM sightings"),
                "active_days": scalar(
                    "SELECT COUNT(DISTINCT date(started_at,'unixepoch','localtime')) FROM sightings"),
                "early_birds": scalar(
                    """SELECT COUNT(*) FROM sightings
                       WHERE CAST(strftime('%H', started_at, 'unixepoch', 'localtime') AS INTEGER) BETWEEN 5 AND 6"""),
                "weekenders": scalar(
                    """SELECT COUNT(*) FROM sightings
                       WHERE strftime('%w', started_at, 'unixepoch', 'localtime') IN ('0','6')"""),
                "regulars": scalar(
                    "SELECT COUNT(*) FROM airframes WHERE detection_count >= 10"),
                # --- deeper sea ---
                "sea_sightings": scalar("SELECT COUNT(*) FROM vessel_sightings"),
                "cargo_ships": scalar("SELECT COUNT(*) FROM vessels WHERE category = 'Cargo'"),
                "tankers": scalar("SELECT COUNT(*) FROM vessels WHERE category = 'Tanker'"),
                "tugs": scalar("SELECT COUNT(*) FROM vessels WHERE category = 'Tug'"),
                "gov_boats": scalar("SELECT COUNT(*) FROM vessels WHERE category = 'Government'"),
                "fishing_boats": scalar("SELECT COUNT(*) FROM vessels WHERE category = 'Fishing'"),
                "big_ships": scalar("SELECT COUNT(*) FROM vessels WHERE length >= 150"),
                "sea_regulars": scalar("SELECT COUNT(*) FROM vessels WHERE detection_count >= 10"),
                # --- atmo ---
                "high_passes": scalar(
                    "SELECT COUNT(*) FROM satellite_passes WHERE max_elevation >= 60"),
                "sat_variety": scalar("SELECT COUNT(DISTINCT norad) FROM satellite_passes"),
                # --- ether ---
                "ether_devices": scalar("SELECT COUNT(*) FROM ether_devices"),
                "ether_kinds": scalar("SELECT COUNT(DISTINCT kind) FROM ether_devices"),
                "ether_residents": scalar("SELECT COUNT(*) FROM ether_devices WHERE resident = 1"),
                "ether_meters": scalar("SELECT COUNT(*) FROM ether_devices WHERE kind = 'meter'"),
                "ether_tpms": scalar("SELECT COUNT(*) FROM ether_devices WHERE kind = 'tpms'"),
                "ether_wx": scalar("SELECT COUNT(*) FROM ether_devices WHERE kind = 'weather'"),
                "ether_mysteries": scalar("SELECT COUNT(*) FROM ether_devices WHERE kind = 'mystery'"),
                "ether_hits": scalar("SELECT COALESCE(SUM(hits),0) FROM ether_devices"),
                # --- storm ---
                "storm_events": scalar(
                    "SELECT COUNT(*) FROM weather_events WHERE kind != 'seed_marker'"),
                "record_days": scalar(
                    "SELECT COUNT(*) FROM weather_events WHERE kind IN ('record_high','record_low')"),
                "snow_events": scalar("SELECT COUNT(*) FROM weather_events WHERE kind = 'snow'"),
                "named_storms": scalar(
                    "SELECT COUNT(*) FROM weather_events WHERE kind = 'named_storm'"),
                "wx_alerts": scalar("SELECT COUNT(*) FROM weather_events WHERE kind = 'alert'"),
                # --- family + journeys ---
                "spotter_credits_total": scalar("SELECT COUNT(*) FROM spotter_credits"),
                "spotter_people": scalar("SELECT COUNT(DISTINCT name) FROM spotter_credits"),
                "follows_ever": scalar("SELECT COUNT(*) FROM followed_craft"),
                "journey_crumbs": scalar("SELECT COUNT(*) FROM journey_points"),
            }

    def get_challenge_stats(self) -> Dict[str, Any]:
        """Time-windowed counters for daily/weekly challenges. 'Today' is the
        local calendar day; 'week' starts on the most recent Sunday."""
        TODAY = "date({c},'unixepoch','localtime') = date('now','localtime')"
        WEEK = "date({c},'unixepoch','localtime') >= date('now','localtime','-6 days','weekday 0')"
        with self._transaction() as conn:
            def scalar(sql: str) -> int:
                row = conn.execute(sql).fetchone()
                return int(row[0]) if row and row[0] is not None else 0

            t = lambda col: TODAY.format(c=col)
            w = lambda col: WEEK.format(c=col)
            return {
                "air_today": scalar(f"SELECT COUNT(*) FROM sightings WHERE {t('started_at')}"),
                "air_week": scalar(f"SELECT COUNT(*) FROM sightings WHERE {w('started_at')}"),
                "new_air_today": scalar(
                    f"""SELECT COUNT(*) FROM airframes
                        WHERE detection_count > 0 AND {t('first_seen')}"""),
                "new_air_week": scalar(
                    f"""SELECT COUNT(*) FROM airframes
                        WHERE detection_count > 0 AND {w('first_seen')}"""),
                "heavy_today": scalar(
                    f"""SELECT COUNT(DISTINCT s.hex) FROM sightings s
                        JOIN airframes a ON a.hex = s.hex
                        WHERE a.primary_type = 'Heavy' AND {t('s.started_at')}"""),
                "sea_today": scalar(f"SELECT COUNT(*) FROM vessel_sightings WHERE {t('started_at')}"),
                "sea_week": scalar(f"SELECT COUNT(*) FROM vessel_sightings WHERE {w('started_at')}"),
                "new_sea_today": scalar(f"SELECT COUNT(*) FROM vessels WHERE {t('first_seen')}"),
                "new_ether_today": scalar(f"SELECT COUNT(*) FROM ether_devices WHERE {t('first_seen')}"),
                "new_ether_week": scalar(f"SELECT COUNT(*) FROM ether_devices WHERE {w('first_seen')}"),
                "games_today": scalar(f"SELECT COUNT(*) FROM kid_scores WHERE {t('played_at')}"),
                "games_week": scalar(f"SELECT COUNT(*) FROM kid_scores WHERE {w('played_at')}"),
                "spotter_today": scalar(f"SELECT COUNT(*) FROM spotter_credits WHERE {t('spotted_at')}"),
                "wx_locked_today": scalar(
                    """SELECT COUNT(*) FROM wx_guesses
                       WHERE target_date = date('now','localtime','+1 day')"""),
                "wx_week": scalar(
                    """SELECT COUNT(DISTINCT target_date || name) FROM wx_guesses
                       WHERE target_date >= date('now','localtime','-6 days','weekday 0')"""),
                "days_week": scalar(
                    f"""SELECT COUNT(DISTINCT date(started_at,'unixepoch','localtime'))
                        FROM sightings WHERE {w('started_at')}"""),
            }

    # =======================================================================
    # Weekly almanac — 7-day aggregate report
    # =======================================================================

    def get_almanac(self, days: int = 7) -> Dict[str, Any]:
        cutoff = time.time() - days * 86400
        with self._transaction() as conn:
            daily_air = [dict(r) for r in conn.execute(
                """SELECT date(started_at, 'unixepoch', 'localtime') AS day,
                          COUNT(*) AS sightings, COUNT(DISTINCT hex) AS unique_craft
                   FROM sightings WHERE started_at >= ?
                   GROUP BY day ORDER BY day""", (cutoff,)).fetchall()]
            daily_sea = [dict(r) for r in conn.execute(
                """SELECT date(started_at, 'unixepoch', 'localtime') AS day,
                          COUNT(*) AS sightings, COUNT(DISTINCT mmsi) AS unique_craft
                   FROM vessel_sightings WHERE started_at >= ?
                   GROUP BY day ORDER BY day""", (cutoff,)).fetchall()]
            new_air = [dict(r) for r in conn.execute(
                """SELECT hex, registration, model, operator, rarity, first_seen
                   FROM airframes WHERE first_seen >= ?
                   ORDER BY first_seen DESC LIMIT 40""", (cutoff,)).fetchall()]
            new_sea = [dict(r) for r in conn.execute(
                """SELECT mmsi, name, category, flag, rarity, first_seen
                   FROM vessels WHERE first_seen >= ?
                   ORDER BY first_seen DESC LIMIT 40""", (cutoff,)).fetchall()]
            top_operators = [dict(r) for r in conn.execute(
                """SELECT a.operator AS name, COUNT(*) AS c
                   FROM sightings s JOIN airframes a ON a.hex = s.hex
                   WHERE s.started_at >= ? AND a.operator IS NOT NULL AND a.operator != ''
                   GROUP BY a.operator ORDER BY c DESC LIMIT 5""", (cutoff,)).fetchall()]
            top_flags = [dict(r) for r in conn.execute(
                """SELECT v.flag AS name, COUNT(*) AS c
                   FROM vessel_sightings vs JOIN vessels v ON v.mmsi = vs.mmsi
                   WHERE vs.started_at >= ? AND v.flag IS NOT NULL AND v.flag != ''
                   GROUP BY v.flag ORDER BY c DESC LIMIT 5""", (cutoff,)).fetchall()]
            week_fastest = conn.execute(
                """SELECT d.hex, d.ground_speed AS value, a.registration, a.model, d.callsign
                   FROM detections d JOIN airframes a ON a.hex = d.hex
                   WHERE d.timestamp >= ? AND d.ground_speed IS NOT NULL AND d.ground_speed < 1200
                   ORDER BY d.ground_speed DESC LIMIT 1""", (cutoff,)).fetchone()
            return {
                "days": days,
                "daily_air": daily_air,
                "daily_sea": daily_sea,
                "new_air": new_air,
                "new_sea": new_sea,
                "top_operators": top_operators,
                "top_flags": top_flags,
                "week_fastest": dict(week_fastest) if week_fastest else None,
            }

    # =======================================================================
    # Achievement unlock dates
    # =======================================================================

    def record_achievement_unlocks(self, ids: List[str]) -> Dict[str, float]:
        """Remember first-unlock time for these achievement ids; returns the
        full id -> earned_at map."""
        with self._transaction() as conn:
            for aid in ids:
                conn.execute(
                    "INSERT OR IGNORE INTO achievement_unlocks (id) VALUES (?)", (aid,))
            return {r["id"]: r["earned_at"] for r in
                    conn.execute("SELECT id, earned_at FROM achievement_unlocks").fetchall()}

    # =======================================================================
    # LandDex — the Traindex (Amtrak trains seen passing)
    # =======================================================================

    def log_train(self, train_num: str, route: Optional[str],
                  speed: Optional[float], rarity: str = "Common") -> None:
        """Upsert a passing train. A repeat within 30 min is the same pass
        (trains take ~10 min to cross the radius), so times_seen only bumps
        after a real gap."""
        now = time.time()
        with self._transaction() as conn:
            row = conn.execute("SELECT last_seen, times_seen, max_speed FROM trains WHERE train_num = ?",
                               (train_num,)).fetchone()
            if row is None:
                conn.execute(
                    """INSERT INTO trains (train_num, route, rarity, first_seen,
                       last_seen, times_seen, max_speed) VALUES (?,?,?,?,?,1,?)""",
                    (train_num, route, rarity, now, now, speed or 0))
            else:
                new_pass = (now - (row["last_seen"] or 0)) > 1800
                conn.execute(
                    """UPDATE trains SET route = COALESCE(?, route), rarity = ?,
                       last_seen = ?, times_seen = times_seen + ?,
                       max_speed = MAX(COALESCE(max_speed, 0), ?)
                       WHERE train_num = ?""",
                    (route, rarity, now, 1 if new_pass else 0, speed or 0, train_num))

    def get_train_count(self) -> int:
        with self._transaction() as conn:
            row = conn.execute("SELECT COUNT(*) AS c FROM trains").fetchone()
            return row["c"] if row else 0

    def list_trains(self, limit: int = 200) -> List[Dict[str, Any]]:
        with self._transaction() as conn:
            return [dict(r) for r in conn.execute(
                """SELECT * FROM trains ORDER BY times_seen DESC, last_seen DESC
                   LIMIT ?""", (limit,)).fetchall()]

    # =======================================================================
    # StormDex — weather event catches
    # =======================================================================

    def log_weather_event(self, event_date: str, kind: str, title: str,
                          detail: str = "", stats_json: Optional[str] = None,
                          severity: str = "") -> None:
        with self._transaction() as conn:
            conn.execute(
                """INSERT INTO weather_events (event_date, kind, title, detail,
                   stats_json, severity) VALUES (?,?,?,?,?,?)
                   ON CONFLICT(event_date, kind, title) DO UPDATE SET
                   detail = excluded.detail, stats_json = excluded.stats_json""",
                (event_date, kind, title, detail, stats_json, severity))

    def list_weather_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._transaction() as conn:
            return [dict(r) for r in conn.execute(
                """SELECT * FROM weather_events
                   ORDER BY event_date DESC, logged_at DESC LIMIT ?""", (limit,)).fetchall()]

    def weather_on_this_day(self, month_day: str) -> List[Dict[str, Any]]:
        """Events from PAST years matching MM-DD — 'on this day in 2026…'."""
        with self._transaction() as conn:
            return [dict(r) for r in conn.execute(
                """SELECT * FROM weather_events
                   WHERE substr(event_date, 6) = ?
                     AND event_date < date('now', 'localtime')
                   ORDER BY event_date DESC LIMIT 6""", (month_day,)).fetchall()]

    # =======================================================================
    # EtherDex — RF/Bluetooth device catches
    # =======================================================================

    def log_ether(self, key: str, kind: str, name: str, rarity: str,
                  meta_json: Optional[str]) -> None:
        """Upsert a heard device; a 15-min gap makes the next hearing a new
        'sighting' (like the trains)."""
        now = time.time()
        with self._transaction() as conn:
            row = conn.execute("SELECT last_seen FROM ether_devices WHERE device_key = ?",
                               (key,)).fetchone()
            if row is None:
                conn.execute(
                    """INSERT INTO ether_devices (device_key, kind, name, rarity,
                       first_seen, last_seen, times_seen, hits, meta_json)
                       VALUES (?,?,?,?,?,?,1,1,?)""",
                    (key, kind, name, rarity, now, now, meta_json))
            else:
                new_pass = (now - (row["last_seen"] or 0)) > 900
                conn.execute(
                    """UPDATE ether_devices SET name = COALESCE(?, name), kind = ?,
                       rarity = ?, last_seen = ?, times_seen = times_seen + ?,
                       hits = hits + 1, meta_json = COALESCE(?, meta_json)
                       WHERE device_key = ?""",
                    (name, kind, rarity, now, 1 if new_pass else 0, meta_json, key))
                # Resident promotion: constantly heard for days = it LIVES here
                # (your Shield, the soundbar, the neighbor's weather station).
                conn.execute(
                    """UPDATE ether_devices SET resident = 1
                       WHERE device_key = ? AND resident = 0
                         AND hits > 150 AND (? - first_seen) > 172800""",
                    (key, now))

    def log_spotter(self, name: str, kind: str, ident: str) -> None:
        with self._transaction() as conn:
            conn.execute("INSERT INTO spotter_credits (name, kind, ident) VALUES (?,?,?)",
                         (name[:24], kind[:8], ident[:32]))

    def get_spotter_board(self) -> List[Dict[str, Any]]:
        with self._transaction() as conn:
            return [dict(r) for r in conn.execute(
                """SELECT name, COUNT(*) AS catches, MAX(spotted_at) AS latest
                   FROM spotter_credits GROUP BY name ORDER BY catches DESC""").fetchall()]

    # -- trainer cards + games ------------------------------------------------
    def set_avatar(self, name: str, avatar: str) -> None:
        with self._transaction() as conn:
            conn.execute("""INSERT INTO profiles (name, avatar) VALUES (?, ?)
                            ON CONFLICT(name) DO UPDATE SET avatar = excluded.avatar""",
                         (name, avatar))

    def log_game_score(self, name: str, game: str, score: float) -> bool:
        """Record a game score; only each kid's TOP 3 per game are kept.
        Returns True if this is a new personal best."""
        with self._transaction() as conn:
            prev = conn.execute(
                "SELECT MAX(score) FROM kid_scores WHERE name = ? AND game = ?",
                (name, game)).fetchone()[0]
            conn.execute(
                "INSERT INTO kid_scores (name, game, score, played_at) VALUES (?,?,?,?)",
                (name, game, score, time.time()))
            conn.execute(
                """DELETE FROM kid_scores WHERE name = ? AND game = ? AND id NOT IN (
                     SELECT id FROM kid_scores WHERE name = ? AND game = ?
                     ORDER BY score DESC, played_at ASC LIMIT 3)""",
                (name, game, name, game))
            return prev is None or score > prev

    def get_profiles(self, names: List[str]) -> List[Dict[str, Any]]:
        """Trainer-card bundle for each family member."""
        with self._transaction() as conn:
            avatars = {r["name"]: r["avatar"] for r in
                       conn.execute("SELECT name, avatar FROM profiles").fetchall()}
            credits = {r["name"]: r["c"] for r in conn.execute(
                "SELECT name, COUNT(*) AS c FROM spotter_credits GROUP BY name").fetchall()}
            wins = {r["name"]: r["c"] for r in conn.execute(
                "SELECT name, COUNT(*) AS c FROM wx_guesses WHERE won = 1 GROUP BY name").fetchall()}
            best: Dict[str, Dict[str, float]] = {}
            for r in conn.execute(
                    "SELECT name, game, MAX(score) AS s FROM kid_scores GROUP BY name, game").fetchall():
                best.setdefault(r["name"], {})[r["game"]] = r["s"]
            return [{"name": n, "avatar": avatars.get(n) or "",
                     "credits": credits.get(n, 0), "wx_wins": wins.get(n, 0),
                     "best": best.get(n, {})} for n in names]

    def wx_guess(self, target_date: str, name: str, guess: float) -> None:
        with self._transaction() as conn:
            conn.execute(
                """INSERT INTO wx_guesses (target_date, name, guess) VALUES (?,?,?)
                   ON CONFLICT(target_date, name) DO UPDATE SET guess = excluded.guess""",
                (target_date, name, guess))

    def wx_guesses_for(self, target_date: str) -> List[Dict[str, Any]]:
        with self._transaction() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM wx_guesses WHERE target_date = ?", (target_date,)).fetchall()]

    def wx_unresolved_dates(self, before: str) -> List[str]:
        with self._transaction() as conn:
            return [r[0] for r in conn.execute(
                """SELECT DISTINCT target_date FROM wx_guesses
                   WHERE resolved = 0 AND target_date < ?""", (before,)).fetchall()]

    def wx_last_result(self) -> Optional[Dict[str, Any]]:
        """The most recently settled guessing day, for the scoreboard."""
        with self._transaction() as conn:
            row = conn.execute(
                """SELECT target_date, actual FROM wx_guesses WHERE resolved = 1
                   ORDER BY target_date DESC LIMIT 1""").fetchone()
            if not row:
                return None
            gs = [dict(r) for r in conn.execute(
                "SELECT name, guess, won FROM wx_guesses WHERE target_date = ?",
                (row["target_date"],)).fetchall()]
            return {"date": row["target_date"], "actual": row["actual"], "guesses": gs}

    def get_plane_question(self) -> Optional[Dict[str, Any]]:
        """Who's That Plane: a random photographed catch + 3 decoy models."""
        with self._transaction() as conn:
            row = conn.execute(
                """SELECT hex, model, registration, operator FROM airframes
                   WHERE photo_url IS NOT NULL AND photo_url != ''
                     AND model IS NOT NULL AND model != '' AND detection_count > 0
                   ORDER BY RANDOM() LIMIT 1""").fetchone()
            if not row:
                return None
            decoys = [r[0] for r in conn.execute(
                """SELECT DISTINCT model FROM airframes
                   WHERE model IS NOT NULL AND model != '' AND model != ?
                   ORDER BY RANDOM() LIMIT 3""", (row["model"],)).fetchall()]
            return {"hex": row["hex"], "answer": row["model"],
                    "operator": row["operator"], "registration": row["registration"],
                    "decoys": decoys}

    def wx_resolve(self, target_date: str, actual: float) -> List[str]:
        """Mark a day resolved; the closest guess(es) win. Returns winners."""
        with self._transaction() as conn:
            rows = [dict(r) for r in conn.execute(
                "SELECT name, guess FROM wx_guesses WHERE target_date = ? AND resolved = 0",
                (target_date,)).fetchall()]
            if not rows:
                return []
            gap = min(abs(r["guess"] - actual) for r in rows)
            winners = [r["name"] for r in rows if abs(r["guess"] - actual) == gap]
            conn.execute("UPDATE wx_guesses SET resolved = 1, actual = ? WHERE target_date = ?",
                         (actual, target_date))
            for w in winners:
                conn.execute(
                    "UPDATE wx_guesses SET won = 1 WHERE target_date = ? AND name = ?",
                    (target_date, w))
            return winners

    # -- journeys (followed craft) --------------------------------------------
    FOLLOW_CAP = 10

    def follow_craft(self, kind: str, craft_id: str, name: Optional[str] = None) -> Dict[str, Any]:
        """Tag a craft for tracking. Re-following something reactivates it and
        keeps its old trail. Capped — every follow costs API polls."""
        with self._transaction() as conn:
            row = conn.execute(
                "SELECT id, active FROM followed_craft WHERE kind = ? AND craft_id = ?",
                (kind, craft_id)).fetchone()
            if row is None or not row["active"]:
                n = conn.execute(
                    "SELECT COUNT(*) FROM followed_craft WHERE active = 1").fetchone()[0]
                if n >= self.FOLLOW_CAP:
                    return {"error": f"Already following {self.FOLLOW_CAP} — unfollow something first"}
            if row is None:
                conn.execute(
                    """INSERT INTO followed_craft (kind, craft_id, name, added_at, active)
                       VALUES (?,?,?,?,1)""", (kind, craft_id, name, time.time()))
            else:
                conn.execute(
                    "UPDATE followed_craft SET active = 1, name = COALESCE(?, name) WHERE id = ?",
                    (name, row["id"]))
            return {"ok": True}

    def unfollow_craft(self, kind: str, craft_id: str) -> None:
        """Deactivate (trail kept; nightly maintenance prunes long-dead ones)."""
        with self._transaction() as conn:
            conn.execute("UPDATE followed_craft SET active = 0 WHERE kind = ? AND craft_id = ?",
                         (kind, craft_id))

    def list_followed(self, active_only: bool = True) -> List[Dict[str, Any]]:
        with self._transaction() as conn:
            q = "SELECT * FROM followed_craft"
            if active_only:
                q += " WHERE active = 1"
            return [dict(r) for r in conn.execute(q + " ORDER BY added_at DESC").fetchall()]

    def get_follow(self, kind: str, craft_id: str) -> Optional[Dict[str, Any]]:
        with self._transaction() as conn:
            r = conn.execute(
                "SELECT * FROM followed_craft WHERE kind = ? AND craft_id = ? AND active = 1",
                (kind, craft_id)).fetchone()
            return dict(r) if r else None

    def update_follow_position(self, follow_id: int, lat: float, lon: float,
                               alt: Optional[float], speed: Optional[float],
                               source: str, name: Optional[str] = None,
                               callsign: Optional[str] = None) -> None:
        now = time.time()
        with self._transaction() as conn:
            conn.execute(
                """UPDATE followed_craft SET last_lat = ?, last_lon = ?, last_alt = ?,
                   last_speed = ?, last_seen = ?, last_source = ?,
                   name = COALESCE(name, ?), callsign = COALESCE(?, callsign)
                   WHERE id = ?""",
                (lat, lon, alt, speed, now, source, name, callsign or None, follow_id))
            # Trail thinning: a new breadcrumb only if we moved or time passed.
            last = conn.execute(
                """SELECT ts, lat, lon FROM journey_points WHERE follow_id = ?
                   ORDER BY ts DESC LIMIT 1""", (follow_id,)).fetchone()
            if (last is None or now - last["ts"] > 120
                    or abs(lat - (last["lat"] or 0)) + abs(lon - (last["lon"] or 0)) > 0.02):
                conn.execute(
                    "INSERT INTO journey_points (follow_id, ts, lat, lon, alt, speed) VALUES (?,?,?,?,?,?)",
                    (follow_id, now, lat, lon, alt, speed))

    def get_journey(self, follow_id: int, limit: int = 1500) -> List[Dict[str, Any]]:
        with self._transaction() as conn:
            rows = conn.execute(
                """SELECT ts, lat, lon, alt, speed FROM journey_points
                   WHERE follow_id = ? ORDER BY ts DESC LIMIT ?""",
                (follow_id, limit)).fetchall()
            return [dict(r) for r in reversed(rows)]

    def list_ether(self, limit: int = 300) -> List[Dict[str, Any]]:
        with self._transaction() as conn:
            return [dict(r) for r in conn.execute(
                """SELECT * FROM ether_devices
                   ORDER BY times_seen DESC, last_seen DESC LIMIT ?""", (limit,)).fetchall()]

    def get_ether_count(self) -> int:
        with self._transaction() as conn:
            row = conn.execute("SELECT COUNT(*) AS c FROM ether_devices").fetchone()
            return row["c"] if row else 0

    # =======================================================================
    # Airport ops board — movements WE observed to/from an airport (free!)
    # =======================================================================

    def get_airport_movements(self, icao: str = "KBDR", hours: float = 18.0) -> Dict[str, Any]:
        """Recent sightings whose route touches the airport: dest=ICAO are
        arrivals, origin=ICAO are departures. This is real observed traffic, so
        the KBDR board works even when the schedule API has nothing (GA field)."""
        icao = icao.upper().strip()
        cutoff = time.time() - hours * 3600
        with self._transaction() as conn:
            rows = conn.execute(
                """SELECT s.hex, s.started_at, s.ended_at, s.callsign,
                          s.origin_airport, s.dest_airport,
                          a.registration, a.model, a.operator
                   FROM sightings s JOIN airframes a ON a.hex = s.hex
                   WHERE s.started_at >= ?
                     AND (s.origin_airport = ? OR s.dest_airport = ?)
                   ORDER BY s.started_at DESC LIMIT 60""",
                (cutoff, icao, icao)).fetchall()
        deps, arrs = [], []
        for r in rows:
            item = {
                "hex": r["hex"],
                "time": r["started_at"],
                "ident": r["callsign"] or r["registration"] or r["hex"],
                "reg": r["registration"],
                "model": r["model"],
                "airline": r["operator"],
                "status": "Seen",
                "source": "observed",
            }
            if r["origin_airport"] == icao:
                deps.append({**item, "other_airport": r["dest_airport"]})
            else:
                arrs.append({**item, "other_airport": r["origin_airport"]})
        return {"departures": deps, "arrivals": arrs}

    # =======================================================================
    # Day replay — today's aircraft tracks from raw detections
    # =======================================================================

    def get_replay(self, day: Optional[str] = None, max_points: int = 6000) -> Dict[str, Any]:
        """Aircraft position history for a local date (default today), grouped
        per airframe and time-ordered, ready for time-lapse playback."""
        day = day or datetime.now().strftime("%Y-%m-%d")
        with self._transaction() as conn:
            rows = conn.execute(
                """SELECT d.hex, d.timestamp, d.lat, d.lon, d.altitude, d.callsign,
                          a.registration, a.model, a.primary_type
                   FROM detections d JOIN airframes a ON a.hex = d.hex
                   WHERE date(d.timestamp, 'unixepoch', 'localtime') = ?
                     AND d.lat IS NOT NULL AND d.lon IS NOT NULL
                   ORDER BY d.timestamp ASC LIMIT ?""", (day, max_points)).fetchall()
        tracks: Dict[str, Dict[str, Any]] = {}
        t_min, t_max = None, None
        for r in rows:
            t = tracks.setdefault(r["hex"], {
                "hex": r["hex"], "callsign": r["callsign"],
                "registration": r["registration"], "model": r["model"],
                "primary_type": r["primary_type"], "points": [],
            })
            t["points"].append([round(r["timestamp"]), r["lat"], r["lon"]])
            if not t["callsign"] and r["callsign"]:
                t["callsign"] = r["callsign"]
            ts = r["timestamp"]
            t_min = ts if t_min is None or ts < t_min else t_min
            t_max = ts if t_max is None or ts > t_max else t_max
        return {"day": day, "start": t_min, "end": t_max,
                "tracks": [t for t in tracks.values() if len(t["points"]) >= 2]}
