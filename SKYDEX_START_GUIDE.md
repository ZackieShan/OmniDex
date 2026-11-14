# SkyDex — Step-by-Step Start Guide for Raspberry Pi

## Prerequisites
- Raspberry Pi 4/5 with Raspberry Pi OS
- SkyDex code copied to `~/skydex/`
- Internet connection (for OpenSky fallback and weather)

---

## Step 1: Install Dependencies (one-time)

```bash
# Option A: Install directly (quickest)
sudo apt update
sudo apt install -y python3-fastapi python3-uvicorn python3-jinja2 python3-aiohttp
# If packages not found:
pip3 install fastapi uvicorn jinja2 aiohttp python-multipart --break-system-packages

# Option B: Virtual environment (cleaner)
cd ~
python3 -m venv skydex-venv
source skydex-venv/bin/activate
pip install fastapi uvicorn jinja2 aiohttp python-multipart
# Then always activate before running:
# source ~/skydex-venv/bin/activate
```

---

## Step 2: Configure Your Location

```bash
nano ~/skydex/config.py
```

Change lines 15-16 to YOUR coordinates (right-click your house in Google Maps):
```python
    lat: float = 41.1635   # ← YOUR latitude
    lon: float = -73.1262  # ← YOUR longitude
```

Save: `Ctrl+O`, `Enter`, `Ctrl+X`

---

## Step 3: Start SkyDex

```bash
cd ~/skydex
python3 main.py
```

You should see:
```
SkyDex starting
Location: Your Town, Your State or Country (LAT, LONG)
Range: 5.0 miles
Starting web server on http://0.0.0.0:8000
Open your browser to http://localhost:8000
```

---

## Step 4: Open the Browser

### From the Pi directly (keyboard + monitor):
```bash
chromium-browser --kiosk http://localhost:8000
```

### From SSH (controlling the Pi's screen remotely):
```bash
DISPLAY=:0 chromium-browser --kiosk http://localhost:8000 &
```

### To see it on the Pi's display without a keyboard:
```bash
# This launches the browser on the Pi's screen from your SSH session
DISPLAY=:0 nohup chromium-browser --kiosk --app=http://localhost:8000 > /dev/null 2>&1 &
```

---

## Step 5: What You Should See

1. **Red Pokédex-themed screen** with dark "screen" area
2. **Top bar**: "SkyDex — Your Town" + live clock
3. **Weather strip**: current temp, conditions, wind
4. **Contact list**: Aircraft currently within 5 miles with:
   - Type icon (like Pokémon type badges)
   - Callsign/tail number
   - Model and operator
   - Altitude, speed, distance
5. **Empty state** (most of the time): rotating aviation facts + your top regulars
6. **Bottom nav**: Contacts | Planedex | Stats

Tap any aircraft row → **Dex Detail page** with:
- Aircraft photo (or placeholder)
- Dex number (#1, #2, #3...)
- Rarity tier (Common → Legendary)
- Evolution tier (Spotted → Tracked → Tagged → Bonded)
- Behavioral types with confidence
- Altitude history chart
- Fun facts about the aircraft type

---

## Step 6: Auto-Start on Boot (optional)

```bash
crontab -e
```

Add this line:
```
@reboot cd /home/skywatch/skydex && PYTHONPATH=/home/skywatch/skydex python3 main.py >> /tmp/skydex.log 2>&1
```

For the browser too:
```
@reboot sleep 10 && DISPLAY=:0 chromium-browser --kiosk --app=http://localhost:8000
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `ModuleNotFoundError` | Run `pip3 install fastapi uvicorn jinja2 aiohttp --break-system-packages` |
| Port 8000 in use | Edit `config.py`, change `api_port: int = 8000` to `8001` |
| No aircraft showing | Run `python3 diagnose.py` — it tests the RTL-SDR, dump1090, and the OpenSky fallback (OAuth2) and tells you which layer is failing. |
| Aircraft show as "Unknown" | Enrichment needs data: confirm internet (adsbdb) and/or run the registry sync (see "Aircraft Enrichment" below). |
| Type icons / speaker icon are blank boxes | The Pi is missing an emoji font. Run `sudo apt install -y fonts-noto-color-emoji && sudo fc-cache -f`, then reload the page. |
| No sounds | Tap the screen once (browsers require a gesture to start audio), and make sure the kiosk launches with `--autoplay-policy=no-user-gesture-required` (pi_setup.sh sets this). The speaker icon in the top bar toggles sound. |
| Blank/black screen | Make sure `templates/` and `static/` folders are in `~/skydex/` |
| Weather not showing | Check internet: `curl -I https://api.weather.gov` |

---

## Aircraft Enrichment (models, owners, registrations)

SkyDex fills in each aircraft's model / operator / registration from three
sources, in order of preference:

1. **Local FAA registry DB** — best for US (N-numbered) and general-aviation
   traffic around KBDR. Offline, fast, no rate limits.
2. **Local OpenSky aircraft DB** — global coverage, includes ICAO type codes.
3. **adsbdb.com API** — live fallback for anything not found locally (needs internet).

The local databases are optional but strongly recommended. Sync them once
(then refresh occasionally — the FAA file updates daily):

```bash
cd ~/skydex
python3 sync_faa_db.py        # ~/.skydex/faa_registry.db   (US registry)
python3 sync_opensky_db.py    # ~/.skydex/opensky_aircraft.db (global)
python3 sync_airports_db.py   # ~/.skydex/airports.db (airport names/cities/countries)
```

Auto-refresh the FAA DB monthly via crontab:
```
0 3 1 * * cd ~/skydex && python3 sync_faa_db.py >> /tmp/skydex_faa_sync.log 2>&1
```

SkyDex picks up the databases automatically on the next restart. Until you
sync them, enrichment falls back to the adsbdb API (internet required).

> **OpenSky access** uses OAuth2 client credentials (set in `config.py` under
> `ReceiverConfig.opensky_client_id` / `opensky_client_secret`). OpenSky removed
> username/password Basic Auth in 2025 — SkyDex now exchanges the client
> credentials for a short-lived Bearer token automatically.

---

## When You Get the RTL-SDR Dongle (NESDR Mini 2+)

This is the biggest upgrade — a local receiver gives you real low-altitude,
local traffic (helicopters, pattern work, the small GA that OpenSky never
carries). Plug in the dongle (antenna outside/high, short coax) and run the two
standard community installers:

```bash
# 1) readsb — the ADS-B decoder (auto-detects the RTL-SDR, adaptive gain)
sudo bash -c "$(wget -nv -O - https://github.com/wiedehopf/adsb-scripts/raw/master/readsb-install.sh)"

# 2) set your receiver location (YOUR coordinates, not this example)
sudo readsb-set-location 41.1635 -73.1262

# 3) tar1090 — serves the live aircraft JSON (and a full map UI)
sudo bash -c "$(wget -nv -O - https://github.com/wiedehopf/tar1090/raw/master/install.sh)"
```

That's it — **SkyDex auto-detects** the local feed at
`http://localhost/tar1090/data/aircraft.json` and switches from OpenSky to your
own antenna automatically (no config change). Verify with `python3 diagnose.py`.
Bonus: a full live map is available at `http://<pi>/tar1090`.

> `pi_setup.sh` runs both installers for you, so if you used it, you're already set.

---

## ACARS — read the planes' text messages (optional extra dongle)

Planes text the ground all day — position reports, gate changes, controller
uplinks — on ACARS. Feed OmniDex with the standard decoders and each plane's
Dex page shows the conversation as chat bubbles (green = plane, blue = ground):

```bash
# Classic VHF ACARS (one dongle, several frequencies at once):
acarsdec -o 0 -j 127.0.0.1:5555 -r <dongle-serial> 131.550 131.725 130.025 131.825

# And/or VDL Mode 2 — the busier digital channel:
dumpvdl2 --rtlsdr <dongle-serial> \
         --output decoded:json:udp:address=127.0.0.1,port=5555 136975000
```

Both can send to the same port (`5555`, changeable in `/admin`). Full notes
in `docs/ACARS.md`. No decoder running? The Dex pages simply don't show the
section — nothing breaks.

---

## SeaDex (Marine / AIS) — the second dongle

SeaDex shows ship traffic on Long Island Sound the same way SkyDex shows
aircraft. It reads from a local **AIS-catcher** instance (a separate RTL-SDR
tuned to the AIS band). Use the **SkyDex ⇄ SeaDex** toggle in the top bar.

> One dongle can only listen to one band at a time, so AIS needs its **own**
> RTL-SDR (alongside the ADS-B one). RTL-SDRs are addressed by serial number,
> so two run side by side.

```bash
# Install AIS-catcher (one-line installer)
sudo bash -c "$(wget -qO - https://raw.githubusercontent.com/jvde-github/AIS-catcher/main/scripts/aiscatcher-install)"

# Run it on the AIS dongle with its web server on :8100
#   -d <serial>   pick the AIS dongle (find serials with: rtl_test)
AIS-catcher -d <serial> -N 8100
```

SeaDex reads `http://localhost:8100/api/ships.json` automatically (set in
`config.py` → `MarineConfig.ais_json_url`). No AIS dongle yet? SeaDex just shows
"no vessels" — SkyDex is unaffected.

### Cloud fallback — AISStream.io (recommended, free, no contribution)

The easiest way to give SeaDex a cloud source is [AISStream.io](https://aisstream.io):
free, real-time WebSocket feed, and — unlike AISHub — it does **not** require you
to contribute your own data first. Just get an API key:

```bash
# One-time: install the WebSocket client library.
# On Raspberry Pi OS / Debian (system Python, PEP 668), use apt:
sudo apt install -y python3-websocket
# Or, if you run SkyDex inside a venv:  pip install websocket-client
```

Then in `config.py` → `MarineConfig`:

```python
aisstream_enabled = True
aisstream_api_key = "YOUR_AISSTREAM_KEY"   # from aisstream.io (keep it secret!)
```

Restart SkyDex. Local AIS-catcher still wins whenever it's running; AISStream
fills in live whenever the local decoder is down. Watch `/api/health` →
`marine.stats.last_source` (`ais-catcher` vs `aisstream`) and
`marine.aisstream.connected`.

> Treat the key like a password — don't paste it into chats or commit it. If it
> leaks, regenerate it on aisstream.io.

### Contribute to AISHub (and get a cloud fallback)

[AISHub](https://www.aishub.net) is a data-sharing co-op — the marine version of
OpenSky/FlightAware. Feed them your decoded AIS and they give you access to the
worldwide aggregated feed. To contribute, add AISHub as a **UDP output** on the
same AIS-catcher command that already serves SeaDex:

```bash
# Serve SeaDex locally (:8100) AND forward NMEA to AISHub over UDP
AIS-catcher -d <serial> -N 8100 -u data.aishub.net 2406
```

That's the whole "configure your station" step from the AISHub welcome email
(host `data.aishub.net` / `144.76.105.244`, UDP port `2406`). Email them to
confirm once it's running; they'll verify the feed and assign you a **username**.

### Use AISHub as SeaDex's fallback

AISHub only assigns a username *after* you've contributed and they verify your
feed — so you need the AIS dongle + AIS-catcher running first (chicken-and-egg).
Once you have the username, SeaDex can pull vessels from the cloud whenever the
local AIS-catcher isn't running — exactly how SkyDex falls back to OpenSky (great
resilience if the AIS dongle is busy, unplugged, or the decoder crashes). In
`config.py` → `MarineConfig`:

```python
aishub_enabled  = True
aishub_username = "YOUR_AISHUB_USERNAME"
```

Restart SkyDex. Local AIS-catcher always wins when it's up; AISHub only fills in
when it's down (throttled to AISHub's 1-request-per-minute limit). You can watch
which source is live at `/api/health` → `marine.stats.last_source`
(`ais-catcher` vs `aishub`).

---

## Keyboard Shortcuts (if you have a keyboard plugged in)

| Key | Action |
|-----|--------|
| `Ctrl+C` in terminal | Stop SkyDex server |
| `F11` in browser | Toggle fullscreen |
| `Ctrl+W` | Close browser tab |
| `Alt+F4` | Close browser window |
