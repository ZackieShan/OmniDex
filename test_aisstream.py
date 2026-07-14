#!/usr/bin/env python3
"""Standalone AISStream.io tester — proves the cloud feed works, independent of
SkyDex. Run it on the Pi:   python3 test_aisstream.py

If you see vessel lines: the key + bounding box are good, and SeaDex will work
once python3-websocket is installed and skydex is restarted.
If you see 'AISStream server error': the API key was rejected.
If it just sits there: no vessels in your box right now — try --wide.
"""

import json
import math
import os
import sys
import time

try:
    import websocket  # pip install websocket-client  /  sudo apt install python3-websocket
except ImportError:
    print("ERROR: the 'websocket' module is missing.")
    print("  On the Pi (system Python):  sudo apt install -y python3-websocket")
    sys.exit(1)

API_KEY = os.environ.get("SKYDEX_AISSTREAM_API_KEY", "")
if not API_KEY:
    print("ERROR: set SKYDEX_AISSTREAM_API_KEY (or put it in .env and export it).")
    sys.exit(1)
HOME_LAT, HOME_LON = 41.1635, -73.1262    # default: KBDR airfield — set your own
RADIUS_MILES = 10.0

# --wide uses a big box (Long Island Sound + NY harbor) to guarantee traffic and
# prove the API key itself works, even if your local 10-mile box is quiet.
wide = "--wide" in sys.argv
if wide:
    box = [[40.4, -74.3], [41.5, -72.3]]
else:
    lat_d = RADIUS_MILES / 69.0
    lon_d = RADIUS_MILES / (69.0 * math.cos(math.radians(HOME_LAT)))
    box = [[HOME_LAT - lat_d, HOME_LON - lon_d], [HOME_LAT + lat_d, HOME_LON + lon_d]]

sub = {
    "APIKey": API_KEY,
    "BoundingBoxes": [box],
    "FilterMessageTypes": ["PositionReport", "ShipStaticData"],
}

print(f"Connecting to AISStream ({'WIDE test box' if wide else f'{RADIUS_MILES:.0f}-mile box around home'})...")
ws = websocket.create_connection("wss://stream.aisstream.io/v0/stream", timeout=30)
ws.send(json.dumps(sub))
print("Connected. Listening 60s (Ctrl+C to stop)...\n")

seen = set()
start = time.time()
try:
    while time.time() - start < 60:
        raw = ws.recv()
        if not raw:
            continue
        msg = json.loads(raw)
        mt = msg.get("MessageType")
        if not mt:
            err = msg.get("error") or msg.get("Error") or msg.get("message")
            print(f"AISStream server error: {err or msg}")
            continue
        meta = msg.get("MetaData") or {}
        mmsi = meta.get("MMSI")
        name = (meta.get("ShipName") or "").strip()
        lat = meta.get("latitude")
        lon = meta.get("longitude")
        if mmsi not in seen:
            seen.add(mmsi)
            print(f"  [{len(seen):3d}] {mt:16s} MMSI={mmsi}  {name or '(no name yet)'}  @ {lat},{lon}")
except KeyboardInterrupt:
    pass
finally:
    ws.close()

print(f"\nDone. {len(seen)} distinct vessels in the box during the test.")
if not seen and not wide:
    print("None in your 10-mile box right now. Re-run with:  python3 test_aisstream.py --wide")
    print("If --wide shows vessels, the key works — your local area is just quiet.")
