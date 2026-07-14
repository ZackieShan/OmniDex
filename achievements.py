"""SkyDex achievements — computed live from database counters (no new tables).

Each achievement maps a counter from Database.get_achievement_stats() to a
threshold. The frontend shows unlocked ones in color with progress bars on the
locked ones. Add new ones freely — they light up retroactively since they're
computed from history.
"""

from __future__ import annotations

from typing import Any, Dict, List

# (id, title, description, stat_key, threshold, icon, domain)
# icon is a small emoji-free label the frontend renders in a colored chip.
ACHIEVEMENTS = [
    # --- Air ---------------------------------------------------------------
    ("first_catch",   "First Catch!",      "Log your first aircraft",              "airframes",    1,   "1",   "air"),
    ("ten_up",        "Ten Up",            "Log 10 different aircraft",            "airframes",    10,  "10",  "air"),
    ("half_century",  "Half Century",      "Log 50 different aircraft",            "airframes",    50,  "50",  "air"),
    ("century",       "Century Club",      "Log 100 different aircraft",           "airframes",    100, "100", "air"),
    ("five_hundred",  "Ace Spotter",       "Log 500 different aircraft",           "airframes",    500, "500", "air"),
    ("heavy_metal",   "Heavy Metal",       "Log 10 heavy widebodies",              "heavies",      10,  "HVY", "air"),
    ("rotorhead",     "Rotorhead",         "Log 10 helicopters",                   "rotors",       10,  "ROT", "air"),
    ("sentinel_duty", "Sentinel Duty",     "Log 5 military aircraft",              "military",     5,   "MIL", "air"),
    ("night_owl",     "Night Owl",         "Catch 5 aircraft between 23:00-05:00", "night_catches", 5,  "OWL", "air"),
    ("responder",     "First Responder",   "Witness an emergency squawk",          "emergencies",  1,   "SOS", "air"),
    ("legendary",     "Legendary!",        "Log a legendary-rarity airframe",      "legendaries",  1,   "LEG", "air"),
    ("bonded",        "Best Friends",      "Bond with an airframe (40+ sightings)", "bonded",      1,   "BFF", "air"),
    ("rush_hour",     "Rush Hour",         "20 aircraft sightings in one day",     "best_day_air", 20,  "20+", "air"),

    # --- Sea ---------------------------------------------------------------
    ("first_vessel",  "Ahoy!",             "Log your first vessel",                "vessels",      1,   "1",   "sea"),
    ("harbormaster",  "Harbormaster",      "Log 25 different vessels",             "vessels",      25,  "25",  "sea"),
    ("fleet_admiral", "Fleet Admiral",     "Log 100 different vessels",            "vessels",      100, "100", "sea"),
    ("worldly_water", "Worldly Waters",    "Vessels from 5 different flags",       "sea_flags",    5,   "FLG", "sea"),
    ("yacht_club",    "Yacht Club",        "Spot a superyacht",                    "superyachts",  1,   "SY",  "sea"),
    ("full_sail",     "Full Sail",         "Log 10 sailing vessels",               "sailing",      10,  "SAIL", "sea"),
    ("variety_pack",  "Variety Pack",      "Log 6 different vessel categories",    "sea_categories", 6, "CAT", "sea"),
    ("regatta_day",   "Regatta Day",       "15 vessel sightings in one day",       "best_day_sea", 15,  "15+", "sea"),

    # --- Sky ---------------------------------------------------------------
    ("pass_logger",   "Station Keeper",    "Log 10 satellite passes",              "iss_passes",   10,  "ISS", "atmo"),
    ("mission_ctrl",  "Mission Control",   "Log 50 satellite passes",              "iss_passes",   50,  "50",  "atmo"),

    # --- Rail --------------------------------------------------------------
    ("first_train",   "All Aboard!",       "Catch your first passing Amtrak",      "trains",       1,   "1",   "land"),
    ("trainspotter",  "Trainspotter",      "Collect 10 different train numbers",   "trains",       10,  "10",  "land"),
    ("acela_hunter",  "Acela!",            "Catch an Acela blasting through",      "acelas",       1,   "ACE", "land"),
    ("crossing_gd",   "Crossing Guard",    "Log 50 total train passes",            "train_passes", 50,  "50",  "land"),

    # --- Deeper cuts ---------------------------------------------------------
    ("type_collect",  "Type Collector",    "Log 8 different aircraft types",       "air_types",    8,   "TYP", "air"),
    ("millennium",    "Millennium Club",   "Log 1,000 different aircraft",         "airframes",    1000, "1K", "air"),
    ("air_show",      "Air Show Day",      "50 aircraft sightings in one day",     "best_day_air", 50,  "50+", "air"),
    ("base_cmdr",     "Base Commander",    "Log 25 military aircraft",             "military",     25,  "25",  "air"),
    ("flag_officer",  "Flag Officer",      "Vessels from 10 different flags",      "sea_flags",    10,  "10F", "sea"),
    ("night_watch",   "Night Watch",       "20 aircraft caught between 23:00-05:00", "night_catches", 20, "20N", "air"),

    # ======================= THE BIG EXPANSION =============================
    # --- Air: collection ladders --------------------------------------------
    ("quarter_club",  "Quarter Club",      "Log 25 different aircraft",            "airframes",    25,   "25",  "air"),
    ("two_fifty",     "Control Tower",     "Log 250 different aircraft",           "airframes",    250,  "250", "air"),
    ("two_grand",     "Double Millennium", "Log 2,000 different aircraft",         "airframes",    2000, "2K",  "air"),
    ("encyclopedia",  "Sky Encyclopedia",  "Log 5,000 different aircraft",         "airframes",    5000, "5K",  "air"),
    ("first_heavy",   "Big Bird",          "Log your first heavy widebody",        "heavies",      1,    "HVY", "air"),
    ("heavy_five",    "Heavy Rotation",    "Log 5 heavy widebodies",               "heavies",      5,    "5H",  "air"),
    ("widebody_wing", "Widebody Wing",     "Log 25 heavy widebodies",              "heavies",      25,   "25H", "air"),
    ("heavy_traffic", "Heavy Traffic",     "Log 50 heavy widebodies",              "heavies",      50,   "50H", "air"),
    ("first_chopper", "Chopper Spotter",   "Log your first helicopter",            "rotors",       1,    "ROT", "air"),
    ("rotor_five",    "Blade Runner",      "Log 5 helicopters",                    "rotors",       5,    "5R",  "air"),
    ("rotor_wash",    "Rotor Wash",        "Log 25 helicopters",                   "rotors",       25,   "25R", "air"),
    ("sikorsky_city", "Sikorsky City",     "Log 50 helicopters — this IS chopper country", "rotors", 50, "50R", "air"),
    ("first_mil",     "Radar Contact",     "Log your first military aircraft",     "military",     1,    "MIL", "air"),
    ("mil_ten",       "Squadron Log",      "Log 10 military aircraft",             "military",     10,   "10M", "air"),
    ("war_bird",      "Warbird Watcher",   "Log 50 military aircraft",             "military",     50,   "50M", "air"),
    ("hall_legends",  "Hall of Legends",   "Log 3 legendary airframes",            "legendaries",  3,    "3L",  "air"),
    ("legend_five",   "Myth Collector",    "Log 5 legendary airframes",            "legendaries",  5,    "5L",  "air"),
    ("first_epic",    "Epic!",             "Log an epic-rarity airframe",          "epics",        1,    "EPC", "air"),
    ("epic_ten",      "Epic Dozen-ish",    "Log 10 epic airframes",                "epics",        10,   "10E", "air"),
    ("epic_farm",     "Epic Collection",   "Log 25 epic airframes",                "epics",        25,   "25E", "air"),

    # --- Air: variety & special ---------------------------------------------
    ("model_ten",     "Model Curator",     "Log 10 different aircraft models",     "air_models",   10,   "10T", "air"),
    ("model_25",      "Model Museum",      "Log 25 different aircraft models",     "air_models",   25,   "25T", "air"),
    ("model_50",      "Model Archive",     "Log 50 different aircraft models",     "air_models",   50,   "50T", "air"),
    ("model_100",     "Everything Flies",  "Log 100 different aircraft models",    "air_models",   100,  "100T", "air"),
    ("op_ten",        "Frequent Flyers",   "Log 10 different operators",           "air_operators", 10,  "OPS", "air"),
    ("op_25",         "Alliance Builder",  "Log 25 different operators",           "air_operators", 25,  "25O", "air"),
    ("op_50",         "Everyone's Airline", "Log 50 different operators",          "air_operators", 50,  "50O", "air"),
    ("time_traveler", "Time Traveler",     "Log an aircraft built before 1980",    "vintage_air",  1,    "OLD", "air"),
    ("warbird_wing",  "Vintage Wing",      "Log 5 aircraft built before 1980",     "vintage_air",  5,    "5V",  "air"),
    ("fresh_factory", "Factory Fresh",     "Log an aircraft built THIS year",      "new_metal",    1,    "NEW", "air"),
    ("intl_visitor",  "International Visitor", "Log a foreign-registered aircraft", "foreign_reg", 1,    "INT", "air"),
    ("embassy_row",   "Embassy Row",       "Log 5 foreign-registered aircraft",    "foreign_reg",  5,    "5I",  "air"),
    ("world_fleet",   "World Fleet",       "Log 15 foreign-registered aircraft",   "foreign_reg",  15,   "15I", "air"),

    # --- Air: dedication ------------------------------------------------------
    ("hundred_sight", "Century of Contacts", "100 total aircraft sightings",       "air_sightings", 100,  "C",   "air"),
    ("k_sight",       "Thousand Contacts", "1,000 total aircraft sightings",       "air_sightings", 1000, "1KS", "air"),
    ("five_k_sight",  "Five Thousand",     "5,000 total aircraft sightings",       "air_sightings", 5000, "5KS", "air"),
    ("ten_k_sight",   "Radar Veteran",     "10,000 total aircraft sightings",      "air_sightings", 10000, "10K", "air"),
    ("week_sky",      "Seven Days of Sky", "Catches on 7 different days",          "active_days",  7,    "7D",  "air"),
    ("month_sky",     "Thirty-Day Logbook", "Catches on 30 different days",        "active_days",  30,   "30D", "air"),
    ("hundred_days",  "Hundred-Day Watch", "Catches on 100 different days",        "active_days",  100,  "100D", "air"),
    ("year_of_sky",   "A Year of Sky",     "Catches on 365 different days",        "active_days",  365,  "365", "air"),
    ("early_bird",    "Early Bird",        "5 catches between 5-7 AM",             "early_birds",  5,    "AM",  "air"),
    ("dawn_patrol",   "Dawn Patrol",       "25 catches between 5-7 AM",            "early_birds",  25,   "25A", "air"),
    ("weekend_war",   "Weekend Warrior",   "25 weekend catches",                   "weekenders",   25,   "W25", "air"),
    ("weekend_100",   "Saturday Regular",  "100 weekend catches",                  "weekenders",   100,  "W1C", "air"),
    ("familiar",      "Familiar Faces",    "5 aircraft seen 10+ times each",       "regulars",     5,    "REG", "air"),
    ("neighborhood",  "The Neighborhood Fleet", "25 aircraft seen 10+ times each", "regulars",     25,   "25F", "air"),
    ("squad_goals",   "Squad Goals",       "Bond with 5 airframes (40+ each)",     "bonded",       5,    "5B",  "air"),
    ("century_day",   "Hundred-Plane Day", "100 aircraft sightings in one day",    "best_day_air", 100,  "1CD", "air"),
    ("sos_three",     "Emergency Channel", "Witness 3 emergency squawks",          "emergencies",  3,    "3S",  "air"),
    ("insomniac",     "Insomniac",         "100 night catches (23:00-05:00)",      "night_catches", 100, "ZZZ", "air"),

    # --- Sea ------------------------------------------------------------------
    ("dock_hand",     "Dock Hand",         "Log 10 different vessels",             "vessels",      10,   "10",  "sea"),
    ("harbor_reg",    "Harbor Regular",    "Log 50 different vessels",             "vessels",      50,   "50",  "sea"),
    ("sound_admiral", "Admiral of the Sound", "Log 250 different vessels",         "vessels",      250,  "250", "sea"),
    ("navy_500",      "Five Hundred Sails", "Log 500 different vessels",           "vessels",      500,  "500", "sea"),
    ("un_water",      "United Nations of Water", "Vessels from 15 different flags", "sea_flags",   15,   "15F", "sea"),
    ("flag_world",    "Flags of the World", "Vessels from 25 different flags",     "sea_flags",    25,   "25F", "sea"),
    ("marina_money",  "Marina Money",      "Spot 5 superyachts",                   "superyachts",  5,    "5SY", "sea"),
    ("yacht_week",    "Yacht Week",        "Spot 10 superyachts",                  "superyachts",  10,   "10Y", "sea"),
    ("first_sail",    "First Sail",        "Log a sailing vessel",                 "sailing",      1,    "SL",  "sea"),
    ("regatta_master", "Regatta Master",   "Log 25 sailing vessels",               "sailing",      25,   "25S", "sea"),
    ("first_cargo",   "Boxes on the Water", "Log your first cargo ship",           "cargo_ships",  1,    "CGO", "sea"),
    ("supply_chain",  "Supply Chain",      "Log 10 cargo ships",                   "cargo_ships",  10,   "10C", "sea"),
    ("port_authority", "Port Authority",   "Log 25 cargo ships",                   "cargo_ships",  25,   "25C", "sea"),
    ("first_tanker",  "Tanker Tracker",    "Log your first tanker",                "tankers",      1,    "TKR", "sea"),
    ("oil_baron",     "Energy Watcher",    "Log 10 tankers",                       "tankers",      10,   "10K", "sea"),
    ("tug_life",      "Tug Life",          "Log your first tugboat",               "tugs",         1,    "TUG", "sea"),
    ("tug_fleet",     "Little Boats, Big Jobs", "Log 5 tugboats",                  "tugs",         5,    "5TG", "sea"),
    ("coast_guard",   "On Patrol",         "Log a government/patrol vessel",       "gov_boats",    1,    "GOV", "sea"),
    ("harbor_watch",  "Harbor Watch",      "Log 5 government vessels",             "gov_boats",    5,    "5G",  "sea"),
    ("fish_finder",   "Fish Finder",       "Log your first fishing boat",          "fishing_boats", 1,   "FSH", "sea"),
    ("fleet_fish",    "Fishing Fleet",     "Log 10 fishing boats",                 "fishing_boats", 10,  "10F", "sea"),
    ("leviathan",     "Leviathan",         "Log a ship over 150 meters",           "big_ships",    1,    "BIG", "sea"),
    ("panamax",       "Panamax Club",      "Log 10 ships over 150 meters",         "big_ships",    10,   "10B", "sea"),
    ("full_spectrum", "Full Spectrum",     "Log 8 different vessel categories",    "sea_categories", 8,  "8C",  "sea"),
    ("hundred_wakes", "Hundred Wakes",     "100 total vessel sightings",           "sea_sightings", 100, "1CW", "sea"),
    ("thousand_wakes", "Thousand Wakes",   "1,000 total vessel sightings",         "sea_sightings", 1000, "1KW", "sea"),
    ("busy_harbor",   "Busy Harbor",       "30 vessel sightings in one day",       "best_day_sea", 30,   "30+", "sea"),
    ("sea_friends",   "Harbor Friends",    "5 vessels seen 10+ times each",        "sea_regulars", 5,    "5HF", "sea"),

    # --- Atmo -----------------------------------------------------------------
    ("first_pass",    "Look Up!",          "Log your first satellite pass",        "iss_passes",   1,    "SAT", "atmo"),
    ("orbital_reg",   "Orbital Regular",   "Log 100 satellite passes",             "iss_passes",   100,  "100", "atmo"),
    ("space_station_fan", "Station Superfan", "Log 250 satellite passes",          "iss_passes",   250,  "250", "atmo"),
    ("straight_up",   "Straight Up",       "A pass peaking above 60°",             "high_passes",  1,    "60°", "atmo"),
    ("zenith_ten",    "Zenith Club",       "10 passes peaking above 60°",          "high_passes",  10,   "10Z", "atmo"),
    ("constellation", "Constellation Collector", "Track 3 different satellites",   "sat_variety",  3,    "3ST", "atmo"),
    ("sky_census",    "Sky Census",        "Track 8 different satellites",         "sat_variety",  8,    "8ST", "atmo"),

    # --- Land -----------------------------------------------------------------
    ("full_roster",   "Full Roster",       "Collect 25 different train numbers",   "trains",       25,   "25",  "land"),
    ("timetable",     "Walking Timetable", "Collect 50 different train numbers",   "trains",       50,   "50",  "land"),
    ("dispatcher",    "Dispatcher",        "Collect 100 different train numbers",  "trains",       100,  "100", "land"),
    ("acela_five",    "Acela Regular",     "Catch 5 different Acelas",             "acelas",       5,    "5A",  "land"),
    ("acela_season",  "Acela Season Pass", "Catch 10 different Acelas",            "acelas",       10,   "10A", "land"),
    ("iron_river",    "Iron River",        "100 total train passes",               "train_passes", 100,  "100", "land"),
    ("rail_baron",    "Rail Baron",        "500 total train passes",               "train_passes", 500,  "500", "land"),
    ("thousand_rails", "Thousand Trains",  "1,000 total train passes",             "train_passes", 1000, "1K",  "land"),
    ("route_master",  "Route Master",      "Catch trains from 3 different routes", "train_routes", 3,    "3RT", "land"),

    # --- EtherDex ---------------------------------------------------------------
    ("first_whisper", "First Whisper",     "Catch your first invisible signal",    "ether_devices", 1,   "1",   "ether"),
    ("ether_ten",     "Signal Hunter",     "Catch 10 different devices",           "ether_devices", 10,  "10",  "ether"),
    ("ether_25",      "Frequency Detective", "Catch 25 different devices",         "ether_devices", 25,  "25",  "ether"),
    ("ether_50",      "The Invisible Neighborhood", "Catch 50 different devices",  "ether_devices", 50,  "50",  "ether"),
    ("ether_100",     "Ether Encyclopedia", "Catch 100 different devices",         "ether_devices", 100, "100", "ether"),
    ("kind_three",    "Three Flavors",     "Catch 3 different kinds of signal",    "ether_kinds",  3,    "3K",  "ether"),
    ("kind_six",      "Spectrum Sampler",  "Catch 6 different kinds of signal",    "ether_kinds",  6,    "6K",  "ether"),
    ("kind_ten",      "Full Spectrum Sweep", "Catch 10 different kinds of signal", "ether_kinds",  10,   "10K", "ether"),
    ("home_base",     "Home Base",         "A device becomes a Resident",          "ether_residents", 1, "RES", "ether"),
    ("family_gadgets", "The Family Gadgets", "5 devices become Residents",         "ether_residents", 5, "5R",  "ether"),
    ("meter_reader",  "Meter Reader",      "Catch a utility meter reporting in",   "ether_meters", 1,    "MTR", "ether"),
    ("utility_insp",  "Utility Inspector", "Catch 5 different utility meters",     "ether_meters", 5,    "5M",  "ether"),
    ("full_tires",    "Full Set of Tires", "Catch 4 tire-pressure sensors",        "ether_tpms",   4,    "4T",  "ether"),
    ("tire_shop",     "Tire Shop",         "Catch 20 tire-pressure sensors",       "ether_tpms",   20,   "20T", "ether"),
    ("neighbor_wx",   "Neighbor's Forecast", "Catch a wireless weather station",   "ether_wx",     1,    "WX",  "ether"),
    ("wx_network",    "Backyard Weather Network", "Catch 5 weather stations",      "ether_wx",     5,    "5W",  "ether"),
    ("x_file",        "X-File",            "Catch a true Mystery Signal",          "ether_mysteries", 1, "???", "ether"),
    ("truth_out",     "The Truth Is Out There", "Catch 10 Mystery Signals",        "ether_mysteries", 10, "10?", "ether"),
    ("k_whispers",    "Thousand Whispers", "1,000 total signal receptions",        "ether_hits",   1000, "1KH", "ether"),
    ("static_ocean",  "Ocean of Static",   "10,000 total signal receptions",       "ether_hits",   10000, "10K", "ether"),

    # --- StormDex ----------------------------------------------------------------
    ("wx_historian",  "Weather Historian", "Log your first weather event",         "storm_events", 1,    "WX",  "storm"),
    ("wx_fifty",      "Storm Chronicler",  "Log 50 weather events",                "storm_events", 50,   "50",  "storm"),
    ("wx_200",        "Climate Archive",   "Log 200 weather events",               "storm_events", 200,  "200", "storm"),
    ("record_breaker", "Record Breaker",   "Witness a temperature record",         "record_days",  1,    "REC", "storm"),
    ("record_ten",    "History in the Making", "Witness 10 temperature records",   "record_days",  10,   "10R", "storm"),
    ("snow_day",      "Snow Day!",         "Log a big snow event",                 "snow_events",  1,    "SNW", "storm"),
    ("blizzard_vet",  "Blizzard Veteran",  "Log 5 big snow events",                "snow_events",  5,    "5SN", "storm"),
    ("named_storm",   "On a First-Name Basis", "Ride out a named storm",           "named_storms", 1,    "NMD", "storm"),
    ("storm_three",   "Three Named Storms", "Ride out 3 named storms",             "named_storms", 3,    "3NS", "storm"),
    ("alert_ready",   "Alert & Ready",     "Log 5 severe weather alerts",          "wx_alerts",    5,    "5AL", "storm"),
    ("storm_season",  "Storm Season Vet",  "Log 25 severe weather alerts",         "wx_alerts",    25,   "25A", "storm"),

    # --- Family & Journeys ---------------------------------------------------------
    ("first_credit",  "Called It!",        "First spotter credit claimed",         "spotter_credits_total", 1,  "SPT", "fam"),
    ("sharp_eyes",    "Sharp Eyes",        "10 spotter credits claimed",           "spotter_credits_total", 10, "10S", "fam"),
    ("hawk_family",   "Family of Hawks",   "50 spotter credits claimed",           "spotter_credits_total", 50, "50S", "fam"),
    ("credit_century", "Spotter Century",  "100 spotter credits claimed",          "spotter_credits_total", 100, "1CS", "fam"),
    ("whole_crew",    "The Whole Crew",    "5 different family members credited",  "spotter_people", 5,  "5P",  "fam"),
    ("bon_voyage",    "Bon Voyage",        "Follow your first craft on a journey", "follows_ever", 1,    "JRN", "fam"),
    ("dispatcher_5",  "Flight Dispatcher", "Follow 5 different craft",             "follows_ever", 5,    "5J",  "fam"),
    ("fleet_tracker", "Fleet Tracker",     "Follow 10 different craft",            "follows_ever", 10,   "10J", "fam"),
    ("breadcrumbs",   "Breadcrumb Trail",  "Collect 100 journey positions",        "journey_crumbs", 100, "100", "fam"),
    ("world_tour",    "Around the World",  "Collect 1,000 journey positions",      "journey_crumbs", 1000, "1K", "fam"),
]


def compute_achievements(stats: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    for aid, title, desc, key, threshold, icon, domain in ACHIEVEMENTS:
        have = int(stats.get(key, 0) or 0)
        out.append({
            "id": aid,
            "title": title,
            "description": desc,
            "icon": icon,
            "domain": domain,
            "unlocked": have >= threshold,
            "progress": min(have, threshold),
            "threshold": threshold,
        })
    # Unlocked first (most recent flavor), then closest-to-unlock.
    out.sort(key=lambda a: (not a["unlocked"], -(a["progress"] / a["threshold"])))
    return out
