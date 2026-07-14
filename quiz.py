"""Professor's Quiz — hand-written multiple-choice questions for the kiosk.

Kid-friendly, drawn from the same lore as the facts ticker (KBDR, Long Island
Sound, aviation, ships, space). get_quiz() returns n random questions with
shuffled answer order; the correct index is included so the frontend can score
locally without another request.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List

# (question, correct answer, [wrong answers], domain)
QUESTIONS = [
    # --- Aviation / KBDR ----------------------------------------------------
    ("What does the airport code KBDR stand for?",
     "Bridgeport — Sikorsky Memorial Airport", ["Boulder Municipal", "Bedford Regional", "Baltimore Downtown"], "air"),
    ("Which helicopter maker is headquartered right next door in Stratford?",
     "Sikorsky", ["Boeing", "Bell", "Robinson"], "air"),
    ("What altitude do jets usually cruise at?",
     "About 35,000 feet", ["About 5,000 feet", "About 100,000 feet", "About 1 mile"], "air"),
    ("What does a squawk code of 7700 mean?",
     "General emergency", ["Everything is fine", "Landing soon", "Radio check"], "air"),
    ("Why do planes leave white trails (contrails) in the sky?",
     "Hot exhaust freezes into ice crystals in cold air", ["They're dumping fuel", "It's smoke", "Cloud seeding"], "air"),
    ("Which plane is nicknamed the 'Queen of the Skies'?",
     "Boeing 747", ["Airbus A320", "Cessna 172", "Concorde"], "air"),
    ("What makes a helicopter different from a plane?",
     "Spinning rotor blades create its lift", ["It has no engine", "It's always smaller", "It can't carry people"], "air"),
    ("What do pilots use ADS-B for?",
     "Broadcasting their position so others can see them", ["Ordering food", "Playing music", "Measuring fuel"], "air"),
    ("Igor Sikorsky, who built the first practical helicopter, came to Stratford from which country?",
     "Russia (Kyiv, then part of the Russian Empire)", ["France", "Brazil", "Japan"], "air"),
    ("What's the fastest passenger plane ever flown?",
     "Concorde — over twice the speed of sound", ["Boeing 737", "Piper Cub", "Airbus A380"], "air"),

    # --- Sea / Long Island Sound -------------------------------------------
    ("What body of water does SeaDex watch?",
     "Long Island Sound", ["The Pacific Ocean", "Lake Erie", "The Mississippi River"], "sea"),
    ("What is the Middle Ground (Stratford Shoal) in the middle of the Sound?",
     "A shallow reef with a lighthouse on it", ["A shipwreck", "An island town", "A whirlpool"], "sea"),
    ("What does AIS do on a ship?",
     "Broadcasts the ship's name, position and speed", ["Steers the ship", "Catches fish", "Makes it faster"], "sea"),
    ("What does a ship's 'knot' measure?",
     "Speed — one nautical mile per hour", ["Rope strength", "Depth", "Cargo weight"], "sea"),
    ("Which river empties into the Sound right at Stratford?",
     "The Housatonic River", ["The Hudson", "The Connecticut", "The Thames"], "sea"),
    ("What does it mean when a vessel is 'at anchor'?",
     "It's parked, held in place by an anchor", ["It's sinking", "It's racing", "It's fishing"], "sea"),
    ("What kind of ship carries liquid cargo like oil?",
     "A tanker", ["A tug", "A ferry", "A sailboat"], "sea"),
    ("What's a superyacht?",
     "A very large private luxury boat (80+ feet)", ["A Navy ship", "A speedboat", "A fishing trawler"], "sea"),

    # --- Space / AtmoDex ----------------------------------------------------
    ("How fast does the International Space Station circle the Earth?",
     "About 17,500 mph — one lap every 90 minutes", ["About 500 mph", "The speed of light", "It doesn't move"], "atmo"),
    ("What makes the Moon shine?",
     "It reflects sunlight", ["It's on fire", "It glows like a lightbulb", "City lights"], "atmo"),
    ("What is a meteor shower?",
     "Earth passing through comet dust that burns up in the sky", ["Rain from space", "Falling stars landing", "Satellite crashes"], "atmo"),
    ("Which planet is the brightest one we can see from here?",
     "Venus", ["Neptune", "Mercury", "Pluto"], "atmo"),
    ("What's the best time to see the ISS fly over?",
     "Just after sunset or before sunrise", ["Noon", "Midnight in winter only", "During rain"], "atmo"),
    ("What does the tide do about every 6 hours in the Sound?",
     "Switches between rising and falling", ["Stops completely", "Freezes", "Reverses the rivers"], "atmo"),
    ("Sirius is the brightest night star. How far away is it?",
     "About 8.6 light-years", ["Just past the Moon", "8.6 miles", "8.6 million miles"], "atmo"),
    ("What was the first satellite ever launched?",
     "Sputnik 1 (1957)", ["Apollo 11", "Hubble", "Voyager 1"], "atmo"),
]


def get_quiz(n: int = 5, domain: str = "all") -> List[Dict[str, Any]]:
    pool = [q for q in QUESTIONS if domain == "all" or q[3] == domain]
    picks = random.sample(pool, min(n, len(pool)))
    out = []
    for question, correct, wrong, dom in picks:
        options = [correct] + list(wrong)
        random.shuffle(options)
        out.append({
            "question": question,
            "options": options,
            "answer": options.index(correct),
            "domain": dom,
        })
    return out
