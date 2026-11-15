# Changelog

All notable changes to OmniDex. Versions follow [semver](https://semver.org)
in spirit: minor = new Dex powers, patch = fixes.

## 1.2.1 — 2026-11-15

### Docs

- Added feature screenshots (`docs/img/`) to the README and `docs/ACARS.md`:
  the Dex-page datalink chat thread and the transient map bubbles. Rendered
  from the shipped CSS with sample messages.

## 1.2.0 — 2026-11-14

### Added — ACARS bubbles pop up on the live map 🗺️💬

Datalink messages now appear right on the map, not just the Dex page: when a
plane in range sends or receives an ACARS message, a little word bubble pops
up next to its marker (green = the plane transmitting, blue = ground
replying), rides along with the moving plane, and fades away after ~7 seconds.

- `GET /api/acars/live?since=<ts>` — fresh messages matched to the planes
  currently in range (by ICAO hex, registration via the Dex DB, or flight
  number), one bubble per plane, newest message wins.
- The map polls every 5 s while the air-mode live map is on screen; bubbles
  follow the glide animation and clean themselves up when the plane leaves
  range or you switch views.
- Bubble text is capped at 140 characters on the map — the full thread still
  lives on the plane's Dex detail page.

## 1.1.0 — 2026-11-14

### Added — ACARS datalink: read the planes' text messages ✈️💬

Planes and the ground send each other short text messages all day (ACARS /
VDL-2) — position reports, gate assignments, clearances, weather requests.
OmniDex now catches them on your own antenna and shows them as a **text-chat
thread** on each plane's Dex detail page:

- **Green bubbles (right)** — the plane transmitting (downlinks).
- **Blue bubbles (left)** — ground stations / controllers replying (uplinks).

What's in the box:

- `acars.py` — a UDP listener that ingests JSON from the two standard
  open-source decoders, **acarsdec** (classic VHF ACARS) and **dumpvdl2**
  (VDL Mode 2 on 136.975). Both can feed the same port; direction (plane vs
  ground) is worked out from the ACARS block-id convention or the VDL-2
  AVLC addresses, which also carry the aircraft's ICAO hex.
- `GET /api/acars/plane/{hex}` — one airframe's thread (matched by hex,
  registration, or flight) and `GET /api/acars/recent` — the firehose.
- A `Datalink — ACARS` section on the Dex detail page (hidden until the
  receiver has actually heard that plane).
- Admin toggles: **ACARS datalink** on/off and the UDP port.
- Setup guide: see `docs/ACARS.md` and the new section in
  `SKYDEX_START_GUIDE.md`.

No new Python dependencies — stdlib only, and the SDR decoding stays in the
dedicated decoder processes, same pattern as readsb and AIS-catcher.

## 1.0.0 — 2026-11-14

- Fresh public baseline: the five Dexes (Sky, Sea, Atmo, Land, Ether), the
  games arcade, trainer cards, achievements, challenges, and the voice.
