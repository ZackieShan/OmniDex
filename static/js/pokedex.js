/**
 * SkyDex - Pokemon-themed Aircraft Tracking Kiosk
 * Main JavaScript: Pokedex-style interactions + Web Audio synthesis
 * Screen: 1024x600 (Raspberry Pi Touchscreen)
 */

// ============================================
// SVG ICONS (no font dependencies — renders on any Pi)
// ============================================
const ICONS = {
  // Weather
  temp:       '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#FFCB05" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 14.76V3.5a2.5 2.5 0 0 0-5 0v11.26a4.5 4.5 0 1 0 5 0z"/></svg>',
  wind:       '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#888" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9.59 4.59A2 2 0 1 1 11 8H2m10.59 11.41A2 2 0 1 0 14 16H2m15.73-8.27A2.5 2.5 0 1 1 19.5 12H2"/></svg>',
  wave:       '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#30A7D7" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12c1.5-2 3-3 5-3s3.5 1 5 3 3 3 5 3 3.5-1 5-3"/></svg>',
  arrowUp:    '<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#4ade80" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19V5M5 12l7-7 7 7"/></svg>',
  arrowDown:  '<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#ff6b6b" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14M5 12l7 7 7-7"/></svg>',
  tideRise:   '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#4ade80" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19V5M5 12l7-7 7 7"/><path d="M2 20h20"/></svg>',
  tideFall:   '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#ff6b6b" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14M5 12l7 7 7-7"/><path d="M2 20h20"/></svg>',
  // Aircraft types
  rotor:      '<svg width="18" height="18" viewBox="0 0 24 24" fill="#F08030"><path d="M12 2L4 7v10l8 5 8-5V7l-8-5zm0 2.5L18.5 8 12 11.5 5.5 8 12 4.5zM5 9l7 4v7l-7-4V9zm14 0v7l-7 4v-7l7-4z"/></svg>',
  jet:        '<svg width="18" height="18" viewBox="0 0 24 24" fill="#6890F0"><path d="M21 16v-2l-8-5V3.5c0-.83-.67-1.5-1.5-1.5S10 2.67 10 3.5V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5l8 2.5z"/></svg>',
  // Source indicator
  antenna:    '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v20M2 12h20"/><circle cx="12" cy="12" r="3"/></svg>',
  cloud:      '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#aaa" stroke-width="2"><path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z"/></svg>',
  // Vertical state arrows
  climb:      '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="#4ade80" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19V5M5 12l7-7 7 7"/></svg>',
  descend:    '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="#ff6b6b" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14M5 12l7 7 7-7"/></svg>',
  speaker:    '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.5 8.5a5 5 0 0 1 0 7M19 5a9 9 0 0 1 0 14"/></svg>',
  speakerOff: '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><line x1="22" y1="9" x2="16" y2="15"/><line x1="16" y1="9" x2="22" y2="15"/></svg>',
};

// ============================================
// AIRCRAFT TYPE ICONS — inline SVG silhouettes (white fill on the colored
// badge). Self-contained so they always render, even on a Pi with no emoji
// font installed.
// ============================================
// Aircraft silhouettes — all TOP-DOWN with the nose pointing up, so the same
// glyph works in list chips AND rotates cleanly to heading on the map.
const TYPE_SVG = {
  // Airliner / jet: slender fuselage, swept wings, swept tailplane
  plane:  '<svg viewBox="0 0 24 24" fill="currentColor" width="72%" height="72%"><path d="M12 1c.55 0 .95.75 1.05 1.9l.4 5.1 7.6 4.55c.3.18.45.45.45.78v1.47l-8-2.35.25 5.2 2.15 1.7v1.45l-3.3-.95-.6 1.85-.6-1.85-3.3.95v-1.45l2.15-1.7.25-5.2-8 2.35v-1.47c0-.33.15-.6.45-.78l7.6-4.55.4-5.1C11.05 1.75 11.45 1 12 1z"/></svg>',
  // Prop / light GA: straight wings well forward, prop disc at the nose
  prop:   '<svg viewBox="0 0 24 24" fill="currentColor" width="72%" height="72%"><circle cx="12" cy="2.6" r="1.5" opacity="0.55"/><path d="M12 2.2c.5 0 .85.6.95 1.5l.25 3.1h7.3c.55 0 1 .45 1 1v1.1c0 .3-.2.55-.5.62l-7.7 1.05-.3 6.05 2.3 1.75v1.4l-3.4-.9-.5 1.73-.5-1.73-3.4.9v-1.4l2.3-1.75-.3-6.05-7.7-1.05c-.3-.07-.5-.32-.5-.62V7.8c0-.55.45-1 1-1h7.3l.25-3.1c.1-.9.45-1.5.95-1.5z"/></svg>',
  // Helicopter TOP view: rotor disc + crossed blades + cabin + tail boom
  heli:   '<svg viewBox="0 0 24 24" width="76%" height="76%"><circle cx="12" cy="8.5" r="7" fill="none" stroke="currentColor" stroke-width="1.1" opacity="0.5"/><path d="M7.05 3.55 16.95 13.45M16.95 3.55 7.05 13.45" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" opacity="0.8"/><ellipse cx="12" cy="8.5" rx="2.5" ry="4" fill="currentColor"/><path d="M11.2 12.2h1.6l-.25 7h1.95v1.6h-5v-1.6h1.95z" fill="currentColor"/></svg>',
  // Military / fighter: sharp nose, delta wing, canted stabs
  fighter:'<svg viewBox="0 0 24 24" fill="currentColor" width="72%" height="72%"><path d="M12 1.2c.4 0 .7.5.85 1.4l.75 5.2 7.4 6v1.8l-7.1-2.6.35 3.7 2.25 1.85v1.5l-3.5-1-.5 1.75-.5-1.75-3.5 1v-1.5l2.25-1.85.35-3.7-7.1 2.6v-1.8l7.4-6 .75-5.2c.15-.9.45-1.4.85-1.4z"/></svg>',
};

function typeIconSvg(type) {
  if (type === 'rotor' || type === 'medevac') return TYPE_SVG.heli;
  if (type === 'sentinel') return TYPE_SVG.fighter;
  if (type === 'trainer' || type === 'hopper') return TYPE_SVG.prop;
  return TYPE_SVG.plane;  // jet / airliner / bizjet / heavy / etc.
}

// ============================================
// GLOBAL STATE
// ============================================
const SkyDex = {
  previousContacts: [],
  currentView: 'contacts',
  previousView: null,
  weatherData: null,
  tideData: null,
  facts: [],
  factIndex: 0,
  stats: null,
  dexData: null,
  isPolling: true,
  audioEnabled: true,
  audioContext: null,
  sourceName: null,
  mode: 'air',   // 'air' = SkyDex, 'sea' = SeaDex
};

// SeaDex vessel category colors (mirror vessels.py) + SVG silhouettes.
const VESSEL_COLORS = {
  Cargo: '#6890F0', Tanker: '#C03028', Passenger: '#F85888', HSC: '#30A7D7',
  Fishing: '#78C850', Sailing: '#98D8D8', Pleasure: '#F8D030', Superyacht: '#FFD700',
  Tug: '#A89078', Government: '#7038F8', Other: '#9e9e9e',
};

// Vessel silhouettes — all TOP-DOWN, bow up, one per category so a tanker,
// tug and sailboat are tellable at a glance. Dark cutouts = deck details.
const _HULL = 'M12 1.8c1.8 2.2 3 5.7 3 10.2v6c0 2-1.3 3.2-3 3.2s-3-1.2-3-3.2v-6c0-4.5 1.2-8 3-10.2z';
const _CUT = 'rgba(0,0,0,0.45)';
const VESSEL_SVG = {
  // Plain hull (unknown/other)
  ship:    `<svg viewBox="0 0 24 24" fill="currentColor" width="74%" height="74%"><path d="${_HULL}"/></svg>`,
  // Cargo: transverse hatch covers down the deck
  cargo:   `<svg viewBox="0 0 24 24" fill="currentColor" width="74%" height="74%"><path d="${_HULL}"/><path d="M9.7 8h4.6M9.7 11h4.6M9.7 14h4.6M9.7 17h4.6" stroke="${_CUT}" stroke-width="1.5"/></svg>`,
  // Tanker: centre pipeline + manifold dots
  tanker:  `<svg viewBox="0 0 24 24" fill="currentColor" width="74%" height="74%"><path d="${_HULL}"/><path d="M12 6.5v12" stroke="${_CUT}" stroke-width="1.3"/><circle cx="12" cy="9" r="1.2" fill="${_CUT}"/><circle cx="12" cy="13.5" r="1.2" fill="${_CUT}"/></svg>`,
  // Ferry / passenger: long cabin superstructure
  ferry:   `<svg viewBox="0 0 24 24" fill="currentColor" width="74%" height="74%"><path d="${_HULL}"/><rect x="9.8" y="7" width="4.4" height="9.5" rx="2" fill="${_CUT}"/></svg>`,
  // Fishing: wheelhouse forward + boom lines splayed at the stern
  fishing: `<svg viewBox="0 0 24 24" fill="currentColor" width="74%" height="74%"><path d="${_HULL}"/><rect x="10.2" y="7.5" width="3.6" height="3.4" rx="1" fill="${_CUT}"/><path d="M12 14.5l-3.4 5M12 14.5l3.4 5" stroke="${_CUT}" stroke-width="1.2"/></svg>`,
  // Tug: short fat hull, heavy bow fender band
  tug:     `<svg viewBox="0 0 24 24" fill="currentColor" width="74%" height="74%"><path d="M12 3.4c2.4 1.6 3.6 4.4 3.6 8v4.8c0 2.2-1.5 3.6-3.6 3.6s-3.6-1.4-3.6-3.6v-4.8c0-3.6 1.2-6.4 3.6-8z"/><path d="M9 7.2c.8-1.6 1.8-2.7 3-3.4 1.2.7 2.2 1.8 3 3.4" fill="none" stroke="${_CUT}" stroke-width="1.6"/><rect x="10.4" y="10.5" width="3.2" height="3.2" rx="1" fill="${_CUT}"/></svg>`,
  // Sailboat: sleek hull, mast dot + boom line
  sail:    `<svg viewBox="0 0 24 24" fill="currentColor" width="74%" height="74%"><path d="M12 1.8c1.4 2.4 2.3 6 2.3 10.4v5.6c0 1.9-1 3.2-2.3 3.2s-2.3-1.3-2.3-3.2v-5.6c0-4.4.9-8 2.3-10.4z"/><circle cx="12" cy="10.5" r="1.3" fill="${_CUT}"/><path d="M12 11.8v5" stroke="${_CUT}" stroke-width="1.1"/></svg>`,
  // Pleasure / yacht: pointed bow, open cockpit aft
  boat:    `<svg viewBox="0 0 24 24" fill="currentColor" width="74%" height="74%"><path d="${_HULL}"/><rect x="9.9" y="12.5" width="4.2" height="5" rx="1.8" fill="${_CUT}"/></svg>`,
  // Government / patrol: bow chevron stripe
  gov:     `<svg viewBox="0 0 24 24" fill="currentColor" width="74%" height="74%"><path d="${_HULL}"/><path d="M9.4 8.2 12 6l2.6 2.2" fill="none" stroke="${_CUT}" stroke-width="1.6"/><path d="M9.4 11 12 8.8l2.6 2.2" fill="none" stroke="${_CUT}" stroke-width="1.6"/></svg>`,
};

function vesselIconSvg(iconKey) {
  return VESSEL_SVG[iconKey] || VESSEL_SVG.ship;
}

// Anchor glyph for the Anchored section/badge (Material "anchor" path).
const ANCHOR_SVG = '<svg viewBox="0 0 24 24" width="13" height="13" fill="currentColor" style="vertical-align:-2px;"><path d="M17 15l1.55 1.55c-.96 1.69-3.33 3.04-5.55 3.37V11h3V9h-3V7.82C14.16 7.4 15 6.3 15 5c0-1.65-1.35-3-3-3S9 3.35 9 5c0 1.3.84 2.4 2 2.82V9H8v2h3v8.92c-2.22-.33-4.59-1.68-5.55-3.37L7 15l-4-3v3c0 3.88 4.92 7 9 7s9-3.11 9-7v-3l-4 3zM12 4c.55 0 1 .45 1 1s-.45 1-1 1-1-.45-1-1 .45-1 1-1z"/></svg>';

function vesselColor(v) {
  return VESSEL_COLORS[v.category] || VESSEL_COLORS.Other;
}

// --- Aircraft type definitions ---
const AIRCRAFT_TYPES = {
  rotor:      { label: 'Rotor',    color: '#F08030', icon: '\u{1F681}', desc: 'Helicopter',     stat: 'HP' },
  jet:        { label: 'Jet',      color: '#6890F0', icon: '\u2708',   desc: 'Jet Aircraft',   stat: 'SPD' },
  sentinel:   { label: 'Sentinel', color: '#C03028', icon: '\u2B50',   desc: 'Military',       stat: 'ATK' },
  heavy:      { label: 'Heavy',    color: '#7038F8', icon: '\u26A1',   desc: 'Heavy Aircraft', stat: 'DEF' },
  bizjet:     { label: 'Bizjet',   color: '#F85888', icon: '\u{1F451}', desc: 'Business Jet',   stat: 'SPA' },
  voyager:    { label: 'Voyager',  color: '#98D8D8', icon: '\u2601',   desc: 'Long Range',     stat: 'SPD' },
  trainer:    { label: 'Trainer',  color: '#78C850', icon: '\u{1F331}', desc: 'Trainer',        stat: 'HP' },
  hopper:     { label: 'Hopper',   color: '#A89078', icon: '\u{1F43E}', desc: 'Light Aircraft', stat: 'SPD' },
  hauler:     { label: 'Hauler',   color: '#B8B8D0', icon: '\u{1F4E6}', desc: 'Cargo',          stat: 'DEF' },
  medevac:    { label: 'Medevac',  color: '#FF6B9D', icon: '\u271A',   desc: 'Air Ambulance',  stat: 'HP' },
  commuter:   { label: 'Commuter', color: '#F8D030', icon: '\u{1F552}', desc: 'Regional',       stat: 'SPD' },
};

const RARITY = {
  common:     { stars: 1, label: 'Common',     color: '#9e9e9e' },
  uncommon:   { stars: 2, label: 'Uncommon',   color: '#4caf50' },
  rare:       { stars: 3, label: 'Rare',       color: '#2196f3' },
  epic:       { stars: 4, label: 'Epic',       color: '#9c27b0' },
  legendary:  { stars: 5, label: 'Legendary',  color: '#FFD700' },
};

const TIERS = {
  spotted:  { label: 'Spotted', fill: 20,  color: '#888' },
  tracked:  { label: 'Tracked', fill: 50,  color: '#30A7D7' },
  tagged:   { label: 'Tagged',  fill: 80,  color: '#4ade80' },
  bonded:   { label: 'Bonded',  fill: 100, color: '#4ade80' },
};

const AVIATION_FACTS = [
  "The Boeing 747 has been in service since 1970 and has flown over 3.5 billion passengers.",
  "A commercial aircraft is struck by lightning about once per year on average.",
  "The world's busiest airport by passenger traffic is Hartsfield-Jackson Atlanta International.",
  "Black boxes are actually bright orange to make them easier to find after a crash.",
  "The Concorde could fly from London to New York in under 3.5 hours.",
  "Airplane windows are round because square windows caused fatal crashes in the 1950s.",
  "The Airbus A380 has over 320 miles of electrical wiring inside it.",
  "Pilots and co-pilots eat different meals in case one causes food poisoning.",
  "The Cessna 172 is the most produced aircraft in history with over 44,000 built.",
  "A fully loaded 747 burns about 1 gallon of fuel per second during cruise.",
  "The SR-71 Blackbird could fly at over Mach 3.2.",
  "Air traffic controllers handle around 2.9 million flights in US airspace each year.",
  "The Antonov AN-225 was the heaviest aircraft ever built, with a max takeoff weight of 640 tons.",
  "Aircraft call signs starting with 'N' are registered in the United States.",
  "Mode S transponders reply to radar interrogations with a unique 24-bit address.",
  "The altitude displayed is pressure altitude, calibrated to sea level pressure.",
  "ADS-B broadcasts an aircraft's position twice per second for tracking.",
  "Helicopters achieve lift by rotating their blades through the air at high speed.",
  "The F-22 Raptor can cruise at supersonic speeds without using afterburners.",
];

// SeaDex fallback facts (used until the server's richer pool loads in sea mode).
const SEA_FACTS = [
  "Long Island Sound is a tidal estuary about 110 miles long, penned in between Connecticut and Long Island.",
  "Lighthouses have marked the Sound's river mouths since the early 1800s — some towers still standing date to the 1820s.",
  "Rocky mid-Sound shoals carry lonely 19th-century lighthouses — more than one famously rumored to be haunted.",
  "The rivers feeding the Sound run all the way down from the Berkshires — tidal salt water pushes miles back upstream.",
  "Bridgeport was a 19th-century oyster capital, with one of the world's first steam-powered dredging fleets.",
  "The Bridgeport–Port Jefferson ferry has crossed the Sound since 1883 and still runs today.",
  "AIS is the sea's version of ADS-B — ships broadcast their position on VHF near 162 MHz, and your dongle is listening.",
  "A vessel's MMSI starts with a country code: 366–369 means a United States ship.",
];

// AtmoDex fallback facts (used until the server's richer pool loads in atmo mode).
const ATMO_FACTS = [
  "Light from the Sun takes about 8 minutes to reach us — you see it as it was 8 minutes ago.",
  "Igor Sikorsky built the first practical helicopter in Connecticut in 1939.",
  "The Apollo Moon spacesuits were designed and sewn in Connecticut.",
  "The ISS laps the Earth every ~90 minutes — 16 sunrises a day for its crew.",
  "The Big Dipper never sets from Connecticut — look north on any clear night.",
  "Project Blue Book logged 12,000+ UFO reports; 701 are still officially 'unidentified'.",
  "The Hudson Valley UFO wave of the 1980s brought thousands of reports over the NY/CT border.",
];

// ============================================
// WEB AUDIO API - Pokemon-style Synthesizer
// ============================================

const SkyDexAudio = {
  ctx: null,

  /** Lazy-init the audio context (must be done after user gesture on some browsers) */
  init() {
    if (!SkyDex.audioEnabled) return false;
    if (!this.ctx) {
      try {
        this.ctx = new (window.AudioContext || window.webkitAudioContext)();
      } catch (e) {
        console.warn('Web Audio not available:', e);
        return false;
      }
    }
    if (this.ctx.state === 'suspended') {
      this.ctx.resume();
    }
    return true;
  },

  /** Pokemon-style "catch" jingle — ascending major arpeggio */
  playCatchJingle() {
    if (!this.init()) return;
    const t = this.ctx.currentTime;
    const notes = [523.25, 659.25, 783.99, 1046.50]; // C5 E5 G5 C6
    notes.forEach((freq, i) => {
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      osc.type = 'square';
      osc.frequency.setValueAtTime(freq, t + i * 0.08);
      gain.gain.setValueAtTime(0.12, t + i * 0.08);
      gain.gain.exponentialRampToValueAtTime(0.001, t + i * 0.08 + 0.35);
      osc.connect(gain);
      gain.connect(this.ctx.destination);
      osc.start(t + i * 0.08);
      osc.stop(t + i * 0.08 + 0.35);
    });
  },

  /** Shiny sparkle — high-pitched shimmer with chorus effect */
  playShinySparkle() {
    if (!this.init()) return;
    const t = this.ctx.currentTime;
    // Two detuned oscillators for shimmer
    [0, 3].forEach((detune, idx) => {
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(2093.00, t); // C7
      osc.frequency.exponentialRampToValueAtTime(4186.01, t + 0.3); // C8
      osc.detune.value = detune;
      gain.gain.setValueAtTime(0.06, t);
      gain.gain.exponentialRampToValueAtTime(0.001, t + 0.5);
      osc.connect(gain);
      gain.connect(this.ctx.destination);
      osc.start(t);
      osc.stop(t + 0.5);
    });
  },

  /** Low whoosh for aircraft flyover — sweeping noise */
  playWhoosh() {
    if (!this.init()) return;
    const t = this.ctx.currentTime;
    const duration = 0.6;
    const bufferSize = this.ctx.sampleRate * duration;
    const buffer = this.ctx.createBuffer(1, bufferSize, this.ctx.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < bufferSize; i++) {
      data[i] = (Math.random() * 2 - 1) * Math.sin((i / bufferSize) * Math.PI);
    }
    const noise = this.ctx.createBufferSource();
    noise.buffer = buffer;
    const filter = this.ctx.createBiquadFilter();
    filter.type = 'bandpass';
    filter.frequency.setValueAtTime(200, t);
    filter.frequency.exponentialRampToValueAtTime(80, t + duration);
    const gain = this.ctx.createGain();
    gain.gain.setValueAtTime(0.08, t);
    gain.gain.exponentialRampToValueAtTime(0.001, t + duration);
    noise.connect(filter);
    filter.connect(gain);
    gain.connect(this.ctx.destination);
    noise.start(t);
    noise.stop(t + duration);
  },

  /** Low beep for UI interaction */
  playBeep() {
    if (!this.init()) return;
    const t = this.ctx.currentTime;
    const osc = this.ctx.createOscillator();
    const gain = this.ctx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(880, t);
    gain.gain.setValueAtTime(0.05, t);
    gain.gain.exponentialRampToValueAtTime(0.001, t + 0.08);
    osc.connect(gain);
    gain.connect(this.ctx.destination);
    osc.start(t);
    osc.stop(t + 0.08);
  },
};

// ============================================
// UTILITY FUNCTIONS
// ============================================

function getAircraftType(aircraft) {
  const model = (aircraft.model || aircraft.type || '').toLowerCase();
  const desc = (aircraft.desc || '').toLowerCase();
  const combined = model + ' ' + desc;

  if (/heli|rotor|chopper|hughes|robinson|bell |eurocopter|airbus.*h|agusta/.test(combined)) return 'rotor';
  if (/fighter|jet.*mil|f-16|f-22|f-35|mig-|su-|military|tornado|harrier/.test(combined)) return 'sentinel';
  if (/cargo|haul|freight|boeing.74[0-9]|747|777|dc-10|md-11|c-17|c-130/.test(combined)) return 'hauler';
  if (/trainer|cessna|piper|beech|diamond|tecnam|flight.*school/.test(combined)) return 'trainer';
  if (/embraer|regional|commuter|atr |dash|crj| bombardier/.test(combined)) return 'commuter';
  if (/global|gulfstream|challenger|learjet|phenom|citation|business|luxury/.test(combined)) return 'bizjet';
  if (/a380|b747|747|heavy|widebody|a340|a330|787|777/.test(combined)) return 'heavy';
  if (/medical|air.*ambulance|medevac|rescue/.test(combined)) return 'medevac';
  if (/glider|sailplane|ultralight|microlight/.test(combined)) return 'hopper';
  return 'jet';
}

function getRarity(aircraft) {
  const model = (aircraft.model || '').toLowerCase();
  if (/a380|an-225|b747.*sp|sr-71|concorde/.test(model)) return 'legendary';
  if (/b747|a340|f-22|f-35|global|g650/.test(model)) return 'epic';
  if (/b787|a350|gulfstream|challenger|citation/.test(model)) return 'rare';
  if (/embraer|crj|dash|atr |boeing|airbus/.test(model)) return 'uncommon';
  return 'common';
}

/** Prefer the server's (sharpened, type-based) rarity; fall back to the regex. */
function rarityKey(obj) {
  if (obj && obj.rarity) {
    const k = String(obj.rarity).toLowerCase();
    if (RARITY[k]) return k;
  }
  return getRarity(obj || {});
}

/** Render real aircraft spec bars (max speed / range / ceiling / seats). */
function renderSpecBars(specs) {
  if (!specs) {
    return '<div style="color:var(--text-faint);font-size:12px;padding:6px 0;">No spec sheet on file for this type yet.</div>';
  }
  const rows = [
    ['Max Speed', specs.speed_kt, ' kt', 600, '#6890f0'],
    ['Range', specs.range_nm, ' nm', 9000, '#78c850'],
    ['Ceiling', specs.ceiling_ft, ' ft', 51000, '#f8d030'],
    ['Max Seats', specs.seats, '', 600, '#f85888'],
  ];
  let html = '<div class="spec-grid">';
  rows.forEach(([label, val, unit, max, color]) => {
    if (val === null || val === undefined) return;
    const pct = Math.min(100, (val / max) * 100);
    const disp = (typeof val === 'number' ? val.toLocaleString() : val) + unit;
    html += `<div class="spec-row"><span class="spec-name">${label}</span><div class="stat-bar-bg"><div class="stat-bar-fill" style="width:${pct}%;background:${color};"></div></div><span class="spec-value">${disp}</span></div>`;
  });
  html += '</div>';
  if (specs.engines) {
    html += `<div style="font-size:11px;color:var(--text-dim);margin-top:6px;">${specs.role || ''}${specs.role ? ' · ' : ''}${specs.engines} engine${specs.engines > 1 ? 's' : ''}</div>`;
  }
  return html;
}

/** SVG type icon as a centered, colored block (the only photo fallback). */
function typeIconBlock(typeKey, color) {
  return `<span style="color:${color};display:flex;align-items:center;justify-content:center;width:100%;height:100%;">${typeIconSvg(typeKey)}</span>`;
}

/** Photo of the specific airframe via the proxy; on failure → the type icon. */
// ============================================
// KID COMPARISONS — numbers translated into things kids can picture.
// ============================================
function kidCompareAlt(ft) {
  if (ft == null || ft < 100) return '';
  if (ft < 1500) return 'about as high as the Empire State Building';
  if (ft < 6000) return `${(ft / 1454).toFixed(1)} Empire State Buildings high`;
  if (ft < 20000) return 'higher than any bird has ever flown';
  return `${(ft / 29032).toFixed(1)} Mount Everests stacked up`;
}

function kidCompareSpeed(kt) {
  if (!kt || kt < 5) return '';
  const mph = Math.round(kt * 1.151);
  if (mph < 90) return `${mph} mph — about highway speed`;
  if (mph < 250) return `${mph} mph — 3 times faster than driving on I-95`;
  // Straight-line NYC -> Boston ≈ 190 miles.
  return `${mph} mph — could fly from New York to Boston in ${Math.max(1, Math.round(190 / mph * 60))} minutes`;
}

function kidCompareShip(lenM, kn) {
  const bits = [];
  if (lenM && lenM >= 20) {
    const ff = lenM / 91.44;
    bits.push(ff >= 1.4 ? `as long as ${ff.toFixed(1)} football fields`
      : ff >= 0.8 ? 'as long as a football field'
      : `about ${Math.max(2, Math.round(lenM / 10.7))} school buses long`);
  }
  if (kn != null && kn > 0.3) {
    const mph = Math.round(kn * 1.151);
    if (mph <= 4) bits.push('moving at walking speed');
    else if (mph <= 13) bits.push(`${mph} mph — bicycle speed`);
    else bits.push(`${mph} mph — really moving for something that heavy`);
  }
  return bits.join(' · ');
}

function photoImg(hex, typeKey, color, style) {
  if (!hex) return typeIconBlock(typeKey, color);
  // loading="lazy": photos only download as their card scrolls into view —
  // THE fix for the Dex's slow first open (hundreds of simultaneous fetches).
  return `<img src="/api/photo/${hex}" loading="lazy" decoding="async" data-type="${typeKey}" data-color="${color}" style="${style}" onerror="photoSvg(this)">`;
}

function photoSvg(img) {
  img.outerHTML = typeIconBlock(img.dataset.type || 'jet', img.dataset.color || 'var(--text-dim)');
}

/** Country flag image (flagcdn) from a {iso2,name} object. */
function flagHtml(country) {
  if (!country || !country.iso2) return '';
  const code = String(country.iso2).toLowerCase();
  return `<img class="flag" src="https://flagcdn.com/20x15/${code}.png" alt="${country.name || ''}" title="${country.name || ''}" onerror="this.style.display='none'">`;
}

/** Airline logo image (kiwi.com) from an IATA code. */
function airlineLogoHtml(iata, cls) {
  if (!iata) return '';
  return `<img class="${cls || 'airline-logo'}" src="https://images.kiwi.com/airlines/64/${String(iata).toUpperCase()}.png" alt="" onerror="this.style.display='none'">`;
}

function getTier(count) {
  if (!count || count < 2) return 'spotted';
  if (count < 5) return 'tracked';
  if (count < 10) return 'tagged';
  return 'bonded';
}

function formatAltitude(alt) {
  if (alt === null || alt === undefined) return { text: '---', class: 'altitude-ground' };
  const num = Math.round(alt);
  // Plain feet, not "FL230" — kids read this, not pilots.
  if (num >= 25000) return { text: `${num.toLocaleString()}ft`, class: 'altitude-high' };
  if (num >= 10000) return { text: `${num.toLocaleString()}ft`, class: 'altitude-mid' };
  if (num >= 100) return { text: `${num.toLocaleString()}ft`, class: 'altitude-low' };
  return { text: `${num}ft`, class: 'altitude-ground' };
}

function formatDistance(dist) {
  if (dist === null || dist === undefined) return '';
  return `${dist.toFixed(1)} mi`;
}

function hexToDexNumber(hex) {
  if (!hex) return '000';
  let hash = 0;
  for (let i = 0; i < hex.length; i++) {
    hash = ((hash << 5) - hash) + hex.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash % 999).toString().padStart(3, '0');
}

function formatSpeed(speed) {
  if (!speed) return '---';
  return `${Math.round(speed)} kts`;
}

function headingToCompass(heading) {
  if (!heading) return '---';
  const dirs = ['N','NNE','NE','ENE','E','ESE','SE','SSE','S','SSW','SW','WSW','W','WNW','NW','NNW'];
  return dirs[Math.round(heading / 22.5) % 16];
}

// ============================================
// CLOCK
// ============================================
// Force US Eastern, 24-hour, everywhere.
const EST_TZ = 'America/New_York';
function fmtTimeEST(epochSec) {
  if (epochSec == null) return '—';
  return new Date(epochSec * 1000).toLocaleTimeString('en-GB',
    { hour: '2-digit', minute: '2-digit', hour12: false, timeZone: EST_TZ });
}
function fmtDateTimeEST(ms) {
  return new Date(ms).toLocaleString('en-GB',
    { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false, timeZone: EST_TZ });
}

// World clocks, ordered east -> west by offset (Tokyo first, Pacific last).
const WORLD_CLOCKS = [
  ['TOKYO', 'Asia/Tokyo'], ['MOSCOW', 'Europe/Moscow'], ['PARIS', 'Europe/Paris'],
  ['LONDON', 'Europe/London'], ['CHICAGO', 'America/Chicago'],
  ['SAN DIEGO', 'America/Los_Angeles'], ['VANCOUVER', 'America/Vancouver'],
];

function updateClock() {
  const now = new Date();
  const time = now.toLocaleTimeString('en-GB',
    { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false, timeZone: EST_TZ });
  const date = now.toLocaleDateString('en-US',
    { weekday: 'short', month: 'short', day: 'numeric', timeZone: EST_TZ });
  document.getElementById('clock-display').innerHTML =
    `${time} <span class="clock-date">${date}</span>`;

  // World strip refreshes on the minute (cheap; Intl does the DST math).
  const wc = document.getElementById('world-clocks');
  if (wc && (now.getSeconds() === 0 || !wc.innerHTML)) {
    wc.innerHTML = WORLD_CLOCKS.map(([name, tz]) => {
      const t = now.toLocaleTimeString('en-GB',
        { hour: '2-digit', minute: '2-digit', hour12: false, timeZone: tz });
      return `<span class="wc-item"><span class="wc-city">${name}</span> ${t}</span>`;
    }).join('');
  }
}
setInterval(updateClock, 1000);
updateClock();

// ============================================
// TYPE BADGE / RARITY / XP RENDERING
// ============================================

function renderTypeBadge(types) {
  if (!types) types = ['jet'];
  if (typeof types === 'string') types = [types];
  let html = '<div class="dex-types-row">';
  types.forEach((t, i) => {
    const typeInfo = AIRCRAFT_TYPES[t] || AIRCRAFT_TYPES.jet;
    html += `<span class="type-pill type-${t} type-reveal" style="animation-delay:${i * 0.1}s;cursor:pointer;"
      onclick="if(window.showTypeInfo)showTypeInfo('${t}')">${typeInfo.label}</span>`;
  });
  html += '</div>';
  return html;
}

function renderTypeIcon(type) {
  const t = AIRCRAFT_TYPES[type] || AIRCRAFT_TYPES.jet;
  return `<div class="type-badge-container type-${type}" title="${t.desc}">${typeIconSvg(type)}</div>`;
}

function renderRarityStars(rarity) {
  const r = RARITY[rarity] || RARITY.common;
  let html = `<span class="rarity-stars rarity-${rarity}" title="${r.label}"
    onclick="event.stopPropagation();if(window.showRarityInfo)showRarityInfo('${rarity}')" style="cursor:pointer;">`;
  for (let i = 0; i < 5; i++) {
    html += `<span class="star">${i < r.stars ? '\u2605' : '\u2606'}</span>`;
  }
  html += '</span>';
  return html;
}

function renderXpBar(tier, count) {
  const t = TIERS[tier] || TIERS.spotted;
  return `
    <div class="xp-bar-container">
      <span class="xp-label">${t.label}</span>
      <div class="xp-bar-bg"><div class="xp-bar-fill tier-${tier}"></div></div>
      <span style="font-size:9px;color:var(--text-dim);">${count || 1}x</span>
    </div>`;
}

// ============================================
// FACT ROTATION
// ============================================

function factPool() {
  if (SkyDex.facts && SkyDex.facts.length) return SkyDex.facts;
  if (SkyDex.mode === 'sea') return SEA_FACTS;
  if (SkyDex.mode === 'atmo') return ATMO_FACTS;
  if (SkyDex.mode === 'land' && window.LAND_FACTS) return window.LAND_FACTS;
  if (SkyDex.mode === 'ether' && window.ETHER_FACTS) return window.ETHER_FACTS;
  return AVIATION_FACTS;
}

function rotateFacts() {
  const facts = factPool();
  SkyDex.factIndex = (SkyDex.factIndex + 1) % facts.length;
  const factEl = document.getElementById('rotating-fact');
  if (factEl) {
    factEl.style.opacity = '0';
    setTimeout(() => {
      factEl.textContent = facts[SkyDex.factIndex];
      factEl.style.opacity = '1';
    }, 300);
  }
}
setInterval(rotateFacts, 15000);

/** Load the KBDR / local / aviation fact mix from the server. */
async function fetchFacts() {
  try {
    const domain = SkyDex.mode === 'sea' ? 'sea'
      : SkyDex.mode === 'atmo' ? 'atmo'
      : SkyDex.mode === 'land' ? 'land'
      : SkyDex.mode === 'ether' ? 'ether' : 'air';
    const res = await fetch(`/api/facts?n=20&domain=${domain}`);
    if (!res.ok) return;
    const data = await res.json();
    if (Array.isArray(data) && data.length) {
      SkyDex.facts = data;
      SkyDex.factIndex = 0;
      updateTicker();
    }
  } catch (e) { /* keep whatever we have */ }
}

/** Fill the bottom scrolling ticker with the current fact pool. */
function updateTicker() {
  const track = document.getElementById('fact-ticker-track');
  if (!track) return;
  const sep = '   ✦   ';
  track.textContent = factPool().join(sep) + sep;
  // Keep a constant, relaxed scroll speed no matter how long the text is.
  const PX_PER_SEC = 35;
  const width = track.scrollWidth || 4000;
  track.style.animationDuration = Math.max(60, Math.round(width / PX_PER_SEC)) + 's';
}

/** Toggle sound effects + swap the speaker icon. */
function toggleAudio() {
  SkyDex.audioEnabled = !SkyDex.audioEnabled;
  if (SkyDex.audioEnabled) SkyDexAudio.init();
  updateAudioIcon();
}

function updateAudioIcon() {
  const el = document.getElementById('audio-indicator');
  if (!el) return;
  el.innerHTML = SkyDex.audioEnabled ? ICONS.speaker : ICONS.speakerOff;
  el.classList.toggle('muted', !SkyDex.audioEnabled);
}

// ============================================
// CATCH ANIMATIONS + AUDIO
// ============================================

function flashScreen() {
  const flash = document.getElementById('catch-flash-overlay');
  if (!flash) return;
  flash.classList.remove('flash-active');
  void flash.offsetWidth;
  flash.classList.add('flash-active');
}

function playCatchAnimation(aircraft) {
  const name = aircraft.callsign || aircraft.registration || aircraft.hex || 'Unknown';
  const typeInfo = AIRCRAFT_TYPES[primaryType(aircraft)] || AIRCRAFT_TYPES.jet;
  const rarity = rarityKey(aircraft);
  const sq = (aircraft.squawk || '').trim();
  const isNew = (aircraft.detection_count || 0) <= 1;

  // Emergency squawk — always alert.
  if (sq === '7500' || sq === '7600' || sq === '7700') {
    flashScreen();
    showToast(`EMERGENCY ${sq} — ${name}`, 'emergency');
    SkyDexAudio.playShinySparkle();
    return;
  }

  // Epic / Legendary — shiny celebration + "who spotted it?" credit.
  if (rarity === 'legendary' || rarity === 'epic') {
    flashScreen();
    SkyDexAudio.playCatchJingle();
    showToast(`★ ${RARITY[rarity].label} catch! ${name} — ${typeInfo.label}`, 'new-catch');
    setTimeout(() => SkyDexAudio.playShinySparkle(), 400);
    if (window.askSpotter) setTimeout(() => askSpotter(name, 'air'), 1200);
    return;
  }

  // Brand-new to your Dex — normal catch jingle.
  if (isNew) {
    flashScreen();
    SkyDexAudio.playCatchJingle();
    showToast(`New to your Dex! ${name} — ${typeInfo.label}`, 'new-catch');
  }
  // Otherwise (a regular re-entering range): stay quiet.
}

function showToast(message, type = '') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 3000);
}

function checkForNewCatches(current) {
  if (!SkyDex.previousContacts.length) {
    SkyDex.previousContacts = current.map(c => c.hex);
    return;
  }
  const prevHexes = new Set(SkyDex.previousContacts);
  const newOnes = current.filter(c => c.hex && !prevHexes.has(c.hex));
  newOnes.forEach(a => playCatchAnimation(a));
  SkyDex.previousContacts = current.map(c => c.hex);
}

// ============================================
// CONTACTS VIEW
// ============================================

function byDistance(a, b) {
  return (a.distance_miles == null ? 9999 : a.distance_miles) -
         (b.distance_miles == null ? 9999 : b.distance_miles);
}

// ── Sky / Sea mode ──
function toggleMode() {
  setMode(SkyDex.mode === 'air' ? 'sea' : 'air');
}

function setMode(mode) {
  SkyDex.mode = mode;
  _trails = {};   // don't carry map breadcrumbs across air/sea
  const skyBtn = document.getElementById('mode-sky');
  const seaBtn = document.getElementById('mode-sea');
  const atmoBtn = document.getElementById('mode-atmo');
  const landBtn = document.getElementById('mode-land');
  const etherBtn = document.getElementById('mode-ether');
  if (skyBtn) skyBtn.classList.toggle('active', mode === 'air');
  if (seaBtn) seaBtn.classList.toggle('active', mode === 'sea');
  if (atmoBtn) atmoBtn.classList.toggle('active', mode === 'atmo');
  if (landBtn) landBtn.classList.toggle('active', mode === 'land');
  if (etherBtn) etherBtn.classList.toggle('active', mode === 'ether');

  document.body.classList.toggle('sea-mode', mode === 'sea');
  document.body.classList.toggle('atmo-mode', mode === 'atmo');
  document.body.classList.toggle('land-mode', mode === 'land');
  document.body.classList.toggle('ether-mode', mode === 'ether');

  // AtmoDex / LandDex / EtherDex repurpose the bottom nav for their own views.
  if (mode === 'atmo' || mode === 'land' || mode === 'ether') {
    setNavLabels(mode);
    SkyDex.facts = [];
    SkyDex.factIndex = 0;
    updateTicker();
    fetchFacts();
    // Each world opens on its most-loved view: Forecast, Grand Central, Radio.
    showView(mode === 'atmo' ? 'atmo-forecast' : mode === 'land' ? 'land-history' : 'ether-tuner');
    return;
  }

  setNavLabels(false);
  const sea = mode === 'sea';
  const title = document.getElementById('live-title');
  if (title) title.textContent = sea ? 'Wild Vessels' : 'Wild Aircraft';
  const sub = document.getElementById('live-subtitle');
  if (sub) sub.textContent = sea ? 'Marine traffic off Stratford' : 'Nearby contacts in range';
  const cap = document.querySelector('.radar-caption');
  if (cap) cap.textContent = sea ? 'Range view · Long Island Sound' : 'Range view · Stratford, CT';
  const et = document.querySelector('#empty-state .empty-title');
  if (et) et.textContent = sea ? 'No vessels in range!' : 'No wild aircraft in range!';

  // Section titles per mode (so Dex/Stats/Graphs never read "Planedex" in sea mode).
  const setTxt = (id, txt) => { const el = document.getElementById(id); if (el) el.textContent = txt; };
  setTxt('dex-title', sea ? 'Fleetdex' : 'Planedex');
  setTxt('dex-subtitle', sea ? 'Your vessel collection' : 'Your aircraft collection');
  setTxt('stats-title', sea ? "Captain's Log" : 'Trainer Card');
  setTxt('graphs-title', sea ? 'Sea Graphs' : 'Graphs');

  // Reset the three summary-card labels so air labels don't linger in sea mode (or vice-versa).
  const statLabels = sea ? ['Sightings', 'Vessels Logged', 'In Range Now'] : ['Total Seen', 'Unique', 'Day Streak'];
  document.querySelectorAll('#stats-summary .stat-card .stat-card-label').forEach((el, i) => { if (statLabels[i]) el.textContent = statLabels[i]; });

  // Rebuild the Dex filters so their options match the current world.
  rebuildTypeFilter(sea);
  rebuildBadgeFilter(sea);

  document.body.classList.toggle('sea-mode', sea);

  // Swap the fact pool to match the world (clear first so the fallback shows instantly).
  SkyDex.facts = [];
  SkyDex.factIndex = 0;
  updateTicker();
  fetchFacts();

  showView('contacts');
}

// --- Dex badge filter ---
const AIR_BADGE_FILTERS = [
  ['all', 'All Badges'], ['frequent', 'Frequent Flyer'], ['centurion', 'Centurion (100+)'],
  ['veteran', 'Veteran (20yr+)'], ['brandnew', 'Brand New (≤5yr)'], ['military', 'Military'],
  ['heavy', 'Heavy'], ['rotor', 'Rotor'], ['emergency', 'Emergency'],
];
const SEA_BADGE_FILTERS = [
  ['all', 'All Badges'], ['frequent', 'Frequent Visitor'], ['regular', 'Harbor Regular (100+)'],
  ['bigship', 'Big Ship (200m+)'], ['anchored', 'Anchored'], ['first', 'First Sighting'],
];

/** Repopulate the Dex badge-filter <select> for the current mode. */
function rebuildBadgeFilter(sea) {
  const sel = document.getElementById('dex-filter-badge');
  if (!sel) return;
  sel.innerHTML = (sea ? SEA_BADGE_FILTERS : AIR_BADGE_FILTERS).map(([v, l]) => `<option value="${v}">${l}</option>`).join('');
}

/** Which filterable badges an aircraft row qualifies for (row-derivable only). */
function airBadgeKeys(c) {
  const keys = [];
  const dc = c.detection_count || 0;
  if (dc >= 10) keys.push('frequent');
  if (dc >= 100) keys.push('centurion');
  const yr = parseInt(c.year_built, 10);
  if (yr) { const age = new Date().getFullYear() - yr; if (age >= 20) keys.push('veteran'); if (age <= 5) keys.push('brandnew'); }
  if (c.is_military) keys.push('military');
  const pt = (c.primary_type || '').toLowerCase();
  if (pt === 'heavy') keys.push('heavy');
  if (pt === 'rotor') keys.push('rotor');
  if (c.emergency_seen) keys.push('emergency');
  return keys;
}

/** Which filterable badges a vessel row qualifies for. */
function vesselBadgeKeys(v) {
  const keys = [];
  const dc = v.detection_count || 0;
  if (dc >= 10) keys.push('frequent');
  if (dc >= 100) keys.push('regular');
  if (v.length && v.length >= 200) keys.push('bigship');
  if ([1, 5].includes(v.nav_status)) keys.push('anchored');
  if (dc <= 1) keys.push('first');
  return keys;
}

/** Repopulate the Dex type-filter <select> for air (aircraft types) or sea (vessel categories). */
function rebuildTypeFilter(sea) {
  const sel = document.getElementById('dex-filter-type');
  if (!sel) return;
  const opts = sea
    ? [['all', 'All Types'], ['cargo', 'Cargo'], ['tanker', 'Tanker'], ['passenger', 'Passenger'],
       ['hsc', 'High-Speed'], ['fishing', 'Fishing'], ['sailing', 'Sailing'], ['pleasure', 'Pleasure'],
       ['superyacht', 'Superyacht'], ['tug', 'Tug'], ['government', 'Government'], ['other', 'Other']]
    : [['all', 'All Types'], ['jet', 'Jet'], ['rotor', 'Rotor'], ['sentinel', 'Sentinel'],
       ['heavy', 'Heavy'], ['bizjet', 'Bizjet'], ['voyager', 'Voyager'], ['trainer', 'Trainer'],
       ['hopper', 'Hopper'], ['hauler', 'Hauler'], ['medevac', 'Medevac'], ['commuter', 'Commuter']];
  sel.innerHTML = opts.map(([v, l]) => `<option value="${v}">${l}</option>`).join('');
}

/** Filter-change dispatcher: rerender the right Dex for the current mode. */
function applyDexFilter() {
  if (SkyDex.mode === 'sea') renderFleetList();
  else renderDexList();
}

async function fetchVessels() {
  try {
    const res = await fetch('/api/vessels');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const vessels = (await res.json()).slice().sort(byDistance);
    SkyDex.contacts = vessels;
    renderVessels(vessels);
    renderRadar(vessels, vesselColor);
    if (_mapMode === 'map') renderMap(vessels, vesselColor);
    const tcv = document.getElementById('tracker-count');
    if (tcv) tcv.textContent = `${vessels.length} vessels nearby`;
  } catch (e) {
    console.error('fetchVessels error:', e);
    const list = document.getElementById('contacts-list');
    if (list && list.children.length === 0) renderEmptyState();
  }
}

function renderVessels(vessels) {
  const list = document.getElementById('contacts-list');
  const empty = document.getElementById('empty-state');
  if (!vessels || vessels.length === 0) {
    list.innerHTML = '';
    empty.classList.remove('hidden');
    return;
  }
  empty.classList.add('hidden');

  // Keep distance-rank numbering (matches the radar) but display in two groups.
  const numbered = vessels.map((v, i) => ({ ...v, _num: i + 1 }));
  const moving = numbered.filter(v => !v.anchored);
  const anchored = numbered.filter(v => v.anchored);

  const rowHtml = (v) => {
    const color = vesselColor(v);
    const rarity = (v.rarity || 'common').toLowerCase();
    const ident = v.name || v.callsign || ('MMSI ' + v.mmsi);
    const spd = (v.speed != null) ? `${v.speed.toFixed(1)} kn` : '';
    const crs = (v.course != null) ? headingToCompass(v.course) : '';
    const dist = formatDistance(v.distance_miles);
    const line2 = [v.category, v.nav_status_text].filter(Boolean).join(' · ');
    const dest = v.destination ? `→ ${v.destination}` : '';
    return `
      <div class="contact-row ${rarity === 'legendary' ? 'legendary-glow' : ''} ${v.anchored ? 'anchored-row' : ''}" onclick="openVessel('${v.mmsi}')">
        <div class="contact-num">${v._num}</div>
        <div class="type-badge-container" style="background:${color};color:#fff;">${vesselIconSvg(v.icon)}</div>
        <div class="contact-info">
          <div class="contact-callsign">${flagHtml(v.country ? { iso2: v.country, name: v.country } : null)}${ident}${v.anchored ? ' <span class="anchor-chip">' + ANCHOR_SVG + '</span>' : ''}</div>
          <div class="contact-model">${line2 || 'Vessel'}</div>
          <div class="contact-route">${dest}</div>
          <div class="contact-kid">${kidShipLine(v)}</div>
          ${renderRarityStars(rarity)}
        </div>
        <div class="contact-stats">
          <div class="distance-display">${[spd, crs].filter(Boolean).join(' · ')}</div>
          <div class="distance-display" style="font-size:13px;color:var(--accent-blue);font-weight:bold;">${dist}</div>
        </div>
      </div>`;
  };

  let html = moving.map(rowHtml).join('');
  if (anchored.length) {
    html += `<div class="live-subsection">${ANCHOR_SVG} Anchored &amp; Moored (${anchored.length})</div>`;
    html += anchored.map(rowHtml).join('');
  }
  list.innerHTML = html;
}

async function fetchContacts() {
  if (SkyDex.mode === 'sea') return fetchVessels();
  try {
    const res = await fetch('/api/contacts');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    // Sort once (nearest first) so the list / radar / map numbers all match.
    const contacts = (data.contacts || data || []).slice().sort(byDistance);
    SkyDex.contacts = contacts;
    checkForNewCatches(contacts);
    renderContacts(contacts);
    renderRadar(contacts);
    if (_mapMode === 'map') renderMap(contacts);
    const tca = document.getElementById('tracker-count');
    if (tca) tca.textContent = `${contacts.length} aircraft nearby`;
  } catch (e) {
    console.error('fetchContacts error:', e);
    const list = document.getElementById('contacts-list');
    if (list.children.length === 0) renderEmptyState();
  }
}

function renderContacts(contacts) {
  const list = document.getElementById('contacts-list');
  const empty = document.getElementById('empty-state');

  if (!contacts || contacts.length === 0) {
    list.innerHTML = '';
    empty.classList.remove('hidden');
    return;
  }

  empty.classList.add('hidden');

  const currentHexes = new Set();
  if (list.children.length > 0) {
    Array.from(list.children).forEach(row => {
      if (row.dataset.hex) currentHexes.add(row.dataset.hex);
    });
  }

  let html = '';
  contacts.forEach((c, i) => {
    const type = primaryType(c);
    const rarity = rarityKey(c);
    const alt = formatAltitude(c.altitude);
    const dist = formatDistance(c.distance_miles);
    const spd = c.ground_speed ? `${Math.round(c.ground_speed)} kt` : '';
    const hdg = (c.track !== undefined && c.track !== null) ? headingToCompass(c.track) : '';
    const phaseIcon = c.phase === 'Climbing' ? ICONS.climb : (c.phase === 'Descending' ? ICONS.descend : '');
    const isNew = !currentHexes.has(c.hex);
    const animClass = isNew ? 'entry-animation' : '';
    const rarityClass = rarity === 'legendary' ? 'legendary-glow' : '';

    const ident = c.callsign || c.registration || c.hex || 'UNKNOWN';
    const modelLine = (c.model || c.type_code || 'Unknown aircraft') + (c.operator ? ' \u2014 ' + c.operator : '');
    const route = (c.origin_icao || c.dest_icao || c.origin_iata || c.dest_iata)
      ? `${c.origin_iata || c.origin_icao || '???'} \u2192 ${c.dest_iata || c.dest_icao || '???'}`
      : '';
    const badges = [];
    if (c.contrail_likely) badges.push('<span class="badge-chip contrail">Contrail</span>');

    html += `
      <div class="contact-row ${animClass} ${rarityClass}" data-hex="${c.hex || ''}" onclick="openDex('${c.hex || ''}')">
        <div class="contact-num">${i + 1}</div>
        ${renderTypeIcon(type)}
        <div class="contact-info">
          <div class="contact-callsign">${flagHtml(c.country)}${ident} ${badges.join('')}</div>
          <div class="contact-model">${airlineLogoHtml(c.airline_iata, 'airline-logo-sm')}${modelLine}</div>
          <div class="contact-route">${route}</div>
          <div class="contact-kid">${kidPlaneLine(c)}</div>
          ${renderRarityStars(rarity)}
        </div>
        <div class="contact-stats">
          <div class="altitude-display ${alt.class}">${phaseIcon}${alt.text}</div>
          <div class="distance-display">${[spd, hdg].filter(Boolean).join(' \u00b7 ')}</div>
          <div class="distance-display" style="font-size:13px;color:var(--accent-blue);font-weight:bold;">${dist}</div>
        </div>
      </div>`;
  });

  list.innerHTML = html;
}

/** Plain-English one-liner for the live list — what a kid would say. */
function kidPlaneLine(c) {
  const who = c.airline_name || c.operator || '';
  const phase = c.phase === 'Climbing' ? 'climbing up'
    : c.phase === 'Descending' ? 'coming down to land'
    : (c.altitude || 0) > 20000 ? 'cruising way up high'
    : (c.altitude || 0) > 0 ? 'flying low' : 'on the move';
  const to = c.dest_city ? ` → going to ${c.dest_city}` : '';
  return `${who ? who + ' — ' : ''}${phase}${to}`;
}

function kidShipLine(v) {
  const what = { Cargo: 'A big cargo ship', Tanker: 'A giant tanker',
    Tug: 'A little tugboat doing a big job', Sailing: 'A sailboat',
    Superyacht: 'A fancy superyacht', Fishing: 'A fishing boat',
    Government: 'A patrol boat', Passenger: 'A ferry full of people',
    Pleasure: 'Somebody’s boat out for fun' }[v.category] || 'A boat';
  const doing = v.anchored ? 'parked on the water'
    : (v.speed || 0) < 1 ? 'barely moving'
    : (v.speed || 0) > 15 ? 'zooming across the Sound' : 'cruising along';
  return `${what}, ${doing}`;
}

/** Pick the type key: prefer the stored/served behavioral classification. */
function primaryType(c) {
  if (c.primary_type) {
    const k = String(c.primary_type).toLowerCase();
    if (AIRCRAFT_TYPES[k]) return k;
  }
  if (Array.isArray(c.types) && c.types.length) {
    const key = (c.types[0].type || '').toLowerCase();
    if (AIRCRAFT_TYPES[key]) return key;
  }
  return getAircraftType(c);
}

/** Radar/range view around home; numbered dots match the list numbers.
 *  colorFn(item) overrides the dot color (used for SeaDex vessels).
 *  Contacts dead-reckon (glide along heading at speed) between server updates. */
let _radarTimer = null;

function renderRadar(contacts, colorFn) {
  const el = document.getElementById('radar');
  if (!el) return;
  contacts = (contacts || []).slice().sort(byDistance);

  const SIZE = 220, C = SIZE / 2, R = 96;
  let maxMi = 5;
  contacts.forEach(c => { if (c.distance_miles != null && c.distance_miles > maxMi) maxMi = c.distance_miles; });
  maxMi = Math.max(1, Math.ceil(maxMi));

  // Project each contact to a local east/north (miles) and give it a velocity
  // vector from its ground speed + track, so we can advance it between polls.
  const items = contacts.map((c, i) => {
    let east0 = null, north0 = null, vE = 0, vN = 0;
    if (c.bearing != null && c.distance_miles != null) {
      const t = c.bearing * Math.PI / 180;     // 0=N up, 90=E right
      east0 = c.distance_miles * Math.sin(t);
      north0 = c.distance_miles * Math.cos(t);
      if (c.ground_speed && c.track != null) {
        const mps = (c.ground_speed * 1.15078) / 3600;  // knots -> miles/sec
        const tk = c.track * Math.PI / 180;
        vE = mps * Math.sin(tk);
        vN = mps * Math.cos(tk);
      }
    }
    const color = colorFn ? colorFn(c) : (AIRCRAFT_TYPES[primaryType(c)] || AIRCRAFT_TYPES.jet).color;
    return { num: i + 1, east0, north0, vE, vN, color };
  });

  SkyDex._radar = { items, maxMi, SIZE, C, R, baseTime: performance.now() };
  _drawRadar();

  // Only animate when the radar is actually visible AND something is moving
  // (skips idle CPU for anchored boats and when the map is the active view).
  if (_radarTimer) { clearInterval(_radarTimer); _radarTimer = null; }
  if (_mapMode === 'radar' && items.some(it => Math.abs(it.vE) > 1e-9 || Math.abs(it.vN) > 1e-9)) {
    _radarTimer = setInterval(_drawRadar, 120);  // ~8 fps glide
  }
}

/** Draw the radar from the stored items, advanced by elapsed time. */
function _drawRadar() {
  const el = document.getElementById('radar');
  const data = SkyDex._radar;
  if (!el || !data) return;
  const { items, maxMi, SIZE, C, R } = data;
  const dt = (performance.now() - data.baseTime) / 1000;  // seconds since last poll
  const ringMi = [maxMi / 3, (2 * maxMi) / 3, maxMi];

  let svg = `<svg viewBox="0 0 ${SIZE} ${SIZE}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto;display:block;">`;
  svg += `<rect width="${SIZE}" height="${SIZE}" rx="10" fill="#0a0f0a"/>`;
  [R / 3, 2 * R / 3, R].forEach((r, i) => {
    svg += `<circle cx="${C}" cy="${C}" r="${r}" fill="none" stroke="#1f3a1f" stroke-width="1"/>`;
    svg += `<text x="${C + 3}" y="${C - r + 10}" fill="#3a6a3a" font-size="8">${Math.round(ringMi[i])}mi</text>`;
  });
  svg += `<line x1="${C}" y1="${C - R}" x2="${C}" y2="${C + R}" stroke="#1f3a1f" stroke-width="1"/>`;
  svg += `<line x1="${C - R}" y1="${C}" x2="${C + R}" y2="${C}" stroke="#1f3a1f" stroke-width="1"/>`;
  svg += `<text x="${C}" y="${C - R - 3}" fill="#4a8a4a" font-size="9" text-anchor="middle">N</text>`;
  svg += `<text x="${C}" y="${C + R + 12}" fill="#4a8a4a" font-size="9" text-anchor="middle">S</text>`;
  svg += `<text x="${C + R + 8}" y="${C + 3}" fill="#4a8a4a" font-size="9" text-anchor="middle">E</text>`;
  svg += `<text x="${C - R - 8}" y="${C + 3}" fill="#4a8a4a" font-size="9" text-anchor="middle">W</text>`;
  svg += `<circle cx="${C}" cy="${C}" r="3" fill="#FFCB05"/>`;

  items.forEach(it => {
    if (it.east0 == null) return;
    const east = it.east0 + it.vE * dt;
    const north = it.north0 + it.vN * dt;
    const dist = Math.hypot(east, north);
    const r = dist > 0 ? Math.min(R, (dist / maxMi) * R) : 0;
    const x = dist > 0 ? C + r * (east / dist) : C;
    const y = dist > 0 ? C - r * (north / dist) : C;
    svg += `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="8" fill="${it.color}" stroke="#0a0f0a" stroke-width="1"/>`;
    svg += `<text x="${x.toFixed(1)}" y="${(y + 3).toFixed(1)}" fill="#fff" font-size="9" font-weight="bold" text-anchor="middle">${it.num}</text>`;
  });
  svg += `</svg>`;
  el.innerHTML = svg;
}

// ============================================
// LIVE MAP (Leaflet) — toggles with the radar
// ============================================
let _map = null;
let _mapMarkers = [];
let _mapMode = 'map';   // map is the primary live view; radar is the fallback
let _trails = {};       // id -> [[lat,lon], ...] breadcrumb history for trailing lines
const TRAIL_MAX = 30;   // how many past positions to keep per contact
let _mapGlide = [];     // per-contact dead-reckoning records for smooth motion
let _mapTimer = null;   // interval that glides map markers between polls
let _glideState = {};   // id -> {lat, lon, t} last REAL fix + when we first saw it
// How far ahead the dashed "projected course" line reaches, in minutes.
const PROJECT_MINUTES_AIR = 5;
const PROJECT_MINUTES_SEA = 15;

function initMap() {
  if (_map || !window.L || !window.SKYDEX_HOME) return;
  const home = window.SKYDEX_HOME;
  _map = L.map('map', { zoomControl: true, attributionControl: true }).setView([home.lat, home.lon], 10);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 18, attribution: '&copy; OpenStreetMap',
  }).addTo(_map);
  L.circleMarker([home.lat, home.lon], { radius: 5, color: '#FFCB05', fillColor: '#FFCB05', fillOpacity: 1 })
    .addTo(_map).bindTooltip('Home');
  if (home.radius) {
    L.circle([home.lat, home.lon], { radius: home.radius * 1609.34, color: '#30A7D7', weight: 1, fill: false }).addTo(_map);
  }
}

function showMapMode(mode) {
  _mapMode = mode;
  const radarEl = document.getElementById('radar');
  const mapEl = document.getElementById('map');
  const bRadar = document.getElementById('rt-radar');
  const bMap = document.getElementById('rt-map');
  if (mode === 'map') {
    if (radarEl) radarEl.style.display = 'none';
    if (mapEl) mapEl.style.display = 'block';
    if (bMap) bMap.classList.add('active');
    if (bRadar) bRadar.classList.remove('active');
    initMap();
    if (_map) {
      setTimeout(() => _map.invalidateSize(), 60);
      renderMap(SkyDex.contacts || [], SkyDex.mode === 'sea' ? vesselColor : null);
    }
  } else {
    if (mapEl) mapEl.style.display = 'none';
    if (radarEl) radarEl.style.display = 'block';
    if (bRadar) bRadar.classList.add('active');
    if (bMap) bMap.classList.remove('active');
    if (_mapTimer) { clearInterval(_mapTimer); _mapTimer = null; }  // stop gliding a hidden map
    // Re-render now so the switch is instant and the glide loop restarts.
    renderRadar(SkyDex.contacts || [], SkyDex.mode === 'sea' ? vesselColor : null);
  }
}

/** Heading (deg from N) + speed (knots) for a contact, or null if unknown. */
function _contactVector(c) {
  const brg = (c.track != null) ? c.track
            : (c.course != null) ? c.course
            : (c.heading != null) ? c.heading : null;
  const kts = (c.ground_speed != null) ? c.ground_speed
            : (c.speed != null) ? c.speed : null;
  if (brg == null || kts == null) return null;
  return { brg, kts };
}

/** Dead-reckon a lat/lon forward by distNm nautical miles along bearingDeg. */
function _projectLatLon(lat, lon, bearingDeg, distNm) {
  const br = bearingDeg * Math.PI / 180;
  const dLat = (distNm / 60) * Math.cos(br);
  const dLon = (distNm / 60) * Math.sin(br) / Math.cos(lat * Math.PI / 180);
  return [lat + dLat, lon + dLon];
}

/** A type-shaped map marker (plane / prop / heli / fighter / ship / sail). */
function mapIconHtml(c, num, color) {
  const isSea = SkyDex.mode === 'sea';
  const glyph = isSea ? vesselIconSvg(c.icon) : typeIconSvg(primaryType(c));
  // All silhouettes are top-down (nose/bow up), so rotate them to heading.
  const vv = _contactVector(c);
  const rotate = vv ? ` transform:rotate(${Math.round(vv.brg)}deg);` : '';
  return `<div class="map-icon" style="border-color:${color};">`
       + `<span class="mi-glyph" style="color:${color};${rotate}">${glyph}</span>`
       + `<span class="mi-num" style="background:${color};">${num}</span>`
       + `</div>`;
}

/** Rebuild the projected-course geometry from a live position (used on every
 *  glide tick so the vector tracks the marker). Returns [stubPt, endPt]. */
function _courseGeom(lat, lon, brg, kts, projMin) {
  const distNm = kts * (projMin / 60);
  return [
    _projectLatLon(lat, lon, brg, distNm * 0.25),
    _projectLatLon(lat, lon, brg, distNm),
  ];
}

function renderMap(contacts, colorFn) {
  if (!_map || !window.L) return;
  _mapMarkers.forEach(m => _map.removeLayer(m));
  _mapMarkers = [];
  _mapGlide = [];
  const projMin = (SkyDex.mode === 'sea') ? PROJECT_MINUTES_SEA : PROJECT_MINUTES_AIR;
  const seen = {};
  const now0 = performance.now();
  (contacts || []).slice().sort(byDistance).forEach((c, i) => {
    if (c.lat == null || c.lon == null) return;
    const color = colorFn ? colorFn(c) : (AIRCRAFT_TYPES[primaryType(c)] || AIRCRAFT_TYPES.jet).color;
    const id = String(c.hex || c.mmsi || `#${i}`);
    seen[id] = true;

    // Velocity (deg/sec) from heading + speed, for dead-reckoning.
    const v = _contactVector(c);
    let vLat = 0, vLon = 0;
    if (v && v.kts >= 0.5) {
      const nmPerSec = v.kts / 3600;
      const br = v.brg * Math.PI / 180;
      vLat = (nmPerSec / 60) * Math.cos(br);
      vLon = (nmPerSec / 60) * Math.sin(br) / Math.cos(c.lat * Math.PI / 180);
    }

    // Persist a per-contact baseline; only reset the clock when the REAL fix
    // moves. Resetting every 1s poll would restart the glide → sawtooth jitter.
    const prev = _glideState[id];
    if (!prev || prev.lat !== c.lat || prev.lon !== c.lon) {
      _glideState[id] = { lat: c.lat, lon: c.lon, t: now0 };
    }
    const t0 = _glideState[id].t;
    const dt0 = Math.min((now0 - t0) / 1000, 30);
    const dlat = c.lat + vLat * dt0;   // where it should be *right now*
    const dlon = c.lon + vLon * dt0;

    // Trailing line — breadcrumb of real fixes, head joined to the live position.
    const trail = _trails[id] || (_trails[id] = []);
    const last = trail[trail.length - 1];
    if (!last || last[0] !== c.lat || last[1] !== c.lon) {
      trail.push([c.lat, c.lon]);
      if (trail.length > TRAIL_MAX) trail.shift();
    }
    const trailLine = L.polyline(trail.concat([[dlat, dlon]]),
      { color, weight: 2, opacity: 0.45, lineCap: 'round' }).addTo(_map);
    _mapMarkers.push(trailLine);

    // Course + projected-course lines from the live position.
    let solid = null, dashed = null, tip = null;
    if (v && v.kts >= 0.5) {
      const [stub, end] = _courseGeom(dlat, dlon, v.brg, v.kts, projMin);
      solid = L.polyline([[dlat, dlon], stub], { color, weight: 3, opacity: 0.9 }).addTo(_map);
      dashed = L.polyline([stub, end], { color, weight: 2, opacity: 0.55, dashArray: '5,5' }).addTo(_map);
      tip = L.circleMarker(end, { radius: 3, color, fillColor: color, fillOpacity: 0.9, weight: 0 })
        .addTo(_map).bindTooltip(`~${projMin} min ahead · ${Math.round(v.kts)} kn ${headingToCompass(v.brg)}`);
      _mapMarkers.push(solid, dashed, tip);
    }

    const icon = L.divIcon({
      className: 'plane-marker',
      html: mapIconHtml(c, i + 1, color),
      iconSize: [36, 36], iconAnchor: [18, 18],   // finger-sized now that touch works
    });
    const m = L.marker([dlat, dlon], { icon }).addTo(_map);
    const ident = c.callsign || c.registration || c.hex || c.name || c.mmsi || '';
    m.bindTooltip(`#${i + 1} ${ident} · ${c.model || c.type_code || c.category || ''}`);
    // Tap a marker -> showcase.js draws its origin/destination route line.
    m.on('click', () => { if (window.onMapMarkerTap) window.onMapMarkerTap(c); });
    _mapMarkers.push(m);

    _mapGlide.push({
      marker: m, solid, dashed, tip, trailLine, trail,
      lat0: c.lat, lon0: c.lon, t0, vLat, vLon,
      brg: v ? v.brg : 0, kts: v ? v.kts : 0, projMin,
    });
  });

  // Drop trails/baselines for contacts no longer in range (keeps memory bounded).
  Object.keys(_trails).forEach(id => { if (!seen[id]) delete _trails[id]; });
  Object.keys(_glideState).forEach(id => { if (!seen[id]) delete _glideState[id]; });

  // Animate positions between polls, but only when something is actually moving.
  if (_mapTimer) { clearInterval(_mapTimer); _mapTimer = null; }
  if (_mapGlide.some(g => g.vLat !== 0 || g.vLon !== 0)) {
    _mapTimer = setInterval(_glideMap, 250);  // 4 fps — smooth without taxing the Pi
  }
}

/** Advance every glided contact from its own baseline fix time. */
function _glideMap() {
  if (!_map || _mapMode !== 'map') return;
  const now = performance.now();
  _mapGlide.forEach(g => {
    if (g.vLat === 0 && g.vLon === 0) return;
    // Cap extrapolation so a stalled feed (e.g. OpenSky cooldown) can't fling
    // markers off into space — freeze after 30s until real data resumes.
    const dt = Math.min((now - g.t0) / 1000, 30);
    const glat = g.lat0 + g.vLat * dt;
    const glon = g.lon0 + g.vLon * dt;
    g.marker.setLatLng([glat, glon]);
    if (g.trailLine) g.trailLine.setLatLngs(g.trail.concat([[glat, glon]]));
    if (g.solid) {
      const [stub, end] = _courseGeom(glat, glon, g.brg, g.kts, g.projMin);
      g.solid.setLatLngs([[glat, glon], stub]);
      g.dashed.setLatLngs([stub, end]);
      g.tip.setLatLng(end);
    }
  });
}

function renderEmptyState() {
  document.getElementById('contacts-list').innerHTML = '';
  document.getElementById('empty-state').classList.remove('hidden');
}

// ============================================
// DEX (COLLECTION) VIEW
// ============================================

async function fetchDex() {
  // Cache-first: render whatever we already have instantly (the prefetch in
  // controls.js usually filled this at startup), then refresh in background.
  if (SkyDex.dexData) renderDexList();
  try {
    const res = await fetch('/api/dex?limit=1000&sort=detection_count');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    SkyDex.dexData = await res.json();
    renderDexList();
  } catch (e) {
    console.error('fetchDex error:', e);
    if (!SkyDex.dexData) document.getElementById('dex-list').innerHTML = '<div class="text-center" style="color:var(--text-dim);padding:20px;">Unable to load Planedex.</div>';
  }
}

function renderDexList() {
  const container = document.getElementById('dex-list');
  const empty = document.getElementById('dex-empty');
  const data = SkyDex.dexData;
  const allEntries = Array.isArray(data) ? data : ((data && data.entries) || []);

  if (allEntries.length === 0) {
    container.innerHTML = '';
    empty.classList.remove('hidden');
    document.getElementById('dex-count').textContent = '0';
    return;
  }

  // Apply type / rarity filters and sort from the filter bar.
  const ft = (document.getElementById('dex-filter-type') || {}).value || 'all';
  const fr = (document.getElementById('dex-filter-rarity') || {}).value || 'all';
  const sort = (document.getElementById('dex-sort') || {}).value || 'count';
  const rarityOrder = { legendary: 5, epic: 4, rare: 3, uncommon: 2, common: 1 };

  const fb = (document.getElementById('dex-filter-badge') || {}).value || 'all';

  let entries = allEntries.slice();
  if (ft !== 'all') entries = entries.filter(e => primaryType(e) === ft);
  if (fr !== 'all') entries = entries.filter(e => rarityKey(e) === fr);
  if (fb !== 'all') entries = entries.filter(e => airBadgeKeys(e).includes(fb));

  // Time window (defaults to This Week): keeps the first Dex open fast by
  // rendering dozens of cards instead of the whole all-time collection.
  const fw = (document.getElementById('dex-filter-window') || {}).value || 'week';
  if (fw !== 'all') {
    const cutoff = Date.now() / 1000 - (fw === 'week' ? 7 : 30) * 86400;
    const windowed = entries.filter(e => (e.last_seen || 0) >= cutoff);
    if (windowed.length) entries = windowed;   // quiet week? fall back to all
  }
  entries.sort((a, b) => {
    if (sort === 'dex') return (a.dex_number || 99999) - (b.dex_number || 99999);
    if (sort === 'rarity') return (rarityOrder[rarityKey(b)] || 0) - (rarityOrder[rarityKey(a)] || 0);
    if (sort === 'name') return String(a.model || a.hex).localeCompare(String(b.model || b.hex));
    return (b.detection_count || 0) - (a.detection_count || 0); // count
  });

  document.getElementById('dex-count').textContent = entries.length;

  if (entries.length === 0) {
    container.innerHTML = '<div class="text-center" style="color:var(--text-dim);padding:24px;grid-column:1/-1;">No aircraft match this filter.</div>';
    empty.classList.add('hidden');
    return;
  }

  empty.classList.add('hidden');

  // List mode: compact photo-free rows — instant even with the full collection.
  const vm = (document.getElementById('dex-view-mode') || {}).value || 'cards';
  if (vm === 'list') {
    container.classList.add('dex-as-list');
    container.innerHTML = entries.map(e => {
      const type = primaryType(e);
      const ti = AIRCRAFT_TYPES[type] || AIRCRAFT_TYPES.jet;
      const num = e.dex_number || hexToDexNumber(e.hex);
      return `<div class="dexl-row" onclick="openDex('${e.hex}')">
          <span class="dexl-num">#${num}</span>
          <span class="dexl-ic" style="color:${ti.color};">${typeIconSvg(type)}</span>
          <span class="dexl-main"><b>${e.registration || e.hex}</b>
            <small>${e.model || ''}${e.operator ? ' · ' + e.operator : ''}</small></span>
          <span class="dexl-count">${e.detection_count || 0}×</span>
          ${renderRarityStars(rarityKey(e))}
        </div>`;
    }).join('');
    return;
  }
  container.classList.remove('dex-as-list');

  let html = '';
  entries.forEach((entry, idx) => {
    const type = primaryType(entry);
    const rarity = rarityKey(entry);
    const dexNum = entry.dex_number || hexToDexNumber(entry.hex);
    const typeInfo = AIRCRAFT_TYPES[type] || AIRCRAFT_TYPES.jet;
    const rarityInfo = RARITY[rarity] || RARITY.common;
    const count = entry.detection_count || entry.count || 0;
    const model = entry.model || entry.registration || entry.hex || 'Unknown';

    html += `
      <div class="dex-card" onclick="openDex('${entry.hex}')" style="animation: entry-bounce 0.4s ease-out ${Math.min(idx, 20) * 0.03}s both;">
        <div class="dex-card-number">#${dexNum}</div>
        <div class="dex-card-sprite" style="background:${typeInfo.color}22;border:2px solid ${typeInfo.color};color:${typeInfo.color};">
          ${entry.photo_url
            ? photoImg(entry.hex, type, typeInfo.color, 'width:100%;height:100%;object-fit:cover;border-radius:50%;')
            : typeIconBlock(type, typeInfo.color)}
        </div>
        <div class="dex-card-name">${model}</div>
        <div class="dex-card-type" style="color:${typeInfo.color};">${typeInfo.label} Type</div>
        <div class="dex-card-rarity" style="color:${rarityInfo.color};">${rarityInfo.label}</div>
        <div class="dex-card-count">${count} sighting${count !== 1 ? 's' : ''}</div>
      </div>`;
  });

  container.innerHTML = html;
}

// ============================================
// DETAIL VIEW
// ============================================

async function openDex(hex) {
  if (!hex) return;
  SkyDex.previousView = SkyDex.currentView;
  SkyDexAudio.playBeep();

  try {
    let detail;
    try {
      const res = await fetch(`/api/airframe/${hex}`);
      if (res.ok) detail = await res.json();
    } catch (e) { /* ignore */ }

    if (!detail || detail.error) {
      const contactsRes = await fetch('/api/contacts');
      const contactsData = await contactsRes.json();
      const contacts = contactsData.contacts || contactsData || [];
      const match = contacts.find(c => c.hex === hex);
      if (match) {
        renderDetail(match);
        showView('detail');
        return;
      }
      showToast('Aircraft data not found', '');
      return;
    }

    renderDetail(detail);
    showView('detail');
  } catch (e) {
    console.error('openDex error:', e);
    showToast('Error loading aircraft details', '');
  }
}

/** Collectible badge chips for the Dex detail card — tap one for its story. */
function renderBadges(badges) {
  if (!badges || !badges.length) return '';
  return '<div class="dex-badges">' + badges.map(b =>
    `<span class="dex-badge" style="background:${b.color}22;border:1px solid ${b.color};color:${b.color};cursor:pointer;"
       onclick="showChipInfo('${encodeURIComponent(b.label || '')}','${encodeURIComponent(b.title || '')}','${b.color}')">${b.label}</span>`
  ).join('') + '</div>';
}

/** This airframe's own top departure / arrival airports. */
function renderRouteStats(rs) {
  if (!rs || ((!rs.origins || !rs.origins.length) && (!rs.dests || !rs.dests.length))) return '';
  const fmt = (list) => (list && list.length)
    ? list.map(r => `<div><b style="color:var(--text);">${r.code}</b> <span style="color:var(--text-dim);">${r.city || ''}</span> <span style="color:var(--accent-yellow);">${r.count}×</span></div>`).join('')
    : '<div style="color:var(--text-faint);">—</div>';
  return `
    <div class="dex-section-title">This Aircraft's Regulars</div>
    <div style="display:flex;gap:12px;font-size:11px;line-height:1.6;">
      <div style="flex:1;min-width:0;"><div style="color:var(--text-dim);text-transform:uppercase;font-size:10px;margin-bottom:3px;">Departs</div>${fmt(rs.origins)}</div>
      <div style="flex:1;min-width:0;"><div style="color:var(--text-dim);text-transform:uppercase;font-size:10px;margin-bottom:3px;">Arrives</div>${fmt(rs.dests)}</div>
    </div>`;
}

function renderDetail(data) {
  // Support both API response formats
  const aircraft = data.airframe || data;
  const type = primaryType({ ...aircraft, types: data.types });
  const rarity = rarityKey(aircraft);
  const tier = data.evolution_tier || getTier(aircraft.detection_count || aircraft.count);
  const dexNum = aircraft.dex_number || hexToDexNumber(aircraft.hex);
  const typeInfo = AIRCRAFT_TYPES[type];
  const alt = formatAltitude(aircraft.altitude);
  const history = data.history || [];
  const sightings = data.sightings || [];

  const container = document.getElementById('detail-content');
  container.innerHTML = `
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;cursor:pointer;" onclick="goBack()">
      <span style="font-size:18px;color:var(--accent-blue);">&#9664;</span>
      <span style="font-size:12px;color:var(--text-dim);">Back to list</span>
    </div>

    <div class="dex-detail-layout">
      <div class="dex-detail-left">
        <div class="dex-number">#${dexNum}</div>
        <div class="dex-name">${flagHtml(aircraft.country)}${aircraft.callsign || aircraft.registration || 'UNKNOWN'}</div>
        ${renderTypeBadge([type])}
        ${renderRarityStars(rarity)}
        ${aircraft.airline_name ? `<div style="display:flex;align-items:center;gap:6px;margin-top:6px;justify-content:center;">${airlineLogoHtml(aircraft.airline_iata)}<span style="font-size:12px;color:var(--text);">${aircraft.airline_name}</span></div>` : ''}

        ${renderBadges(data.badges)}

        <div class="dex-photo-frame ${rarity === 'legendary' ? 'legendary-glow' : ''}">
          ${photoImg(aircraft.hex, type, typeInfo.color, 'width:100%;height:100%;object-fit:cover;')}
        </div>
        ${aircraft.photo_credit ? `<div class="photo-credit">Photo © ${aircraft.photo_credit} · Planespotters</div>` : ''}

        ${data.type_fact ? `<div class="dex-fact"><span class="dex-fact-label">Did you know?</span> ${data.type_fact}</div>` : ''}

        ${renderXpBar(tier, aircraft.detection_count || aircraft.count)}

        ${aircraft.hex ? `<div style="text-align:center;margin-top:10px;">
          <button class="day-summary-btn" style="width:auto;display:inline-flex;margin:0;"
            onclick="followCraft('air','${aircraft.hex}','${String(aircraft.registration || aircraft.callsign || '').replace(/'/g, '')}')">
            &#128205; Follow this plane</button>
        </div>` : ''}

        <div style="margin-top:8px;font-size:11px;color:var(--text-dim);text-align:center;">
          ${typeInfo.desc} &bull; ${RARITY[rarity].label}
        </div>
      </div>

      <div class="dex-detail-right">
        ${(aircraft.origin_iata || aircraft.origin_icao || aircraft.dest_iata || aircraft.dest_icao) ? `
        <div class="route-banner">
          <div class="route-banner-line">${aircraft.origin_city || aircraft.origin_icao || '—'} (${aircraft.origin_iata || aircraft.origin_icao || '?'}) → ${aircraft.dest_city || aircraft.dest_icao || '—'} (${aircraft.dest_iata || aircraft.dest_icao || '?'})</div>
          ${(aircraft.origin_name || aircraft.dest_name) ? `<div class="route-banner-sub">${aircraft.origin_name || aircraft.origin_icao || '?'} → ${aircraft.dest_name || aircraft.dest_icao || '?'}</div>` : ''}
          ${aircraft.airline_name ? `<div class="route-banner-sub">${aircraft.airline_name}${aircraft.callsign ? ' · ' + aircraft.callsign : ''}</div>` : ''}
        </div>` : ''}
        ${(() => { const wow = [kidCompareAlt(aircraft.altitude), kidCompareSpeed(aircraft.ground_speed || aircraft.speed)].filter(Boolean).join(' · ');
          return wow ? `<div class="dex-fact">&#10024; Right now: ${wow}</div>` : ''; })()}
        <div class="dex-section-title">Aircraft Data</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;font-size:12px;margin-bottom:12px;">
          <div><span style="color:var(--text-dim);">Hex:</span> <span style="color:var(--text);font-family:monospace;">${aircraft.hex || '---'}</span></div>
          <div><span style="color:var(--text-dim);">Model:</span> <span style="color:var(--text);">${aircraft.model || aircraft.type_code || 'Unknown'}</span></div>
          <div><span style="color:var(--text-dim);">Altitude:</span> <span style="color:${alt.class === 'altitude-high' ? '#ff6b6b' : 'var(--text)'};font-weight:bold;">${alt.text}</span></div>
          <div><span style="color:var(--text-dim);">Speed:</span> <span style="color:var(--text);">${formatSpeed(aircraft.ground_speed || aircraft.speed)}</span></div>
          <div><span style="color:var(--text-dim);">Heading:</span> <span style="color:var(--text);">${aircraft.track || aircraft.heading || '---'}\u00B0 (${headingToCompass(aircraft.track || aircraft.heading)})</span></div>
          <div><span style="color:var(--text-dim);">Distance:</span> <span style="color:var(--text);">${formatDistance(aircraft.distance_miles || aircraft.distance)}</span></div>
          <div><span style="color:var(--text-dim);">Phase:</span> <span style="color:var(--accent-blue);font-weight:bold;">${data.phase || '—'}</span></div>
          <div><span style="color:var(--text-dim);">Contrail:</span> <span style="color:var(--text);">${data.contrail_likely ? 'Likely ✦' : 'Unlikely'}</span></div>
          ${(aircraft.origin_iata || aircraft.origin_icao) ? `<div><span style="color:var(--text-dim);">From:</span> <span style="color:var(--text);">${aircraft.origin_iata || aircraft.origin_icao}${aircraft.origin_city ? ' · ' + aircraft.origin_city : ''}${aircraft.origin_country ? ', ' + aircraft.origin_country : ''}</span></div>` : ''}
          ${(aircraft.dest_iata || aircraft.dest_icao) ? `<div><span style="color:var(--text-dim);">To:</span> <span style="color:var(--text);">${aircraft.dest_iata || aircraft.dest_icao}${aircraft.dest_city ? ' · ' + aircraft.dest_city : ''}${aircraft.dest_country ? ', ' + aircraft.dest_country : ''}</span></div>` : ''}
          <div><span style="color:var(--text-dim);">Seen:</span> <span style="color:var(--accent-yellow);">${aircraft.detection_count || aircraft.count || 1} time${(aircraft.detection_count || aircraft.count || 1) > 1 ? 's' : ''}</span></div>
          <div><span style="color:var(--text-dim);">Operator:</span> <span style="color:var(--text);">${aircraft.operator || 'Unknown'}</span></div>
          ${aircraft.year_built ? `<div><span style="color:var(--text-dim);">Built:</span> <span style="color:var(--text);">${aircraft.year_built}</span></div>` : ''}
          ${aircraft.first_seen ? `<div><span style="color:var(--text-dim);">First spotted:</span> <span style="color:var(--text);">${new Date(aircraft.first_seen * 1000).toLocaleDateString()}</span></div>` : ''}
        </div>

        <div class="dex-section-title">Type Specs ${aircraft.type_code ? '(' + aircraft.type_code + ')' : ''}</div>
        ${renderSpecBars(data.specs)}

        <div id="acars-thread"></div>

        ${renderRouteStats(data.route_stats)}

        <div class="dex-section-title">Sighting Log</div>
        <div class="battle-log">
          ${sightings.length
            ? sightings.map(s => {
                const t = s.started_at ? fmtDateTimeEST(s.started_at * 1000) : '--';
                const durMin = (s.started_at && s.ended_at) ? Math.max(1, Math.round((s.ended_at - s.started_at) / 60)) : null;
                const o = s.origin_city || s.origin_airport;
                const d = s.dest_city || s.dest_airport;
                const route = (o || d) ? ` · ${o || '???'} → ${d || '???'}` : '';
                return `<div class="log-entry"><span class="log-time">${t}</span> seen${durMin ? ' ' + durMin + ' min' : ''}${route}</div>`;
              }).join('')
            : `<div class="log-entry">Live sighting — not yet logged to your Dex.</div>`}
          <div class="log-entry" style="color:var(--text-faint);">${aircraft.detection_count || sightings.length || 0} sighting${(aircraft.detection_count || sightings.length || 0) !== 1 ? 's' : ''} on record</div>
        </div>
      </div>
    </div>`;

  loadAcarsThread(aircraft);
}

/** Datalink (ACARS/VDL-2) chat thread for the Dex detail page. Green bubbles =
 * the plane transmitting (downlink); blue bubbles = ground/controller uplinks.
 * Stays hidden unless the ACARS receiver has heard this airframe. */
async function loadAcarsThread(aircraft) {
  const holder = document.getElementById('acars-thread');
  if (!holder || !aircraft || !aircraft.hex) return;
  try {
    const q = new URLSearchParams({ reg: aircraft.registration || '',
                                    flight: (aircraft.callsign || '').trim() });
    const res = await fetch(`/api/acars/plane/${aircraft.hex}?${q}`);
    if (!res.ok) return;
    const d = await res.json();
    const msgs = d.messages || [];
    if (!d.enabled || !msgs.length) return;
    const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    const who = esc(aircraft.callsign || aircraft.registration || 'PLANE');
    holder.innerHTML = `
      <div class="dex-section-title">Datalink — ACARS</div>
      <div class="acars-chat">` + msgs.map(m => {
        const t = new Date(m.ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        const down = m.dir === 'down';
        const meta = `${down ? who : 'GROUND'} · ${t}` +
          (m.label ? ` · ${esc(m.label)}` : '') + (m.freq ? ` · ${esc(m.freq)} MHz` : '');
        return `<div class="acars-row ${down ? 'down' : 'up'}">
            <div class="acars-bubble ${down ? 'from-plane' : 'from-ground'}">
              <div class="acars-meta">${meta}</div>
              <div class="acars-text">${esc(m.text)}</div>
            </div>
          </div>`;
      }).join('') + `</div>
      <div class="acars-note">Plane &#x2194; ground text messages heard on your own antenna.
        Green = ${who} transmitting &middot; blue = ground replies.</div>`;
  } catch (e) { /* no datalink — section stays hidden */ }
}

// ============================================
// STATS VIEW
// ============================================

async function fetchStats() {
  try {
    const res = await fetch('/api/stats');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    SkyDex.stats = await res.json();
    renderStats();
  } catch (e) {
    console.error('fetchStats error:', e);
    SkyDex.stats = { total: 0, unique: 0, streak: 0, types: {} };
    renderStats();
  }
}

// ============================================
// GRAPHS VIEW
// ============================================

async function fetchGraphs() {
  try {
    const res = await fetch('/api/stats');
    if (res.ok) SkyDex.stats = await res.json();
  } catch (e) {
    console.error('fetchGraphs error:', e);
  }
  renderGraphs();
}

/** Set an element's text by id (no-op if missing). */
function _setText(id, t) { const e = document.getElementById(id); if (e) e.textContent = t; }
/** Show/hide an element by id. */
function _setShow(id, show) { const e = document.getElementById(id); if (e) e.style.display = show ? '' : 'none'; }

function renderGraphs() {
  const s = SkyDex.stats || {};
  // Air section titles (restore in case sea mode relabeled them).
  _setText('g-typeday-title', 'Activity by Fleet Type — by Day');
  _setText('g-hour-title', 'Activity by Hour — Today');
  _setText('g-models-title', 'Top Models');
  _setText('g-operators-title', 'Top Operators');
  _setText('g-dep-title', 'Top Departure Cities');
  _setText('g-arr-title', 'Top Arrival Cities');
  _setText('g-deprare-title', 'Rarest Departure Cities');
  _setText('g-arrrare-title', 'Rarest Arrival Cities');
  _setText('g-emerg-title', 'Emergency Squawks');
  _setShow('g-emerg-title', true);
  _setShow('chart-emergencies', true);
  const ctd = document.getElementById('chart-type-day');
  if (ctd) ctd.innerHTML = renderTypeDayChart(s.activity_by_type_day || {});
  const cht = document.getElementById('chart-hour-today');
  if (cht) cht.innerHTML = renderHourChart(s.activity_by_hour_today || []);
  const cdep = document.getElementById('chart-dep-cities');
  if (cdep) cdep.innerHTML = renderCityChart(s.dep_cities || [], 'var(--accent-blue)');
  const carr = document.getElementById('chart-arr-cities');
  if (carr) carr.innerHTML = renderCityChart(s.arr_cities || [], 'var(--accent-green)');
  const cdepR = document.getElementById('chart-dep-cities-rare');
  if (cdepR) cdepR.innerHTML = renderCityChart(s.dep_cities_rare || [], 'var(--accent-yellow)');
  const carrR = document.getElementById('chart-arr-cities-rare');
  if (carrR) carrR.innerHTML = renderCityChart(s.arr_cities_rare || [], 'var(--accent-yellow)');
  const cem = document.getElementById('chart-emergencies');
  if (cem) cem.innerHTML = renderEmergencies(s.emergency_counts || {}, s.emergencies || []);
  const cmod = document.getElementById('chart-models');
  if (cmod) cmod.innerHTML = renderRankChart(s.top_models || [], 'var(--accent-blue)');
  const cop = document.getElementById('chart-operators');
  if (cop) cop.innerHTML = renderRankChart(s.top_operators || [], 'var(--accent-green)');
}

/** Horizontal bar chart of {label, count} items (models, operators, …). */
function renderRankChart(list, color) {
  if (!list || !list.length) {
    return '<div style="color:var(--text-dim);font-size:11px;padding:8px 0;">No data logged yet.</div>';
  }
  const max = Math.max(1, ...list.map(x => x.count));
  return list.map(x => {
    const pct = (x.count / max) * 100;
    return `<div style="display:flex;align-items:center;gap:6px;margin:4px 0;font-size:11px;">
      <div style="width:120px;flex-shrink:0;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;" title="${x.label}">${x.label}</div>
      <div style="flex:1;min-width:0;background:#222;border-radius:3px;overflow:hidden;height:12px;"><div style="width:${pct}%;height:100%;background:${color};border-radius:3px;"></div></div>
      <div style="width:30px;text-align:right;color:var(--text-dim);">${x.count}</div>
    </div>`;
  }).join('');
}

/** Emergency squawk counts (7500/7600/7700) + recent events log. */
function renderEmergencies(counts, list) {
  const labels = { '7700': '7700 General', '7600': '7600 Radio Fail', '7500': '7500 Hijack' };
  const colors = { '7700': '#ff4d4d', '7600': '#FFCB05', '7500': '#ff5cf0' };
  const total = Object.values(counts || {}).reduce((a, b) => a + b, 0);
  if (!total) {
    return '<div style="color:var(--text-dim);font-size:11px;padding:8px 0;">No emergency squawks recorded — that\'s a good thing.</div>';
  }
  let html = '<div style="display:flex;gap:18px;margin-bottom:10px;">';
  ['7700', '7600', '7500'].forEach(code => {
    html += `<div style="text-align:center;"><div style="font-size:24px;font-weight:bold;color:${colors[code]};">${counts[code] || 0}</div><div style="font-size:9px;color:var(--text-dim);">${labels[code]}</div></div>`;
  });
  html += '</div>';
  if (list && list.length) {
    html += '<div class="battle-log" style="max-height:none;">' + list.map(e => {
      const t = e.timestamp ? fmtDateTimeEST(e.timestamp * 1000) : '--';
      return `<div class="log-entry"><span class="log-time">${t}</span> <b style="color:${colors[e.squawk] || '#ff4d4d'};">${e.squawk}</b> ${e.callsign || e.model || e.hex || ''}</div>`;
    }).join('') + '</div>';
  }
  return html;
}

/** Horizontal bar chart of cities by sighting count. */
function renderCityChart(list, color) {
  if (!list || !list.length) {
    return '<div style="color:var(--text-dim);font-size:11px;padding:8px 0;">No route data yet — needs callsigns + adsbdb lookups.</div>';
  }
  const max = Math.max(1, ...list.map(x => x.count));
  return list.map(x => {
    const pct = (x.count / max) * 100;
    return `<div style="display:flex;align-items:center;gap:6px;margin:4px 0;font-size:11px;">
      <div style="width:108px;flex-shrink:0;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;" title="${x.city}">${x.city}</div>
      <div style="flex:1;min-width:0;background:#222;border-radius:3px;overflow:hidden;height:12px;"><div style="width:${pct}%;height:100%;background:${color};border-radius:3px;"></div></div>
      <div style="width:26px;text-align:right;color:var(--text-dim);">${x.count}</div>
    </div>`;
  }).join('');
}

/** Stacked bar chart: sightings per day-of-week, segmented by fleet type. */
function renderTypeDayChart(byType, colorFn, labelFn) {
  const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  const types = Object.keys(byType || {});
  if (!types.length) {
    return '<div style="color:var(--text-dim);font-size:11px;padding:8px 0;">No sightings logged yet.</div>';
  }
  const totals = days.map((_, d) => types.reduce((sum, t) => sum + ((byType[t] || [])[d] || 0), 0));
  const maxTotal = Math.max(1, ...totals);
  const H = 96;
  const colorFor = colorFn || ((t) => (AIRCRAFT_TYPES[t.toLowerCase()] || { color: '#888' }).color);
  const labelFor = labelFn || ((t) => (AIRCRAFT_TYPES[t.toLowerCase()] || { label: t }).label);

  let bars = `<div style="display:flex;align-items:flex-end;gap:6px;height:${H}px;">`;
  for (let d = 0; d < 7; d++) {
    let segs = '';
    types.forEach((t) => {
      const v = (byType[t] || [])[d] || 0;
      if (!v) return;
      segs += `<div title="${labelFor(t)}: ${v}" style="height:${(v / maxTotal) * H}px;background:${colorFor(t)};"></div>`;
    });
    bars += `<div style="flex:1;display:flex;flex-direction:column;justify-content:flex-end;gap:1px;border-bottom:1px solid #333;">${segs}</div>`;
  }
  bars += '</div>';

  let labels = '<div style="display:flex;gap:6px;margin-top:3px;">';
  for (let d = 0; d < 7; d++) {
    labels += `<div style="flex:1;text-align:center;font-size:9px;color:var(--text-dim);">${days[d]}<br><span style="color:var(--text);">${totals[d] || ''}</span></div>`;
  }
  labels += '</div>';

  let legend = '<div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:8px;">';
  types.forEach((t) => {
    legend += `<span style="display:flex;align-items:center;gap:3px;font-size:10px;color:var(--text-dim);"><span style="width:9px;height:9px;border-radius:2px;background:${colorFor(t)};"></span>${labelFor(t)}</span>`;
  });
  legend += '</div>';

  return bars + labels + legend;
}

/** Bar chart: sightings per hour for today (current hour highlighted). */
function renderHourChart(arr) {
  if (!arr || !arr.length) arr = new Array(24).fill(0);
  const total = arr.reduce((a, b) => a + b, 0);
  if (!total) {
    return '<div style="color:var(--text-dim);font-size:11px;padding:8px 0;">No sightings yet today.</div>';
  }
  const max = Math.max(1, ...arr);
  const H = 72;
  const nowHour = new Date().getHours();

  let bars = `<div style="display:flex;align-items:flex-end;gap:2px;height:${H}px;">`;
  for (let h = 0; h < 24; h++) {
    const v = arr[h] || 0;
    const color = v ? (h === nowHour ? 'var(--accent-yellow)' : 'var(--accent-blue)') : '#333';
    const ht = v ? Math.max(2, (v / max) * H) : 1;
    bars += `<div title="${h}:00 — ${v}" style="flex:1;height:${ht}px;background:${color};border-radius:2px 2px 0 0;"></div>`;
  }
  bars += '</div>';

  let labels = '<div style="display:flex;gap:2px;margin-top:3px;">';
  for (let h = 0; h < 24; h++) {
    const hh = String(h).padStart(2, '0');
    const isNow = h === nowHour;
    labels += `<div style="flex:1;text-align:center;font-size:8px;color:${isNow ? 'var(--accent-yellow)' : 'var(--text-dim)'};${isNow ? 'font-weight:bold;' : ''}">${hh}</div>`;
  }
  labels += '</div>';

  return bars + labels;
}

function renderStats() {
  const s = SkyDex.stats || {};
  // Air section titles (restore in case sea mode relabeled them).
  _setText('st-type-title', 'Fleet by Type');
  _setText('st-rarity-title', 'Rarity Breakdown');
  _setText('st-regulars-title', 'Top Regulars');
  _setText('st-routes-title', 'Routes');

  const cards = document.querySelectorAll('#stats-summary .stat-card');
  const setCard = (i, value, label) => {
    if (!cards[i]) return;
    const v = cards[i].querySelector('.stat-card-value');
    const l = cards[i].querySelector('.stat-card-label');
    if (v) v.textContent = value;
    if (l) l.textContent = label;
  };
  setCard(0, s.total_visits || 0, 'Sightings');
  setCard(1, s.total_airframes || 0, 'Aircraft Logged');
  setCard(2, s.live_contacts || 0, 'In Range Now');

  // Fleet by behavioral type (Rotor / Hauler / Hopper / ...)
  const typeBreak = document.getElementById('type-breakdown');
  if (typeBreak) {
    const tb = Object.entries(s.type_breakdown || {}).sort((a, b) => b[1] - a[1]);
    if (tb.length === 0) {
      typeBreak.innerHTML = '<span style="color:var(--text-dim);font-size:11px;">No aircraft logged yet.</span>';
    } else {
      typeBreak.innerHTML = tb.map(([t, c]) => {
        const info = AIRCRAFT_TYPES[t.toLowerCase()] || { color: '#888', label: t };
        return `<div class="type-dist-item"><div class="type-dist-dot" style="background:${info.color};"></div><span>${info.label}: ${c}</span></div>`;
      }).join('');
    }
  }

  // Routes: top on the left, rarest on the right (full-width bottom row)
  const ac = (n) => `(${n} aircraft)`;
  const routeRow = (label, obj, color) => {
    if (!obj) return '';
    const place = [obj.city, obj.country].filter(Boolean).join(', ');
    const desc = (obj.name || place)
      ? `<span style="color:var(--text-dim);"> — ${[obj.name, place].filter(Boolean).join(' · ')}</span>`
      : '';
    return `<div style="margin-bottom:5px;"><span style="color:var(--text-dim);">${label}:</span> <b style="color:${color};">${obj.code}</b>${desc} <span style="color:var(--text-dim);">${ac(obj.count)}</span></div>`;
  };
  const noRoute = '<span style="color:var(--text-dim);font-size:11px;">No route data yet — needs callsigns + adsbdb lookups; keep it running.</span>';
  const rTop = document.getElementById('routes-top');
  if (rTop) {
    const lines = [routeRow('Top departure', s.top_origin, 'var(--accent-blue)'),
                   routeRow('Top destination', s.top_dest, 'var(--accent-blue)')].filter(Boolean);
    rTop.innerHTML = lines.length ? lines.join('') : noRoute;
  }
  const rRare = document.getElementById('routes-rare');
  if (rRare) {
    const lines = [routeRow('Rarest departure', s.bottom_origin, 'var(--accent-yellow)'),
                   routeRow('Rarest destination', s.bottom_dest, 'var(--accent-yellow)')].filter(Boolean);
    rRare.innerHTML = lines.length ? lines.join('') : noRoute;
  }

  // Rarity breakdown
  const typeDist = document.getElementById('type-distribution');
  const dist = s.rarity_distribution || {};
  const entries = Object.entries(dist).sort((a, b) => b[1] - a[1]);
  if (entries.length === 0) {
    typeDist.innerHTML = '<span style="color:var(--text-dim);font-size:11px;">No aircraft logged yet — wait for one to fly within range.</span>';
  } else {
    const colors = { Common: '#9e9e9e', Uncommon: '#4caf50', Rare: '#2196f3', Epic: '#9c27b0', Legendary: '#FFD700' };
    typeDist.innerHTML = entries.map(([r, c]) =>
      `<div class="type-dist-item"><div class="type-dist-dot" style="background:${colors[r] || '#888'};"></div><span>${r}: ${c}</span></div>`
    ).join('');
  }

  // Top regulars
  const log = document.getElementById('recent-log');
  const top = s.top_airframes || (s.top_airframe ? [s.top_airframe] : []);
  if (top && top.length && (top[0].detection_count || 0) > 0) {
    log.innerHTML = top.map(a =>
      `<div class="log-entry"><span class="log-time">#${a.dex_number || '?'}</span> ${a.registration || a.hex} — ${a.model || 'Unknown'} <span style="color:var(--accent-yellow);">${a.detection_count || 0}x</span></div>`
    ).join('');
  } else {
    log.innerHTML = '<div class="log-entry">No regulars logged yet.</div>';
  }
}

// ============================================
// WEATHER + TIDE (Live View Conditions Bar)
// ============================================

async function fetchWeather() {
  try {
    const [weatherRes, tideRes] = await Promise.allSettled([
      fetch('/api/weather'),
      fetch('/api/tide'),
    ]);

    if (weatherRes.status === 'fulfilled' && weatherRes.value.ok) {
      SkyDex.weatherData = await weatherRes.value.json();
    }
    if (tideRes.status === 'fulfilled' && tideRes.value.ok) {
      SkyDex.tideData = await tideRes.value.json();
    }

    renderConditions();
  } catch (e) {
    console.error('fetchWeather error:', e);
  }
}

async function fetchAlerts() {
  try {
    const res = await fetch('/api/alerts');
    if (!res.ok) return;
    renderAlerts(await res.json());
  } catch (e) { /* keep whatever's showing */ }
}

function renderAlerts(alerts) {
  const el = document.getElementById('alert-banner');
  if (!el) return;
  if (!Array.isArray(alerts) || !alerts.length) {
    el.classList.add('hidden');
    el.innerHTML = '';
    return;
  }
  const WARN = '<svg viewBox="0 0 24 24" width="12" height="12" fill="currentColor" style="vertical-align:-2px;margin-right:4px;"><path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/></svg>';
  const WAVE = '<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" style="vertical-align:-2px;margin-right:4px;"><path d="M2 8c2 0 2 2 4 2s2-2 4-2 2 2 4 2 2-2 4-2 2 2 4 2"/><path d="M2 14c2 0 2 2 4 2s2-2 4-2 2 2 4 2 2-2 4-2 2 2 4 2"/></svg>';
  el.classList.remove('hidden');
  el.innerHTML = alerts.map(a => {
    const ev = a.event || 'Advisory';
    const sev = (a.severity || '').toLowerCase();
    const isWarn = /warning/.test(ev.toLowerCase()) || sev === 'severe' || sev === 'extreme';
    const cls = isWarn ? 'alert-warning' : 'alert-advisory';
    const icon = a.kind === 'marine' ? WAVE : WARN;
    const title = (a.headline || ev).replace(/"/g, '');
    return `<span class="alert-chip ${cls}" title="${title}">${icon}${ev}</span>`;
  }).join('');
}

function renderConditions() {
  const strip = document.getElementById('weather-strip');
  const w = SkyDex.weatherData;
  const t = SkyDex.tideData;

  if (!w && !t) {
    strip.classList.add('hidden');
    return;
  }

  strip.classList.remove('hidden');
  let html = '';

  // --- Weather section ---
  if (w) {
    const temp = w.temp_f !== undefined ? `${Math.round(w.temp_f)}\u00B0F` : '';
    const wind = w.wind_speed !== undefined ? `${w.wind_speed}` : '';
    const cond = w.condition || '';

    html += '<div style="display:flex;align-items:center;gap:8px;">';
    if (temp) html += `<div class="weather-item">${ICONS.temp}<span class="weather-temp">${temp}</span></div>`;
    if (cond) html += `<div class="weather-item" style="font-size:10px;">${ICONS.cloud}<span>${cond}</span></div>`;
    if (wind) html += `<div class="weather-item">${ICONS.wind}<span>${wind}</span></div>`;
    html += '</div>';
  }

  // Divider
  if (w && t) {
    html += '<div style="width:1px;height:16px;background:var(--screen-light);margin:0 4px;flex-shrink:0;"></div>';
  }

  // --- Tide section ---
  if (t) {
    const tideLabel = t.tide_state === 'rising' ? 'Rising' : t.tide_state === 'falling' ? 'Falling' : 'Tide';
    const height = t.current_height_ft !== undefined ? `${t.current_height_ft}ft` : '';
    const tideIcon = t.tide_state === 'rising' ? ICONS.tideRise : t.tide_state === 'falling' ? ICONS.tideFall : ICONS.wave;

    html += '<div style="display:flex;align-items:center;gap:8px;">';
    html += `<div class="weather-item">${tideIcon}<span style="color:var(--accent-blue);font-weight:bold;">${tideLabel}</span></div>`;
    if (height) html += `<div class="weather-item">${ICONS.wave}<span>${height}</span></div>`;

    if (t.next_high) {
      html += `<div class="weather-item" style="color:var(--accent-green);">${ICONS.arrowUp}<span>${t.next_high.time}</span></div>`;
    }
    if (t.next_low) {
      html += `<div class="weather-item" style="color:#ff6b6b;">${ICONS.arrowDown}<span>${t.next_low.time}</span></div>`;
    }
    html += '</div>';
  }

  // --- Location (name + coordinates), next to the tide readout ---
  const home = window.SKYDEX_HOME;
  if (home) {
    if (w || t) {
      html += '<div style="width:1px;height:16px;background:var(--screen-light);margin:0 4px;flex-shrink:0;"></div>';
    }
    const PIN = '<svg viewBox="0 0 24 24" width="12" height="12" fill="currentColor" style="vertical-align:-2px;margin-right:3px;"><path d="M12 2C8.1 2 5 5.1 5 9c0 5.2 7 13 7 13s7-7.8 7-13c0-3.9-3.1-7-7-7zm0 9.5A2.5 2.5 0 1 1 12 6.5a2.5 2.5 0 0 1 0 5z"/></svg>';
    html += `<div class="weather-item" style="font-size:10px;">${PIN}<span>${home.name || 'Home'}</span>`
          + `<span style="color:var(--text-dim);margin-left:5px;">${home.lat.toFixed(3)}, ${home.lon.toFixed(3)}</span></div>`;
  }

  // Source indicator (dump1090 vs OpenSky) + METAR
  html += '<div style="margin-left:auto;display:flex;align-items:center;gap:6px;">';
  if (SkyDex.sourceName) {
    const srcColor = SkyDex.sourceName === 'dump1090' ? '#4ade80' : SkyDex.sourceName === 'opensky' ? '#30A7D7' : '#888';
    html += `<div style="font-size:9px;color:${srcColor};display:flex;align-items:center;gap:3px;">${ICONS.antenna}<span>${SkyDex.sourceName}</span></div>`;
  }
  if (w && w.metar) {
    html += `<div style="font-family:monospace;font-size:9px;opacity:0.5;color:var(--text-dim);">${w.metar.substring(0, 30)}</div>`;
  }
  html += '</div>';

  strip.innerHTML = html;
}

/** Poll receiver health to show data source (dump1090 vs OpenSky) */
async function fetchReceiverStatus() {
  try {
    const res = await fetch('/api/health');
    if (!res.ok) return;
    const data = await res.json();
    if (data.receiver) {
      const stats = data.receiver.source_stats || {};
      SkyDex.sourceName = stats.last_source || 'none';
      // Also update the status LED color based on source
      const led = document.getElementById('status-led');
      if (led) {
        if (SkyDex.sourceName === 'dump1090') {
          led.style.background = '#4ade80';
          led.style.boxShadow = '0 0 6px #4ade80';
        } else if (SkyDex.sourceName === 'opensky') {
          led.style.background = '#30A7D7';
          led.style.boxShadow = '0 0 6px #30A7D7';
        } else {
          led.style.background = '#ff6b6b';
          led.style.boxShadow = '0 0 6px #ff6b6b';
        }
      }
    }
  } catch (e) {
    // silent
  }
}

// ============================================
// SEADEX VIEWS (Fleetdex / vessel detail / sea stats & graphs)
// ============================================

function fetchFleetdex() {
  if (SkyDex.fleetData) renderFleetList();   // cache-first (prefetched at startup)
  fetch('/api/vessel-dex?limit=1000').then(r => (r.ok ? r.json() : []))
    .then(d => { SkyDex.fleetData = d; renderFleetList(); })
    .catch(e => console.error('fetchFleetdex error:', e));
}

function renderFleetList() {
  const container = document.getElementById('dex-list');
  const empty = document.getElementById('dex-empty');
  const all = Array.isArray(SkyDex.fleetData) ? SkyDex.fleetData : [];
  if (!all.length) {
    container.innerHTML = '';
    empty.classList.remove('hidden');
    document.getElementById('dex-count').textContent = '0';
    return;
  }
  const ft = (document.getElementById('dex-filter-type') || {}).value || 'all';
  const fr = (document.getElementById('dex-filter-rarity') || {}).value || 'all';
  const sort = (document.getElementById('dex-sort') || {}).value || 'count';
  const rarityOrder = { legendary: 5, epic: 4, rare: 3, uncommon: 2, common: 1 };
  const fb = (document.getElementById('dex-filter-badge') || {}).value || 'all';
  let entries = all.slice();
  if (ft !== 'all') entries = entries.filter(v => (v.category || 'other').toLowerCase() === ft);
  if (fr !== 'all') entries = entries.filter(v => (v.rarity || 'common').toLowerCase() === fr);
  if (fb !== 'all') entries = entries.filter(v => vesselBadgeKeys(v).includes(fb));
  const fw = (document.getElementById('dex-filter-window') || {}).value || 'week';
  if (fw !== 'all') {
    const cutoff = Date.now() / 1000 - (fw === 'week' ? 7 : 30) * 86400;
    const windowed = entries.filter(v => (v.last_seen || 0) >= cutoff);
    if (windowed.length) entries = windowed;
  }
  entries.sort((a, b) => {
    if (sort === 'dex') return (a.dex_number || 99999) - (b.dex_number || 99999);
    if (sort === 'rarity') return (rarityOrder[(b.rarity || 'common').toLowerCase()] || 0) - (rarityOrder[(a.rarity || 'common').toLowerCase()] || 0);
    if (sort === 'name') return String(a.name || a.mmsi).localeCompare(String(b.name || b.mmsi));
    return (b.detection_count || 0) - (a.detection_count || 0);
  });
  document.getElementById('dex-count').textContent = entries.length;
  if (!entries.length) {
    container.innerHTML = '<div class="text-center" style="color:var(--text-dim);padding:24px;grid-column:1/-1;">No vessels match this filter.</div>';
    empty.classList.add('hidden');
    return;
  }
  empty.classList.add('hidden');

  const vm = (document.getElementById('dex-view-mode') || {}).value || 'cards';
  if (vm === 'list') {
    container.classList.add('dex-as-list');
    container.innerHTML = entries.map(v => {
      const color = vesselColor(v);
      return `<div class="dexl-row" onclick="openVessel('${v.mmsi}')">
          <span class="dexl-num">#${v.dex_number || '?'}</span>
          <span class="dexl-ic" style="color:${color};">${vesselIconSvg(v.icon)}</span>
          <span class="dexl-main"><b>${v.name || 'MMSI ' + v.mmsi}</b>
            <small>${v.category || 'Vessel'}${v.flag ? ' · ' + v.flag : ''}</small></span>
          <span class="dexl-count">${v.detection_count || 0}×</span>
          ${renderRarityStars((v.rarity || 'common').toLowerCase())}
        </div>`;
    }).join('');
    return;
  }
  container.classList.remove('dex-as-list');

  container.innerHTML = entries.map((v, idx) => {
    const color = vesselColor(v);
    const rarity = (v.rarity || 'common').toLowerCase();
    const rarityInfo = RARITY[rarity] || RARITY.common;
    const count = v.detection_count || 0;
    const name = v.name || ('MMSI ' + v.mmsi);
    return `
      <div class="dex-card" onclick="openVessel('${v.mmsi}')" style="animation: entry-bounce 0.4s ease-out ${Math.min(idx, 20) * 0.03}s both;">
        <div class="dex-card-number">#${v.dex_number || '?'}</div>
        <div class="dex-card-sprite" style="background:${color}22;border:2px solid ${color};color:${color};">
          ${v.photo_url
            ? `<img src="/api/photo-vessel/${v.mmsi}" alt="" loading="lazy" decoding="async" style="width:100%;height:100%;object-fit:cover;" onerror="this.style.display='none';this.nextElementSibling.style.display='flex';"><span style="display:none;color:${color};align-items:center;justify-content:center;width:100%;height:100%;">${vesselIconSvg(v.icon)}</span>`
            : `<span style="color:${color};display:flex;align-items:center;justify-content:center;width:100%;height:100%;">${vesselIconSvg(v.icon)}</span>`}
        </div>
        <div class="dex-card-name">${name}</div>
        <div class="dex-card-type" style="color:${color};">${v.category || 'Vessel'}</div>
        <div class="dex-card-rarity" style="color:${rarityInfo.color};">${rarityInfo.label}</div>
        <div class="dex-card-count">${count} sighting${count !== 1 ? 's' : ''}</div>
      </div>`;
  }).join('');
}

async function openVessel(mmsi) {
  if (!mmsi) return;
  SkyDex.previousView = SkyDex.currentView;
  SkyDexAudio.playBeep();
  try {
    const res = await fetch(`/api/vessel/${mmsi}`);
    const data = res.ok ? await res.json() : null;
    if (!data || data.error) { showToast('Vessel data not found', ''); return; }
    renderVesselDetail(data);
    showView('detail');
  } catch (e) {
    console.error('openVessel error:', e);
    showToast('Error loading vessel details', '');
  }
}

function renderVesselDetail(data) {
  const v = data.vessel || data;
  const color = vesselColor(v);
  const rarity = (v.rarity || 'common').toLowerCase();
  const sightings = data.sightings || [];
  document.getElementById('detail-content').innerHTML = `
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;cursor:pointer;" onclick="goBack()">
      <span style="font-size:18px;color:var(--accent-blue);">&#9664;</span>
      <span style="font-size:12px;color:var(--text-dim);">Back to list</span>
    </div>
    <div class="dex-detail-layout">
      <div class="dex-detail-left">
        <div class="dex-number">#${v.dex_number || '?'}</div>
        <div class="dex-name">${flagHtml(v.flag ? { iso2: v.flag, name: v.flag } : null)}${v.name || ('MMSI ' + v.mmsi)}</div>
        <div class="dex-types-row"><span class="type-pill" style="background:${color};">${v.category || 'Vessel'}</span></div>
        ${renderRarityStars(rarity)}
        ${renderBadges(data.badges)}
        <div class="dex-photo-frame">
          ${v.photo_url
            ? `<img src="/api/photo-vessel/${v.mmsi}" alt="${v.name || ''}" loading="lazy" decoding="async" style="width:100%;height:100%;object-fit:cover;border-radius:6px;" onerror="this.style.display='none';this.nextElementSibling.style.display='flex';"><span class="dex-photo-placeholder" style="display:none;width:50%;height:50%;color:${color};">${vesselIconSvg(v.icon)}</span>`
            : `<span class="dex-photo-placeholder" style="width:50%;height:50%;color:${color};">${vesselIconSvg(v.icon)}</span>`}
        </div>
        <div style="margin-top:8px;font-size:11px;color:var(--text-dim);text-align:center;">${(RARITY[rarity] || RARITY.common).label} vessel</div>
        <div style="text-align:center;margin-top:10px;">
          <button class="day-summary-btn" style="width:auto;display:inline-flex;margin:0;"
            onclick="followCraft('sea','${v.mmsi}','${String(v.name || '').replace(/'/g, '')}')">
            &#128205; Follow this ship</button>
        </div>
        ${v.photo_credit ? `<div style="margin-top:2px;font-size:9px;color:var(--text-faint);text-align:center;">Photo: ${v.photo_credit}</div>` : ''}
        ${data.type_fact ? `<div class="dex-fact"><span class="dex-fact-label">Did you know?</span> ${data.type_fact}</div>` : ''}
      </div>
      <div class="dex-detail-right">
        ${v.destination ? `<div class="route-banner"><div class="route-banner-line">Destination: ${v.destination}</div>${v.nav_status_text ? `<div class="route-banner-sub">${v.nav_status_text}</div>` : ''}</div>` : ''}
        ${(() => { const wow = kidCompareShip(v.length, v.speed);
          return wow ? `<div class="dex-fact">&#10024; This ship is ${wow}</div>` : ''; })()}
        <div class="dex-section-title">Vessel Data</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;font-size:12px;margin-bottom:12px;">
          <div><span style="color:var(--text-dim);">MMSI:</span> <span style="color:var(--text);font-family:monospace;">${v.mmsi}</span></div>
          ${v.imo ? `<div><span style="color:var(--text-dim);">IMO:</span> <span style="color:var(--text);font-family:monospace;">${v.imo}</span></div>` : ''}
          ${(v.flag_name || v.flag) ? `<div><span style="color:var(--text-dim);">Flag:</span> <span style="color:var(--text);">${flagHtml(v.flag ? { iso2: v.flag, name: v.flag_name || v.flag } : null)}${v.flag_name || v.flag}</span></div>` : ''}
          <div><span style="color:var(--text-dim);">Type:</span> <span style="color:var(--text);">${v.category || 'Unknown'}</span></div>
          <div><span style="color:var(--text-dim);">Speed:</span> <span style="color:var(--text);">${v.speed != null ? v.speed.toFixed(1) + ' kn' : '---'}</span></div>
          <div><span style="color:var(--text-dim);">Course:</span> <span style="color:var(--text);">${v.course != null ? Math.round(v.course) + '° (' + headingToCompass(v.course) + ')' : '---'}</span></div>
          <div><span style="color:var(--text-dim);">Distance:</span> <span style="color:var(--text);">${formatDistance(v.distance_miles)}</span></div>
          <div><span style="color:var(--text-dim);">Length:</span> <span style="color:var(--text);">${v.length ? Math.round(v.length) + ' m' : '---'}</span></div>
          ${v.callsign ? `<div><span style="color:var(--text-dim);">Callsign:</span> <span style="color:var(--text);">${v.callsign}</span></div>` : ''}
          ${v.nav_status_text ? `<div><span style="color:var(--text-dim);">Status:</span> <span style="color:var(--text);">${v.nav_status_text}</span></div>` : ''}
          <div><span style="color:var(--text-dim);">Seen:</span> <span style="color:var(--accent-yellow);">${v.detection_count || 0}×</span></div>
          ${v.first_seen ? `<div><span style="color:var(--text-dim);">First spotted:</span> <span style="color:var(--text);">${new Date(v.first_seen * 1000).toLocaleDateString()}</span></div>` : ''}
        </div>
        ${data.wiki && data.wiki.extract ? `<div class="dex-section-title">From Wikipedia</div><div class="dex-fact" style="margin-bottom:12px;">${data.wiki.extract}${data.wiki.url ? ` <a href="${data.wiki.url}" target="_blank" style="color:var(--accent-blue);">More ›</a>` : ''}</div>` : ''}
        <div class="dex-section-title">Sighting Log</div>
        <div class="battle-log">
          ${sightings.length ? sightings.map(s => {
            const t = s.started_at ? fmtDateTimeEST(s.started_at * 1000) : '--';
            const durMin = (s.started_at && s.ended_at) ? Math.max(1, Math.round((s.ended_at - s.started_at) / 60)) : null;
            const dest = s.destination ? ' · → ' + s.destination : '';
            return `<div class="log-entry"><span class="log-time">${t}</span> seen${durMin ? ' ' + durMin + ' min' : ''}${dest}</div>`;
          }).join('') : '<div class="log-entry">Live sighting — not yet logged.</div>'}
          <div class="log-entry" style="color:var(--text-faint);">${data.total_sightings || sightings.length || 0} sighting(s) on record</div>
        </div>
      </div>
    </div>`;
}

function fetchSeaStats() {
  fetch('/api/sea-stats').then(r => (r.ok ? r.json() : {})).then(s => { SkyDex.seaStats = s; renderSeaStats(s); }).catch(e => console.error('fetchSeaStats error:', e));
}

function renderSeaStats(s) {
  s = s || {};
  // Water-native section titles (so nothing reads "Operator/Routes" for boats).
  _setText('st-type-title', 'Fleet by Category');
  _setText('st-rarity-title', 'Rarity Breakdown');
  _setText('st-regulars-title', 'Harbor Regulars');
  _setText('st-routes-title', 'Destinations & Flags');
  const cards = document.querySelectorAll('#stats-summary .stat-card');
  const setCard = (i, val, label) => { if (cards[i]) { const v = cards[i].querySelector('.stat-card-value'); const l = cards[i].querySelector('.stat-card-label'); if (v) v.textContent = val; if (l) l.textContent = label; } };
  setCard(0, s.total_sightings || 0, 'Sightings');
  setCard(1, s.total_vessels || 0, 'Vessels Logged');
  setCard(2, s.live_vessels || 0, 'In Range Now');

  const tb = document.getElementById('type-breakdown');
  if (tb) {
    const e = Object.entries(s.category_distribution || {}).sort((a, b) => b[1] - a[1]);
    tb.innerHTML = e.length ? e.map(([c, n]) => `<div class="type-dist-item"><div class="type-dist-dot" style="background:${VESSEL_COLORS[c] || '#888'};"></div><span>${c}: ${n}</span></div>`).join('') : '<span style="color:var(--text-dim);font-size:11px;">No vessels logged yet.</span>';
  }
  const rd = document.getElementById('type-distribution');
  if (rd) {
    const e = Object.entries(s.rarity_distribution || {}).sort((a, b) => b[1] - a[1]);
    const colors = { Common: '#9e9e9e', Uncommon: '#4caf50', Rare: '#2196f3', Epic: '#9c27b0', Legendary: '#FFD700' };
    rd.innerHTML = e.length ? e.map(([r, n]) => `<div class="type-dist-item"><div class="type-dist-dot" style="background:${colors[r] || '#888'};"></div><span>${r}: ${n}</span></div>`).join('') : '<span style="color:var(--text-dim);font-size:11px;">No vessels logged yet.</span>';
  }
  const rTop = document.getElementById('routes-top');
  if (rTop) rTop.innerHTML = (s.top_destinations || []).length ? s.top_destinations.map(d => `<div><b style="color:var(--accent-blue);">${d.label}</b> <span style="color:var(--text-dim);">(${d.count}×)</span></div>`).join('') : '<span style="color:var(--text-dim);font-size:11px;">No destinations yet.</span>';
  const rRare = document.getElementById('routes-rare');
  if (rRare) rRare.innerHTML = (s.top_flags || []).length ? s.top_flags.map(f => `<div>${flagHtml({ iso2: f.label, name: f.name || f.label })}<b style="color:var(--text);">${f.name || f.label}</b> <span style="color:var(--text-dim);">(${f.count}×)</span></div>`).join('') : '<span style="color:var(--text-dim);font-size:11px;">No flag data yet.</span>';
  const log = document.getElementById('recent-log');
  if (log) {
    const top = s.top_vessels || [];
    log.innerHTML = (top.length && (top[0].detection_count || 0) > 0) ? top.map(v => `<div class="log-entry"><span class="log-time">#${v.dex_number || '?'}</span> ${v.name || ('MMSI ' + v.mmsi)} — ${v.category || ''} <span style="color:var(--accent-yellow);">${v.detection_count || 0}×</span></div>`).join('') : '<div class="log-entry">No regulars logged yet.</div>';
  }

  // --- Water-specific extras (shown only in sea mode via CSS) ---
  const nav = document.getElementById('nav-status-breakdown');
  if (nav) {
    const e = Object.entries(s.nav_status_distribution || {}).sort((a, b) => b[1] - a[1]);
    nav.innerHTML = e.length ? e.map(([k, n]) => `<div class="type-dist-item"><div class="type-dist-dot" style="background:#15a3a3;"></div><span>${k}: ${n}</span></div>`).join('') : '<span style="color:var(--text-dim);font-size:11px;">No nav-status data yet.</span>';
  }
  const big = document.getElementById('biggest-vessels');
  if (big) {
    const list = s.biggest_vessels || [];
    big.innerHTML = list.length ? list.map(v => `<div><b style="color:${VESSEL_COLORS[v.category] || 'var(--text)'};">${v.name || ('MMSI ' + v.mmsi)}</b> <span style="color:var(--accent-yellow);">${Math.round(v.length)} m</span> <span style="color:var(--text-dim);">${v.category || ''}</span></div>`).join('') : '<span style="color:var(--text-dim);font-size:11px;">No size data yet.</span>';
  }
  const close = document.getElementById('closest-approach');
  if (close) {
    const c = s.closest_approach;
    close.innerHTML = (c && c.min_distance != null) ? `<b style="color:var(--accent-blue);">${c.name || ('MMSI ' + c.mmsi)}</b><br><span style="color:var(--accent-yellow);font-size:16px;font-weight:bold;">${formatDistance(c.min_distance)}</span> <span style="color:var(--text-dim);">${c.category || ''}</span>` : '<span style="color:var(--text-dim);font-size:11px;">No approach data yet.</span>';
  }
  const dwell = document.getElementById('longest-dwell');
  if (dwell) {
    const dw = s.longest_dwell;
    if (dw && dw.secs != null) {
      const mins = Math.round(dw.secs / 60);
      const txt = mins >= 60 ? `${Math.floor(mins / 60)}h ${mins % 60}m` : `${mins} min`;
      dwell.innerHTML = `<b style="color:var(--accent-blue);">${dw.name || ('MMSI ' + dw.mmsi)}</b><br><span style="color:var(--accent-yellow);font-size:16px;font-weight:bold;">${txt}</span> <span style="color:var(--text-dim);">in range</span>`;
    } else {
      dwell.innerHTML = '<span style="color:var(--text-dim);font-size:11px;">No dwell data yet.</span>';
    }
  }
}

function fetchSeaGraphs() {
  fetch('/api/sea-stats').then(r => (r.ok ? r.json() : {})).then(s => { SkyDex.seaStats = s; renderSeaGraphs(s); }).catch(e => console.error('fetchSeaGraphs error:', e));
}

function renderSeaGraphs(s) {
  s = s || {};
  // Water-native graph titles, and hide the air-only Emergency chart.
  _setText('g-typeday-title', 'Activity by Category — by Day');
  _setText('g-hour-title', 'Activity by Hour — Today');
  _setText('g-models-title', 'Top Categories');
  _setText('g-operators-title', 'Top Flags');
  _setText('g-dep-title', 'Top Destinations');
  _setText('g-arr-title', 'Vessel Sizes');
  _setText('g-deprare-title', 'Nav Status');
  _setText('g-arrrare-title', 'Rarity Mix');
  _setShow('g-emerg-title', false);
  _setShow('chart-emergencies', false);

  const toRank = (obj) => Object.entries(obj || {}).map(([l, c]) => ({ label: l, count: c })).sort((a, b) => b.count - a.count);
  const vColor = (cat) => VESSEL_COLORS[cat] || '#888';

  const set = (id, html) => { const el = document.getElementById(id); if (el) el.innerHTML = html; };
  set('chart-type-day', renderTypeDayChart(s.activity_by_type_day || {}, vColor, (c) => c));
  set('chart-hour-today', renderHourChart(s.activity_by_hour_today || []));
  set('chart-models', renderRankChart(toRank(s.category_distribution), 'var(--accent-blue)'));
  set('chart-operators', renderRankChart((s.top_flags || []).map(f => ({ label: f.name || f.label, count: f.count })), 'var(--accent-green)'));
  set('chart-dep-cities', renderRankChart(s.top_destinations || [], 'var(--accent-blue)'));
  set('chart-arr-cities', renderRankChart(toRank(s.size_distribution), '#15a3a3'));
  set('chart-dep-cities-rare', renderRankChart(toRank(s.nav_status_distribution), '#15a3a3'));
  set('chart-arr-cities-rare', renderRankChart(toRank(s.rarity_distribution), 'var(--accent-yellow)'));
}

// ============================================
// DAY SUMMARY (combined Air + Sea, only from Live)
// ============================================

function openDaySummary() {
  SkyDexAudio.playBeep();
  showView('daysummary');
}

function fetchDaySummary() {
  const el = document.getElementById('daysummary-content');
  if (el) el.innerHTML = '<div style="text-align:center;color:var(--text-dim);padding:30px;">Compiling today’s report…</div>';
  fetch('/api/day-summary').then(r => (r.ok ? r.json() : null))
    .then(d => { if (d) renderDaySummary(d); })
    .catch(e => { console.error('day summary error:', e); if (el) el.innerHTML = '<div style="text-align:center;color:#ff6b6b;padding:30px;">Could not load the day summary.</div>'; });
}

function renderDaySummary(d) {
  const air = d.air || {};
  const sea = d.sea || {};
  const dateEl = document.getElementById('daysummary-date');
  if (dateEl && d.date) dateEl.textContent = d.date;

  const num = (x) => (x == null ? '—' : x);
  const statCard = (val, label, color) => `<div class="ds-stat"><div class="ds-stat-val"${color ? ` style="color:${color};"` : ''}>${val}</div><div class="ds-stat-lbl">${label}</div></div>`;
  const rankList = (list, color) => (list && list.length)
    ? list.map(r => `<div class="ds-rank"><span class="ds-rank-lbl">${r.label}</span><span class="ds-rank-ct" style="color:${color || 'var(--accent-yellow)'};">${r.count}</span></div>`).join('')
    : '<div class="ds-empty">None today.</div>';
  const chips = (obj, colorFn) => {
    const e = Object.entries(obj || {}).sort((a, b) => b[1] - a[1]);
    return e.length ? e.map(([k, v]) => `<span class="ds-chip" style="border-color:${colorFn(k)};color:${colorFn(k)};">${k} · ${v}</span>`).join('') : '<div class="ds-empty">None today.</div>';
  };
  const tagFor = (t) => (AIRCRAFT_TYPES[(t || '').toLowerCase()] || { color: '#888' }).color;
  const catColor = (c) => VESSEL_COLORS[c] || '#888';
  const aName = (o) => o ? (o.registration || o.callsign || o.model || o.hex || '—') : '—';

  const fastest = air.fastest, highest = air.highest;
  const busiest = (air.busiest_hour != null) ? `${String(air.busiest_hour).padStart(2, '0')}:00` : '—';

  const airRoster = (air.roster || []).map(r => {
    const ident = r.registration || r.model || r.hex;
    const sub = [r.model, r.operator].filter(Boolean).join(' · ');
    const alt = r.max_alt != null ? Math.round(r.max_alt).toLocaleString() + ' ft' : '—';
    const spd = r.max_spd != null ? Math.round(r.max_spd) + ' kt' : '—';
    const tag = r.is_new ? '<span class="ds-new">NEW</span>' : `<span class="ds-rep">×${r.detection_count || 1} all-time</span>`;
    return `<div class="ds-roster-row">
      <div class="ds-roster-main"><b style="color:${tagFor(r.primary_type)};">${ident}</b> ${tag}<div class="ds-roster-sub">${sub || 'Unknown aircraft'}</div></div>
      <div class="ds-roster-stats"><span>${r.visits}× today</span><span>${alt}</span><span>${spd}</span></div>
    </div>`;
  }).join('') || '<div class="ds-empty">No aircraft logged today yet.</div>';

  const emerg = (air.emergencies || []).length
    ? `<div class="ds-emerg"><div class="ds-emerg-title">Emergency squawks today</div>${air.emergencies.map(e => `<div class="ds-row">${e.squawk} — ${e.registration || e.callsign || e.hex}${e.model ? ' (' + e.model + ')' : ''}</div>`).join('')}</div>`
    : '';

  const biggest = sea.biggest;
  const seaRoster = (sea.roster || []).map(r => {
    const ident = r.name || ('MMSI ' + r.mmsi);
    const len = r.length ? Math.round(r.length) + ' m' : '—';
    const tag = r.is_new ? '<span class="ds-new">NEW</span>' : `<span class="ds-rep">×${r.detection_count || 1} all-time</span>`;
    const sub = [r.category, r.destination ? ('→ ' + r.destination) : ''].filter(Boolean).join(' · ');
    return `<div class="ds-roster-row">
      <div class="ds-roster-main">${flagHtml(r.flag ? { iso2: r.flag, name: r.flag } : null)}<b style="color:${catColor(r.category)};">${ident}</b> ${tag}<div class="ds-roster-sub">${sub || 'Vessel'}</div></div>
      <div class="ds-roster-stats"><span>${r.visits}× today</span><span>${len}</span></div>
    </div>`;
  }).join('') || '<div class="ds-empty">No vessels logged today yet.</div>';

  document.getElementById('daysummary-content').innerHTML = `
    <div class="ds-section">
      <div class="ds-head"><span class="ds-dot" style="background:var(--accent-blue);"></span> SkyDex — Aircraft</div>
      <div class="ds-stats">
        ${statCard(num(air.visits), 'Visits')}
        ${statCard(num(air.unique), 'Unique')}
        ${statCard(num(air.new), 'New', 'var(--accent-green)')}
        ${statCard(num(air.repeat), 'Repeats')}
        ${statCard(num(air.live_now), 'In range now', 'var(--accent-yellow)')}
      </div>
      <div class="ds-highlights">
        <div class="ds-hl"><div class="ds-hl-lbl">Fastest</div><div class="ds-hl-val">${fastest ? Math.round(fastest.val) + ' kt' : '—'}</div><div class="ds-hl-sub">${aName(fastest)}</div></div>
        <div class="ds-hl"><div class="ds-hl-lbl">Highest</div><div class="ds-hl-val">${highest ? Math.round(highest.val).toLocaleString() + ' ft' : '—'}</div><div class="ds-hl-sub">${aName(highest)}</div></div>
        <div class="ds-hl"><div class="ds-hl-lbl">Busiest hour</div><div class="ds-hl-val">${busiest}</div><div class="ds-hl-sub">local time</div></div>
      </div>
      ${emerg}
      <div class="ds-cols">
        <div><div class="ds-sub">Types seen</div><div class="ds-chips">${chips(air.by_type, tagFor)}</div></div>
        <div><div class="ds-sub">Top models</div>${rankList(air.top_models)}</div>
      </div>
      <div class="ds-sub">Top routes (from → to)</div>${rankList(air.top_routes, 'var(--accent-blue)')}
      <div class="ds-sub">Who came by (${(air.roster || []).length})</div>
      <div class="ds-roster">${airRoster}</div>
    </div>

    <div class="ds-section">
      <div class="ds-head"><span class="ds-dot" style="background:#15a3a3;"></span> SeaDex — Vessels</div>
      <div class="ds-stats">
        ${statCard(num(sea.visits), 'Visits')}
        ${statCard(num(sea.unique), 'Unique')}
        ${statCard(num(sea.new), 'New', 'var(--accent-green)')}
        ${statCard(num(sea.repeat), 'Repeats')}
        ${statCard(num(sea.live_now), 'In range now', '#15a3a3')}
      </div>
      <div class="ds-highlights">
        <div class="ds-hl"><div class="ds-hl-lbl">Biggest</div><div class="ds-hl-val">${biggest && biggest.val ? Math.round(biggest.val) + ' m' : '—'}</div><div class="ds-hl-sub">${biggest ? (biggest.name || ('MMSI ' + biggest.mmsi)) : '—'}</div></div>
      </div>
      <div class="ds-cols">
        <div><div class="ds-sub">Categories</div><div class="ds-chips">${chips(sea.by_category, catColor)}</div></div>
        <div><div class="ds-sub">Top destinations</div>${rankList(sea.top_destinations, '#15a3a3')}</div>
      </div>
      <div class="ds-sub">Top flags</div>${rankList(sea.top_flags, '#15a3a3')}
      <div class="ds-sub">Who came by (${(sea.roster || []).length})</div>
      <div class="ds-roster">${seaRoster}</div>
    </div>`;
}

// ============================================
// ATMODEX (Tonight's Sky)
// ============================================

function _atmoTime(e) {
  return fmtTimeEST(e);
}

function _passWhen(p) {
  const t = p.startUTC || p.start || p.startTime || p.risetime || p.time || p.aos;
  if (typeof t === 'number') return new Date(t > 1e12 ? t : t * 1000).toLocaleString('en-GB', { weekday: 'short', hour: '2-digit', minute: '2-digit', hour12: false, timeZone: EST_TZ });
  if (typeof t === 'string') return t;
  return '';
}

// --- Tonight (moon, sun, viewing, aurora, planets) ---
function fetchAtmo() {  // 'Tonight' view
  const el = document.getElementById('atmo-content');
  if (el && !el.innerHTML.trim()) el.innerHTML = '<div style="text-align:center;color:var(--text-dim);padding:30px;">Reading the sky…</div>';
  fetch('/api/atmo').then(r => (r.ok ? r.json() : null)).then(d => { if (d) { SkyDex.atmoData = d; renderTonight(d); } }).catch(e => console.error('atmo error:', e));
}

function renderTonight(d) {
  const el = document.getElementById('atmo-content');
  if (!el) return;
  const moon = d.moon || {}, sun = d.sun || {}, view = d.viewing || {}, aurora = d.aurora || null;
  const planets = d.planets || [], w = d.weather || {}, alerts = d.alerts || [], tide = d.tide || null;
  const conj = d.conjunctions || [], solunar = d.solunar || null, lp = d.light_pollution || null, z = d.zodiac || null;
  const vColor = view.score >= 80 ? 'var(--accent-green)' : view.score >= 60 ? 'var(--accent-yellow)' : view.score >= 40 ? '#ffa94d' : '#ff6b6b';

  let html = `<div class="atmo-hero">
    <div class="atmo-quality" style="border-color:${vColor};">
      <div class="atmo-quality-label" style="color:${vColor};">${view.label || '—'}</div>
      <div class="atmo-sub">stargazing${view.reasons && view.reasons.length ? ' · ' + view.reasons.join(', ') : ''}</div>
    </div>
    <div class="atmo-wx">
      ${w.temp_f != null ? `<div class="atmo-big">${Math.round(w.temp_f)}°F</div>` : ''}
      <div class="atmo-sub">${w.condition || ''}${w.wind_speed ? ' · wind ' + w.wind_speed : ''}</div>
    </div>
  </div>`;

  if (alerts.length) {
    html += `<div class="atmo-alerts">${alerts.map(a => `<span class="alert-chip ${/warning/i.test(a.event || '') ? 'alert-warning' : 'alert-advisory'}">${a.event}</span>`).join('')}</div>`;
  }

  html += `<div class="atmo-grid">
    <div class="atmo-card">
      <div class="atmo-card-title">Moon</div>
      <div class="atmo-moon">
        <div class="atmo-moon-disc" style="--illum:${moon.illumination || 0}%;"></div>
        <div><div class="atmo-big">${moon.phase || '—'}</div>
          <div class="atmo-sub">${moon.illumination != null ? moon.illumination + '% lit' : ''}${moon.age_days != null ? ' · day ' + moon.age_days : ''}</div></div>
      </div>
    </div>
    <div class="atmo-card">
      <div class="atmo-card-title">Sun</div>
      <div class="atmo-line"><span>Sunrise</span><b>${_atmoTime(sun.sunrise)}</b></div>
      <div class="atmo-line"><span>Sunset</span><b>${_atmoTime(sun.sunset)}</b></div>
      <div class="atmo-line"><span>Fully dark</span><b>${_atmoTime(sun.civil_dusk)}</b></div>
    </div>
  </div>`;

  if (aurora && aurora.kp != null) {
    html += `<div class="dex-section-title">Aurora Watch</div><div class="atmo-line"><span>Kp index <b style="color:${aurora.storm ? '#4ade80' : 'var(--text-dim)'};">${aurora.kp}</b></span><b>${aurora.outlook || ''}</b></div>`;
  }

  html += `<div class="dex-section-title">Visible Planets</div>`;
  html += planets.length
    ? '<div class="atmo-planets">' + planets.map(p => `<div class="atmo-planet"><b>${p.name}</b><span class="atmo-sub">${p.when_visible} · ${p.direction}${p.magnitude != null ? ' · mag ' + p.magnitude : ''}</span></div>`).join('') + '</div>'
    : '<div class="ds-empty">No naked-eye planets well-placed right now.</div>';

  if (conj.length) {
    html += `<div class="dex-section-title">Sky Events Tonight</div>` +
      conj.map(c => `<div class="atmo-line"><span>${c.a} &amp; ${c.b}</span><b>${c.separation}° apart</b></div>`).join('');
  }

  if (solunar) {
    html += `<div class="dex-section-title">Fishing (Solunar)</div>`;
    html += `<div class="atmo-line"><span>Today's outlook</span><b>${solunar.quality}</b></div>`;
    (solunar.major || []).forEach(m => { html += `<div class="atmo-line"><span>${m.type}</span><b>${_atmoTime(m.time)}</b></div>`; });
    if (solunar.note) html += `<div class="atmo-sub" style="margin-top:3px;">${solunar.note}</div>`;
  }

  if (tide) {
    const ts = tide.tide_state === 'rising' ? 'Rising' : tide.tide_state === 'falling' ? 'Falling' : 'Tide';
    html += `<div class="dex-section-title">Tide</div><div class="atmo-line"><span>${ts}${tide.current_height_ft != null ? ' · ' + tide.current_height_ft + ' ft' : ''}</span><b>${tide.next_high ? 'High ' + tide.next_high.time : ''}${tide.next_low ? '  Low ' + tide.next_low.time : ''}</b></div>`;
  }

  if (lp) {
    html += `<div class="dex-section-title">Stargazing Tip</div><div class="atmo-tip">${lp.label} — ${lp.tip}</div>`;
  }
  if (z && z.sun_sign) {
    html += `<div class="dex-section-title">Sky Sign (for fun)</div><div class="atmo-line"><span>Sun in <b style="color:var(--text);">${z.sun_sign}</b> · Moon in <b style="color:var(--text);">${z.moon_sign}</b></span></div>${z.blurb ? `<div class="atmo-sub" style="margin-top:3px;">${z.blurb}</div>` : ''}`;
  }
  el.innerHTML = html;
}

// --- Sky Guide (meteor showers, look-up tips, APOD) ---
function fetchSkyGuide() {
  const el = document.getElementById('atmo-guide-content');
  if (el && !el.innerHTML.trim()) el.innerHTML = '<div style="text-align:center;color:var(--text-dim);padding:30px;">Loading sky guide…</div>';
  // Render the guide skeleton FIRST, then fill the async sections — firing
  // these in parallel let renderSkyGuide wipe out an already-rendered APOD
  // (the "where's my picture of the day?" bug).
  fetch('/api/atmo').then(r => (r.ok ? r.json() : null)).then(d => {
    if (d) renderSkyGuide(d);
    fetch('/api/atmo/apod').then(r => (r.ok ? r.json() : null)).then(renderApod).catch(() => {});
    fetch('/api/atmo/asteroids').then(r => (r.ok ? r.json() : null)).then(renderAsteroids).catch(() => {});
    fetch('/api/atmo/launches').then(r => (r.ok ? r.json() : null)).then(renderLaunches).catch(() => {});
  }).catch(e => console.error('guide error:', e));
}

function renderAsteroids(list) {
  const el = document.getElementById('atmo-asteroids');
  if (!el) return;
  if (!Array.isArray(list) || !list.length) { el.innerHTML = ''; return; }
  el.innerHTML = '<div class="dex-section-title">Near-Earth Asteroids (this week)</div>' +
    list.slice(0, 8).map(a => {
      const dist = a.miss_lunar != null ? `${a.miss_lunar} LD` : '';
      const haz = a.hazardous ? ' <span style="color:#ff6b6b;font-weight:bold;">⚠</span>' : '';
      return `<div class="atmo-line"><span>${a.name || 'asteroid'}${haz}<div class="atmo-sub">${a.diameter_m ? '~' + a.diameter_m + ' m' : ''}${a.velocity_kms ? ' · ' + a.velocity_kms + ' km/s' : ''}${a.date ? ' · ' + a.date : ''}</div></span><b>${dist}</b></div>`;
    }).join('') +
    '<div class="atmo-sub" style="margin-top:4px;">LD = lunar distances (1 LD ≈ 384,000 km). ⚠ = NASA "potentially hazardous".</div>';
}

function renderLaunches(list) {
  const el = document.getElementById('atmo-launches');
  if (!el) return;
  if (!Array.isArray(list) || !list.length) { el.innerHTML = ''; return; }
  el.innerHTML = '<div class="dex-section-title">Upcoming Launches</div>' + list.slice(0, 8).map(l => {
    const when = l.net ? fmtDateTimeEST(new Date(l.net).getTime()) : 'TBD';
    const vis = l.visible_from_ct ? ' <span style="color:var(--accent-green);">· may be visible from CT</span>' : '';
    return `<div class="atmo-line"><span>${l.name || ''}<div class="atmo-sub">${l.provider || ''}${l.location ? ' · ' + l.location : ''}${vis}</div></span><b>${when}</b></div>`;
  }).join('');
}

function renderSkyGuide(d) {
  const el = document.getElementById('atmo-guide-content');
  if (!el) return;
  const showers = d.meteor_showers || {}, tips = d.sky_tips || [], comets = d.comets || [];
  // Listen to Space leads — one tap and the Guide has a soundtrack. Both
  // options also live in EtherDex (World Radio POI / Live tuner).
  let html = `<div class="dex-section-title">Listen to Space</div>
    <div class="tuner-row">
      <button class="day-summary-btn" style="margin:0;width:auto;display:inline-flex;" onclick="atmoMissionControl()">
        &#127925; Mission Control — NASA audio</button>
      ${(typeof getSetting === 'function' && getSetting('antenna_tuner', false))
        ? `<button class="day-summary-btn" style="margin:0;width:auto;display:inline-flex;" onclick="atmoIssAntenna()">
        &#128225; ISS 145.800 — our antenna</button>` : ''}
    </div>
    <div id="atmo-listen-note" class="atmo-sub"></div>`;
  // APOD next — it's the showpiece.
  html += `<div id="atmo-apod"></div>`;
  html += `<div class="dex-section-title">Meteor Showers</div>`;
  if (showers.active && showers.active.length) {
    html += showers.active.map(s => `<div class="atmo-line"><span>${s.name}${s.peaking ? ' <b style="color:var(--accent-yellow);">PEAKING</b>' : ''} <span class="atmo-sub">${s.parent}</span></span><b>~${s.zhr}/hr · peak ${s.peak}</b></div>`).join('');
  } else if (showers.next) {
    html += `<div class="atmo-line"><span>Next: ${showers.next.name}</span><b>in ${showers.next.days_away} days (peak ${showers.next.peak})</b></div>`;
  } else {
    html += '<div class="ds-empty">No major showers active right now.</div>';
  }
  html += `<div class="dex-section-title">Look Up Tonight</div><div class="atmo-tips">${tips.map(t => `<div class="atmo-tip">${t}</div>`).join('')}</div>`;
  if (comets.length) {
    html += `<div class="dex-section-title">Notable Comets</div>` +
      comets.map(c => `<div class="atmo-line"><span><b style="color:var(--text);">${c.name}</b></span></div><div class="atmo-sub" style="margin:-2px 0 6px;">${c.note}</div>`).join('');
  }
  html += `<div id="atmo-asteroids"></div><div id="atmo-launches"></div>`;
  // Satellites live at the bottom of the Guide now (their old nav slot became StormDex).
  html += `<div class="dex-section-title">Satellites Overhead</div><div id="atmo-sats-content"></div>`;
  el.innerHTML = html;
  fetchSatellites();
}

function renderApod(d) {
  const el = document.getElementById('atmo-apod');
  if (!el || !d || d.error) return;
  if (d.media_type && d.media_type !== 'image') {
    el.innerHTML = `<div class="dex-section-title">NASA Picture of the Day</div><div class="atmo-sub">${d.title || ''} — <a href="${d.url}" target="_blank" style="color:var(--accent-blue);">view</a></div>`;
    return;
  }
  el.innerHTML = `<div class="dex-section-title">NASA Picture of the Day</div>
    <div class="atmo-apod">
      ${d.url ? `<img src="${d.url}" alt="" style="width:100%;border-radius:8px;display:block;">` : ''}
      <div class="atmo-apod-title">${d.title || ''}</div>
      <div class="atmo-sub" style="max-height:120px;overflow:auto;margin-top:4px;">${d.explanation || ''}</div>
    </div>`;
}

// --- Satellites (catalog + live passes) ---
function fetchSatellites() {
  const el = document.getElementById('atmo-sats-content');
  if (el && !el.innerHTML.trim()) el.innerHTML = '<div style="text-align:center;color:var(--text-dim);padding:30px;">Finding satellites…</div>';
  fetch('/api/atmo/satellites').then(r => (r.ok ? r.json() : null)).then(d => { if (d) renderSatellites(d); }).catch(e => console.error('sats error:', e));
}

function renderSatellites(d) {
  const el = document.getElementById('atmo-sats-content');
  if (!el) return;
  const cat = d.catalog || [], passes = d.passes || {};
  if (!cat.length) { el.innerHTML = '<div class="ds-empty">No satellite data.</div>'; return; }
  // Soonest next pass first; satellites without a computed pass sink to the
  // bottom (naked-eye ones ahead of the rest within that group).
  const nextStart = (s) => {
    const ps = passes[String(s.norad)] || [];
    return ps.length && ps[0].start ? ps[0].start : Infinity;
  };
  cat.sort((a, b) => {
    const d1 = nextStart(a) - nextStart(b);
    if (d1) return d1 < 0 ? -1 : 1;
    return (b.naked_eye === true) - (a.naked_eye === true);
  });
  let html = '<div class="atmo-sub" style="margin-bottom:8px;">Notable satellites overhead — soonest pass first.</div>';
  html += cat.map(s => {
    const ps = passes[String(s.norad)] || [];
    const next = ps.length ? `${_passWhen(ps[0])}${ps[0].max_elevation != null ? ' · max ' + ps[0].max_elevation + '°' : ''}` : '';
    const eye = s.naked_eye ? '<span class="sat-eye" title="Visible to the naked eye">●</span>' : '';
    return `<div class="sat-card" onclick="openSatellite(${s.norad})">
      <div class="sat-head"><b>${s.name}</b>${eye}<span class="sat-type">${s.type || ''}</span></div>
      <div class="atmo-sub">${s.owner || ''}${s.country ? ' · ' + s.country : ''}</div>
      <div class="sat-purpose">${s.purpose || ''}</div>
      ${s.note ? `<div class="atmo-sub" style="margin-top:3px;">${s.note}</div>` : ''}
      ${next ? `<div class="sat-pass">Next pass: <b>${next}</b></div>` : ''}
    </div>`;
  }).join('');
  el.innerHTML = html;
}

const SAT_SVG = '<svg viewBox="0 0 24 24" width="100%" height="100%" fill="currentColor"><path d="M11.3 1.7 8.5 4.5l2.1 2.1-1.4 1.4L7.1 6 5 8.1l2.1 2.1-1.4 1.4-2.1-2.1L1.7 11.3a1 1 0 0 0 0 1.4l2.1 2.1 2-2 1.5 1.4-2.1 2.1 2.8 2.8 2.1-2.1 1.4 1.4-2 2 2.1 2.1a1 1 0 0 0 1.4 0l1.8-1.9-2.1-2.1 1.4-1.4 2.1 2.1 2.1-2.1-2.1-2.1 1.4-1.4 2.1 2.1 1.9-1.8a1 1 0 0 0 0-1.4l-9.9-9.9a1 1 0 0 0-1.4 0z"/></svg>';

async function openSatellite(norad) {
  if (!norad) return;
  SkyDex.previousView = SkyDex.currentView;
  SkyDexAudio.playBeep();
  try {
    const res = await fetch(`/api/atmo/satellite/${norad}`);
    const d = res.ok ? await res.json() : null;
    if (!d || d.error) { showToast('Satellite not found', ''); return; }
    renderSatelliteDetail(d);
    showView('detail');
  } catch (e) { console.error('openSatellite error:', e); showToast('Error loading satellite', ''); }
}

function renderGroundTrack(track) {
  if (!Array.isArray(track) || track.length < 2) return '';
  const W = 280, H = 140;
  const px = (lon) => ((lon + 180) / 360) * W;
  const py = (lat) => ((90 - lat) / 180) * H;
  let segs = [], cur = [], prev = null;
  track.forEach(p => {
    if (prev && Math.abs(p[1] - prev[1]) > 180) { segs.push(cur); cur = []; }   // date-line wrap
    cur.push(`${px(p[1]).toFixed(1)},${py(p[0]).toFixed(1)}`); prev = p;
  });
  if (cur.length) segs.push(cur);
  const polys = segs.filter(s => s.length > 1).map(s => `<polyline points="${s.join(' ')}" fill="none" stroke="#6a4fd0" stroke-width="2"/>`).join('');
  return `<div class="dex-section-title">Ground Track (next ~90 min)</div>
    <svg viewBox="0 0 ${W} ${H}" style="width:100%;background:#0a0f1a;border-radius:8px;">
      <rect width="${W}" height="${H}" fill="#0a0f1a"/>
      <line x1="0" y1="${H / 2}" x2="${W}" y2="${H / 2}" stroke="#1f2a40" stroke-width="1"/>
      <line x1="${W / 2}" y1="0" x2="${W / 2}" y2="${H}" stroke="#1f2a40" stroke-width="1"/>
      ${polys}
      <circle cx="${px(track[0][1]).toFixed(1)}" cy="${py(track[0][0]).toFixed(1)}" r="4" fill="#ffd24a"/>
    </svg>`;
}

function renderSatelliteDetail(d) {
  const s = d.satellite || {};
  const passes = d.passes || [];
  const pos = d.position;
  const hist = d.history || [];
  const color = '#6a4fd0';
  const passHtml = passes.length
    ? passes.slice(0, 6).map(p => `<div class="atmo-line"><span>${_passWhen(p) || 'Pass'}</span><b>max ${p.max_elevation != null ? p.max_elevation + '°' : '—'}</b></div>`).join('')
    : '<div class="ds-empty">No passes in the next 24h (or pass prediction isn\'t set up — see notes).</div>';
  const posHtml = pos ? `
        <div class="dex-section-title">Live Position ${pos.overhead ? '<span class="sat-now">OVERHEAD NOW</span>' : ''}</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;font-size:12px;margin-bottom:8px;">
          <div><span style="color:var(--text-dim);">Over:</span> <span style="color:var(--text);">${pos.lat}, ${pos.lon}</span></div>
          <div><span style="color:var(--text-dim);">Altitude:</span> <span style="color:var(--text);">${pos.alt_km} km</span></div>
          <div><span style="color:var(--text-dim);">Speed:</span> <span style="color:var(--text);">${pos.velocity_kms} km/s</span></div>
          <div><span style="color:var(--text-dim);">From you:</span> <span style="color:var(--text);">${pos.elevation != null ? pos.elevation + '° el' : '—'}${pos.azimuth != null ? ' · ' + pos.azimuth + '° az' : ''}</span></div>
        </div>
        ${renderGroundTrack(pos.track)}` : '';
  const histHtml = hist.length ? `<div class="dex-section-title">Logged Passes (${d.total_logged || hist.length})</div>` +
    hist.map(h => `<div class="atmo-line"><span>${fmtDateTimeEST(h.start_at * 1000)}</span><b>max ${h.max_elevation != null ? Math.round(h.max_elevation) + '°' : '—'}</b></div>`).join('') : '';
  document.getElementById('detail-content').innerHTML = `
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;cursor:pointer;" onclick="goBack()">
      <span style="font-size:18px;color:var(--accent-blue);">&#9664;</span>
      <span style="font-size:12px;color:var(--text-dim);">Back to satellites</span>
    </div>
    <div class="dex-detail-layout">
      <div class="dex-detail-left">
        <div class="dex-name">${s.name || ('NORAD ' + s.norad)}</div>
        <div class="dex-types-row"><span class="type-pill" style="background:${color};">${s.type || 'Satellite'}</span></div>
        <div class="dex-photo-frame"><span class="dex-photo-placeholder" style="width:46%;height:46%;color:${color};">${SAT_SVG}</span></div>
        <div style="margin-top:8px;font-size:11px;text-align:center;color:${s.naked_eye ? 'var(--accent-yellow)' : 'var(--text-dim)'};">${s.naked_eye ? '★ Visible to the naked eye' : 'Telescope / radio only'}</div>
        ${d.fact ? `<div class="dex-fact"><span class="dex-fact-label">Did you know?</span> ${d.fact}</div>` : ''}
      </div>
      <div class="dex-detail-right">
        <div class="dex-section-title">Satellite Data</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;font-size:12px;margin-bottom:12px;">
          <div><span style="color:var(--text-dim);">NORAD:</span> <span style="color:var(--text);font-family:monospace;">${s.norad}</span></div>
          <div><span style="color:var(--text-dim);">Type:</span> <span style="color:var(--text);">${s.type || '—'}</span></div>
          <div style="grid-column:1/-1;"><span style="color:var(--text-dim);">Owner:</span> <span style="color:var(--text);">${s.owner || '—'}</span></div>
          <div><span style="color:var(--text-dim);">Country:</span> <span style="color:var(--text);">${s.country || '—'}</span></div>
        </div>
        <div class="dex-section-title">Purpose</div>
        <div style="font-size:13px;color:var(--text);margin-bottom:10px;">${s.purpose || '—'}</div>
        ${s.note ? `<div class="atmo-sub" style="margin-bottom:10px;">${s.note}</div>` : ''}
        ${posHtml}
        <div class="dex-section-title">Upcoming Passes</div>
        ${passHtml}
        ${histHtml}
        ${renderNearMisses(d.near_misses)}
      </div>
    </div>`;
}

function renderNearMisses(list) {
  if (!Array.isArray(list) || !list.length) return '';
  const rows = list.map(n => {
    const dist = (n.distance != null) ? `${n.distance} km` : '';
    const when = n.time ? (String(n.time).length > 4 ? String(n.time).slice(0, 16).replace('T', ' ') : n.time) : '';
    return `<div class="atmo-line"><span>${n.object || 'object'}</span><b>${[dist, when].filter(Boolean).join(' · ') || '—'}</b></div>`;
  }).join('');
  return `<div class="dex-section-title">Close Approaches</div>${rows}`;
}

// UFO easter egg — streak a saucer across the screen, then jump to launches.
function ufoZoom() {
  const o = document.getElementById('ufo-overlay');
  if (o) { o.classList.remove('ufo-fly'); void o.offsetWidth; o.classList.add('ufo-fly'); }
  try { SkyDexAudio.playBeep(); } catch (e) { /* ignore */ }
  setTimeout(() => { if (SkyDex.mode !== 'atmo') setMode('atmo'); showView('atmo-guide'); }, 1000);
  setTimeout(() => { if (o) o.classList.remove('ufo-fly'); }, 2200);
}

// --- Forecast (multi-day weather) ---
function fetchForecast() {
  const el = document.getElementById('atmo-forecast-content');
  if (el && !el.innerHTML.trim()) el.innerHTML = '<div style="text-align:center;color:var(--text-dim);padding:30px;">Loading forecast…</div>';
  fetch('/api/forecast').then(r => (r.ok ? r.json() : null)).then(d => {
    // Back-compat: old server shape was a bare array of periods.
    if (Array.isArray(d)) d = { periods: d, climate: null, national: [], alerts: [] };
    renderForecast(d || { periods: [] });
  }).catch(e => console.error('forecast error:', e));
}

/** Keyword -> weather icon SVG (drawn inline, no emoji). */
function wxIcon(shortText) {
  const s = (shortText || '').toLowerCase();
  const svg = (inner) => `<svg viewBox="0 0 24 24" width="30" height="30" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${inner}</svg>`;
  const CLOUD = '<path d="M17.5 18H7a4 4 0 1 1 .6-7.96A5.5 5.5 0 0 1 18 8.5a4.5 4.5 0 0 1-.5 9.5z"/>';
  if (/thunder|t-?storm/.test(s)) return `<span style="color:#ffd24a;">${svg(CLOUD + '<path d="M12 14l-2 4h3l-2 4" stroke="#ffd24a"/>')}</span>`;
  if (/snow|flurr|sleet|wintry/.test(s)) return `<span style="color:#bfe3ff;">${svg(CLOUD + '<path d="M9 20v.1M12 21v.1M15 20v.1" stroke-width="2.4"/>')}</span>`;
  if (/rain|shower|drizzle/.test(s)) return `<span style="color:#30A7D7;">${svg(CLOUD + '<path d="M9 20l-.5 1.5M12.5 20l-.5 1.5M16 20l-.5 1.5"/>')}</span>`;
  if (/fog|mist|haze/.test(s)) return `<span style="color:#9aa7b7;">${svg('<path d="M4 10h16M3 14h18M5 18h14"/>')}</span>`;
  if (/wind|breez|blustery/.test(s)) return `<span style="color:#98D8D8;">${svg('<path d="M3 8h9a3 3 0 1 0-3-3M3 12h13a3 3 0 1 1-3 3M3 16h7"/>')}</span>`;
  if (/partly|mostly sunny|mostly clear|scattered/.test(s)) return `<span style="color:#ffd24a;">${svg('<circle cx="9" cy="9" r="3.5"/><path d="M9 2v1.6M2 9h1.6M4.2 4.2l1.1 1.1"/><path d="M18.5 19H10a3.5 3.5 0 1 1 .7-6.9A4.5 4.5 0 0 1 19 13a3.2 3.2 0 0 1-.5 6z" fill="rgba(154,167,183,0.25)"/>')}</span>`;
  if (/cloud|overcast/.test(s)) return `<span style="color:#9aa7b7;">${svg(CLOUD)}</span>`;
  return `<span style="color:#ffd24a;">${svg('<circle cx="12" cy="12" r="4.5"/><path d="M12 3v2.2M12 18.8V21M3 12h2.2M18.8 12H21M5.4 5.4l1.5 1.5M17.1 17.1l1.5 1.5M18.6 5.4l-1.5 1.5M6.9 17.1l-1.5 1.5"/>')}</span>`;
}

function renderForecast(d) {
  const el = document.getElementById('atmo-forecast-content');
  if (!el) return;
  const periods = d.periods || [];
  let html = '';

  // --- Today's climate record + "did we break it?" ---
  const c = d.climate;
  if (c && c.record_high != null) {
    const todayHi = periods.length ? Math.round(periods.find(p => p.is_daytime)?.temp ?? NaN) : NaN;
    let chase = '';
    if (!isNaN(todayHi)) {
      const gap = c.record_high - todayHi;
      chase = gap <= 0
        ? `<b style="color:#ff6b6b;">Today's forecast of ${todayHi}° would BREAK the record!</b>`
        : `Today's forecast high ${todayHi}° — <b style="color:var(--text);">${gap}° shy</b> of the record.`;
    }
    html += `<div class="fc-record">
        <div class="fc-record-title">Records for this date (since ${c.since})</div>
        <div class="fc-record-vals">
          <span>HIGH <b style="color:#ff9f43;">${c.record_high}°</b> <small>(${c.high_year})</small></span>
          <span>LOW <b style="color:#74b9ff;">${c.record_low}°</b> <small>(${c.low_year})</small></span>
        </div>
        ${chase ? `<div class="atmo-sub" style="margin-top:4px;">${chase}</div>` : ''}
      </div>`;
  }

  if (!periods.length) {
    html += '<div class="ds-empty">Forecast unavailable right now.</div>';
    el.innerHTML = html;
    return;
  }

  // --- Which weekdays have active alerts (for day-card badges) ---
  const alertDays = {};
  (d.alerts || []).forEach(a => {
    if (!a.onset) return;
    try {
      const start = new Date(a.onset);
      const end = a.ends ? new Date(a.ends) : start;
      for (let t = start.getTime(); t <= end.getTime() && t < start.getTime() + 7 * 864e5; t += 864e5) {
        const wd = new Date(t).toLocaleDateString('en-US', { weekday: 'long', timeZone: EST_TZ });
        (alertDays[wd] = alertDays[wd] || []).push(a.event);
      }
    } catch (e) {}
  });
  const todayWd = new Date().toLocaleDateString('en-US', { weekday: 'long', timeZone: EST_TZ });

  // --- Day cards: pair NWS day + night periods into one card with hi/lo ---
  const cards = [];
  for (let i = 0; i < periods.length; i++) {
    const p = periods[i];
    if (p.is_daytime === false && cards.length === 0) {
      cards.push({ name: p.name, hi: null, lo: p.temp, short: p.short, wind: p.wind, precip: p.precip });
      continue;
    }
    const night = periods[i + 1] && periods[i + 1].is_daytime === false ? periods[++i] : null;
    cards.push({ name: p.name, hi: p.temp, lo: night ? night.temp : p.temp_low,
                 short: p.short, wind: p.wind, dir: p.wind_dir, precip: p.precip });
  }

  html += '<div class="fc-grid">' + cards.slice(0, 10).map(cd => {
    const wd = (cd.name || '').split(' ')[0];
    const dayAlerts = alertDays[wd] || (/(today|tonight|this)/i.test(cd.name || '') ? alertDays[todayWd] || [] : []);
    const badge = dayAlerts.length
      ? `<div class="fc-alert" title="${dayAlerts.join(', ')}">&#9888; ${dayAlerts[0]}${dayAlerts.length > 1 ? ' +' + (dayAlerts.length - 1) : ''}</div>` : '';
    return `<div class="fc-card">
        <div class="fc-day">${cd.name || ''}</div>
        <div class="fc-ic">${wxIcon(cd.short)}</div>
        <div class="fc-temps">${cd.hi != null ? `<b>${Math.round(cd.hi)}°</b>` : ''}${cd.lo != null ? `<span>${Math.round(cd.lo)}°</span>` : ''}</div>
        <div class="fc-short">${cd.short || ''}</div>
        <div class="fc-meta">${cd.wind ? cd.wind + (cd.dir ? ' ' + cd.dir : '') : ''}${cd.precip ? ` · ${cd.precip}%` : ''}</div>
        ${badge}
      </div>`;
  }).join('') + '</div>';

  // --- Hour by hour (next 24h, horizontal scroll) ---
  const hours = d.hourly || [];
  if (hours.length) {
    // Highlight the hour we're living in right now.
    const nowLbl = new Date().toLocaleTimeString('en-US',
      { hour: 'numeric', timeZone: EST_TZ }).replace(':00', '').replace(/ /g, ' ');
    html += `<div class="dex-section-title">Hour by Hour</div><div class="fc-hourly">` +
      hours.map(h => {
        const isNow = String(h.label).trim() === nowLbl.trim();
        return `
        <div class="fch ${isNow ? 'now' : ''}">
          <div class="fch-t">${isNow ? 'NOW' : h.label}</div>
          <div class="fch-i">${wxIcon(h.short)}</div>
          <b>${h.temp != null ? Math.round(h.temp) + '°' : '—'}</b>
          <div class="fch-p">${h.precip ? h.precip + '%' : '&nbsp;'}</div>
        </div>`;
      }).join('') + '</div>';
  }

  // --- Home Weather Station: the living Windy map, front and center ---
  window._forecastHome = d.home || { lat: 41.1635, lon: -73.1262 };
  html += `<div class="dex-section-title">Home Weather Station</div>
    <div id="windy-holder"></div>
    <div class="atmo-sub" style="margin:4px 0 12px;">Live wind flowing over the house —
    tap the chips for rain radar, gusts, temperature &amp; clouds.</div>`;

  // --- Serious weather elsewhere in the country ---
  if ((d.national || []).length) {
    html += `<div class="dex-section-title">Around the Country</div>` +
      d.national.map(n => `<div class="atmo-line">
          <span><b style="color:${n.severity === 'Extreme' ? '#ff6b6b' : '#ffd24a'};">${n.event}</b></span>
          <b style="font-weight:normal;color:var(--text-dim);">${n.area}</b></div>`).join('') +
      `<div class="atmo-sub" style="margin-top:3px;">Most serious active NWS alerts nationwide.</div>`;
  }

  el.innerHTML = html;
  openWindy(window._windyLayer || 'wind', true);
}

// --- Home Weather Station (Windy embed — always mounted on the forecast) ---
const WINDY_LAYERS = [['wind', 'Wind'], ['rain', 'Rain'], ['gust', 'Gusts'],
                      ['temp', 'Temp'], ['clouds', 'Clouds']];

function openWindy(layer, quiet) {
  const holder = document.getElementById('windy-holder');
  if (!holder) return;
  if (!quiet && window.SkyDexAudio && SkyDexAudio.playBeep) SkyDexAudio.playBeep();
  window._windyLayer = layer;   // survives the 15-min auto-refresh
  const h = window._forecastHome || { lat: 41.1635, lon: -73.1262 };
  holder.innerHTML = `
    <div class="tuner-row">${WINDY_LAYERS.map(([k, label]) =>
      `<button class="band-chip ${k === layer ? 'on' : ''}" onclick="openWindy('${k}')">${label}</button>`).join('')}
    </div>
    <iframe id="windy-frame" frameborder="0"
      src="https://embed.windy.com/embed2.html?lat=${h.lat}&lon=${h.lon}&detailLat=${h.lat}&detailLon=${h.lon}&zoom=7&level=surface&overlay=${layer}&menu=&message=&marker=true&calendar=now&type=map&location=coordinates&metricWind=mph&metricTemp=%C2%B0F"></iframe>`;
}

// The forecast view itself also re-renders every 15 min while on screen, so
// the hourly strip and day cards can't go stale on an always-on kiosk.
setInterval(() => {
  if (SkyDex.currentView === 'atmo-forecast') fetchForecast();
}, 900000);

// --- Mode-aware bottom nav (air/sea views vs AtmoDex views) ---
function navTo(slot) {
  if (SkyDex.mode === 'atmo') {
    const m = { contacts: 'atmo', dex: 'atmo-storms', stats: 'atmo-forecast', graphs: 'atmo-guide' };
    showView(m[slot] || 'atmo');
  } else if (SkyDex.mode === 'land') {
    const m = { contacts: 'land', dex: 'land-dex', stats: 'land-road', graphs: 'land-history' };
    showView(m[slot] || 'land');
  } else if (SkyDex.mode === 'ether') {
    const m = { contacts: 'ether', dex: 'ether-dex', stats: 'ether-tuner', graphs: 'ether-bands' };
    showView(m[slot] || 'ether');
  } else {
    showView(slot);
  }
}

function setNavLabels(mode) {
  // Back-compat: callers used to pass a boolean "is atmo".
  const m = mode === true ? 'atmo' : (mode === false ? 'air' : mode);
  const L = m === 'atmo'
    ? { 'btn-contacts': 'Tonight', 'btn-dex': 'Storms', 'btn-stats': 'Forecast', 'btn-graphs': 'Guide' }
    : m === 'land'
    ? { 'btn-contacts': 'Station', 'btn-dex': 'Traindex', 'btn-stats': 'Road', 'btn-graphs': 'Grand Central' }
    : m === 'ether'
    ? { 'btn-contacts': 'Airwaves', 'btn-dex': 'iSpy', 'btn-stats': 'Radio', 'btn-graphs': 'HAM it Up' }
    : { 'btn-contacts': 'Live', 'btn-dex': 'Dex', 'btn-stats': 'Stats', 'btn-graphs': 'Graphs' };
  Object.entries(L).forEach(([id, txt]) => {
    const el = document.querySelector(`#${id} .pokedex-btn-label`);
    if (el) el.textContent = txt;
  });
}

// ============================================
// VIEW NAVIGATION
// ============================================

function showView(viewName) {
  if (viewName !== 'detail') {
    SkyDex.previousView = SkyDex.currentView;
  }
  SkyDex.currentView = viewName;

  // Stop the radar/map glide loops when we leave the live view (saves CPU).
  if (viewName !== 'contacts') {
    if (_radarTimer) { clearInterval(_radarTimer); _radarTimer = null; }
    if (_mapTimer) { clearInterval(_mapTimer); _mapTimer = null; }
  }

  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  const target = document.getElementById(`view-${viewName}`);
  if (target) target.classList.add('active');

  document.querySelectorAll('.pokedex-btn').forEach(btn => btn.classList.remove('active'));
  const btnMap = {
    contacts: 'btn-contacts', dex: 'btn-dex', stats: 'btn-stats', graphs: 'btn-graphs',
    atmo: 'btn-contacts', 'atmo-storms': 'btn-dex', 'atmo-forecast': 'btn-stats', 'atmo-guide': 'btn-graphs',
    land: 'btn-contacts', 'land-dex': 'btn-dex',
    'land-road': 'btn-stats', 'land-history': 'btn-graphs',
    ether: 'btn-contacts', 'ether-dex': 'btn-dex',
    'ether-tuner': 'btn-stats', 'ether-bands': 'btn-graphs',
  };
  if (btnMap[viewName]) {
    const btn = document.getElementById(btnMap[viewName]);
    if (btn) btn.classList.add('active');
  }

  const sea = SkyDex.mode === 'sea';
  if (viewName === 'dex') sea ? fetchFleetdex() : fetchDex();
  if (viewName === 'stats') sea ? fetchSeaStats() : fetchStats();
  if (viewName === 'contacts') { showMapMode(_mapMode); fetchContacts(); }
  if (viewName === 'graphs') sea ? fetchSeaGraphs() : fetchGraphs();
  if (viewName === 'daysummary') fetchDaySummary();
  if (viewName === 'atmo') fetchAtmo();
  if (viewName === 'atmo-guide') fetchSkyGuide();
  if (viewName === 'atmo-storms' && window.fetchStorms) fetchStorms();
  if (viewName === 'atmo-forecast') fetchForecast();
  if (viewName === 'land' && window.fetchLand) fetchLand();
  if (viewName === 'land-dex' && window.fetchLandDex) fetchLandDex();
  if (viewName === 'land-road' && window.fetchLandRoad) fetchLandRoad();
  if (viewName === 'land-history' && window.fetchLandHistory) fetchLandHistory();
  if (viewName === 'ether' && window.fetchEther) fetchEther();
  if (viewName === 'ether-dex' && window.renderISpy) renderISpy();
  if (viewName === 'ether-tuner' && window.renderTuner) renderTuner();
  if (viewName === 'ether-bands' && window.renderBands) renderBands();
}

function goBack() {
  SkyDexAudio.playBeep();
  if (SkyDex.previousView) {
    showView(SkyDex.previousView);
  } else {
    showView('contacts');
  }
}

// ============================================
// PRESS-AND-HOLD SCROLL (bottom arrow pads)
// ============================================

let _scrollTimer = null;

function _activeScrollEl() {
  // For the Live view, scroll the list column; otherwise the active view.
  const live = document.querySelector('#view-contacts.active .live-list');
  if (live) return live;
  return document.querySelector('.view.active');
}

function startScroll(dir) {
  stopScroll();
  const el = _activeScrollEl();
  if (!el) return;
  el.scrollTop += dir * 24;               // immediate nudge on tap
  _scrollTimer = setInterval(() => {
    const e = _activeScrollEl();
    if (e) e.scrollTop += dir * 14;       // continuous while held
  }, 16);
}

function stopScroll() {
  if (_scrollTimer) {
    clearInterval(_scrollTimer);
    _scrollTimer = null;
  }
}

// ============================================
// POLLING
// ============================================

function startPolling() {
  // Contacts every second (dead-reckoning glides positions between fetches)
  setInterval(() => {
    if (SkyDex.isPolling && SkyDex.currentView === 'contacts') {
      fetchContacts();
    }
  }, 1000);

  // Weather + Tide every minute; advisories alongside (server caches 5 min)
  setInterval(() => {
    fetchWeather();
    fetchAlerts();
  }, 60000);

  // Receiver source status every 10 seconds
  setInterval(() => {
    fetchReceiverStatus();
  }, 10000);

  // Initial fetches
  fetchContacts();
  fetchWeather();
  fetchAlerts();
  fetchReceiverStatus();
}

// ============================================
// INITIALIZATION
// ============================================

function initSkyDex() {
  console.log('\u{1F681} SkyDex initializing...');
  SkyDex.facts = [...AVIATION_FACTS];
  SkyDex.factIndex = Math.floor(Math.random() * AVIATION_FACTS.length);

  const factEl = document.getElementById('rotating-fact');
  if (factEl) factEl.textContent = AVIATION_FACTS[SkyDex.factIndex];

  updateAudioIcon();
  updateTicker();
  rebuildBadgeFilter(false);  // populate the air badge options on first load
  fetchFacts();
  setInterval(fetchFacts, 300000);  // refresh fact pool every 5 min

  // Initialize audio context on first user interaction (required by some browsers)
  document.addEventListener('click', () => {
    SkyDexAudio.init();
  }, { once: true });

  startPolling();
  showView('contacts');

  console.log('\u{1F681} SkyDex ready! Scanning the skies...');
}

document.addEventListener('DOMContentLoaded', initSkyDex);
