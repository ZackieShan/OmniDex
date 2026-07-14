"""Fun facts about the home airport, the local sky and water, aircraft types,
and aviation trivia.

Used by the empty-state screen and Dex detail pages."""

import random
from typing import List

# -- Home airport / general-aviation lore ------------------------------------

AIRPORT_FACTS: List[str] = [
    "Runway numbers are compass headings divided by ten — runway 6/24 points roughly northeast (060°) one way and southwest (240°) the other.",
    "Small towered airports often close the tower overnight; after hours, pilots self-announce their positions on a shared frequency called the CTAF.",
    "General-aviation airports outnumber airline airports in the US by more than ten to one — most flying happens far from the big hubs.",
    "'Reliever' airports soak up small planes and business jets so the big international hubs don't have to — that's why quiet fields see surprise bizjet traffic.",
    "The traffic pattern at most GA airports is flown at about 1,000 feet above the field — that's why the same planes seem to circle the neighborhood.",
    "Igor Sikorsky, the Russian-American aviation pioneer, built and flew the first practical helicopter in Connecticut — the VS-300 first flew in 1939.",
    "Sikorsky tested the VS-300 tethered to the ground first — early hops measured in seconds, not minutes.",
    "During WWII, Connecticut factories built over 500 Catalina PBY flying boats that were launched onto Long Island Sound for test flights.",
    "Modern military helicopters are still flight-tested over Long Island Sound — if you see a Black Hawk in the pattern, it may be a factory test flight.",
    "A 4,700-foot runway is plenty for business jets but a stretch for anything bigger — which quietly decides what kinds of planes you'll ever see at a small field.",
    "Crosswind days send traffic onto an airport's secondary runway — the pattern over your house can literally change with the weather.",
    "On a busy summer weekend, a shoreline GA airport sees floatplanes, banner-towers, and flight-school Cessnas all sharing the same patch of sky.",
    "Coastal airports fight a constant, gentle war with birds — salt marshes next door are major stopovers, so wildlife control is a real aviation job.",
    "Many small airports host an annual fly-in — vintage warbirds, helicopter demos, and pancake breakfasts on the ramp.",
]

SHORELINE_FACTS: List[str] = [
    "From the Connecticut shoreline on a clear day you can watch jets lining up for New York's airports — 30 miles away but visible as silver glints at 8,000 feet.",
    "Long Island sits about 10 miles across the Sound from the Connecticut shore; on clear days the far shore looks close enough to touch.",
    "A shoreline bluff even 30 feet above the water makes a superb plane- and ship-watching spot — height flattens the horizon and doubles what you can see.",
    "The Hurricane of 1938 rebuilt much of the Connecticut shoreline — the seawalls you see today are its legacy.",
    "Salt marshes along the Sound are major bird stopovers on the Atlantic flyway — which is why so many shorebirds share the sky with the planes.",
    "Old shoreline rail rights-of-way from the 1920s beach-train era survive today as walking trails.",
    "Shoreline towns on the Sound have some of the highest per-capita private pilot populations in Connecticut — easy access to small airports helps.",
    "Watching from a coastline means double traffic: aircraft overhead and vessels on the water, all broadcasting their positions in the clear.",
    "The glow of nearby cities washes out faint stars — but face the open water and the sky gets darker fast.",
]

AVIATION_FACTS: List[str] = [
    "ADS-B Out broadcasts position, altitude, speed, and callsign on 1090 MHz every half-second — your RTL-SDR is eavesdropping on the sky's heartbeat.",
    "Every aircraft's ICAO 24-bit address is assigned at manufacture and stays with the airframe for life. It is the DNA of the plane.",
    "Mode S transponders reply to ground radar interrogations, but ADS-B Out squawks continuously — no radar needed. The plane advertises itself.",
    "Aircraft squawk 1200 for VFR flight in the US. 7500 means hijack, 7600 means radio failure, 7700 means emergency.",
    "Contrails form when hot jet exhaust meets cold humid air above ~26,000 feet. The water vapor flash-freezes into ice crystals.",
    "RVSM — Reduced Vertical Separation Minimum — lets planes fly 1,000 feet apart between FL290 and FL410, doubling airway capacity.",
    "The Cessna 172 Skyhawk is the most produced aircraft in history at over 44,000 units. Every flight school has at least three.",
    "Wake turbulence from a Boeing 747 can flip a light aircraft. The FAA mandates 5-mile separation behind heavies for small planes.",
    "Transponder category bits in Mode S tell you if an aircraft is light, small, large, heavy, or high-vortex — your SDR decodes this for free.",
    "FlightAware and Flightradar24 get most of their data from volunteers with RTL-SDR dongles just like yours. You are the network.",
    "A helicopter's transponder category code is different from fixed-wing — your receiver can tell a rotor from a prop before you see it.",
    "The ISS orbits at 17,500 mph at 250 miles up. Its ham radio beacon sometimes shows up on ADS-B aggregators as a prank.",
    "Air Force One is a VC-25A (modified Boeing 747-200B) with tail number 28000 or 29000. Either tail broadcasts a classified callsign.",
    "The A380 has a wingspan of 261 feet — wider than the Wright Brothers' first flight was long (120 feet).",
    "GA aircraft under 10,000 feet use QNH (altimeter setting). Above 18,000 feet, everyone uses 29.92 inHg — that is Flight Levels.",
]

# -- Aircraft type facts (populated on first enrichment) --------------------

TYPE_FACTS: dict[str, str] = {
    "B738": "The Boeing 737-800 is the workhorse of the world's short-haul fleets. Over 5,000 delivered. Southwest alone has 200+.",
    "B739": "The 737-900 is the longest variant of the 737 family. It needs a special tail skid because the fuselage is so long.",
    "A320": "The Airbus A320 family was the first airliner with digital fly-by-wire. The side-stick controller replaced the yoke.",
    "A321": "The A321neo can fly 4,000 nautical miles — transatlantic range in a narrowbody. JetBlue uses it for London flights.",
    "C172": "The Cessna 172 first flew in 1955 and is still in production. It is the Honda Civic of the sky: boring, reliable, everywhere.",
    "C182": "The Cessna 182 Skylane adds a constant-speed propeller and more power to the 172 formula. Popular for cross-country GA flights.",
    "PA28": "The Piper Cherokee PA-28 series has been training pilots since 1960. The low wing makes it feel sportier than a Cessna.",
    "R44": "The Robinson R44 is the world's best-selling helicopter for a reason: it is cheap to run and seats four. Flight schools love it.",
    "EC35": "The Eurocopter EC135 (now Airbus H135) is the default air ambulance helicopter. Its Fenestron tail is unmistakable.",
    "B350": "The Beechcraft King Air 350 is the gold standard turboprop twin. If a hospital says 'air ambulance,' it is probably a King Air.",
    "GLF5": "The Gulfstream G550 can fly 6,750 nautical miles at Mach 0.85. It costs $50+ million and its owners do not care about your 401k.",
    "C130": "The Lockheed C-130 Hercules has been in continuous production since 1954. It lands on dirt strips, drops paratroopers, and fights fires.",
    "C17": "The C-17 Globemaster III can carry an M1 Abrams tank, perform tactical airlift into unimproved strips, and do a combat landing at 120 knots.",
    "F16": "The F-16 Fighting Falcon was the first fighter designed to be aerodynamically unstable — computers keep it in the air 40 times per second.",
    "F35": "The F-35 Lightning II has 8 million lines of code. Its helmet projects a 360-degree view synthesized from six infrared cameras.",
    "P8": "The Boeing P-8 Poseidon is a 737-800 modified for submarine hunting. It drops sonobuoys, torpedoes, and carries a MAD boom.",
    "K35R": "The KC-135 Stratotanker has been refueling fighters since 1957. Over 800 built; some are still flying with original fuselages.",
    "E3TF": "The E-3 Sentry AWACS carries a 30-foot rotating radar dome. It can track 250 targets simultaneously at 250 miles.",
    "A339": "The Airbus A330-900neo wraps new Trent 7000 engines and Sharklet wingtips around the proven A330 — about 25% more fuel-efficient than the original.",
    "A359": "The Airbus A350-900 is over 50% composite by weight. Its windows are the largest on any airliner and the cabin is pressurized to a comfortable 6,000 ft.",
    "A35K": "The A350-1000 stretches the A350 to seat over 400. Six-wheel main bogies spread its weight so it can use the same runways as smaller jets.",
    "B77W": "The 777-300ER is the workhorse of long-haul. Its GE90 engines are so large in diameter that one is nearly as wide as a 737's fuselage.",
    "B788": "The 787 Dreamliner's carbon-fiber fuselage lets it run higher humidity and lower cabin altitude, which is why you feel less jet-lagged.",
    "B744": "The 747-400's hump houses the upper deck. Its four engines and distinctive shape made it the 'Queen of the Skies' for decades.",
    "AN2": "The Antonov An-2 is the largest single-engine biplane ever mass-produced — and it has no published stall speed; in a stiff wind it can fly backward over the ground.",
    "DC3": "The Douglas DC-3 first flew in 1935 and many are STILL flying. It's often said the only replacement for a DC-3 is another DC-3.",
    "P51": "The P-51 Mustang's range, thanks to drop tanks, let it escort bombers all the way to Berlin and back in WWII.",
    "ST75": "The Boeing-Stearman Model 75 trained tens of thousands of WWII pilots. Today these biplanes are prized for barnstorming and wing-walking acts.",
    "R66": "The Robinson R66 added a turbine engine to Robinson's light-helicopter formula, giving it more power, altitude, and a luggage compartment.",
    "S92": "The Sikorsky S-92 — built in Connecticut — is a workhorse for offshore oil rigs and search-and-rescue worldwide.",
}


# ===========================================================================
# SEADEX — Long Island Sound and vessel trivia
# ===========================================================================

# -- The Sound itself --------------------------------------------------------

SOUND_FACTS: List[str] = [
    "Long Island Sound is a tidal estuary of the Atlantic — about 110 miles long and 21 miles across at its widest — penned in between Connecticut and Long Island.",
    "The Sound holds roughly 18 trillion gallons of water. Its average depth is only about 63 feet, but 'The Race' near Fishers Island plunges past 300.",
    "Long Island Sound is a federally designated 'Estuary of National Significance' — a nursery for striped bass, bluefish, flounder, and the Sound's comeback species, the osprey.",
    "More than 20 lighthouses still stand around Long Island Sound — several built on lonely mid-Sound rocks, and more than one famously rumored to be haunted.",
    "Rocky shoals in the middle of the Sound split the shipping traffic: deep-draft vessels favor the marked channels rather than risk the rocks.",
    "The rivers that pour into the Sound are tidal for miles — saltwater pushes far upstream, which is why you'll see seals in winter and herring runs in spring near their mouths.",
    "Tides on the Sound swing 6–7 feet twice a day, and currents rip hard through the river mouths — local mariners time their passages to the slack.",
    "From the Connecticut shore on a clear day you can see straight across to Long Island — the far shore is only about 10 miles away over open water.",
    "Every headland where a river meets the Sound has carried a navigation light for two centuries — some towers still standing date to the 1800s.",
]

# -- Maritime history on the Sound -------------------------------------------

HARBOR_FACTS: List[str] = [
    "Connecticut's shoreline towns were settled in the 1630s right on their rivers, and shipbuilding was one of the first trades — sloops and schooners slid into the water within a few decades.",
    "In WWII, factories on the Sound built hundreds of PBY Catalina flying boats, rolled down to the water and launched for test flights.",
    "Connecticut oyster beds were once so valuable that shellfish grounds were mapped, leased, and fought over — the state still farms oysters in these waters today.",
    "Sound harbors grew into some of the busiest ports on the East Coast in the 1800s — oystering, whaling, and manufacturing all shipped out of them.",
    "The Sound was a 19th-century oyster capital: its steam-powered dredging fleets were among the first in the world, seeding beds all across the estuary.",
    "Ferries have crossed the Sound between Connecticut and Long Island since 1883 — one famous route was reportedly backed by showman P.T. Barnum, and it still runs today.",
    "Lighthouse keepers on the Sound — several of them women — are credited with saving dozens of lives from wrecks in the age of sail.",
    "Deepwater anchorages on the Connecticut coast were prized so highly in the colonial era that neighboring harbors openly rivaled each other for shipping.",
    "The passenger ferries you see crossing the Sound cover about 15 nautical miles of open water in roughly 75 minutes.",
]

# -- General marine / AIS trivia (mirrors AVIATION_FACTS) --------------------

MARINE_FACTS: List[str] = [
    "AIS — the Automatic Identification System — is the sea's version of ADS-B. Ships broadcast their position, course, and speed on VHF around 162 MHz, and your dongle is listening in.",
    "Every vessel's MMSI is a 9-digit ID. The first three digits are the country code — 366–369 means United States, 232–235 the UK, 244–246 the Netherlands.",
    "Class A AIS (big commercial ships) transmits every 2–10 seconds under way; Class B (smaller boats and yachts) reports less often — so freighters refresh on your radar faster than sailboats.",
    "International law (SOLAS) requires AIS on all ships over 300 gross tons and every passenger vessel — which is why tankers and ferries almost always show up, but a rowboat never will.",
    "A vessel's AIS 'destination' and ETA are typed in by the crew, so you'll sometimes see playful or blank entries — it's the one field humans, not sensors, fill in.",
    "AIS navigation-status codes tell you what a ship is doing: 'under way using engine,' 'at anchor,' 'restricted maneuverability,' even 'aground.'",
    "Ship length and beam in an AIS message are encoded as distances from the antenna to bow, stern, port, and starboard — add them up and you get the hull's size.",
    "Just like ADS-B, much of the global AIS map is built by hobbyists running receivers like yours — every shore station fills in coverage the satellites miss.",
]

# -- Vessel-type facts (keyed by SeaDex category) ---------------------------

VESSEL_TYPE_FACTS: dict[str, str] = {
    "Cargo": "Cargo ships move about 90% of world trade. A modern container ship can stack over 20,000 boxes — a wall of steel the length of four football fields.",
    "Tanker": "Tankers carry crude oil, refined fuel, chemicals, or liquefied gas. The biggest can hold two million barrels — enough to fill ~125 Olympic pools.",
    "Passenger": "Passenger ships range from local ferries to cruise liners; the largest cruise ships now carry more than 7,000 guests, a small floating city.",
    "HSC": "High-speed craft — fast catamaran and hydrofoil ferries — cruise at 35+ knots, roughly double a normal ferry, riding above the drag of the water.",
    "Fishing": "Fishing vessels off the Sound chase striped bass, fluke, scallops, and lobster. Many switch their AIS nav-status to 'engaged in fishing' while working a set.",
    "Sailing": "Sailing vessels are the only traffic on the Sound that runs on wind alone — under AIS rule they broadcast nav-status 'under way sailing' when the engine is off.",
    "Pleasure": "Pleasure craft — private motor yachts and weekend cruisers — pack the Sound every summer. Carrying AIS is optional for them, so the ones you see opted in.",
    "Tug": "Tugs are the muscle of the harbor: a modern tractor tug puts out 5,000+ horsepower and can spin in place to nudge a ship a thousand times its size.",
    "Government": "Government vessels include Coast Guard cutters, pilot boats, and law-enforcement craft. Pilot boats dart out to put a local expert aboard inbound ships.",
    "Other": "Not every AIS contact fits a neat box — research ships, dredgers, buoy tenders, and the occasional mystery transponder all show up as 'other' on the Sound.",
}


def get_sea_fact(category: str | None = None) -> str:
    """Random SeaDex fact. Categories: 'sound', 'harbor', 'marine', or None for any."""
    pools = {
        "sound": SOUND_FACTS,
        "harbor": HARBOR_FACTS,
        "marine": MARINE_FACTS,
    }
    if category and category in pools:
        return random.choice(pools[category])
    return random.choice(SOUND_FACTS + HARBOR_FACTS + MARINE_FACTS)


def get_sea_facts_for_empty_state(n: int = 3) -> List[str]:
    """A diverse mix of sea facts for the empty-state / ticker."""
    selected: List[str] = []
    for cat in ("sound", "harbor", "marine"):
        selected.append(get_sea_fact(cat))
    while len(selected) < n:
        f = get_sea_fact()
        if f not in selected:
            selected.append(f)
    return selected[:n]


def get_vessel_type_fact(category: str | None) -> str | None:
    """Fun fact about a vessel category (Cargo, Tanker, Sailing, ...)."""
    if not category:
        return None
    return VESSEL_TYPE_FACTS.get(category)


# ===========================================================================
# ATMODEX — space, satellites, stars, CT aerospace, UFO lore
# ===========================================================================

SPACE_FACTS: List[str] = [
    "Light from the Sun takes about 8 minutes 20 seconds to reach us — you always see the Sun as it was 8 minutes ago.",
    "The Andromeda Galaxy is 2.5 million light-years away — the light hitting your eye tonight left before humans existed.",
    "There are more stars in the observable universe than grains of sand on every beach on Earth.",
    "A day on Venus is longer than its year — it rotates slower than it orbits the Sun.",
    "Saturn's rings are mostly water ice and would fit in the gap between Earth and the Moon — but are only ~10 meters thick in places.",
    "Jupiter's Great Red Spot is a storm wider than Earth that has raged for at least 350 years.",
    "If you could drive to the Moon at highway speed, it would take about five months.",
    "Neutron stars are so dense that a teaspoon of one would weigh about a billion tons.",
    "The footprints left by Apollo astronauts will likely last millions of years — there's no wind on the Moon to erase them.",
]

SATELLITE_FACTS: List[str] = [
    "Over 10,000 active satellites now orbit Earth, plus tens of thousands of tracked debris fragments.",
    "The ISS orbits at about 17,500 mph and laps the Earth every ~90 minutes — 16 sunrises a day for the crew.",
    "Satellites you see drifting across the night sky are catching sunlight — they wink out when they enter Earth's shadow.",
    "Geostationary satellites orbit at 22,236 miles and circle once per day, so they appear to hang motionless over one spot.",
    "Polar-orbiting weather satellites like NOAA-19 broadcast images on 137 MHz that hobbyists pick up with an SDR — the same kind of dongle SkyDex uses.",
    "The ISS is the third-brightest object in the night sky, after the Moon and Venus.",
    "GPS satellites carry atomic clocks and must correct for Einstein's relativity — without it, GPS would drift miles off per day.",
    "Starlink satellites sometimes appear as a 'train' of dots shortly after launch before they raise their orbits.",
]

STAR_FACTS: List[str] = [
    "Polaris, the North Star, sits almost exactly above Earth's axis — from here it's about 41° above the northern horizon, equal to your latitude.",
    "Betelgeuse, Orion's shoulder, is so huge that if placed where the Sun is, it would swallow Mars.",
    "The Big Dipper isn't a constellation — it's an 'asterism', part of Ursa Major, and it never sets from Connecticut.",
    "Sirius, the brightest night star, is only 8.6 light-years away — practically next door.",
    "Most stars you see are bigger and brighter than the Sun; the faint, common red dwarfs are too dim to see by eye.",
    "The two stars at the end of the Big Dipper's bowl point straight to Polaris — the original wayfinder's trick.",
    "Twinkling is our atmosphere bending starlight; planets twinkle less because they're disks, not points.",
]

CT_AEROSPACE_FACTS: List[str] = [
    "Igor Sikorsky built and flew the first practical helicopter in Connecticut in 1939.",
    "The Apollo spacesuits that walked on the Moon were designed and sewn in Connecticut — by ILC and Hamilton Standard (Windsor Locks).",
    "Pratt & Whitney in East Hartford built the engines that powered everything from WWII fighters to the F-15, F-16, F-22, and F-35.",
    "Hamilton Standard of Windsor Locks made propellers for much of WWII aviation — and life-support systems for the Space Shuttle.",
    "Kaman Aerospace in Bloomfield, CT pioneered the twin-rotor 'eggbeater' helicopter and built the K-MAX heavy-lift aircraft.",
    "Chance Vought built the bent-wing F4U Corsair fighter in Connecticut during WWII.",
    "Connecticut's nickname could almost be 'the Arsenal of Aerospace' — Sikorsky, Pratt & Whitney, Hamilton Standard, and Kaman all call it home.",
]

UFO_FACTS: List[str] = [
    "The US government renamed 'UFOs' to 'UAPs' (Unidentified Anomalous Phenomena) — and in 2022 opened an official office to study them.",
    "'Flying saucer' was coined in 1947 after pilot Kenneth Arnold described objects moving 'like a saucer skipping on water'.",
    "Project Blue Book, the US Air Force's UFO study, logged over 12,000 sightings between 1952 and 1969; 701 remain officially 'unidentified'.",
    "Most UFO reports turn out to be planes, satellites, Venus, or weather balloons — which is exactly why a sky-tracker like this is handy.",
    "In 2021 the Pentagon released a report on 144 military UAP sightings; only one could be confidently explained.",
    "Navy pilots' 2004 'Tic Tac' encounter off California became the most famous modern UAP case after the footage was declassified.",
]

FAMOUS_UFO_FACTS: List[str] = [
    "The Hudson Valley UFO wave (1982–1986) brought thousands of reports of a huge boomerang of lights over the NY/CT border — many from Connecticut.",
    "Betty and Barney Hill reported the first widely-known 'alien abduction' in 1961 — in New Hampshire, just up the road in New England.",
    "The Phoenix Lights (1997) were seen by thousands across Arizona; the later flares were explained, the earlier V-formation never fully was.",
    "Roswell, New Mexico (1947): the Army first said 'flying disc', then 'weather balloon' — birthing the most famous UFO story of all.",
    "The Kecksburg incident (1965, Pennsylvania) saw an acorn-shaped object recovered by the military and never publicly explained.",
    "The 1980 Rendlesham Forest event in England — near a US air base — is often called 'Britain's Roswell'.",
]

_ATMO_POOLS = {
    "space": SPACE_FACTS,
    "satellites": SATELLITE_FACTS,
    "stars": STAR_FACTS,
    "ct_aerospace": CT_AEROSPACE_FACTS,
    "ufo": UFO_FACTS,
    "famous_ufo": FAMOUS_UFO_FACTS,
}


def get_atmo_fact(category: str | None = None) -> str:
    """Random AtmoDex fact. Categories: space, satellites, stars, ct_aerospace, ufo, famous_ufo."""
    if category and category in _ATMO_POOLS:
        return random.choice(_ATMO_POOLS[category])
    allf = sum(_ATMO_POOLS.values(), [])
    return random.choice(allf)


def get_atmo_facts_for_empty_state(n: int = 5) -> List[str]:
    """A diverse mix of AtmoDex facts for the ticker."""
    selected: List[str] = []
    for cat in ("space", "stars", "satellites", "ct_aerospace", "ufo", "famous_ufo"):
        selected.append(get_atmo_fact(cat))
    while len(selected) < n:
        f = get_atmo_fact()
        if f not in selected:
            selected.append(f)
    return selected[:n]


def get_fact(category: str | None = None) -> str:
    """Get a random fact. Categories: 'airport', 'local', 'aviation', or None for any."""
    pools = {
        "airport": AIRPORT_FACTS,
        "local": SHORELINE_FACTS,
        "aviation": AVIATION_FACTS,
    }
    if category and category in pools:
        return random.choice(pools[category])
    all_facts = AIRPORT_FACTS + SHORELINE_FACTS + AVIATION_FACTS
    return random.choice(all_facts)


def get_facts_for_empty_state(n: int = 3) -> List[str]:
    """Get a diverse set of facts for the empty-state screen."""
    selected = []
    categories = ["airport", "local", "aviation"]
    for cat in categories:
        selected.append(get_fact(cat))
    # Fill remaining slots with random facts
    while len(selected) < n:
        f = get_fact()
        if f not in selected:
            selected.append(f)
    return selected[:n]


def get_type_fact(type_code: str) -> str | None:
    """Get a fun fact about a specific aircraft type."""
    return TYPE_FACTS.get(type_code.upper())


# ===========================================================================
# LandDex — rail lore for the New Haven Line / Northeast Corridor
# ===========================================================================

RAIL_FACTS = [
    "The shoreline tracks opened in 1848 as the New York & New Haven Railroad — trains have run along this coast for over 175 years.",
    "The New Haven Line is the busiest commuter rail line in the United States — roughly 40 million riders a year before you count Amtrak.",
    "Acela trains blast through the local stations without stopping — they can hit 150 mph, though the curvy Connecticut shoreline holds them to under 100 here.",
    "Several century-old movable bridges still carry the shoreline line over Connecticut's rivers — swing spans dating to the early 1900s that open for boats to this day.",
    "Metro-North's M8 railcars were built by Kawasaki and can draw power two ways: overhead wire on the New Haven Line and third rail into Grand Central.",
    "The overhead catenary on the New Haven Line is some of the oldest mainline electrification in America — the New Haven Railroad wired it starting in 1907.",
    "Four tracks run along much of the shoreline: locals weave between the outer tracks while Acelas overtake on the inside pair.",
    "The Northeast Corridor (Boston-NYC-DC) is the busiest passenger rail line in the Western Hemisphere — over 2,000 train movements a day system-wide.",
    "A New Haven Line express covers the ~60 miles from the mid-shoreline into Grand Central in around 80 minutes.",
    "Freight still moves on these tracks at night — CSX and Providence & Worcester locals serve shoreline customers after the commuter rush ends.",
    "The New Haven Railroad's famous 'McGinnis scheme' orange-and-black N-H logo from the 1950s still shows up on Metro-North heritage equipment.",
    "Before Amtrak (1971), the New York, New Haven & Hartford Railroad ran everything here — locals called the whole system simply 'The New Haven.'",
    "A modern M8 consist accelerates faster than most sports cars from 0-30 mph — electric traction delivers full torque instantly.",
    "GG-1 electrics and steam engines once thundered along this corridor; today the same rails host 21st-century Acela II 'Avelia Liberty' trainsets.",
]


def get_land_facts_for_empty_state(n: int = 3) -> list:
    """Random rail facts for the LandDex ticker."""
    return random.sample(RAIL_FACTS, min(n, len(RAIL_FACTS)))


# ===========================================================================
# EtherDex — radio lore for the ticker
# ===========================================================================

ETHER_FACTS = [
    # -- the invisible neighborhood ------------------------------------------
    "Right now, invisible radio waves from dozens of machines are passing through your body. The kiosk hears them.",
    "Every modern car tire has a radio in it — tire-pressure sensors chirp their ID as cars roll past the house.",
    "Your neighbor's wireless weather station broadcasts the temperature in the clear — anyone with a $30 radio can read it.",
    "Smart utility meters chirp their readings all day on 915 MHz — every house on the street, thousands of times a day.",
    "Cheap RTL-SDR dongles were designed as European TV tuners — hackers discovered they could hear EVERYTHING.",
    "The FCC calls 433 MHz gear 'Part 15 devices' — allowed to whisper, forbidden to shout, and required to accept all interference.",
    "Radio waves travel at the speed of light: a signal from that passing car reached the kiosk in about 30 nanoseconds.",
    "A quarter-wave antenna for 433 MHz is just 16.5 centimeters — physics sets the size of every antenna you see.",
    # -- history ----------------------------------------------------------------
    "Marconi sent the first transatlantic signal in 1901 — the letter 'S'. Physicists said Earth's curve made it impossible. The ionosphere disagreed.",
    "The first voice ever broadcast was Christmas Eve 1906 — ship operators expecting Morse code suddenly heard a violin playing 'O Holy Night'.",
    "Nikola Tesla demonstrated a radio-controlled boat in 1898 — the crowd suspected a trained monkey was hidden inside.",
    "Titanic's operators tapped out both 'CQD' and the newer 'SOS' as she sank. Within months, Congress required radios on every large ship.",
    "Early transmitters were literal SPARKS jumping a gap — they splattered noise across the whole spectrum and were outlawed by 1927.",
    "Orson Welles' 1938 'War of the Worlds' radio play was staged as fake news bulletins — some listeners fled a fictional Martian invasion of New Jersey.",
    "Bluetooth is named after Harald Bluetooth, a 10th-century Danish king who united the tribes. The logo is his initials in runes.",
    "Hollywood star Hedy Lamarr co-invented frequency hopping in WWII to protect torpedo radio signals — the ancestor of Bluetooth and WiFi.",
    "During the World Wars, soldiers built 'foxhole radios' from a razor blade, a pencil stub, and wire — a working receiver, no battery.",
    "A crystal radio needs NO power at all — the radio wave itself carries enough energy to whisper into an earphone.",
    # -- microwaves ----------------------------------------------------------------
    "The microwave oven exists because radar engineer Percy Spencer walked past a magnetron in 1945 and the chocolate bar in his pocket melted.",
    "Your microwave, WiFi, and Bluetooth all crowd the same 2.4 GHz band — that's why popcorn time can stutter a movie stream.",
    "Microwaves don't cook from the inside out — they penetrate about an inch, and the middle cooks by plain old heat conduction.",
    "A microwave oven is a 1,000-watt radio transmitter inside a Faraday cage. The door mesh has holes too small for 2.4 GHz waves to squeeze through.",
    "About one percent of old analog TV static was the cosmic microwave background — the actual afterglow of the Big Bang, on channel 3.",
    # -- weird -----------------------------------------------------------------------
    "Number stations still haunt shortwave: robotic voices reading endless digits, almost certainly messages to spies. No government admits to them.",
    "UVB-76, 'The Buzzer', has droned from Russia since the 1970s. Rarely, a live voice breaks in to read names and numbers. Purpose: still unknown.",
    "Hams sometimes hear their own transmission echo back seconds later — 'Long Delayed Echoes', unexplained for a century and counting.",
    "The Navy talks to submerged submarines using waves so long that a single wavelength is bigger than Connecticut.",
    "The 'Wow!' signal — 72 seconds of intense narrowband radio from deep space, 1977 — never repeated, never explained.",
    "AM stations reach 10× farther at night: a layer of the ionosphere that absorbs their waves literally evaporates at sunset.",
    "In 1903, a magician hijacked Marconi's 'secure' wireless demo and transmitted insults in Morse — history's first radio hack.",
    "Aircraft transponders, ship AIS, train telemetry, tire sensors, weather stations: this kiosk now hears five radio languages at once.",
]


def get_ether_facts_for_empty_state(n: int = 3) -> list:
    """Random radio facts for the EtherDex ticker."""
    return random.sample(ETHER_FACTS, min(n, len(ETHER_FACTS)))
