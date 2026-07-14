"""Reference spec sheets for common aircraft types, keyed by ICAO type code.

Used by the Dex detail page to show *real* aircraft stats (max speed, range,
service ceiling, max seats) instead of made-up game numbers.

Figures are approximate, published type specs — good enough for a "dex" entry.
Fields per entry:
    name      human model name
    role      short role label
    speed_kt  approx max/cruise speed in knots
    range_nm  max range in nautical miles
    ceiling_ft service ceiling in feet
    seats     typical max seats / passengers
    engines   number of engines
"""

from __future__ import annotations

from typing import Any, Dict, Optional

# Normalization maxes for the spec bars on the detail page.
SPEC_MAX = {
    "speed_kt": 600.0,
    "range_nm": 9000.0,
    "ceiling_ft": 51000.0,
    "seats": 600.0,
}


SPECS: Dict[str, Dict[str, Any]] = {
    # ---- General aviation (singles / light twins) ----
    "C150": {"name": "Cessna 150", "role": "Trainer", "speed_kt": 109, "range_nm": 350, "ceiling_ft": 14000, "seats": 2, "engines": 1},
    "C152": {"name": "Cessna 152", "role": "Trainer", "speed_kt": 110, "range_nm": 415, "ceiling_ft": 14700, "seats": 2, "engines": 1},
    "C172": {"name": "Cessna 172 Skyhawk", "role": "Light GA", "speed_kt": 163, "range_nm": 640, "ceiling_ft": 14000, "seats": 4, "engines": 1},
    "C82R": {"name": "Cessna 182 RG", "role": "Light GA", "speed_kt": 156, "range_nm": 1025, "ceiling_ft": 17700, "seats": 4, "engines": 1},
    "C182": {"name": "Cessna 182 Skylane", "role": "Light GA", "speed_kt": 150, "range_nm": 930, "ceiling_ft": 18100, "seats": 4, "engines": 1},
    "C206": {"name": "Cessna 206 Stationair", "role": "Utility GA", "speed_kt": 151, "range_nm": 730, "ceiling_ft": 15700, "seats": 6, "engines": 1},
    "C210": {"name": "Cessna 210 Centurion", "role": "Light GA", "speed_kt": 174, "range_nm": 900, "ceiling_ft": 17300, "seats": 6, "engines": 1},
    "SR20": {"name": "Cirrus SR20", "role": "Light GA", "speed_kt": 155, "range_nm": 709, "ceiling_ft": 17500, "seats": 5, "engines": 1},
    "SR22": {"name": "Cirrus SR22", "role": "Light GA", "speed_kt": 183, "range_nm": 1049, "ceiling_ft": 17500, "seats": 5, "engines": 1},
    "S22T": {"name": "Cirrus SR22T", "role": "Light GA", "speed_kt": 213, "range_nm": 1021, "ceiling_ft": 25000, "seats": 5, "engines": 1},
    "DA40": {"name": "Diamond DA40", "role": "Light GA", "speed_kt": 150, "range_nm": 720, "ceiling_ft": 16400, "seats": 4, "engines": 1},
    "DA42": {"name": "Diamond DA42 TwinStar", "role": "Light Twin", "speed_kt": 197, "range_nm": 1300, "ceiling_ft": 18000, "seats": 4, "engines": 2},
    "PA28": {"name": "Piper Cherokee / Archer", "role": "Light GA", "speed_kt": 128, "range_nm": 522, "ceiling_ft": 14000, "seats": 4, "engines": 1},
    "PA32": {"name": "Piper Saratoga", "role": "Light GA", "speed_kt": 168, "range_nm": 1000, "ceiling_ft": 16700, "seats": 6, "engines": 1},
    "PA44": {"name": "Piper Seminole", "role": "Light Twin", "speed_kt": 162, "range_nm": 700, "ceiling_ft": 15000, "seats": 4, "engines": 2},
    "PA46": {"name": "Piper Malibu / Meridian", "role": "High-perf GA", "speed_kt": 260, "range_nm": 1340, "ceiling_ft": 30000, "seats": 6, "engines": 1},
    "BE33": {"name": "Beechcraft Bonanza 33", "role": "Light GA", "speed_kt": 176, "range_nm": 900, "ceiling_ft": 18000, "seats": 5, "engines": 1},
    "BE35": {"name": "Beechcraft Bonanza V35", "role": "Light GA", "speed_kt": 176, "range_nm": 900, "ceiling_ft": 18000, "seats": 5, "engines": 1},
    "BE36": {"name": "Beechcraft Bonanza A36", "role": "Light GA", "speed_kt": 176, "range_nm": 920, "ceiling_ft": 18500, "seats": 6, "engines": 1},
    "BE58": {"name": "Beechcraft Baron 58", "role": "Light Twin", "speed_kt": 200, "range_nm": 1480, "ceiling_ft": 20688, "seats": 6, "engines": 2},
    "M20P": {"name": "Mooney M20", "role": "Light GA", "speed_kt": 174, "range_nm": 1000, "ceiling_ft": 18000, "seats": 4, "engines": 1},

    # ---- Turboprops ----
    "BE20": {"name": "Beechcraft King Air 200", "role": "Turboprop Twin", "speed_kt": 290, "range_nm": 1580, "ceiling_ft": 35000, "seats": 13, "engines": 2},
    "B350": {"name": "Beechcraft King Air 350", "role": "Turboprop Twin", "speed_kt": 312, "range_nm": 1806, "ceiling_ft": 35000, "seats": 11, "engines": 2},
    "PC12": {"name": "Pilatus PC-12", "role": "Turboprop Single", "speed_kt": 290, "range_nm": 1845, "ceiling_ft": 30000, "seats": 9, "engines": 1},
    "TBM9": {"name": "Daher TBM 900", "role": "Turboprop Single", "speed_kt": 330, "range_nm": 1730, "ceiling_ft": 31000, "seats": 6, "engines": 1},
    "C208": {"name": "Cessna 208 Caravan", "role": "Utility Turboprop", "speed_kt": 186, "range_nm": 1070, "ceiling_ft": 25000, "seats": 14, "engines": 1},
    "AT43": {"name": "ATR 42", "role": "Regional Turboprop", "speed_kt": 268, "range_nm": 840, "ceiling_ft": 25000, "seats": 50, "engines": 2},
    "AT72": {"name": "ATR 72", "role": "Regional Turboprop", "speed_kt": 276, "range_nm": 825, "ceiling_ft": 25000, "seats": 78, "engines": 2},
    "AT76": {"name": "ATR 72-600", "role": "Regional Turboprop", "speed_kt": 276, "range_nm": 825, "ceiling_ft": 25000, "seats": 78, "engines": 2},
    "DH8D": {"name": "Bombardier Dash 8 Q400", "role": "Regional Turboprop", "speed_kt": 360, "range_nm": 1100, "ceiling_ft": 27000, "seats": 90, "engines": 2},
    "SF34": {"name": "Saab 340", "role": "Regional Turboprop", "speed_kt": 250, "range_nm": 935, "ceiling_ft": 25000, "seats": 34, "engines": 2},

    # ---- Business jets ----
    "C25A": {"name": "Cessna CitationJet CJ2", "role": "Business Jet", "speed_kt": 410, "range_nm": 1600, "ceiling_ft": 45000, "seats": 7, "engines": 2},
    "C25B": {"name": "Cessna Citation CJ3", "role": "Business Jet", "speed_kt": 416, "range_nm": 1875, "ceiling_ft": 45000, "seats": 9, "engines": 2},
    "C25C": {"name": "Cessna Citation CJ4", "role": "Business Jet", "speed_kt": 451, "range_nm": 2165, "ceiling_ft": 45000, "seats": 10, "engines": 2},
    "C56X": {"name": "Cessna Citation Excel / XLS", "role": "Business Jet", "speed_kt": 441, "range_nm": 2100, "ceiling_ft": 45000, "seats": 9, "engines": 2},
    "C68A": {"name": "Cessna Citation Latitude", "role": "Business Jet", "speed_kt": 446, "range_nm": 2700, "ceiling_ft": 45000, "seats": 9, "engines": 2},
    "C700": {"name": "Cessna Citation Longitude", "role": "Business Jet", "speed_kt": 476, "range_nm": 3500, "ceiling_ft": 45000, "seats": 12, "engines": 2},
    "E55P": {"name": "Embraer Phenom 300", "role": "Business Jet", "speed_kt": 453, "range_nm": 2010, "ceiling_ft": 45000, "seats": 9, "engines": 2},
    "CL35": {"name": "Bombardier Challenger 350", "role": "Business Jet", "speed_kt": 470, "range_nm": 3200, "ceiling_ft": 45000, "seats": 10, "engines": 2},
    "CL60": {"name": "Bombardier Challenger 605", "role": "Business Jet", "speed_kt": 470, "range_nm": 4000, "ceiling_ft": 41000, "seats": 12, "engines": 2},
    "LJ45": {"name": "Learjet 45", "role": "Business Jet", "speed_kt": 465, "range_nm": 1710, "ceiling_ft": 51000, "seats": 9, "engines": 2},
    "F2TH": {"name": "Dassault Falcon 2000", "role": "Business Jet", "speed_kt": 482, "range_nm": 4000, "ceiling_ft": 47000, "seats": 10, "engines": 2},
    "GLF5": {"name": "Gulfstream G550", "role": "Heavy Business Jet", "speed_kt": 488, "range_nm": 6750, "ceiling_ft": 51000, "seats": 16, "engines": 2},
    "GLF6": {"name": "Gulfstream G650", "role": "Heavy Business Jet", "speed_kt": 516, "range_nm": 7000, "ceiling_ft": 51000, "seats": 18, "engines": 2},
    "GLEX": {"name": "Bombardier Global Express", "role": "Heavy Business Jet", "speed_kt": 488, "range_nm": 6000, "ceiling_ft": 51000, "seats": 17, "engines": 2},

    # ---- Airliners (narrowbody) ----
    "B737": {"name": "Boeing 737", "role": "Narrowbody", "speed_kt": 470, "range_nm": 3000, "ceiling_ft": 41000, "seats": 215, "engines": 2},
    "B738": {"name": "Boeing 737-800", "role": "Narrowbody", "speed_kt": 470, "range_nm": 2935, "ceiling_ft": 41000, "seats": 189, "engines": 2},
    "B739": {"name": "Boeing 737-900", "role": "Narrowbody", "speed_kt": 470, "range_nm": 2950, "ceiling_ft": 41000, "seats": 220, "engines": 2},
    "B38M": {"name": "Boeing 737 MAX 8", "role": "Narrowbody", "speed_kt": 470, "range_nm": 3550, "ceiling_ft": 41000, "seats": 189, "engines": 2},
    "B39M": {"name": "Boeing 737 MAX 9", "role": "Narrowbody", "speed_kt": 470, "range_nm": 3300, "ceiling_ft": 41000, "seats": 220, "engines": 2},
    "A319": {"name": "Airbus A319", "role": "Narrowbody", "speed_kt": 470, "range_nm": 3700, "ceiling_ft": 39000, "seats": 156, "engines": 2},
    "A320": {"name": "Airbus A320", "role": "Narrowbody", "speed_kt": 470, "range_nm": 3300, "ceiling_ft": 39000, "seats": 180, "engines": 2},
    "A321": {"name": "Airbus A321", "role": "Narrowbody", "speed_kt": 470, "range_nm": 3200, "ceiling_ft": 39000, "seats": 220, "engines": 2},
    "A20N": {"name": "Airbus A320neo", "role": "Narrowbody", "speed_kt": 470, "range_nm": 3500, "ceiling_ft": 39800, "seats": 195, "engines": 2},
    "A21N": {"name": "Airbus A321neo", "role": "Narrowbody", "speed_kt": 470, "range_nm": 4000, "ceiling_ft": 39800, "seats": 244, "engines": 2},
    "E170": {"name": "Embraer 170", "role": "Regional Jet", "speed_kt": 470, "range_nm": 2150, "ceiling_ft": 41000, "seats": 80, "engines": 2},
    "E75L": {"name": "Embraer 175", "role": "Regional Jet", "speed_kt": 470, "range_nm": 2200, "ceiling_ft": 41000, "seats": 88, "engines": 2},
    "E190": {"name": "Embraer 190", "role": "Regional Jet", "speed_kt": 470, "range_nm": 2850, "ceiling_ft": 41000, "seats": 114, "engines": 2},
    "CRJ2": {"name": "Bombardier CRJ200", "role": "Regional Jet", "speed_kt": 470, "range_nm": 1700, "ceiling_ft": 41000, "seats": 50, "engines": 2},
    "CRJ7": {"name": "Bombardier CRJ700", "role": "Regional Jet", "speed_kt": 470, "range_nm": 1700, "ceiling_ft": 41000, "seats": 78, "engines": 2},
    "CRJ9": {"name": "Bombardier CRJ900", "role": "Regional Jet", "speed_kt": 470, "range_nm": 1550, "ceiling_ft": 41000, "seats": 90, "engines": 2},
    "B752": {"name": "Boeing 757-200", "role": "Narrowbody", "speed_kt": 493, "range_nm": 3900, "ceiling_ft": 42000, "seats": 239, "engines": 2},

    # ---- Airliners (widebody) ----
    "B763": {"name": "Boeing 767-300", "role": "Widebody", "speed_kt": 470, "range_nm": 5980, "ceiling_ft": 43100, "seats": 269, "engines": 2},
    "B772": {"name": "Boeing 777-200", "role": "Widebody", "speed_kt": 490, "range_nm": 5240, "ceiling_ft": 43100, "seats": 314, "engines": 2},
    "B77W": {"name": "Boeing 777-300ER", "role": "Widebody", "speed_kt": 490, "range_nm": 7370, "ceiling_ft": 43100, "seats": 396, "engines": 2},
    "B788": {"name": "Boeing 787-8 Dreamliner", "role": "Widebody", "speed_kt": 490, "range_nm": 7355, "ceiling_ft": 43000, "seats": 248, "engines": 2},
    "B789": {"name": "Boeing 787-9 Dreamliner", "role": "Widebody", "speed_kt": 490, "range_nm": 7635, "ceiling_ft": 43000, "seats": 296, "engines": 2},
    "A332": {"name": "Airbus A330-200", "role": "Widebody", "speed_kt": 470, "range_nm": 7250, "ceiling_ft": 41450, "seats": 247, "engines": 2},
    "A333": {"name": "Airbus A330-300", "role": "Widebody", "speed_kt": 470, "range_nm": 6350, "ceiling_ft": 41450, "seats": 277, "engines": 2},
    "A359": {"name": "Airbus A350-900", "role": "Widebody", "speed_kt": 488, "range_nm": 8100, "ceiling_ft": 43100, "seats": 315, "engines": 2},
    "B744": {"name": "Boeing 747-400", "role": "Heavy Widebody", "speed_kt": 490, "range_nm": 7260, "ceiling_ft": 45000, "seats": 416, "engines": 4},
    "B748": {"name": "Boeing 747-8", "role": "Heavy Widebody", "speed_kt": 490, "range_nm": 7730, "ceiling_ft": 43100, "seats": 467, "engines": 4},
    "A388": {"name": "Airbus A380", "role": "Superheavy", "speed_kt": 516, "range_nm": 8000, "ceiling_ft": 43000, "seats": 525, "engines": 4},

    # ---- Helicopters ----
    "R44": {"name": "Robinson R44", "role": "Light Helicopter", "speed_kt": 130, "range_nm": 300, "ceiling_ft": 14000, "seats": 4, "engines": 1},
    "R66": {"name": "Robinson R66", "role": "Light Helicopter", "speed_kt": 140, "range_nm": 350, "ceiling_ft": 14000, "seats": 5, "engines": 1},
    "B06": {"name": "Bell 206 JetRanger", "role": "Light Helicopter", "speed_kt": 120, "range_nm": 374, "ceiling_ft": 13500, "seats": 5, "engines": 1},
    "B407": {"name": "Bell 407", "role": "Light Helicopter", "speed_kt": 140, "range_nm": 337, "ceiling_ft": 18690, "seats": 7, "engines": 1},
    "B429": {"name": "Bell 429", "role": "Light Twin Helicopter", "speed_kt": 155, "range_nm": 411, "ceiling_ft": 20000, "seats": 8, "engines": 2},
    "EC35": {"name": "Airbus H135", "role": "Twin Helicopter", "speed_kt": 137, "range_nm": 343, "ceiling_ft": 20000, "seats": 8, "engines": 2},
    "EC45": {"name": "Airbus H145", "role": "Twin Helicopter", "speed_kt": 137, "range_nm": 351, "ceiling_ft": 20000, "seats": 11, "engines": 2},
    "H135": {"name": "Airbus H135", "role": "Twin Helicopter", "speed_kt": 137, "range_nm": 343, "ceiling_ft": 20000, "seats": 8, "engines": 2},
    "H145": {"name": "Airbus H145", "role": "Twin Helicopter", "speed_kt": 137, "range_nm": 351, "ceiling_ft": 20000, "seats": 11, "engines": 2},
    "AS50": {"name": "Airbus AS350 Écureuil", "role": "Light Helicopter", "speed_kt": 133, "range_nm": 357, "ceiling_ft": 16100, "seats": 6, "engines": 1},
    "S76": {"name": "Sikorsky S-76", "role": "Twin Helicopter", "speed_kt": 155, "range_nm": 411, "ceiling_ft": 13800, "seats": 13, "engines": 2},
    "S92": {"name": "Sikorsky S-92", "role": "Heavy Helicopter", "speed_kt": 165, "range_nm": 539, "ceiling_ft": 15000, "seats": 19, "engines": 2},
    "S61": {"name": "Sikorsky S-61 / Sea King", "role": "Heavy Helicopter", "speed_kt": 120, "range_nm": 450, "ceiling_ft": 12500, "seats": 26, "engines": 2},
    "S70": {"name": "Sikorsky S-70 / Black Hawk", "role": "Utility Helicopter", "speed_kt": 159, "range_nm": 320, "ceiling_ft": 19000, "seats": 14, "engines": 2},
    "H53": {"name": "Sikorsky CH-53 / CH-53K", "role": "Heavy-lift Helicopter", "speed_kt": 150, "range_nm": 540, "ceiling_ft": 16750, "seats": 37, "engines": 3},
    "R22": {"name": "Robinson R22", "role": "Light Helicopter", "speed_kt": 96, "range_nm": 240, "ceiling_ft": 14000, "seats": 2, "engines": 1},
    "B47": {"name": "Bell 47", "role": "Light Helicopter", "speed_kt": 73, "range_nm": 215, "ceiling_ft": 10500, "seats": 3, "engines": 1},
    "B205": {"name": "Bell 205 / UH-1 Huey", "role": "Utility Helicopter", "speed_kt": 120, "range_nm": 300, "ceiling_ft": 19000, "seats": 15, "engines": 1},
    "B212": {"name": "Bell 212", "role": "Twin Helicopter", "speed_kt": 120, "range_nm": 273, "ceiling_ft": 13000, "seats": 15, "engines": 2},
    "B412": {"name": "Bell 412", "role": "Twin Helicopter", "speed_kt": 122, "range_nm": 402, "ceiling_ft": 20000, "seats": 15, "engines": 2},
    "B222": {"name": "Bell 222", "role": "Twin Helicopter", "speed_kt": 150, "range_nm": 360, "ceiling_ft": 15000, "seats": 10, "engines": 2},
    "B230": {"name": "Bell 230", "role": "Twin Helicopter", "speed_kt": 140, "range_nm": 370, "ceiling_ft": 15000, "seats": 10, "engines": 2},
    "B427": {"name": "Bell 427", "role": "Light Twin Helicopter", "speed_kt": 140, "range_nm": 394, "ceiling_ft": 18000, "seats": 8, "engines": 2},
    "B430": {"name": "Bell 430", "role": "Twin Helicopter", "speed_kt": 140, "range_nm": 350, "ceiling_ft": 16000, "seats": 10, "engines": 2},
    "B505": {"name": "Bell 505 Jet Ranger X", "role": "Light Helicopter", "speed_kt": 125, "range_nm": 340, "ceiling_ft": 18000, "seats": 5, "engines": 1},
    "EC30": {"name": "Airbus H130", "role": "Light Helicopter", "speed_kt": 130, "range_nm": 330, "ceiling_ft": 16000, "seats": 7, "engines": 1},
    "AS65": {"name": "Airbus AS365 Dauphin", "role": "Twin Helicopter", "speed_kt": 145, "range_nm": 430, "ceiling_ft": 15000, "seats": 12, "engines": 2},
    "AS32": {"name": "Airbus AS332 Super Puma", "role": "Heavy Helicopter", "speed_kt": 150, "range_nm": 460, "ceiling_ft": 15000, "seats": 24, "engines": 2},
    "EC55": {"name": "Airbus H155", "role": "Twin Helicopter", "speed_kt": 175, "range_nm": 432, "ceiling_ft": 15000, "seats": 13, "engines": 2},
    "A109": {"name": "Leonardo A109", "role": "Light Twin Helicopter", "speed_kt": 168, "range_nm": 513, "ceiling_ft": 19600, "seats": 8, "engines": 2},
    "A119": {"name": "Leonardo AW119 Koala", "role": "Light Helicopter", "speed_kt": 134, "range_nm": 525, "ceiling_ft": 15000, "seats": 7, "engines": 1},
    "A139": {"name": "Leonardo AW139", "role": "Twin Helicopter", "speed_kt": 165, "range_nm": 573, "ceiling_ft": 20000, "seats": 15, "engines": 2},
    "A169": {"name": "Leonardo AW169", "role": "Twin Helicopter", "speed_kt": 145, "range_nm": 432, "ceiling_ft": 15000, "seats": 10, "engines": 2},
    "A189": {"name": "Leonardo AW189", "role": "Heavy Helicopter", "speed_kt": 145, "range_nm": 490, "ceiling_ft": 20000, "seats": 19, "engines": 2},
    "H500": {"name": "MD 500", "role": "Light Helicopter", "speed_kt": 130, "range_nm": 232, "ceiling_ft": 16000, "seats": 5, "engines": 1},
    "EXPL": {"name": "MD 900 Explorer", "role": "Twin Helicopter", "speed_kt": 134, "range_nm": 350, "ceiling_ft": 17000, "seats": 8, "engines": 2},
    "H47": {"name": "Boeing CH-47 Chinook", "role": "Heavy-lift Helicopter", "speed_kt": 170, "range_nm": 400, "ceiling_ft": 18500, "seats": 33, "engines": 2},

    # ---- Military (a sampling — KBDR / Sikorsky country) ----
    "C130": {"name": "Lockheed C-130 Hercules", "role": "Military Transport", "speed_kt": 320, "range_nm": 2050, "ceiling_ft": 33000, "seats": 92, "engines": 4},
    "C17": {"name": "Boeing C-17 Globemaster III", "role": "Strategic Airlift", "speed_kt": 450, "range_nm": 2780, "ceiling_ft": 45000, "seats": 102, "engines": 4},
    "K35R": {"name": "Boeing KC-135 Stratotanker", "role": "Aerial Tanker", "speed_kt": 530, "range_nm": 1500, "ceiling_ft": 50000, "seats": 80, "engines": 4},
    "P8": {"name": "Boeing P-8 Poseidon", "role": "Maritime Patrol", "speed_kt": 490, "range_nm": 1200, "ceiling_ft": 41000, "seats": 9, "engines": 2},
    "F16": {"name": "F-16 Fighting Falcon", "role": "Fighter", "speed_kt": 1147, "range_nm": 2000, "ceiling_ft": 50000, "seats": 1, "engines": 1},
    "H60": {"name": "Sikorsky UH-60 Black Hawk", "role": "Military Helicopter", "speed_kt": 159, "range_nm": 320, "ceiling_ft": 19000, "seats": 14, "engines": 2},
    "UH60": {"name": "Sikorsky UH-60 Black Hawk", "role": "Military Helicopter", "speed_kt": 159, "range_nm": 320, "ceiling_ft": 19000, "seats": 14, "engines": 2},

    # ---- More airliners (widebody variants) ----
    "A338": {"name": "Airbus A330-800neo", "role": "Widebody", "speed_kt": 470, "range_nm": 8150, "ceiling_ft": 41450, "seats": 257, "engines": 2},
    "A339": {"name": "Airbus A330-900neo", "role": "Widebody", "speed_kt": 470, "range_nm": 7200, "ceiling_ft": 41450, "seats": 287, "engines": 2},
    "A342": {"name": "Airbus A340-200", "role": "Heavy Widebody", "speed_kt": 487, "range_nm": 6700, "ceiling_ft": 41450, "seats": 261, "engines": 4},
    "A343": {"name": "Airbus A340-300", "role": "Heavy Widebody", "speed_kt": 487, "range_nm": 7400, "ceiling_ft": 41450, "seats": 295, "engines": 4},
    "A345": {"name": "Airbus A340-500", "role": "Heavy Widebody", "speed_kt": 488, "range_nm": 9000, "ceiling_ft": 41450, "seats": 313, "engines": 4},
    "A346": {"name": "Airbus A340-600", "role": "Heavy Widebody", "speed_kt": 488, "range_nm": 7900, "ceiling_ft": 41450, "seats": 380, "engines": 4},
    "A35K": {"name": "Airbus A350-1000", "role": "Widebody", "speed_kt": 488, "range_nm": 8700, "ceiling_ft": 43100, "seats": 410, "engines": 2},
    "B762": {"name": "Boeing 767-200", "role": "Widebody", "speed_kt": 470, "range_nm": 6590, "ceiling_ft": 43100, "seats": 245, "engines": 2},
    "B764": {"name": "Boeing 767-400", "role": "Widebody", "speed_kt": 470, "range_nm": 5625, "ceiling_ft": 43100, "seats": 304, "engines": 2},
    "B77L": {"name": "Boeing 777-200LR", "role": "Widebody", "speed_kt": 490, "range_nm": 8555, "ceiling_ft": 43100, "seats": 317, "engines": 2},
    "B78X": {"name": "Boeing 787-10 Dreamliner", "role": "Widebody", "speed_kt": 490, "range_nm": 6430, "ceiling_ft": 43000, "seats": 336, "engines": 2},
    "MD11": {"name": "McDonnell Douglas MD-11", "role": "Heavy Widebody", "speed_kt": 473, "range_nm": 6840, "ceiling_ft": 43000, "seats": 293, "engines": 3},
    "DC10": {"name": "McDonnell Douglas DC-10", "role": "Heavy Widebody", "speed_kt": 470, "range_nm": 5200, "ceiling_ft": 42000, "seats": 270, "engines": 3},

    # ---- More airliners (narrowbody / regional) ----
    "B753": {"name": "Boeing 757-300", "role": "Narrowbody", "speed_kt": 493, "range_nm": 3400, "ceiling_ft": 42000, "seats": 280, "engines": 2},
    "B712": {"name": "Boeing 717", "role": "Regional Jet", "speed_kt": 438, "range_nm": 2060, "ceiling_ft": 37000, "seats": 134, "engines": 2},
    "MD82": {"name": "McDonnell Douglas MD-82", "role": "Narrowbody", "speed_kt": 440, "range_nm": 2050, "ceiling_ft": 37000, "seats": 172, "engines": 2},
    "MD83": {"name": "McDonnell Douglas MD-83", "role": "Narrowbody", "speed_kt": 440, "range_nm": 2500, "ceiling_ft": 37000, "seats": 172, "engines": 2},
    "MD88": {"name": "McDonnell Douglas MD-88", "role": "Narrowbody", "speed_kt": 440, "range_nm": 2050, "ceiling_ft": 37000, "seats": 150, "engines": 2},
    "MD90": {"name": "McDonnell Douglas MD-90", "role": "Narrowbody", "speed_kt": 440, "range_nm": 2400, "ceiling_ft": 37000, "seats": 158, "engines": 2},
    "BCS1": {"name": "Airbus A220-100", "role": "Narrowbody", "speed_kt": 470, "range_nm": 3400, "ceiling_ft": 41000, "seats": 135, "engines": 2},
    "BCS3": {"name": "Airbus A220-300", "role": "Narrowbody", "speed_kt": 470, "range_nm": 3350, "ceiling_ft": 41000, "seats": 160, "engines": 2},
    "E145": {"name": "Embraer ERJ-145", "role": "Regional Jet", "speed_kt": 450, "range_nm": 1550, "ceiling_ft": 37000, "seats": 50, "engines": 2},
    "E135": {"name": "Embraer ERJ-135", "role": "Regional Jet", "speed_kt": 450, "range_nm": 1750, "ceiling_ft": 37000, "seats": 37, "engines": 2},
    "E195": {"name": "Embraer 195", "role": "Regional Jet", "speed_kt": 470, "range_nm": 2300, "ceiling_ft": 41000, "seats": 124, "engines": 2},
    "E290": {"name": "Embraer E190-E2", "role": "Regional Jet", "speed_kt": 470, "range_nm": 2850, "ceiling_ft": 41000, "seats": 114, "engines": 2},
    "E295": {"name": "Embraer E195-E2", "role": "Regional Jet", "speed_kt": 470, "range_nm": 2600, "ceiling_ft": 41000, "seats": 146, "engines": 2},
    "RJ85": {"name": "Avro RJ85", "role": "Regional Jet", "speed_kt": 412, "range_nm": 1500, "ceiling_ft": 35000, "seats": 100, "engines": 4},
    "F100": {"name": "Fokker 100", "role": "Regional Jet", "speed_kt": 445, "range_nm": 1680, "ceiling_ft": 35000, "seats": 109, "engines": 2},
    "F70": {"name": "Fokker 70", "role": "Regional Jet", "speed_kt": 445, "range_nm": 1900, "ceiling_ft": 35000, "seats": 80, "engines": 2},
    "SW4": {"name": "Fairchild Swearingen Metroliner", "role": "Commuter Turboprop", "speed_kt": 248, "range_nm": 1000, "ceiling_ft": 25000, "seats": 19, "engines": 2},
    "BE99": {"name": "Beechcraft 99", "role": "Commuter Turboprop", "speed_kt": 247, "range_nm": 910, "ceiling_ft": 25000, "seats": 15, "engines": 2},
    "B190": {"name": "Beechcraft 1900", "role": "Commuter Turboprop", "speed_kt": 280, "range_nm": 1500, "ceiling_ft": 25000, "seats": 19, "engines": 2},
    "JS41": {"name": "BAe Jetstream 41", "role": "Commuter Turboprop", "speed_kt": 295, "range_nm": 800, "ceiling_ft": 26000, "seats": 29, "engines": 2},

    # ---- More business jets / turboprops ----
    "C510": {"name": "Cessna Citation Mustang", "role": "Light Business Jet", "speed_kt": 340, "range_nm": 1150, "ceiling_ft": 41000, "seats": 5, "engines": 2},
    "C525": {"name": "Cessna CitationJet CJ1", "role": "Business Jet", "speed_kt": 389, "range_nm": 1300, "ceiling_ft": 41000, "seats": 6, "engines": 2},
    "C550": {"name": "Cessna Citation II", "role": "Business Jet", "speed_kt": 385, "range_nm": 1900, "ceiling_ft": 43000, "seats": 9, "engines": 2},
    "C650": {"name": "Cessna Citation III/VI/VII", "role": "Business Jet", "speed_kt": 470, "range_nm": 2000, "ceiling_ft": 51000, "seats": 9, "engines": 2},
    "C750": {"name": "Cessna Citation X", "role": "Business Jet", "speed_kt": 528, "range_nm": 3460, "ceiling_ft": 51000, "seats": 12, "engines": 2},
    "CL30": {"name": "Bombardier Challenger 300", "role": "Business Jet", "speed_kt": 470, "range_nm": 3100, "ceiling_ft": 45000, "seats": 9, "engines": 2},
    "GL7T": {"name": "Bombardier Global 7500", "role": "Heavy Business Jet", "speed_kt": 516, "range_nm": 7700, "ceiling_ft": 51000, "seats": 19, "engines": 2},
    "FA7X": {"name": "Dassault Falcon 7X", "role": "Heavy Business Jet", "speed_kt": 488, "range_nm": 5950, "ceiling_ft": 51000, "seats": 16, "engines": 3},
    "FA50": {"name": "Dassault Falcon 50", "role": "Business Jet", "speed_kt": 475, "range_nm": 3000, "ceiling_ft": 49000, "seats": 9, "engines": 3},
    "F900": {"name": "Dassault Falcon 900", "role": "Heavy Business Jet", "speed_kt": 480, "range_nm": 4500, "ceiling_ft": 51000, "seats": 12, "engines": 3},
    "LJ35": {"name": "Learjet 35", "role": "Business Jet", "speed_kt": 460, "range_nm": 2050, "ceiling_ft": 45000, "seats": 8, "engines": 2},
    "LJ60": {"name": "Learjet 60", "role": "Business Jet", "speed_kt": 466, "range_nm": 2400, "ceiling_ft": 51000, "seats": 8, "engines": 2},
    "PC24": {"name": "Pilatus PC-24", "role": "Light Business Jet", "speed_kt": 440, "range_nm": 2000, "ceiling_ft": 45000, "seats": 10, "engines": 2},
    "DHC6": {"name": "DHC-6 Twin Otter", "role": "Utility Turboprop", "speed_kt": 170, "range_nm": 770, "ceiling_ft": 25000, "seats": 19, "engines": 2},
    "PA31": {"name": "Piper Navajo", "role": "Light Twin", "speed_kt": 227, "range_nm": 1000, "ceiling_ft": 26300, "seats": 8, "engines": 2},

    # ---- More general aviation (singles & twins) ----
    "C310": {"name": "Cessna 310", "role": "Light Twin", "speed_kt": 220, "range_nm": 1500, "ceiling_ft": 19750, "seats": 6, "engines": 2},
    "C337": {"name": "Cessna 337 Skymaster", "role": "Light Twin", "speed_kt": 173, "range_nm": 1100, "ceiling_ft": 19500, "seats": 6, "engines": 2},
    "C414": {"name": "Cessna 414", "role": "Light Twin", "speed_kt": 235, "range_nm": 1320, "ceiling_ft": 30800, "seats": 8, "engines": 2},
    "C421": {"name": "Cessna 421 Golden Eagle", "role": "Light Twin", "speed_kt": 240, "range_nm": 1500, "ceiling_ft": 30200, "seats": 8, "engines": 2},
    "AA5": {"name": "Grumman American AA-5", "role": "Light GA", "speed_kt": 130, "range_nm": 600, "ceiling_ft": 13800, "seats": 4, "engines": 1},
    "BE76": {"name": "Beechcraft Duchess", "role": "Light Twin", "speed_kt": 154, "range_nm": 780, "ceiling_ft": 20000, "seats": 4, "engines": 2},
    "P28A": {"name": "Piper Cherokee 140/180", "role": "Light GA", "speed_kt": 124, "range_nm": 465, "ceiling_ft": 14000, "seats": 4, "engines": 1},
    "RV7": {"name": "Van's RV-7", "role": "Experimental", "speed_kt": 200, "range_nm": 800, "ceiling_ft": 20000, "seats": 2, "engines": 1},
    "RV8": {"name": "Van's RV-8", "role": "Experimental", "speed_kt": 200, "range_nm": 800, "ceiling_ft": 21500, "seats": 2, "engines": 1},

    # ---- Warbirds, biplanes & vintage ----
    "AN2": {"name": "Antonov An-2 (biplane)", "role": "Biplane Utility", "speed_kt": 139, "range_nm": 460, "ceiling_ft": 14400, "seats": 12, "engines": 1},
    "ST75": {"name": "Boeing/Stearman Model 75 (biplane)", "role": "Biplane Trainer", "speed_kt": 110, "range_nm": 430, "ceiling_ft": 11200, "seats": 2, "engines": 1},
    "PTS2": {"name": "Pitts Special S-2 (biplane)", "role": "Aerobatic Biplane", "speed_kt": 152, "range_nm": 270, "ceiling_ft": 21300, "seats": 2, "engines": 1},
    "PTSS": {"name": "Pitts Special S-1 (biplane)", "role": "Aerobatic Biplane", "speed_kt": 152, "range_nm": 270, "ceiling_ft": 22300, "seats": 1, "engines": 1},
    "WACO": {"name": "Waco classic biplane", "role": "Biplane", "speed_kt": 100, "range_nm": 300, "ceiling_ft": 12000, "seats": 3, "engines": 1},
    "DH82": {"name": "de Havilland Tiger Moth (biplane)", "role": "Biplane Trainer", "speed_kt": 90, "range_nm": 260, "ceiling_ft": 13600, "seats": 2, "engines": 1},
    "CALL": {"name": "Christen/Aviat Eagle (biplane)", "role": "Aerobatic Biplane", "speed_kt": 140, "range_nm": 350, "ceiling_ft": 17000, "seats": 2, "engines": 1},
    "P51": {"name": "North American P-51 Mustang", "role": "Warbird Fighter", "speed_kt": 380, "range_nm": 1000, "ceiling_ft": 41900, "seats": 1, "engines": 1},
    "SPIT": {"name": "Supermarine Spitfire", "role": "Warbird Fighter", "speed_kt": 330, "range_nm": 420, "ceiling_ft": 36500, "seats": 1, "engines": 1},
    "T6": {"name": "North American T-6 Texan", "role": "Warbird Trainer", "speed_kt": 180, "range_nm": 730, "ceiling_ft": 24200, "seats": 2, "engines": 1},
    "P40": {"name": "Curtiss P-40 Warhawk", "role": "Warbird Fighter", "speed_kt": 310, "range_nm": 650, "ceiling_ft": 29000, "seats": 1, "engines": 1},
    "YK52": {"name": "Yakovlev Yak-52", "role": "Warbird Trainer", "speed_kt": 154, "range_nm": 290, "ceiling_ft": 13100, "seats": 2, "engines": 1},
    "J3": {"name": "Piper J-3 Cub", "role": "Vintage GA", "speed_kt": 76, "range_nm": 220, "ceiling_ft": 11500, "seats": 2, "engines": 1},
    "PA18": {"name": "Piper PA-18 Super Cub", "role": "Utility GA", "speed_kt": 100, "range_nm": 460, "ceiling_ft": 16000, "seats": 2, "engines": 1},
    "DC3": {"name": "Douglas DC-3", "role": "Vintage Airliner", "speed_kt": 180, "range_nm": 1370, "ceiling_ft": 23200, "seats": 28, "engines": 2},

    # ---- More helicopters ----
    "H269": {"name": "Schweizer 269 / 300", "role": "Light Helicopter", "speed_kt": 86, "range_nm": 195, "ceiling_ft": 10200, "seats": 3, "engines": 1},
    "EC25": {"name": "Airbus H225 Super Puma", "role": "Heavy Helicopter", "speed_kt": 150, "range_nm": 460, "ceiling_ft": 15000, "seats": 24, "engines": 2},
}

# A few synonyms / variant codes that map to an existing entry.
_ALIASES = {
    "C72S": "C172", "C72R": "C172", "C162": "C152",
    "E75S": "E75L", "E175": "E75L",
    "AT75": "AT76", "B06T": "B06",
}


def get_specs(type_code: Optional[str]) -> Optional[Dict[str, Any]]:
    """Return the spec sheet for an ICAO type code, or None if unknown."""
    if not type_code:
        return None
    tc = type_code.upper().strip()
    if tc in SPECS:
        return SPECS[tc]
    if tc in _ALIASES and _ALIASES[tc] in SPECS:
        return SPECS[_ALIASES[tc]]
    return None


def spec_summary(type_code: Optional[str]) -> Optional[str]:
    """A one-line factual blurb generated from the spec sheet, e.g.:
    'The Airbus A330-900neo is a widebody with 2 engines, up to 287 seats,
    ~470 kt top speed, 7,200 nm range and a 41,450 ft ceiling.'
    Returns None if the type isn't in the spec table."""
    s = get_specs(type_code)
    if not s:
        return None
    role = (s.get("role") or "aircraft").lower()
    bits = []
    eng = s.get("engines")
    if eng:
        bits.append(f"{eng} engine" + ("s" if eng > 1 else ""))
    if s.get("seats"):
        bits.append(f"up to {s['seats']} seats")
    if s.get("speed_kt"):
        bits.append(f"~{s['speed_kt']} kt top speed")
    if s.get("range_nm"):
        bits.append(f"{s['range_nm']:,} nm range")
    if s.get("ceiling_ft"):
        bits.append(f"a {s['ceiling_ft']:,} ft ceiling")
    name = s.get("name", type_code)
    if bits:
        return f"The {name} is a {role} with " + ", ".join(bits) + "."
    return f"The {name} is a {role}."
