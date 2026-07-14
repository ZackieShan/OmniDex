#!/usr/bin/env python3
"""SkyDex Diagnostic — run this on your Pi when no aircraft are detected.

Tests every layer of the detection pipeline:
  1. RTL-SDR dongle (USB device present?)
  2. rtl_test (can we talk to the dongle?)
  3. dump1090/readsb running (HTTP response?)
  4. OpenSky API (auth working? aircraft returned?)
  5. SkyDex health endpoint
  6. NWS weather endpoint
  7. NOAA tide endpoint

Usage:
    cd ~/skydex
    python3 diagnose.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.request

# ---------------------------------------------------------------------------
# Colour output
# ---------------------------------------------------------------------------
G = "\033[92m"
R = "\033[91m"
Y = "\033[93m"
B = "\033[94m"
X = "\033[0m"

def ok(msg):   print(f"  {G}OK{X}  {msg}")
def fail(msg): print(f"  {R}FAIL{X} {msg}")
def warn(msg): print(f"  {Y}WARN{X} {msg}")
def info(msg): print(f"  {B}INFO{X} {msg}")

# ---------------------------------------------------------------------------
# 1. RTL-SDR Dongle
# ---------------------------------------------------------------------------
def check_rtlsdr():
    print("\n" + "=" * 50)
    print("1. RTL-SDR Dongle (NESDR Mini 2+)")
    print("=" * 50)

    # Check USB device
    try:
        out = subprocess.run(["lsusb"], capture_output=True, text=True, timeout=5)
        if "RTL" in out.stdout or "Realtek" in out.stdout or "0bda" in out.stdout:
            ok("RTL-SDR dongle found via lsusb")
            for line in out.stdout.splitlines():
                if "RTL" in line or "Realtek" in line or "0bda" in line:
                    info(f"  {line.strip()}")
        else:
            fail("No RTL-SDR dongle found in lsusb")
            info("Looking for 'RTL', 'Realtek', or '0bda' in lsusb output...")
            info("Output snippet: " + out.stdout[:300])
    except FileNotFoundError:
        fail("lsusb not found (install usbutils: sudo apt-get install usbutils)")
    except Exception as e:
        fail(f"lsusb failed: {e}")

    # rtl_test
    try:
        out = subprocess.run(
            ["rtl_test", "-t"],
            capture_output=True, text=True, timeout=10,
        )
        if out.returncode == 0 or "Found" in out.stderr:
            ok("rtl_test can communicate with dongle")
        else:
            warn("rtl_test returned non-zero — dongle may be in use by another process")
        if "Found" in out.stderr:
            for line in out.stderr.splitlines():
                if "Found" in line:
                    info(f"  {line.strip()}")
        if "No supported" in out.stderr:
            fail("No RTL-SDR devices found by rtl_test")
    except FileNotFoundError:
        fail("rtl_test not found (install rtl-sdr: sudo apt-get install rtl-sdr)")
    except subprocess.TimeoutExpired:
        fail("rtl_test timed out (dongle may be in use by dump1090/readsb)")
    except Exception as e:
        fail(f"rtl_test failed: {e}")

# ---------------------------------------------------------------------------
# 2. dump1090 / readsb
# ---------------------------------------------------------------------------
def check_dump1090():
    print("\n" + "=" * 50)
    print("2. dump1090 / readsb (local ADS-B decoder)")
    print("=" * 50)

    urls = [
        ("readsb", "http://localhost:8080/data/aircraft.json"),
        ("dump1090-fa", "http://localhost:8080/data/aircraft.json"),
        ("dump1090", "http://localhost:8080/data.json"),
    ]

    for name, url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "SkyDex-diagnose"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.load(resp)
            aircraft = data.get("aircraft", [])
            ok(f"{name} responding at {url} — {len(aircraft)} aircraft in JSON")
            if aircraft:
                info(f"  Sample: hex={aircraft[0].get('hex')}, "
                     f"alt={aircraft[0].get('alt_baro')}, "
                     f"lat={aircraft[0].get('lat')}, lon={aircraft[0].get('lon')}")
            return True
        except urllib.error.URLError as e:
            fail(f"{name} not responding at {url}: {e}")
        except Exception as e:
            fail(f"{name} error at {url}: {e}")

    warn("No local ADS-B decoder detected — SkyDex will use OpenSky fallback")
    return False

# ---------------------------------------------------------------------------
# 3. OpenSky API
# ---------------------------------------------------------------------------
def check_opensky():
    print("\n" + "=" * 50)
    print("3. OpenSky Network API (fallback data source)")
    print("=" * 50)

    # Your OAuth2 client credentials (read from config so there is one place
    # to change them). OpenSky removed Basic Auth in 2025 — we must exchange
    # these for a short-lived Bearer token.
    try:
        from config import SkyDexConfig
        cfg = SkyDexConfig()
        client_id = cfg.receiver.opensky_client_id
        client_secret = cfg.receiver.opensky_client_secret
        lat, lon = cfg.location.lat, cfg.location.lon
    except Exception:
        import os
        client_id = os.environ.get("SKYDEX_OPENSKY_CLIENT_ID", "")
        client_secret = os.environ.get("SKYDEX_OPENSKY_CLIENT_SECRET", "")
        lat, lon = 41.1635, -73.1262

    bbox = f"?lamin={lat-0.5}&lomin={lon-0.7}&lamax={lat+0.5}&lomax={lon+0.7}"
    url = "https://opensky-network.org/api/states/all" + bbox

    # Step 1: obtain an OAuth2 Bearer token
    token = None
    try:
        import urllib.parse
        token_url = ("https://auth.opensky-network.org/auth/realms/opensky-network/"
                     "protocol/openid-connect/token")
        body = urllib.parse.urlencode({
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        }).encode()
        treq = urllib.request.Request(token_url, data=body, headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "SkyDex-diagnose",
        })
        with urllib.request.urlopen(treq, timeout=15) as resp:
            token = json.load(resp).get("access_token")
        if token:
            ok("OpenSky OAuth2 token acquired")
    except urllib.error.HTTPError as e:
        fail(f"OpenSky token request rejected (HTTP {e.code}) — check client_id/client_secret")
    except Exception as e:
        fail(f"OpenSky token request failed: {e}")

    # Step 2: query states with the Bearer token
    if token:
        try:
            req = urllib.request.Request(url, headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": "SkyDex-diagnose",
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.load(resp)
            states = data.get("states") or []
            ok(f"OpenSky AUTHENTICATED — {len(states)} aircraft in bbox")
            if states:
                s = states[0]
                info(f"  Sample: icao24={s[0]}, callsign={s[1]}, "
                     f"lat={s[6]}, lon={s[5]}, alt={s[13] or s[7]}")
            return len(states)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                fail("OpenSky rate limited (HTTP 429) — too many requests")
            else:
                fail(f"OpenSky HTTP error {e.code}: {e.reason}")
        except Exception as e:
            fail(f"OpenSky authenticated request failed: {e}")

    # Try anonymous fallback
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SkyDex-diagnose"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.load(resp)
        states = data.get("states") or []
        warn(f"OpenSky ANONYMOUS — {len(states)} aircraft (limited quota)")
        return len(states)
    except Exception as e:
        fail(f"OpenSky anonymous also failed: {e}")

    return 0

# ---------------------------------------------------------------------------
# 4. SkyDex Health
# ---------------------------------------------------------------------------
def check_skydex():
    print("\n" + "=" * 50)
    print("4. SkyDex Server Health")
    print("=" * 50)

    try:
        req = urllib.request.Request("http://localhost:8000/api/health")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.load(resp)

        ok("SkyDex server responding")
        info(f"  Status: {data.get('status')}")
        info(f"  Database: {data.get('database')}")

        rx = data.get("receiver")
        if rx:
            if "error" in rx:
                fail(f"  Receiver error: {rx['error']}")
            else:
                ok(f"  Receiver running: {rx.get('running')}")
                ok(f"  Contact count: {rx.get('contact_count')}")
                ok(f"  In 5mi: {rx.get('contacts_in_range_5mi')}")
                ok(f"  In 20mi: {rx.get('contacts_in_range_20mi')}")
                ok(f"  Nearest: {rx.get('nearest_contact_mi')} mi")
                src = rx.get("source_stats", {})
                info(f"  Source: {src.get('last_source')} "
                     f"(dump1090={src.get('dump1090',0)}, opensky={src.get('opensky',0)}, errors={src.get('errors',0)})")
        else:
            fail("  No receiver data in health response")
    except urllib.error.URLError as e:
        fail(f"SkyDex server not responding: {e}")
        info("Is the server running?  sudo systemctl status skydex")
    except Exception as e:
        fail(f"SkyDex health check failed: {e}")

# ---------------------------------------------------------------------------
# 5. NWS Weather
# ---------------------------------------------------------------------------
def check_nws():
    print("\n" + "=" * 50)
    print("5. NWS Weather API")
    print("=" * 50)

    lat, lon = 41.1635, -73.1262
    try:
        url = f"https://api.weather.gov/points/{lat:.4f},{lon:.4f}"
        req = urllib.request.Request(url, headers={
            "User-Agent": "SkyDex-diagnose (skydex@localhost)",
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.load(resp)
        props = data.get("properties", {})
        ok(f"NWS points API OK — grid: {props.get('gridId')}/{props.get('gridX')},{props.get('gridY')}")

        # Try forecast
        forecast_url = props.get("forecast")
        if forecast_url:
            req2 = urllib.request.Request(forecast_url, headers={
                "User-Agent": "SkyDex-diagnose (skydex@localhost)",
            })
            with urllib.request.urlopen(req2, timeout=10) as resp2:
                fc = json.load(resp2)
            periods = fc.get("properties", {}).get("periods", [])
            if periods:
                ok(f"NWS forecast OK — {periods[0].get('temperature')}F, {periods[0].get('shortForecast')}")
    except Exception as e:
        fail(f"NWS weather failed: {e}")

# ---------------------------------------------------------------------------
# 6. NOAA Tide
# ---------------------------------------------------------------------------
def check_tide():
    print("\n" + "=" * 50)
    print("6. NOAA Tide API")
    print("=" * 50)

    try:
        url = ("https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
               "?date=today&station=8467150&product=predictions"
               "&datum=mllw&units=english&time_zone=lst_ldt&format=json")
        req = urllib.request.Request(url, headers={"User-Agent": "SkyDex-diagnose"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.load(resp)
        preds = data.get("predictions", [])
        ok(f"NOAA tide API OK — {len(preds)} predictions today")
        if preds:
            info(f"  Next: {preds[0].get('type')} at {preds[0].get('t')} = {preds[0].get('v')}ft")
    except Exception as e:
        fail(f"NOAA tide failed: {e}")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("=" * 50)
    print(" SkyDex Diagnostic Tool")
    print(f" Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    check_rtlsdr()
    check_dump1090()
    opensky_count = check_opensky()
    check_skydex()
    check_nws()
    check_tide()

    print("\n" + "=" * 50)
    print(" Summary")
    print("=" * 50)

    if opensky_count > 0:
        ok(f"OpenSky is returning {opensky_count} aircraft — SkyDex SHOULD detect planes")
        info("If SkyDex still shows 0, the issue is likely:")
        info("  - The receiver isn't falling back to OpenSky (check logs)")
        info("  - The enrichment pipeline is crashing (check /tmp/skydex.log)")
    else:
        fail("OpenSky returned 0 aircraft — possible causes:")
        info("  - OpenSky API is down or rate-limiting")
        info("  - Your bbox area is genuinely empty (unlikely near KBDR)")

    print("\n" + "=" * 50)
    print(" Quick fixes to try:")
    print("=" * 50)
    print("""
1. If dump1090/readsb is NOT running, start it:
   sudo systemctl start readsb
   OR build & start dump1090 manually

2. Restart SkyDex to pick up OpenSky fallback:
   sudo systemctl restart skydex

3. Watch live logs:
   journalctl -u skydex -f

4. Test OpenSky directly (OAuth2 — Basic Auth no longer works):
   TOKEN=$(curl -s -X POST \\
     'https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token' \\
     -d 'grant_type=client_credentials' \\
     -d 'client_id=YOUR_OPENSKY_CLIENT_ID' \\
     -d 'client_secret=YOUR_OPENSKY_CLIENT_SECRET' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
   curl -H "Authorization: Bearer $TOKEN" \\
     'https://opensky-network.org/api/states/all?lamin=40.6&lomin=-73.8&lamax=41.7&lomax=-72.4'
""")

if __name__ == "__main__":
    main()
