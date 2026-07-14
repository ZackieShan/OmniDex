/* SkyDex etherdex.js — EtherDex mode: the invisible radio neighborhood.
 * Live "Airwaves" view + the Etherdex collection. Loads after pokedex.js. */

// Fallback ticker facts until /api/facts?domain=ether loads.
window.ETHER_FACTS = [
  "Right now, invisible radio waves from dozens of machines are passing through this room.",
  "The microwave oven exists because a radar engineer's chocolate bar melted in his pocket in 1945.",
  "Number stations still haunt shortwave: robotic voices reading digits to spies. No government admits to them.",
  "Hollywood star Hedy Lamarr co-invented frequency hopping — the ancestor of Bluetooth and WiFi.",
  "About 1% of old TV static was the afterglow of the Big Bang.",
  "The Navy talks to submarines with radio waves longer than the state of Connecticut.",
  "In 1903, a magician hacked Marconi's 'secure' wireless demo and broadcast insults in Morse code.",
];

const ETHER_KINDS = {
  weather:    { label: 'Weather Station',   color: '#30A7D7' },
  tpms:       { label: 'Car Tire Sensor',   color: '#A89078' },
  doorbell:   { label: 'Doorbell',          color: '#F8D030' },
  remote:     { label: 'Remote / Key Fob',  color: '#78C850' },
  alarm:      { label: 'Alarm / Detector',  color: '#ff6b6b' },
  meter:      { label: 'Utility Meter',     color: '#48c9b0' },
  security:   { label: 'Door/Window Sensor', color: '#ff7f50' },
  garage:     { label: 'Garage Door',       color: '#95a5a6' },
  oil:        { label: 'Oil Tank Gauge',    color: '#8d6e63' },
  bbq:        { label: 'BBQ Thermometer',   color: '#e17055' },
  pool:       { label: 'Pool Thermometer',  color: '#00bcd4' },
  lightning:  { label: 'Lightning Detector', color: '#f7dc6f' },
  wifi_home:    { label: 'Home WiFi',        color: '#5dade2' },
  wifi_router:  { label: 'WiFi Router',      color: '#5dade2' },
  wifi_mesh:    { label: 'Mesh WiFi',        color: '#48c9b0' },
  wifi_public:  { label: 'Public Hotspot',   color: '#f5b041' },
  wifi_printer: { label: 'WiFi Printer',     color: '#B8B8D0' },
  wifi_camera:  { label: 'WiFi Camera',      color: '#ff7f50' },
  wifi_hidden:  { label: 'Hidden Network',   color: '#9b59d0' },
  mystery:    { label: 'Mystery Signal',    color: '#9b59d0' },
  bt:         { label: 'Bluetooth Gadget',  color: '#0082FC' },
  headphones: { label: 'Headphones',        color: '#ff6b9d' },
  watch:      { label: 'Smart Watch',       color: '#4ade80' },
  tv:         { label: 'TV / Streaming Box', color: '#7859c4' },
  speaker:    { label: 'Speaker',           color: '#ff9f43' },
  car:        { label: 'Car',               color: '#9db4c8' },
  phone:      { label: 'Phone',             color: '#0082FC' },
  appliance:  { label: 'Appliance',         color: '#98D8D8' },
  printer:    { label: 'Printer',           color: '#B8B8D0' },
};

/** "About how far away?" — RSSI translated into kid-world distance.
 *  Bluetooth RSSI (dBm, ~-40 close … -90 far) vs rtl_433 level (0 … -25). */
function etherDistance(meta) {
  if (!meta) return '';
  if (meta.rssi_bt != null) {
    const r = meta.rssi_bt;
    if (r > -50) return 'right next to the kiosk (~5 ft)';
    if (r > -65) return 'in the same room (~10-20 ft)';
    if (r > -75) return 'somewhere in the house (~30-50 ft)';
    if (r > -85) return 'edge of the yard (~60-100 ft)';
    return 'far away — barely a whisper';
  }
  if (meta.rssi != null) {
    const r = Math.abs(meta.rssi);
    if (r < 6) return 'very close — strong signal';
    if (r < 12) return 'nearby (~a house or two away)';
    if (r < 18) return 'down the street';
    return 'far away — barely a whisper';
  }
  return '';
}

const ETHER_SVG = {
  // Radio waves (default / mystery)
  wave: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" width="70%" height="70%"><circle cx="12" cy="18" r="2" fill="currentColor" stroke="none"/><path d="M8.5 14.5a5 5 0 0 1 7 0M5.7 11.7a9 9 0 0 1 12.6 0M3 9a13 13 0 0 1 18 0"/></svg>',
  weather: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" width="70%" height="70%"><path d="M12 3v3M12 18v3M3 12h3M18 12h3"/><circle cx="12" cy="12" r="4"/><circle cx="12" cy="12" r="1.4" fill="currentColor" stroke="none"/></svg>',
  tpms: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="70%" height="70%"><circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3.5"/><path d="M12 4v3M12 17v3M4 12h3M17 12h3" stroke-linecap="round"/></svg>',
  bt: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" width="66%" height="66%"><path d="M7 7l10 10-5 4V3l5 4L7 17"/></svg>',
};

const ETHER_SVG_EXTRA = {
  headphones: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" width="66%" height="66%"><path d="M4 15v-3a8 8 0 0 1 16 0v3"/><rect x="3" y="14" width="4" height="7" rx="2" fill="currentColor" stroke="none"/><rect x="17" y="14" width="4" height="7" rx="2" fill="currentColor" stroke="none"/></svg>',
  watch: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" width="62%" height="62%"><rect x="7" y="6" width="10" height="12" rx="3"/><path d="M9 6l.5-3h5L15 6M9 18l.5 3h5l.5-3M12 10v2.5l2 1"/></svg>',
  tv: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" width="66%" height="66%"><rect x="3" y="5" width="18" height="12" rx="2"/><path d="M8 21h8M12 17v4"/></svg>',
  speaker: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" width="62%" height="62%"><rect x="6" y="3" width="12" height="18" rx="2"/><circle cx="12" cy="14" r="3.4"/><circle cx="12" cy="7.5" r="1.4" fill="currentColor" stroke="none"/></svg>',
  car: '<svg viewBox="0 0 24 24" fill="currentColor" width="66%" height="66%"><path d="M5 11l1.5-4.5A2 2 0 0 1 8.4 5h7.2a2 2 0 0 1 1.9 1.5L19 11a2 2 0 0 1 2 2v4h-2a2 2 0 1 1-4 0H9a2 2 0 1 1-4 0H3v-4a2 2 0 0 1 2-2zm2.1 0h9.8l-1-3H8.1z"/></svg>',
  phone: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" width="58%" height="58%"><rect x="7" y="2" width="10" height="20" rx="2.5"/><path d="M11 18.5h2" stroke-linecap="round"/></svg>',
  meter: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" width="64%" height="64%"><circle cx="12" cy="12" r="8.5"/><path d="M12 12l3.6-3.6M12 5.5v1.5M18.5 12H17M5.5 12H7"/><circle cx="12" cy="12" r="1.3" fill="currentColor" stroke="none"/></svg>',
  security: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" width="62%" height="62%"><path d="M12 3l7 3v5c0 4.8-3.2 7.9-7 10-3.8-2.1-7-5.2-7-10V6z"/><path d="M9.5 12l2 2 3.5-4"/></svg>',
  garage: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" width="64%" height="64%"><path d="M3 10l9-6 9 6v10h-3.5v-9h-11v9H3z"/><path d="M6.5 14h11M6.5 17h11M6.5 20h11"/></svg>',
  oil: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linejoin="round" width="58%" height="58%"><path d="M12 3s6.5 7.5 6.5 11.5a6.5 6.5 0 0 1-13 0C5.5 10.5 12 3 12 3z"/><path d="M9 15a3 3 0 0 0 3 3" stroke-linecap="round"/></svg>',
  bbq: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" width="64%" height="64%"><path d="M4 10h16a8 8 0 0 1-16 0z" fill="currentColor" stroke="none"/><path d="M8 17l-2 4M16 17l2 4M12 18v3M8 3v3M12 2v3M16 3v3"/></svg>',
  pool: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" width="64%" height="64%"><path d="M2 16c2 1.6 4 1.6 6 0s4-1.6 6 0 4 1.6 6 0M2 20c2 1.6 4 1.6 6 0s4-1.6 6 0 4 1.6 6 0"/><path d="M12 3v8M9.5 5.5L12 3l2.5 2.5"/></svg>',
  lightning: '<svg viewBox="0 0 24 24" fill="currentColor" width="60%" height="60%"><path d="M13 2L4.5 13.5H10L8.5 22 17.5 9.5H12z"/></svg>',
};

const WIFI_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" width="64%" height="64%"><path d="M2 8.5a15 15 0 0 1 20 0M5 12a10 10 0 0 1 14 0M8 15.4a5 5 0 0 1 8 0"/><circle cx="12" cy="19" r="1.2" fill="currentColor" stroke="none"/></svg>';

function etherIcon(kind) {
  if (kind && kind.indexOf('wifi') === 0) return WIFI_SVG;
  if (ETHER_SVG_EXTRA[kind]) return ETHER_SVG_EXTRA[kind];
  if (kind === 'bt' || kind === 'appliance' || kind === 'printer') return ETHER_SVG.bt;
  if (kind === 'weather') return ETHER_SVG.weather;
  if (kind === 'tpms') return ETHER_SVG.tpms;
  return ETHER_SVG.wave;
}

/** Kid-readable second line: what it's measuring + about how far away. */
function _etherMeta(meta) {
  if (!meta) return '';
  const bits = [];
  if (meta.temp_c != null) bits.push('reads ' + Math.round(meta.temp_c * 9 / 5 + 32) + '°F');
  if (meta.humidity != null) bits.push(meta.humidity + '% humidity');
  if (meta.pressure_kpa != null) bits.push('tire at ' + Math.round(meta.pressure_kpa * 0.145) + ' psi');
  if (meta.consumption != null) bits.push('meter reading: ' + Number(meta.consumption).toLocaleString());
  if (meta.wind_kmh != null) bits.push('wind ' + Math.round(meta.wind_kmh * 0.621) + ' mph');
  if (meta.rain_mm != null) bits.push('has counted ' + (meta.rain_mm / 25.4).toFixed(2) + '" of rain');
  if (meta.strikes != null) bits.push('&#9889; ' + meta.strikes + ' lightning strikes counted');
  if (meta.moisture != null) bits.push('soil ' + meta.moisture + '% wet');
  if (meta.band) bits.push(meta.band + (meta.locked ? ' · 🔒 password-locked' : ' · open'));
  if (meta.signal_pct != null) {
    const s = meta.signal_pct;
    bits.push(s > 70 ? 'very close — probably in this house'
      : s > 45 ? 'nearby — next door or so'
      : s > 20 ? 'down the street' : 'far away — faint');
  }
  const dist = etherDistance(meta);
  if (dist) bits.push('probably ' + dist);
  return bits.join(' · ');
}

let _etherTimer = null;

// ============================================
// AIRWAVES (live view)
// ============================================
async function fetchEther() {
  const el = document.getElementById('ether-content');
  _etherCollRefresh();   // collection summary lives at the bottom of Airwaves now
  try {
    renderEther(await (await fetch('/api/ether')).json());
  } catch (e) {
    if (el) el.innerHTML = '<div class="ds-empty">Receiver unreachable.</div>';
  }
  if (_etherTimer) clearInterval(_etherTimer);
  _etherTimer = setInterval(() => {
    if (SkyDex.currentView === 'ether') fetchEther._quiet();
    else { clearInterval(_etherTimer); _etherTimer = null; }
  }, 20000);
}
fetchEther._quiet = async function () {
  try { renderEther(await (await fetch('/api/ether')).json()); } catch (e) {}
};

function renderEther(d) {
  const el = document.getElementById('ether-content');
  if (!el) return;
  const live = d.live || [];
  const st = d.status || {};
  const count = document.getElementById('ether-count');
  if (count) count.innerHTML =
    `<div style="font-size:22px;font-weight:bold;color:var(--accent-yellow);">${d.collection_count || 0}</div>devices collected`;
  window._etherStatus = st;   // band chips read the current hop list from here
  // Keep the global stop button honest about server-side tuner audio.
  window._listenUntil = st.listening ? Date.now() + (st.listening.seconds_left || 0) * 1000 : 0;
  const sub = document.getElementById('ether-sub');
  if (sub) sub.textContent = st.rtl_running
    ? `Listening on ${(st.freqs || []).join(' + ') || '433 MHz'} + Bluetooth · last 20 minutes`
    : !st.rtl_installed ? 'rtl-433 NOT INSTALLED — sudo apt install rtl-433, then restart'
    : st.device === '(none pinned!)' ? 'NO DONGLE PINNED — /admin → Ether → device selector → :0162, then restart'
    : st.last_error ? `RF receiver error: ${st.last_error}`
    : 'RF receiver starting (or dongle busy) · Bluetooth only';

  if (!live.length) {
    el.innerHTML = etherScope([]) + bandChips(st.freqs) + listenChips(st) + `<div class="ds-empty">The ether is quiet…<br><br>
      Weather stations report every ~30s. Tire sensors need a car to drive past.
      Click your car's key fob near the kiosk for an instant test catch.</div>` + _etherCollSummaryHtml();
    return;
  }
  const now = Date.now() / 1000;
  // Residents (the Shield, the soundbar…) fold into one line — they LIVE here;
  // the card list stays reserved for things actually passing through.
  const residents = live.filter(v => v.resident);
  const visitors = live.filter(v => !v.resident);
  let html = etherScope(live) + bandChips(st.freqs) + listenChips(st);
  if (residents.length) {
    html += `<div class="resident-row">&#127968; <b>Home &amp; regulars (${residents.length}):</b>
      ${residents.map(v => v.name || v.key).slice(0, 8).join(' · ')}${residents.length > 8 ? ' …' : ''}</div>`;
  }
  if (!visitors.length) {
    html += `<div class="ds-empty">Nothing passing through right now — just the residents above.</div>`;
  }
  html += visitors.map(v => {
    const k = ETHER_KINDS[v.kind] || ETHER_KINDS.mystery;
    const ago = Math.max(0, Math.round((now - v.last) / 60));
    return `<div class="pass-card">
        <div class="pass-icon" style="color:${k.color};">${etherIcon(v.kind)}</div>
        <div class="pass-body">
          <div class="pass-name">${v.name || 'Unknown'} <span class="sat-type" style="color:${k.color};">${k.label}</span></div>
          <div class="pass-sub">${_etherMeta(v.meta) || 'just saying hello on the airwaves'}</div>
        </div>
        <div class="pass-stats">
          <div class="pass-dist">${ago === 0 ? 'now' : ago + ' min ago'}</div>
        </div>
      </div>`;
  }).join('');
  html += _etherCollSummaryHtml();
  el.innerHTML = html;
}

// ============================================
// ETHERDEX COLLECTION SUMMARY + iSPY
// ============================================
// The old EtherDex collection view became iSpy; the collection now lives as
// a compact summary at the bottom of Airwaves (cached, refreshed lazily).
async function _etherCollRefresh() {
  if (window._etherCollAt && Date.now() - window._etherCollAt < 600e3) return;
  try {
    const d = await (await fetch('/api/ether/collection')).json();
    if (Array.isArray(d)) { window._etherColl = d; window._etherCollAt = Date.now(); }
  } catch (e) { /* keep the old cache */ }
}

function _etherCollSummaryHtml() {
  const devices = window._etherColl;
  if (!devices || !devices.length) return '';
  const kinds = new Set(devices.map(v => v.kind));
  const res = devices.filter(v => v.resident);
  const top = devices.slice().sort((a, b) => (b.times_seen || 0) - (a.times_seen || 0)).slice(0, 6);
  return `<div class="dex-section-title">The Collection — ${devices.length} devices ever heard
      · ${kinds.size} kinds · ${res.length} residents</div>
    <div class="tuner-row">` +
    top.map(v => {
      const k = ETHER_KINDS[v.kind] || ETHER_KINDS.mystery;
      return `<span class="band-chip" style="border-color:${k.color};color:${k.color};cursor:default;">
        ${_esc((v.name || v.device_key || '').slice(0, 22))} ×${v.times_seen}</span>`;
    }).join('') +
    `</div><div class="atmo-sub">Devices, never people · unheard for 90 days = forgotten.</div>`;
}

// ============================================
// iSPY — WHERE IN THE WORLD? A real webcam, 3 guesses, hints between.
// Only a FIRST-try guess scores (+20 × 5 rounds = 100).
// ============================================
let _ispy = null;
const ISPY_ROUNDS = 5;
const ISPY_PADS = [
  { city: 'Tokyo', country: 'Japan', continent: 'Asia' },
  { city: 'Paris', country: 'France', continent: 'Europe' },
  { city: 'Sydney', country: 'Australia', continent: 'Oceania' },
  { city: 'Cairo', country: 'Egypt', continent: 'Africa' },
  { city: 'Lima', country: 'Peru', continent: 'South America' },
  { city: 'Reykjavik', country: 'Iceland', continent: 'Europe' },
];

/** The shared player lives in games.js as a plain `let` — it is NOT on
 *  window, so read it lexically (and fall back safely if games.js is absent). */
function _ispyPlayer() {
  try { return (typeof _player !== 'undefined' && _player) ? _player : 'Guest'; }
  catch (e) { return 'Guest'; }
}

function ispySetPlayer(n) {
  if (window.SkyDexAudio && SkyDexAudio.playBeep) SkyDexAudio.playBeep();
  try {
    _player = n;                            // the games.js binding — shared everywhere
    localStorage.setItem('skydex_player', n);
  } catch (e) {}
  showToast(n + ' is playing!', 'success');
  renderISpy();
}

function renderISpy() {
  const el = document.getElementById('etherdex-content');
  if (!el) return;
  const who = _ispyPlayer();
  const names = (typeof SPOTTERS !== 'undefined' ? SPOTTERS : ['Guest']);
  el.innerHTML = `
    <div class="ds-empty" style="padding:18px;">Somewhere on Earth, a camera is watching a street,
      a beach, a harbor… Spin the globe, study the picture, and figure out WHERE.
      Three tries, a hint before each — but only a first-try guess earns points!</div>
    <div class="tuner-row" style="justify-content:center;">
      <span class="atmo-sub" style="align-self:center;">Who's playing?</span>
      ${names.map(n => `<button class="band-chip ${n === who ? 'on' : ''}"
        onclick="ispySetPlayer('${n}')">${n}</button>`).join('')}
    </div>
    <div class="tuner-row" style="justify-content:center;">
      <button class="day-summary-btn" style="margin:0;width:auto;display:inline-flex;padding:14px 30px;font-size:17px;"
        onclick="ispyStart()">&#127758; Spin the Globe</button>
    </div>
    <div id="ispy-stage"></div>`;
}

function ispyStart() {
  if (window.SkyDexAudio && SkyDexAudio.playBeep) SkyDexAudio.playBeep();
  _ispy = { round: 0, score: 0, fails: 0 };
  ispyNext();
}

async function ispyNext() {
  const stage = document.getElementById('ispy-stage');
  if (!stage) return;
  if (_ispy.round >= ISPY_ROUNDS) return _ispyFinish();
  stage.innerHTML = '<div class="ds-empty">Spinning the globe… finding a camera…</div>';
  let q;
  try { q = await (await fetch('/api/ispy')).json(); } catch (e) { q = { error: 'iSpy desk unreachable' }; }
  if (q.error) { stage.innerHTML = `<div class="ds-empty">${_esc(q.error)}</div>`; return; }
  // Windy's preview JPEGs are squeezed to a fixed 400x224 — cameras that
  // aren't 16:9 arrive distorted AT THE SOURCE. The /full/ variant keeps the
  // true aspect and much more detail; fall back to the preview if absent.
  let img = null;
  const full = String(q.answer.image).replace('/preview/', '/full/');
  if (full !== q.answer.image && await _preload(full)) img = full;
  else if (await _preload(q.answer.image)) img = q.answer.image;
  if (!img) {
    if (++_ispy.fails < 4) return ispyNext();     // camera-shy cam — spin again
    stage.innerHTML = '<div class="ds-empty">The cameras are shy right now — try again in a minute.</div>';
    return;
  }
  q.answer.image = img;
  _ispy.fails = 0;
  _ispy.q = q.answer;
  _ispy.tries = 0;
  // 6 location cards: the answer + real-decoy cams + famous-city padding.
  const seen = new Set([q.answer.country]);
  const opts = [q.answer];
  (q.decoys || []).concat(ISPY_PADS).forEach(d => {
    if (opts.length < 6 && d.city && !seen.has(d.country)) { seen.add(d.country); opts.push(d); }
  });
  _ispy.choices = _shuffle(opts.slice());
  stage.innerHTML = `
    <div class="game-head">Round ${_ispy.round + 1}/${ISPY_ROUNDS} · Score ${_ispy.score} · ${_esc(_ispyPlayer())}</div>
    <div class="ispy-cam"><img src="${q.answer.image}" alt=""><div class="ispy-live">&#128308; somewhere on Earth</div></div>
    <div id="ispy-hint" class="atmo-tip">${_ispyHint(0)}</div>
    <div class="game-head" style="font-size:16px;">Where is this? <span id="ispy-tries">&#9679;&#9679;&#9679;</span></div>
    <div class="ispy-choices">${_ispy.choices.map((c, i) =>
      `<button class="ispy-choice" onclick="ispyGuess(${i}, this)">
         <b>${_esc(c.city)}</b><span>${_esc(c.country)}</span></button>`).join('')}</div>`;
  stage.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function _ispyHint(n) {
  const a = _ispy.q;
  if (n === 0) return `Hint 1: This place is in <b>${_esc(a.continent || 'the world (that narrows it down!)')}</b>.`;
  if (n === 1) {
    const hr = (new Date().getUTCHours() + Math.round((a.lon || 0) / 15) + 24) % 24;
    const label = ((hr % 12) || 12) + (hr < 5 ? ' in the middle of the night' : hr < 12 ? ' in the morning'
      : hr < 18 ? ' in the afternoon' : ' at night');
    return `Hint 2: Look at the light — it's about <b>${label}</b> there right now.`;
  }
  return `Hint 3: The country's name starts with <b>"${_esc((a.country || '?')[0])}"</b>.`;
}

function ispyGuess(i, btn) {
  const c = _ispy.choices[i], a = _ispy.q;
  if (!c || btn.disabled) return;
  const right = c.city === a.city && c.country === a.country;
  if (right) {
    const pts = _ispy.tries === 0 ? 20 : 0;
    _ispy.score += pts;
    if (window.SkyDexAudio && SkyDexAudio.playCatchJingle) { try { SkyDexAudio.playCatchJingle(); } catch (e) {} }
    _ispyReveal(pts, false);
  } else {
    if (window.SkyDexAudio && SkyDexAudio.playBeep) SkyDexAudio.playBeep();
    btn.classList.add('wrong');
    btn.disabled = true;
    _ispy.tries++;
    const dots = document.getElementById('ispy-tries');
    if (dots) dots.innerHTML = '&#9679;'.repeat(Math.max(0, 3 - _ispy.tries)) + '&#9675;'.repeat(_ispy.tries);
    if (_ispy.tries >= 3) return _ispyReveal(0, true);
    const h = document.getElementById('ispy-hint');
    if (h) h.innerHTML = _ispyHint(_ispy.tries);
  }
}

function _ispyReveal(pts, failed) {
  const a = _ispy.q;
  document.querySelectorAll('.ispy-choice').forEach(b => {
    b.disabled = true;
    if (b.querySelector('b') && b.querySelector('b').textContent === a.city) b.classList.add('right');
  });
  // Clean transition: the MAP takes the webcam's place and flies to the answer.
  const cam = document.querySelector('.ispy-cam');
  const mapId = 'ispy-map-' + _ispy.round;
  if (cam) cam.innerHTML = `<div id="${mapId}" class="ispy-map-inplace"></div>`;
  if (window.L && a.lat != null) {
    setTimeout(() => {
      try {
        const m = L.map(mapId, { zoomControl: false, attributionControl: false })
          .setView([20, (a.lon || 0) - 60], 2);
        L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
          { maxZoom: 10 }).addTo(m);
        setTimeout(() => m.flyTo([a.lat, a.lon], 5, { duration: 1.6 }), 250);
        setTimeout(() => L.circleMarker([a.lat, a.lon], { radius: 8, color: '#fff',
          fillColor: '#FFCB05', fillOpacity: 1 }).addTo(m)
          .bindTooltip(a.city).openTooltip(), 1900);
      } catch (e) {}
    }, 60);
  }
  const stage = document.getElementById('ispy-stage');
  stage.insertAdjacentHTML('beforeend', `
    <div class="ispy-reveal">
      <div class="game-head" style="font-size:17px;">
        ${failed ? 'It was' : pts ? '&#127881; FIRST TRY! +20 points —' : '&#10004; Got there (points need a first-try) —'}
        <b>${_esc(a.city)}, ${_esc(a.country)}</b></div>
      <div class="atmo-tip">&#128247; <b>${_esc(a.title || 'Live camera')}</b> — a real
        ${_esc(a.category || 'public')} cam in ${_esc(a.continent || 'the world')}, updating all day.
        ${a.lat != null ? `It sits at ${a.lat.toFixed(2)}°, ${a.lon.toFixed(2)}°.` : ''}</div>
      <div class="tuner-row" style="justify-content:center;margin-top:10px;">
        ${a.player ? `<button class="day-summary-btn" style="margin:0;width:auto;display:inline-flex;"
          onclick="ispyMotion('${mapId}')">&#9654; Watch this place move</button>` : ''}
        <button class="day-summary-btn" style="margin:0;width:auto;display:inline-flex;padding:12px 24px;font-size:15px;"
          onclick="_ispy.round++;ispyNext()">${_ispy.round + 1 >= ISPY_ROUNDS ? 'Finish' : 'Next camera'} &#9654;</button>
      </div>
    </div>`);
}

/** Post-reveal payoff: swap the map for the camera's day-timelapse player —
 *  the same spot, moving. (No spoiler risk once the answer is out.) */
function ispyMotion(mapId) {
  const a = _ispy.q;
  const el = document.getElementById(mapId);
  if (!el || !a.player) return;
  if (window.SkyDexAudio && SkyDexAudio.playBeep) SkyDexAudio.playBeep();
  el.outerHTML = `<iframe class="ispy-motion" src="${a.player}" frameborder="0" allowfullscreen></iframe>`;
}

function _ispyFinish() {
  const stage = document.getElementById('ispy-stage');
  const s = _ispy.score, name = _ispyPlayer();
  stage.innerHTML = `<div class="game-over">
      <div class="ach-party-kicker">ISPY — WHERE IN THE WORLD?</div>
      <div class="game-score">${s}</div>
      <div class="atmo-sub">${_esc(name)}'s score · ${s / 20} first-try finds out of ${ISPY_ROUNDS}</div>
      <div class="tuner-row" style="justify-content:center;margin-top:12px;">
        <button class="day-summary-btn" style="margin:0;width:auto;display:inline-flex;" onclick="renderISpy()">Play again</button>
      </div>
    </div>`;
  fetch('/api/game/score', { method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: name, game: 'ispy', score: s }) })
    .then(r => r.json()).then(d => {
      if (d.personal_best) {
        showToast('NEW iSpy personal best! &#127942;', 'success');
        if (window.SkyDexAudio && SkyDexAudio.playCatchJingle) { try { SkyDexAudio.playCatchJingle(); } catch (e) {} }
      }
    }).catch(() => {});
}

// ============================================
// RF SCOPE — waves "on the map", honestly:
// blips ring out from the kiosk; distance = signal strength, not location
// (a doorbell doesn't broadcast GPS — nothing on these bands does).
// ============================================
function etherScope(live) {
  const SIZE = 220, C = SIZE / 2, R = 96;
  const now = Date.now() / 1000;
  let blips = '';
  (live || []).slice(0, 24).forEach(v => {
    // Stable pseudo-bearing from the device key; radius from signal strength.
    let h = 0; for (let i = 0; i < v.key.length; i++) h = (h * 137 + v.key.charCodeAt(i)) % 3600;
    const ang = (h / 3600) * 2 * Math.PI;
    const rssi = v.meta && v.meta.rssi != null ? Math.abs(v.meta.rssi) : 12;
    const r = Math.min(R - 8, 18 + rssi * 3.4);          // strong = close
    const x = C + r * Math.sin(ang), y = C - r * Math.cos(ang);
    const k = ETHER_KINDS[v.kind] || ETHER_KINDS.mystery;
    const fresh = (now - v.last) < 120;
    blips += `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${fresh ? 5 : 3.5}" fill="${k.color}" opacity="${fresh ? 1 : 0.45}">
      ${fresh ? '<animate attributeName="r" values="4;7;4" dur="2s" repeatCount="indefinite"/>' : ''}</circle>`;
  });
  return `<svg viewBox="0 0 ${SIZE} ${SIZE}" style="width:min(46vw,240px);display:block;margin:0 auto;">
      <rect width="${SIZE}" height="${SIZE}" rx="12" fill="#0a0f0a"/>
      ${[R / 3, 2 * R / 3, R].map(r => `<circle cx="${C}" cy="${C}" r="${r}" fill="none" stroke="#2a1f3a" stroke-width="1"/>`).join('')}
      <line x1="${C}" y1="${C - R}" x2="${C}" y2="${C + R}" stroke="#2a1f3a"/>
      <line x1="${C - R}" y1="${C}" x2="${C + R}" y2="${C}" stroke="#2a1f3a"/>
      <circle cx="${C}" cy="${C}" r="3.5" fill="#FFCB05"/>
      ${blips}
      <text x="${C}" y="${SIZE - 7}" font-size="7.5" fill="#8b949e" text-anchor="middle">ring = signal strength · bearing unknown (radio keeps its secrets)</text>
    </svg>`;
}

// ============================================
// WORLD RADIO — throw a dart at the planet
// Primary: Radio-Browser.info (free, unlimited, community-run).
// Fallback: the keyed RapidAPI providers via /api/radio/fallback.
// ============================================
const RB_HOSTS = ['https://de1.api.radio-browser.info',
                  'https://nl1.api.radio-browser.info',
                  'https://at1.api.radio-browser.info'];

async function rbFetch(path) {
  for (const h of RB_HOSTS) {
    try {
      // no-store: the browser was caching identical "random" URLs, which is
      // why the dart kept landing on the same station.
      const r = await fetch(h + path, { cache: 'no-store' });
      if (r.ok) return await r.json();
    } catch (e) { /* next mirror */ }
  }
  throw new Error('radio-browser down');
}

let _radio = { map: null, layer: null, countries: null, station: null };

// Points of Interest — destination listening, each with a story and a spot on
// the map. 'url' = direct stream; 'q' = looked up live in Radio-Browser.
const POI_RADIOS = [
  { name: 'The ISS', place: 'low Earth orbit', iss: true,
    url: 'https://ice1.somafm.com/missioncontrol-128-mp3',
    blurb: 'Spins the globe to where the Station is RIGHT NOW + plays live NASA mission audio',
    lat: 0, lon: -140 },
  { name: 'WPKN 89.5', place: 'Bridgeport CT', q: 'WPKN',
    blurb: "Bridgeport's legendary freeform station — broadcasting weird & wonderful since 1963",
    lat: 41.17, lon: -73.19 },
  { name: 'WXXI', place: 'Rochester NY', q: 'WXXI',
    blurb: 'Public radio from upstate New York — news, classical, and lake-effect weather!',
    lat: 43.16, lon: -77.61 },
  { name: 'WWOZ', place: 'New Orleans LA', q: 'WWOZ',
    blurb: 'Jazz from the city that invented it — DJs broadcast from the French Quarter',
    lat: 29.96, lon: -90.06 },
  { name: 'BBC World Service', place: 'London UK', q: 'BBC World Service',
    blurb: 'The most listened-to station on Earth — the voice of shortwave for 90 years',
    lat: 51.52, lon: -0.12 },
  { name: 'J-WAVE', place: 'Tokyo Japan', q: 'J-WAVE',
    blurb: "Tokyo's coolest FM — it's already tomorrow there (check the clock up top)",
    lat: 35.66, lon: 139.73 },
  { name: 'Radio Paradise', place: 'Paradise CA', url: 'https://stream.radioparadise.com/mp3-192',
    blurb: 'Two people in a small California town, hand-picking music for the whole internet',
    fact: 'Paradise, California', lat: 39.76, lon: -121.62 },
];

async function playPoi(i) {
  if (window.SkyDexAudio && SkyDexAudio.playBeep) SkyDexAudio.playBeep();
  const poi = POI_RADIOS[i];
  if (!poi) return;
  const now = document.getElementById('radio-now');
  if (now) now.innerHTML = `Tuning to ${poi.name}…`;

  // Resolve the stream: direct URL or a live Radio-Browser lookup.
  let st = null;
  if (poi.url) {
    st = { name: poi.name, url_resolved: poi.url, country: poi.place, tags: '' };
  }
  if (!st && poi.q) {
    try {
      const l = await rbFetch('/json/stations/search?name=' + encodeURIComponent(poi.q) +
        '&limit=8&hidebroken=true&order=votes&reverse=true');
      st = (l || [])[0];
    } catch (e) {}
  }
  if (!st) { showToast(poi.name + ' seems off the air — try another'); return; }
  st._poiPin = true;                        // our pin is exact — wiki must not re-fly the map
  if (poi.fact) st._factHint = poi.fact;
  if (poi.iss) st._skipFact = true;         // we write our own ISS fact card below

  // The ISS pin goes wherever the Station actually is at this moment.
  let lat = poi.lat, lon = poi.lon, pinLabel = poi.name;
  if (poi.iss) {
    try {
      const d = await (await fetch('/api/atmo/satellite/25544')).json();
      if (d.position && d.position.lat != null) {
        lat = d.position.lat; lon = d.position.lon;
        pinLabel = 'The ISS is HERE right now';
      }
    } catch (e) {}
  }

  _spinGlobeThen(lat, lon, () => {
    _dropPin(lat, lon, pinLabel);
    st.geo_lat = null; st.geo_long = null;   // we handled the map ourselves
    playStation(st, false);
    if (poi.iss) {
      fetch('/api/atmo/passes').then(r => r.json()).then(p => {
        const nx = (p.passes || []).find(x => x.start > Date.now() / 1000);
        const fact = document.getElementById('radio-fact');
        if (fact) fact.innerHTML = `<div class="dex-section-title">About the ISS</div>
          <div class="atmo-tip">You're hearing SomaFM's Mission Control — real NASA audio, but it's
          internet radio <i>about</i> space, not radio <i>from</i> space. The REAL station transmits on
          <b>145.800 MHz FM</b> as it passes over —
          ${nx ? `next pass: <b>${_passWhen(nx)}</b> (peaks ${Math.round(nx.max_elevation || 0)}°).` : 'no more passes today.'}
          Our own antenna can hear it: Airwaves &rarr; Live tuner &rarr; <b>ISS 145.800</b>.
          The pin shows where it is right now, moving at 17,500 mph.</div>`;
      }).catch(() => {});
    }
  });
}

function renderTuner() {
  const el = document.getElementById('tuner-content');
  if (!el) return;
  el.innerHTML = `
    <div id="radiomap"></div>
    <div id="radio-now" class="ds-empty" style="padding:12px;">Throw a dart, tap a Point of Interest, or pick a country below.</div>
    <div id="radio-fact"></div>
    <div class="dex-section-title">Points of Interest</div>
    <div class="poi-row">${POI_RADIOS.map((p, i) =>
      `<button class="poi-card" onclick="playPoi(${i})">
         <b>${p.name}</b><small>${p.place}</small><span>${p.blurb}</span>
       </button>`).join('')}</div>
    <div class="dex-section-title">Pick a Country</div>
    <div id="radio-countries"><div class="ds-empty">Loading countries…</div></div>
    <div id="radio-stations"></div>
    <div id="radio-shelf"></div>`;
  _renderShelves('skydex_radio');

  if (_radio.map) { try { _radio.map.remove(); } catch (e) {} _radio.map = null; }
  if (window.L) {
    _radio.map = L.map('radiomap', { zoomControl: true, worldCopyJump: true })
      .setView([25, 10], 2);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
      { maxZoom: 12, attribution: '&copy; OpenStreetMap' }).addTo(_radio.map);
    L.circleMarker([41.1965, -73.1310], { radius: 5, color: '#FFCB05',
      fillColor: '#FFCB05', fillOpacity: 1 }).addTo(_radio.map).bindTooltip('Home');
    _radio.layer = L.layerGroup().addTo(_radio.map);
    setTimeout(() => _radio.map.invalidateSize(), 80);
  }
  _radioCountries();
}

// Kid favorites lead the grid — big flags, big targets. "All countries" expands
// the full Radio-Browser list underneath.
const KID_COUNTRIES = [
  ['US', 'United States'], ['JP', 'Japan'],       ['MX', 'Mexico'],
  ['FR', 'France'],        ['GB', 'United Kingdom'], ['BR', 'Brazil'],
  ['IT', 'Italy'],         ['AU', 'Australia'],   ['IN', 'India'],
  ['IS', 'Iceland'],       ['KE', 'Kenya'],       ['KR', 'South Korea'],
];
let _allCountriesShown = false;

function _countryCard(code, name, count) {
  return `<button class="country-card" onclick="radioCountry('${code}','${String(name).replace(/'/g, '')}')">
    <img src="https://flagcdn.com/w80/${String(code).toLowerCase()}.png" alt="" loading="lazy">
    <span>${_esc(name)}${count ? `<small>${count} stations</small>` : ''}</span>
  </button>`;
}

function _renderCountryGrid() {
  const el = document.getElementById('radio-countries');
  if (!el) return;
  const picks = KID_COUNTRIES.map(([c, n]) => _countryCard(c, n, null)).join('');
  const moreBtn = `<button class="country-card" style="justify-content:center;" onclick="toggleAllCountries()">
    <span>${_allCountriesShown ? '&#9650; Show fewer' : '&#127758; ALL countries&hellip;'}</span></button>`;
  let all = '';
  if (_allCountriesShown && _radio.countries) {
    all = `<div class="country-grid country-more">` +
      _radio.countries.map(c => _countryCard(c.iso_3166_1, c.name, c.stationcount)).join('') +
      `</div>`;
  }
  el.innerHTML = `<div class="country-grid">${picks}${moreBtn}</div>${all}`;
}

function toggleAllCountries() {
  if (window.SkyDexAudio && SkyDexAudio.playBeep) SkyDexAudio.playBeep();
  _allCountriesShown = !_allCountriesShown;
  _renderCountryGrid();
}

async function _radioCountries() {
  try {
    if (!_radio.countries) {
      _radio.countries = (await rbFetch('/json/countries')).filter(c => c.stationcount > 5);
      _radio.countries.sort((a, b) => a.name.localeCompare(b.name));
    }
  } catch (e) { console.error('countries failed:', e); }
  _renderCountryGrid();
}

// RB tag soup -> one kid-readable genre chip with its own color.
const KID_GENRES = [
  [/kids|children|family/i,                    'For Kids',       '#ff6b9d'],
  [/news|talk|information/i,                   'News & Talk',    '#9db4c8'],
  [/classical|orchestr|opera|symph/i,          'Classical',      '#B8B8D0'],
  [/jazz|blues|swing/i,                        'Jazz & Blues',   '#7859c4'],
  [/rock|metal|punk|indie|alternative/i,       'Rock',           '#ff6b6b'],
  [/dance|electro|edm|house|techno|club/i,     'Dance Party',    '#4ade80'],
  [/hip ?hop|rap|urban|r&b/i,                  'Hip-Hop',        '#ff9f43'],
  [/country|folk|bluegrass/i,                  'Country & Folk', '#d4a373'],
  [/sport|football|soccer/i,                   'Sports',         '#30A7D7'],
  [/relig|christian|gospel|islam|quran/i,      'Faith',          '#98D8D8'],
  [/oldies|retro|60s|70s|80s|90s/i,            'Oldies',         '#e17055'],
  [/pop|top ?40|hits|charts/i,                 'Pop Hits',       '#FFD700'],
  [/culture|tradition|world|ethnic/i,          'Local Culture',  '#48c9b0'],
  [/music/i,                                   'Music',          '#FFCB05'],
];

function kidGenre(tags) {
  for (const [re, label, color] of KID_GENRES) {
    if (re.test(tags || '')) return { label, color };
  }
  return { label: 'Surprise Mix', color: '#9b59d0' };
}

/** Gold map pin that DROPS onto the station — the payoff of every spin. */
const PIN_SVG = '<svg viewBox="0 0 34 44" width="34" height="44" xmlns="http://www.w3.org/2000/svg"><path d="M17 2C9 2 3 8 3 16c0 10 14 26 14 26s14-16 14-26C31 8 25 2 17 2z" fill="#FFCB05" stroke="#0a0f0a" stroke-width="2"/><circle cx="17" cy="15" r="5.5" fill="#0a0f0a"/></svg>';

function _dropPin(lat, lon, label) {
  if (!_radio.map) return;
  _radio.layer.clearLayers();
  const icon = L.divIcon({ className: 'pin-marker', html: PIN_SVG,
    iconSize: [34, 44], iconAnchor: [17, 42] });
  L.marker([lat, lon], { icon }).addTo(_radio.layer).bindTooltip(label || '');
}

/** THE SHOW: whip the globe around a full turn, decelerate onto the target,
 *  zoom in, then let the pin drop. */
let _spinning = false;
function _spinGlobeThen(lat, lon, done) {
  const map = _radio.map;
  if (!map || _spinning) { if (done) done(); return; }
  _spinning = true;
  _radio.layer.clearLayers();
  map.setView([20, map.getCenter().lng], 2, { animate: false });
  const startLng = map.getCenter().lng;
  const total = 360 + ((((lon - startLng) % 360) + 360) % 360);
  const t0 = performance.now(), DUR = 1700;
  const iv = setInterval(() => {
    const p = Math.min(1, (performance.now() - t0) / DUR);
    const ease = 1 - Math.pow(1 - p, 3);          // fast spin, gentle landing
    map.setView([20, startLng + total * ease], 2, { animate: false });
    if (p >= 1) {
      clearInterval(iv);
      map.flyTo([lat, lon], 5, { duration: 1.1 });
      setTimeout(() => { _spinning = false; if (done) done(); }, 1200);
    }
  }, 33);
}

function _throwDartAnim() {
  const o = document.getElementById('dart-overlay');
  if (o) { o.classList.remove('fly'); void o.offsetWidth; o.classList.add('fly'); }
  setTimeout(() => { if (o) o.classList.remove('fly'); }, 900);
}

async function radioDart() {
  if (window.SkyDexAudio && SkyDexAudio.playBeep) SkyDexAudio.playBeep();
  if (SkyDex.currentView !== 'ether-tuner') { showView('ether-tuner'); }
  _throwDartAnim();
  const now = document.getElementById('radio-now');
  if (now) now.innerHTML = '&#127919; Dart in the air…';
  try {
    const st = (await rbFetch('/json/stations/search?order=random&limit=1&hidebroken=true'
      + '&has_geo_info=true&_=' + Date.now()))[0];
    if (st) {
      // Spin the globe, land, drop the pin — THEN the music starts.
      _spinGlobeThen(st.geo_lat, st.geo_long, () => {
        _dropPin(st.geo_lat, st.geo_long, st.name);
        playStation(st, false);            // false: the map move already happened
      });
      return;
    }
  } catch (e) { /* fall back to keyed APIs */ }
  try {
    const list = await (await fetch('/api/radio/fallback')).json();
    if (list.length) return playStation(list[Math.floor(Math.random() * list.length)], false);
  } catch (e) {}
  if (now) now.innerHTML = '<div class="ds-empty">Every radio source is unreachable — check the internet connection.</div>';
}

async function radioCountry(code, name) {
  if (!code) return;
  if (window.SkyDexAudio && SkyDexAudio.playBeep) SkyDexAudio.playBeep();
  const el = document.getElementById('radio-stations');
  if (el) el.innerHTML = '<div class="ds-empty">Tuning across the border…</div>';
  // Fly the map + show the country's story and postcards right away — the
  // wiki lookup handles both (name doubles as the page title).
  if (name) _radioFact({ country: name });
  try {
    const list = await rbFetch('/json/stations/search?countrycode=' + code +
      '&order=votes&reverse=true&limit=12&hidebroken=true');
    window._radioList = list;
    el.innerHTML = `<div class="dex-section-title">Top Stations${name ? ' — ' + _esc(name) : ''}</div>
      <div class="stn-grid">` + list.map((s, i) => {
      const g = kidGenre(s.tags);
      return `<button class="stn-card" onclick="playStation(window._radioList[${i}], true)">
          <div class="stn-name">${_esc(s.name)}</div>
          <div class="stn-row">
            <span class="genre-chip" style="background:${g.color};">${g.label}</span>
            <span class="stn-votes">${s.votes || 0} &#9829;</span>
          </div>
        </button>`;
    }).join('') + '</div>' || '<div class="ds-empty">No stations listed there.</div>';
    el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  } catch (e) {
    if (el) el.innerHTML = '<div class="ds-empty">Station list unavailable.</div>';
  }
}

/** "Postcards from X" — a strip of photos from the country/city's Wikipedia
 *  page (flags, maps, and logos filtered out; just the good stuff). */
async function _postcards(title, holder) {
  try {
    const d = await (await fetch('https://en.wikipedia.org/api/rest_v1/page/media-list/' +
      encodeURIComponent(title))).json();
    const pics = (d.items || [])
      .filter(x => x.type === 'image' && x.srcset && x.srcset[0] &&
        !/flag|coat|arms|locator|map|logo|icon|seal|emblem|banner|\.svg/i.test(x.title || ''))
      .slice(0, 6)
      .map(x => x.srcset[0].src.replace(/^\/\//, 'https://'));
    if (!pics.length || !holder) return;
    holder.insertAdjacentHTML('beforeend',
      `<div class="dex-section-title">Postcards from ${_esc(title)}</div>
       <div class="postcards">${pics.map(u => `<img src="${u}" loading="lazy" alt="">`).join('')}</div>`);
  } catch (e) { /* no postcards, no harm */ }
}

function playStation(st, fly) {
  const audio = document.getElementById('tuner-audio');
  if (!audio || !st) return;
  if (window._tuneAbandon) _tuneAbandon();   // Name That Tune lets go of the audio
  audio.onerror = null;
  _radio.station = st;
  audio.src = st.url_resolved || st.url;
  audio.volume = getVolume();
  audio.play().catch(() => {
    const now = document.getElementById('radio-now');
    if (now) now.innerHTML += ' <span style="color:#ff6b6b;">(stream refused — throw again)</span>';
  });

  const now = document.getElementById('radio-now');
  const g = kidGenre(st.tags);
  if (now) now.innerHTML = `
    <div class="pass-card pass-acela" style="margin:0;">
      <div class="pass-icon" style="color:#FFD700;">${ETHER_SVG.wave}</div>
      <div class="pass-body">
        <div class="pass-name">${st.name || 'Mystery station'}</div>
        <div class="pass-sub"><span class="genre-chip" style="background:${g.color};margin-right:6px;">${g.label}</span>${[st.state, st.country].filter(Boolean).join(', ')}</div>
      </div>
      <div class="pass-stats"><button class="day-summary-btn" style="margin:0;width:auto;display:inline-flex;padding:5px 11px;font-size:11px;" onclick="radioStop()">&#9632; Stop</button></div>
    </div>`;

  // Every play lands on the "recently visited" shelf (slimmed for storage).
  _shelfRemember('skydex_radio', st.stationuuid || st.name || '',
    st.name || 'Mystery station',
    [st.state, st.country].filter(Boolean).join(', '),
    { stationuuid: st.stationuuid, name: st.name, url_resolved: st.url_resolved || st.url,
      country: st.country, state: st.state, tags: st.tags, bitrate: st.bitrate,
      geo_lat: st.geo_lat, geo_long: st.geo_long });

  if (fly && _radio.map && st.geo_lat != null && st.geo_long != null) {
    _radio.layer.clearLayers();
    _radio.map.flyTo([st.geo_lat, st.geo_long], 6, { duration: 1.8 });
    setTimeout(() => _dropPin(st.geo_lat, st.geo_long, st.name), 1700);
  }
  _radioFact(st);
}

function radioStop() {
  const audio = document.getElementById('tuner-audio');
  if (audio) { audio.pause(); audio.removeAttribute('src'); audio.load(); }
  const now = document.getElementById('radio-now');
  if (now) now.innerHTML = 'Throw another dart!';
}

async function _radioFact(st) {
  if (st && st._skipFact) return;
  const el = document.getElementById('radio-fact');
  if (!el) return;
  el.innerHTML = '';
  const hasOwnGeo = st.geo_lat != null && st.geo_long != null;
  const titles = [st._factHint, st.state, st.country].filter(Boolean);
  for (let i = 0; i < titles.length; i++) {
    try {
      const d = await (await fetch('https://en.wikipedia.org/api/rest_v1/page/summary/' +
        encodeURIComponent(titles[i]))).json();
      if (d && d.extract) {
        el.innerHTML = `<div class="dex-section-title">About ${d.title}</div>
          <div class="atmo-tip">${d.extract}</div>`;
        _postcards(d.title, el);   // culture photos under the fact
        // Station didn't publish coordinates? Fly to its city/country instead —
        // Wikipedia hands us the centroid in the same response.
        if (!hasOwnGeo && !st._poiPin && d.coordinates && _radio.map) {
          const zoom = i === 0 ? 7 : 5;   // state/city match = closer zoom
          _radio.map.flyTo([d.coordinates.lat, d.coordinates.lon], zoom, { duration: 1.8 });
          setTimeout(() => _dropPin(d.coordinates.lat, d.coordinates.lon,
            `${st.name ? st.name + ' — near ' : ''}${d.title}${st.name ? ' (approx.)' : ''}`), 1700);
        }
        return;
      }
    } catch (e) { /* try the next title */ }
  }
}

// ============================================
// HAM IT UP — callsign lookups (hamdb.org)
// ============================================
const FAMOUS_HAMS = [
  ['W1AW', "ARRL HQ — ham radio's mothership, 30 minutes away in Newington CT"],
  ['NA1SS', 'The International Space Station itself — astronauts make ham contacts from orbit, and kids can too'],
  ['K1JT', 'Joe Taylor — Nobel Prize physicist who invented the weak-signal digital modes hams use to bounce signals off the Moon'],
  ['W5LFL', 'Owen Garriott — the first ham to transmit from SPACE (aboard the Shuttle, 1983)'],
  ['WB6ACU', 'Joe Walsh of the Eagles — rock legend, lifelong serious ham operator'],
  ['KB2GSD', 'Walter Cronkite — the most trusted voice in news was a licensed ham'],
  ['K7UGA', 'Barry Goldwater — his station ran phone patches home for soldiers in Vietnam'],
];

// Live ham repeaters with verified Broadcastify feeds (plain audio streams —
// no embeds, nothing to block us). Local first: these are YOUR hams.
const HAM_REPEATERS = [
  { id: 21651, name: 'W1EE Stamford DMR — 447.125 MHz',
    blurb: 'Fairfield County hams — this repeater is ~20 miles down I-95 from the kiosk. Some of these voices are your neighbors.' },
  { id: 5041, name: 'KB1AEV Northern CT Linked Repeaters',
    blurb: 'A web of linked repeaters blanketing northern Connecticut — one conversation, heard across half the state.' },
];
let _repIdx = -1;

// Real local scanner feeds via Broadcastify (verified feed IDs). Police in
// Stratford/Bridgeport is ENCRYPTED and not streamable — so this is fire, EMS,
// and the nearest available police dispatch. Each id = broadcastify feed number.
const SCANNER_FEEDS = [
  { id: 5712,  name: 'Stratford Fire & EMS',   blurb: 'Our own town — engines and ambulances dispatched right here in Stratford.' },
  { id: 40926, name: 'Bridgeport Fire',         blurb: "The big city next door — one of Connecticut's busiest fire departments." },
  { id: 37592, name: 'Bridgeport Area EMS',     blurb: 'Ambulances across greater Bridgeport — calls come in around the clock.' },
  { id: 35282, name: 'New Haven Fire',          blurb: 'Fire dispatch for New Haven — busy, clear, and just up I-95.' },
  { id: 18265, name: 'New Haven Area Police',   blurb: 'South-Central CT police dispatch — the closest LISTENABLE police (Stratford & Bridgeport PD scramble their radios).' },
  { id: 6850,  name: 'Rochester NY Police', blurb: 'Police dispatch from Rochester, up in western New York.' },
  { id: 3025,  name: 'Rochester NY Fire', blurb: 'Fire engines rolling in western New York.' },
  { id: 32602, name: 'Indianapolis Police',     blurb: 'The #1 most-listened scanner in America right now — home of the Indy 500, and never quiet.' },
  { id: 21738, name: 'Pittsburgh — All Services', blurb: 'Police, fire AND EMS for the Steel City, all on one busy channel.' },
  { id: 11446, name: 'Cleveland Police',        blurb: 'Big-city police dispatch on Lake Erie — one of the busiest feeds anywhere.' },
];

function renderBands() {   // (the nav slot kept its internal name)
  const el = document.getElementById('bands-content');
  if (!el) return;
  el.innerHTML = `
    <div class="dex-section-title">&#128658; Local Scanner — Fire, EMS &amp; Police</div>
    <div class="tuner-row" style="justify-content:center;margin-bottom:8px;">
      <button class="day-summary-btn" style="margin:0;width:auto;display:inline-flex;padding:11px 22px;font-size:15px;"
        onclick="playScannerRandom()">&#127922; Surprise Me — random scanner</button>
    </div>
    <div class="scanner-grid">${SCANNER_FEEDS.map((f, i) =>
      `<button class="scanner-card" onclick="playScanner(${i})">
         <b>${f.name}</b><span>${f.blurb}</span></button>`).join('')}</div>
    <div class="board-note">Live dispatch from real firehouses, ambulances &amp; police, via Broadcastify.
      Quiet between calls — that's a good thing! (Our own Stratford &amp; Bridgeport police scramble
      their radios, so those aren't here — but plenty of nearby departments are.)</div>

    <div class="dex-section-title" style="margin-top:16px;">&#127911; HAM it Up</div>
    <div class="tuner-row" style="justify-content:center;">
      <button class="day-summary-btn" style="margin:0;width:auto;display:inline-flex;padding:10px 18px;font-size:14px;" onclick="spinDial()">
        &#127922; Spin Local — CT hams
      </button>
      <button class="day-summary-btn" style="margin:0;width:auto;display:inline-flex;padding:10px 18px;font-size:14px;" onclick="spinWorld()">
        &#127758; Spin the World
      </button>
      <button class="day-summary-btn" style="margin:0;width:auto;display:inline-flex;padding:10px 18px;font-size:14px;" onclick="hamRandom()">
        &#127911; Meet a Ham
      </button>
    </div>
    <div id="std-holder"></div>
    <div id="ham-result"></div>
    <div class="board-note" style="margin-top:10px;">Live Connecticut repeaters via Broadcastify.
      From a phone you can also look up any callsign:
      <input id="ham-call" type="text" placeholder="W1AW" maxlength="10"
        style="background:#0d1117;color:var(--text);border:1px solid #444;border-radius:6px;padding:4px 8px;font-size:12px;width:90px;text-transform:uppercase;"
        onkeydown="if(event.key==='Enter')hamLookup(this.value)">
    </div>
    <div id="ham-shelf"></div>`;
  _renderShelves('skydex_ham');
}

/** Surprise Me: jump to a random scanner feed (never repeats the last one). */
let _scanLast = -1;
function playScannerRandom() {
  let i;
  do { i = Math.floor(Math.random() * SCANNER_FEEDS.length); }
  while (SCANNER_FEEDS.length > 1 && i === _scanLast);
  _scanLast = i;
  playScanner(i);
}

/** Play a local public-safety scanner feed (fire/EMS/police dispatch). */
function playScanner(i) {
  _scanLast = i;
  if (window.SkyDexAudio && SkyDexAudio.playBeep) SkyDexAudio.playBeep();
  const f = SCANNER_FEEDS[i];
  const holder = document.getElementById('std-holder');
  const audio = document.getElementById('tuner-audio');
  if (!f || !holder || !audio) return;
  if (window._tuneAbandon) _tuneAbandon();
  audio.onerror = null;
  audio.src = 'https://broadcastify.cdnstream1.com/' + f.id + '?nocache=' + Date.now();
  audio.volume = getVolume();
  audio.play().catch(() => showToast('That feed is offline — try another'));
  holder.innerHTML = `
    <div class="pass-card pass-acela" style="margin-top:8px;">
      <div class="pass-icon" style="color:#ff6b6b;">${ETHER_SVG.wave}</div>
      <div class="pass-body">
        <div class="pass-name">&#128680; ${f.name}</div>
        <div class="pass-sub">${f.blurb}</div>
      </div>
      <div class="pass-stats">
        <button class="day-summary-btn" style="margin:0;width:auto;display:inline-flex;padding:5px 11px;font-size:11px;" onclick="radioStop();document.getElementById('std-holder').innerHTML='';">&#9632; Stop</button>
      </div>
    </div>
    <div class="board-note">Real dispatchers and crews. Silent stretches are normal — when a call
      comes in, you'll hear the address, the units, and the calm voices that run toward trouble.</div>`;
}

/** Tune the next live repeater — real local ham conversations, no typing. */
function spinDial() {
  if (window.SkyDexAudio && SkyDexAudio.playBeep) SkyDexAudio.playBeep();
  const holder = document.getElementById('std-holder');
  const audio = document.getElementById('tuner-audio');
  if (!holder || !audio) return;
  _repIdx = (_repIdx + 1) % HAM_REPEATERS.length;
  const rep = HAM_REPEATERS[_repIdx];
  audio.src = 'https://broadcastify.cdnstream1.com/' + rep.id + '?nocache=' + Date.now();
  audio.volume = getVolume();
  audio.play().catch(() => showToast('Stream unavailable — spin again'));
  holder.innerHTML = `
    <div class="pass-card pass-acela" style="margin-top:8px;">
      <div class="pass-icon" style="color:#FFD700;">${ETHER_SVG.wave}</div>
      <div class="pass-body">
        <div class="pass-name">${rep.name}</div>
        <div class="pass-sub">${rep.blurb}</div>
      </div>
      <div class="pass-stats">
        <button class="day-summary-btn" style="margin:0;width:auto;display:inline-flex;padding:5px 11px;font-size:11px;" onclick="radioStop();document.getElementById('std-holder').innerHTML='';">&#9632; Stop</button>
      </div>
    </div>
    <div class="board-note">Repeaters are silent between conversations — that's normal, not broken.
      Hams key up in bursts: commute time and evenings are liveliest. Spin again to switch repeaters.</div>`;
  _inlineHamFor(rep.name);   // introduce the operator behind the repeater
}

/** Worldwide spin: ham/repeater/shortwave streams from the Radio-Browser
 *  directory. We pool EVERY matching station across all the tags once (cached
 *  an hour), then deal randomly — the old one-per-tag fetch kept serving the
 *  same three stations. */
const WORLD_HAM_TAGS = ['ham radio', 'amateur radio', 'ham', 'repeater',
                        'shortwave', 'amateur'];
let _worldPool = null, _worldPoolAt = 0, _worldLast = '';

async function _buildWorldPool() {
  if (_worldPool && _worldPool.length && Date.now() - _worldPoolAt < 3600e3) return _worldPool;
  const seen = new Set();
  const pool = [];
  for (const tag of WORLD_HAM_TAGS) {
    try {
      const list = await rbFetch('/json/stations/search?tag=' +
        encodeURIComponent(tag) + '&limit=40&hidebroken=true&order=votes&reverse=true');
      (list || []).forEach(s => {
        const id = s.stationuuid || s.url_resolved || s.url;
        if (id && !seen.has(id)) { seen.add(id); pool.push(s); }
      });
    } catch (e) { /* next tag */ }
  }
  _worldPool = pool;
  _worldPoolAt = Date.now();
  return pool;
}

async function spinWorld() {
  if (window.SkyDexAudio && SkyDexAudio.playBeep) SkyDexAudio.playBeep();
  const holder = document.getElementById('std-holder');
  const audio = document.getElementById('tuner-audio');
  if (!holder || !audio) return;
  // When pigs fly, worldwide hams come in.
  const pig = document.getElementById('pig-overlay');
  if (pig) { pig.classList.remove('fly'); void pig.offsetWidth; pig.classList.add('fly'); }
  setTimeout(() => { if (pig) pig.classList.remove('fly'); }, 2600);
  holder.innerHTML = '<div class="ds-empty">&#128055; Spinning the whole planet…</div>';

  let st = null;
  try {
    const pool = await _buildWorldPool();
    if (pool.length) {
      for (let tries = 0; tries < 6; tries++) {
        const pick = pool[Math.floor(Math.random() * pool.length)];
        if ((pick.stationuuid || pick.name) !== _worldLast || pool.length === 1) {
          st = pick;
          _worldLast = pick.stationuuid || pick.name;
          break;
        }
      }
    }
  } catch (e) { /* fall through */ }
  if (!st) {
    holder.innerHTML = '<div class="ds-empty">The world went quiet — spin again.</div>';
    return;
  }
  audio.src = st.url_resolved || st.url;
  audio.volume = getVolume();
  audio.play().catch(() => showToast('Stream refused — spin again'));
  holder.innerHTML = `
    <div class="pass-card pass-acela" style="margin-top:8px;">
      <div class="pass-icon" style="color:#FFD700;">${ETHER_SVG.wave}</div>
      <div class="pass-body">
        <div class="pass-name">${st.name || 'Mystery signal'}</div>
        <div class="pass-sub">${[st.state, st.country].filter(Boolean).join(', ') || 'location unknown'}${st.tags ? ' · ' + st.tags.split(',').slice(0, 3).join(', ') : ''}</div>
      </div>
      <div class="pass-stats">
        <button class="day-summary-btn" style="margin:0;width:auto;display:inline-flex;padding:5px 11px;font-size:11px;" onclick="radioStop();document.getElementById('std-holder').innerHTML='';">&#9632; Stop</button>
      </div>
    </div>
    <div class="board-note">Ham &amp; shortwave streams from around the world — quality varies wildly,
      that's half the charm. Silence between conversations is normal. Spin again for somewhere new.</div>`;
  _inlineHamFor(st.name);   // if the stream is named after a callsign, meet them
}

/** Spot a callsign inside a stream's name (repeaters are usually named after
 *  their owner: "W1EE 447.125 Stamford") and introduce the ham behind it. */
function _hamCallFrom(text) {
  const m = (text || '').toUpperCase().match(/\b([A-Z]{1,2}\d[A-Z]{1,3})\b/);
  if (!m) return null;
  const call = m[1];
  if (['MHZ', 'KHZ'].includes(call) || call.length < 4) return null;
  return call;
}

async function _inlineHamFor(text) {
  const call = _hamCallFrom(text);
  const holder = document.getElementById('std-holder');
  if (!call || !holder) return;
  try {
    const d = await (await fetch('/api/ham/' + encodeURIComponent(call))).json();
    if (d.not_found || d.error || !d.name) return;
    holder.insertAdjacentHTML('beforeend', `
      <div class="fc-record" style="margin-top:6px;">
        <div class="fc-record-title">The ham behind this signal — ${d.call}</div>
        <div class="atmo-line"><span><b style="color:var(--text);">${d.name}</b></span>
          <b style="font-weight:normal;color:var(--text-dim);">${[d.city, d.state].filter(Boolean).join(', ')}</b></div>
        ${d.miles_away != null ? `<div class="atmo-line"><span>Distance from home</span><b>${d.miles_away.toLocaleString()} mi</b></div>` : ''}
      </div>`);
    _shelfRemember('skydex_ham', d.call, d.call,
      [d.name, d.city, d.state].filter(Boolean).join(' · '), { call: d.call });
  } catch (e) { /* no card, no harm */ }
}

/** No-typing ham lookup: introduces a random legend of the hobby. */
function hamRandom() {
  const pick = FAMOUS_HAMS[Math.floor(Math.random() * FAMOUS_HAMS.length)];
  hamLookup(pick[0]);
}

async function hamLookup(call) {
  call = (call || '').trim().toUpperCase();
  if (!call) return;
  const el = document.getElementById('ham-result');
  if (el) el.innerHTML = '<div class="ds-empty">Checking the logbooks…</div>';
  try {
    const d = await (await fetch('/api/ham/' + encodeURIComponent(call))).json();
    const famous = FAMOUS_HAMS.find(([c]) => c === call);
    if (d.not_found || d.error) {
      // Famous calls still get their story even if the FCC file is silent.
      el.innerHTML = famous
        ? `<div class="fc-record" style="margin-top:10px;border-color:#FFD700;">
             <div class="fc-record-title">${call}</div>
             <div class="atmo-tip" style="margin-top:6px;">${famous[1]}</div></div>`
        : '<div class="ds-empty">' +
          (d.error ? 'Lookup failed — try again.' : call + " isn't in the directory.") + '</div>';
      if (famous) _shelfRemember('skydex_ham', call, call, 'Legend of the hobby', { call: call });
      return;
    }
    el.innerHTML = `
      <div class="fc-record" style="margin-top:10px;">
        <div class="fc-record-title">${d.call}</div>
        <div class="fc-record-vals"><span style="font-size:18px;font-weight:bold;color:var(--text);">${d.name || 'Name withheld'}</span></div>
        <div class="atmo-line"><span>Location</span><b>${[d.city, d.state, d.country].filter(Boolean).join(', ') || '—'}</b></div>
        ${d.miles_away != null ? `<div class="atmo-line"><span>Distance from home</span><b>${d.miles_away.toLocaleString()} miles</b></div>` : ''}
        ${d.grid ? `<div class="atmo-line"><span>Grid square</span><b>${d.grid}</b></div>` : ''}
        ${d.class ? `<div class="atmo-line"><span>License class</span><b>${d.class}</b></div>` : ''}
        ${famous ? `<div class="atmo-tip" style="margin-top:8px;">${famous[1]}</div>` : ''}
        <div id="ham-iss-pass"></div>
        <div class="tuner-row" style="margin-top:10px;">
          <span class="atmo-sub" style="align-self:center;">You can't stream a callsign — but you can hear hams like ${d.call.length > 2 ? 'them' : 'this'} right now:</span>
          <button class="day-summary-btn" style="margin:0;width:auto;display:inline-flex;" onclick="spinDial()">&#127922; Local</button>
          <button class="day-summary-btn" style="margin:0;width:auto;display:inline-flex;" onclick="spinWorld()">&#127758; Worldwide</button>
        </div>
      </div>`;
    _shelfRemember('skydex_ham', d.call, d.call,
      [d.name, d.city, d.state].filter(Boolean).join(' · '), { call: d.call });
    // NA1SS is the one callsign you CAN plan to hear: 145.800 FM when overhead.
    if (call === 'NA1SS') {
      fetch('/api/atmo/passes').then(r => r.json()).then(p => {
        const nx = (p.passes || []).find(x => x.start > Date.now() / 1000);
        const box = document.getElementById('ham-iss-pass');
        if (box && nx) box.innerHTML = `<div class="atmo-tip" style="margin-top:8px;">
          &#128752; You CAN hear this one — from your yard, with a cheap handheld radio on
          <b>145.800 MHz FM</b>, during a pass. Next pass: <b>${_passWhen(nx)}</b>
          (peaks ${Math.round(nx.max_elevation || 0)}°). Astronauts sometimes answer.</div>`;
      }).catch(() => {});
    }
  } catch (e) {
    if (el) el.innerHTML = '<div class="ds-empty">Lookup failed — network hiccup.</div>';
  }
}

// ============================================
// SHELVES — rolling last-10 "recently visited" + up to 5 starred favorites,
// for hams (skydex_ham) and radio stations (skydex_radio). Lives in the
// kiosk browser's localStorage; tap a row to revisit, tap the star to keep.
// ============================================
function _esc(s) {
  return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}
function _lsGet(k) { try { return JSON.parse(localStorage.getItem(k)) || []; } catch (e) { return []; } }
function _lsSet(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} }

function _shelfRemember(base, id, title, sub, data) {
  if (!id) return;
  const rec = _lsGet(base + '_recent').filter(x => x._id !== id);
  rec.unshift({ _id: id, title: title, sub: sub || '', data: data });
  _lsSet(base + '_recent', rec.slice(0, 10));
  _renderShelves(base);
}

function _shelfIsFav(base, id) { return _lsGet(base + '_favs').some(x => x._id === id); }

function shelfStar(base, list, i) {
  if (window.SkyDexAudio && SkyDexAudio.playBeep) SkyDexAudio.playBeep();
  const x = _lsGet(base + '_' + list)[i];
  if (!x) return;
  let favs = _lsGet(base + '_favs');
  if (favs.some(f => f._id === x._id)) {
    favs = favs.filter(f => f._id !== x._id);
  } else if (favs.length >= 5) {
    return showToast('Favorites are full (5) — un-star one first');
  } else {
    favs.push(x);
  }
  _lsSet(base + '_favs', favs);
  _renderShelves(base);
}

function shelfTap(base, list, i) {
  if (window.SkyDexAudio && SkyDexAudio.playBeep) SkyDexAudio.playBeep();
  const x = _lsGet(base + '_' + list)[i];
  if (!x || !x.data) return;
  if (base === 'skydex_ham') hamLookup(x.data.call);
  else playStation(x.data, true);
}

function _shelfHtml(base) {
  const favs = _lsGet(base + '_favs'), rec = _lsGet(base + '_recent');
  if (!favs.length && !rec.length) {
    // Empty shelves still show themselves — otherwise nobody knows they exist.
    const hint = base === 'skydex_ham'
      ? 'Every ham you meet lands here automatically — tap &#127911; Meet a Ham to start collecting. Star &#9734; up to 5 favorites.'
      : 'Every station you play lands here — throw a dart! Star &#9734; up to 5 favorites.';
    return `<div class="shelf">
      <div class="dex-section-title">&#128336; Recently visited</div>
      <div class="board-note">${hint}</div></div>`;
  }
  const row = (x, i, list) => `
    <div class="shelf-row">
      <div class="shelf-main" onclick="shelfTap('${base}','${list}',${i})">
        <b>${_esc(x.title)}</b>${x.sub ? `<span>${_esc(x.sub)}</span>` : ''}
      </div>
      <button class="shelf-star ${_shelfIsFav(base, x._id) ? 'on' : ''}"
        onclick="shelfStar('${base}','${list}',${i})">${_shelfIsFav(base, x._id) ? '&#9733;' : '&#9734;'}</button>
    </div>`;
  let h = '<div class="shelf">';
  if (favs.length) h += `<div class="dex-section-title">&#11088; Favorites (${favs.length}/5)</div>`
    + favs.map((x, i) => row(x, i, 'favs')).join('');
  if (rec.length) h += `<div class="dex-section-title">&#128336; Recently visited</div>`
    + rec.map((x, i) => row(x, i, 'recent')).join('');
  return h + '</div>';
}

function _renderShelves(base) {
  const el = document.getElementById(base === 'skydex_ham' ? 'ham-shelf' : 'radio-shelf');
  if (el) el.innerHTML = _shelfHtml(base);
}

// ============================================
// LISTEN TO SPACE (buttons on the AtmoDex Sky Guide) — same audio paths as
// EtherDex: SomaFM via the browser, the ISS downlink via the antenna.
// ============================================
function atmoMissionControl() {
  if (window.SkyDexAudio && SkyDexAudio.playBeep) SkyDexAudio.playBeep();
  const audio = document.getElementById('tuner-audio');
  if (!audio) return;
  audio.src = 'https://ice1.somafm.com/missioncontrol-128-mp3';
  audio.volume = getVolume();
  audio.play().catch(() => showToast('Stream unavailable — try again'));
  const n = document.getElementById('atmo-listen-note');
  if (n) n.innerHTML = `Playing SomaFM Mission Control — real NASA audio over ambient music
    (internet radio <i>about</i> space). Stop with the &#9632; button up top.`;
}

async function atmoIssAntenna() {
  if (window.SkyDexAudio && SkyDexAudio.playBeep) SkyDexAudio.playBeep();
  try {
    const d = await (await fetch('/api/ether/listen', { method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ preset: 'iss' }) })).json();
    const ded = d.listening && d.listening.dedicated;
    window._listenUntil = Date.now() + 15 * 60 * 1000;
    const n = document.getElementById('atmo-listen-note');
    if (n) n.innerHTML = `Antenna tuned to <b>145.800 MHz</b> — radio <i>from</i> space, but only
      when the ISS is overhead AND transmitting (see passes below). Expect static otherwise.
      Auto-stops in 15 min. ${ded ? 'Sensor hunting keeps running on its own dongle.'
                                  : 'Sensor hunting pauses meanwhile.'} &#9632; up top stops it sooner.`;
    showToast('Antenna tuned to the ISS downlink');
  } catch (e) { showToast('Tuner unreachable'); }
}

// ============================================
// AIRWAVES BAND CHIPS — tap to retune the local receiver
// ============================================
const TUNABLE_BANDS = [
  ['315M',    '315 MHz',  'Key fobs & US tire sensors — click your fob for an instant catch.'],
  ['345M',    '345 MHz',  "Home security door/window sensors. That's the neighbors' gear — tune respectfully."],
  ['433.92M', '433 MHz',  'The town square: weather stations, doorbells, gate remotes.'],
  ['915M',    '915 MHz',  'Smart utility meters — the whole street reports in, all day. The richest band.'],
];

function bandChips(freqs) {
  const active = (freqs || []).map(String);
  return '<div class="tuner-row" style="justify-content:center;margin:8px 0 4px;">' +
    TUNABLE_BANDS.map(([f, label, desc]) => {
      const on = active.includes(f);
      return `<button class="band-chip ${on ? 'on' : ''}" onclick="toggleBand('${f}')"
          oncontextmenu="event.preventDefault();showInfoModal('${label}','<p>${desc.replace(/'/g, '&#39;')}</p>')">
          ${label}</button>`;
    }).join('') +
    `<button class="band-chip" style="opacity:.7;" onclick="showInfoModal('The Bands',
      '<p>${TUNABLE_BANDS.map(([f, l, d]) => '<b>' + l + '</b>: ' + d.replace(/'/g, '&#39;')).join('</p><p>')}</p>')">?</button>` +
    '</div>';
}

async function toggleBand(f) {
  const st = window._etherStatus || {};
  let freqs = (st.freqs || ['433.92M']).map(String);
  freqs = freqs.includes(f) ? freqs.filter(x => x !== f) : freqs.concat([f]);
  if (!freqs.length) freqs = ['433.92M'];
  try {
    await fetch('/api/ether/retune', { method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ freqs: freqs.join(',') }) });
    showToast('Receiver retuning: ' + freqs.join(' + '));
    setTimeout(fetchEther._quiet, 1500);
  } catch (e) { showToast('Retune failed'); }
}

// ============================================
// LIVE TUNER — same dongle, demodulated to real audio out the Pi's speakers.
// Sensor logging pauses while listening; auto-resumes after 15 min or Stop.
// ============================================
const LISTEN_PRESETS = [
  ['wx',     'WX Radio',   'NOAA Weather Radio 162.55 — the robot voice reading the forecast, straight off the air.'],
  ['marine', 'Marine 16',  'Channel 16, 156.8 MHz — boats on the Sound hailing each other. Quiet until someone keys up!'],
  ['ham2m',  'Ham 146.52', 'The 2-meter calling channel — hams saying hello antenna-to-antenna, no internet.'],
  ['tower',  'KBDR Tower', "Bridgeport tower on YOUR antenna, 120.9 AM — compare it with the streaming Tower button!"],
  ['iss',    'ISS 145.800', 'The REAL Space Station downlink. Silent unless the ISS is overhead (check AtmoDex for the next pass) AND transmitting — crew contacts and SSTV picture events. When it works, you heard space with your own antenna.'],
  ['pilots', 'Pilot Chat',  'The unofficial air-to-air channel (123.45) — jets six miles overhead gossiping and swapping turbulence reports. Busiest mid-day when the sky is full.'],
  ['bridge', 'Marine 13',   'Bridge-to-bridge: tug and barge captains talking each other through the channel — the chattiest working-waterfront frequency.'],
  ['rail',   'Railroad',    'The railroad band (160.92) — crews, dispatchers, and robotic trackside defect detectors that count every axle out loud.'],
  ['guard',  'Guard 121.5', 'The aviation emergency channel. Almost always silent — except when bored pilots meow on it. Really. Aviation has a cat problem.'],
  ['aprs',   'APRS 144.39', "Ham GPS beacons — sounds like robot ducks arguing. Every burst is a real transmitter announcing itself. Weirdly hypnotic."],
];

function listenChips(st) {
  // Antenna mode is opt-in (gear drawer / admin): off-air audio is mostly
  // theater next to the internet streams, so it hides until curiosity strikes.
  if (typeof getSetting === 'function' && !getSetting('antenna_tuner', false)
      && !(st && st.listening)) return '';
  const on = st && st.listening;
  return '<div class="tuner-row" style="justify-content:center;margin:0 0 6px;">' +
    `<span class="atmo-sub" style="align-self:center;">&#128225; Live tuner:</span>` +
    LISTEN_PRESETS.map(([id, label, desc]) => {
      const active = on && on.id === id;
      return `<button class="band-chip ${active ? 'on' : ''}" onclick="toggleListen('${id}')"
          oncontextmenu="event.preventDefault();showInfoModal('${label}','<p>${desc.replace(/'/g, '&#39;')}</p>')">
          ${active ? '&#128264; ' : ''}${label}</button>`;
    }).join('') +
    (on ? `<span class="atmo-sub" style="align-self:center;color:#ff6b6b;">ON AIR${on.dedicated ? '' : ' — sensor hop paused'} (${Math.ceil((on.seconds_left || 0) / 60)} min left)</span>` : '') +
    '</div>';
}

async function toggleListen(id) {
  if (window.SkyDexAudio && SkyDexAudio.playBeep) SkyDexAudio.playBeep();
  const st = window._etherStatus || {};
  const active = st.listening && st.listening.id === id;
  try {
    if (active) {
      await fetch('/api/ether/listen/stop', { method: 'POST' });
      window._listenUntil = 0;
      showToast('Live tuner off — back to sensor hunting');
    } else {
      const p = LISTEN_PRESETS.find(x => x[0] === id);
      await fetch('/api/ether/listen', { method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ preset: id }) });
      window._listenUntil = Date.now() + 15 * 60 * 1000;   // corrected by next status poll
      showToast('Tuning the antenna to ' + (p ? p[1] : id) + '…');
    }
    setTimeout(fetchEther._quiet, 1500);
  } catch (e) { showToast('Tuner unreachable'); }
}
