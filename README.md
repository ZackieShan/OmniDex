# OmniDex (SkyDex)

A Pokédex for the invisible world around your house. A Raspberry Pi kiosk
that catches — and collects — the airplanes, ships, trains, satellites,
weather, and radio signals passing through your neighborhood, wrapped in a
game the whole family plays. A STEM project built to teach kids that the air
around them is full of real, findable things.

Born on the shoulder of Long Island Sound.

## The five Dexes

- **SkyDex** — aircraft overhead via ADS-B (local dongle) or a free internet
  feed. Catch them when they enter your "pokéball" radius. Add an ACARS
  decoder and each plane's Dex page grows a live **text-chat thread** of its
  datalink messages — green bubbles from the plane, blue from the ground
  (see `docs/ACARS.md`).
- **SeaDex** — vessels on the Sound via AIS (local receiver or AISStream).
- **AtmoDex** — a live weather station, 10-day forecast, animated wind map,
  the ISS and satellite passes, NASA's photo of the day, and StormDex history.
- **LandDex** — Metro-North & Amtrak boards, a live train map, and drive-time
  road trips.
- **EtherDex** — the invisible radio neighborhood: wireless sensors (rtl_433),
  Bluetooth & WiFi presence, a world-radio dart game, ham streams, local
  scanner feeds, and iSpy (guess-the-webcam).

Plus a **Games arcade** (Who's That Plane, flag & language quizzes, Cloud
Spotter, Storm School, Map Master, Morse Academy, Weather Time Machine…),
per-kid **trainer cards** with trophies, 130+ **achievements**, and daily /
weekly **challenges**.

## Hardware

- Raspberry Pi 4/5 + a 1080p touchscreen
- A **powered** USB hub (non-negotiable for SDR dongles)
- 1–3 RTL-SDR dongles + antennas (start with zero — planes fall back to the
  cloud — and add as the hobby bites)
- Optional USB speaker for the radio's own voice

Full shopping + wiring list is in `skydex-gift-kit/NEIGHBOR_GUIDE.md`.

## Setup

```bash
sudo apt install -y python3-pip rtl-433 espeak-ng alsa-utils
pip3 install fastapi uvicorn jinja2 sgp4 websocket-client --break-system-packages

cp .env.example .env      # then paste your own free API keys
python3 main.py           # browse to http://<pi>:8000
```

Every key has a free tier; a blank key just disables that one feature. The
admin page at `/api-less http://<pi>:8000/admin` has every toggle.

> **Secrets:** `.env` is git-ignored on purpose — it holds real API keys.
> Never commit it. If you fork/clone, start from `.env.example`.

## Give one to a neighbor

`skydex-gift-kit/` turns your working copy into a scrubbed gift with a
friendly setup wizard (family names, kiosk title, location, their own keys) —
no code editing required. See that folder's README.

## House rules

- **Never port-forward the kiosk to the internet** — it has no auth. Use
  Tailscale to reach it remotely.
- EtherDex logs **devices & networks, never people** — broadcast names and
  signal only, forgotten after 90 days.
- Receive-only. Nothing here transmits.

## License

MIT — see `LICENSE`. Share it, remix it, hand it to a kid.
