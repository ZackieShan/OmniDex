# Aircraft reference images

Drop reference photos here to show a generic picture for an aircraft **type**
on the Dex detail page (used when SkyDex doesn't have a photo of the specific
airframe).

## Naming

Name each file after the **ICAO type code**, uppercase, `.jpg`:

```
C172.jpg     Cessna 172
SR22.jpg     Cirrus SR22
B738.jpg     Boeing 737-800
A320.jpg     Airbus A320
R44.jpg      Robinson R44
EC35.jpg     Airbus H135
GLF5.jpg     Gulfstream G550
```

The type code is shown on the Dex detail page next to "Type Specs", and is the
same code used in `aircraft_specs.py`.

## How the photo is chosen (in order)

1. A photo of the *specific* airframe, if adsbdb has one (`photo_url`).
2. `/(/static/img/aircraft/<TYPE_CODE>.jpg)` — the reference image you drop here.
3. The built-in SVG silhouette (plane / helicopter / fighter) — always works.

So this folder is optional: if a type image is missing, SkyDex quietly falls
back to the silhouette. Add images for the types you see most around KBDR first
(Cessna 172, Cirrus SR22, King Air, the local Sikorsky helicopters, etc.).

## Tips

- Keep them reasonably small (e.g. 600×400, < ~150 KB) — they load on the Pi.
- Use images you have the right to use (your own photos, public-domain, or
  appropriately licensed). Landscape orientation looks best in the photo frame.
