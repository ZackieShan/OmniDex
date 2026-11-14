# Changelog

All notable changes to OmniDex. Versions follow [semver](https://semver.org)
in spirit: minor = new Dex powers, patch = fixes.

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
