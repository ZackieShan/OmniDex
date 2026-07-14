/* SkyDex controls.js — runtime settings, SSE live push, auto night-dim,
 * ISS pass alerts, LiveATC audio, and the quick-settings drawer.
 * Loads after pokedex.js (plain script, shares its globals). */

// ============================================
// SETTINGS (fetched once, refreshed by drawer)
// ============================================
window.SkySettings = {};

function getSetting(key, fallback) {
  const v = window.SkySettings[key];
  return v === undefined ? fallback : v;
}

async function loadSkySettings() {
  try {
    window.SkySettings = await (await fetch('/api/settings')).json();
  } catch (e) { console.error('settings load failed:', e); }
  applySettingsToUi();
}

function applySettingsToUi() {
  const quiz = document.getElementById('quiz-btn');
  if (quiz) quiz.style.display = getSetting('quiz_enabled', true) ? '' : 'none';
  const atc = document.getElementById('atc-btn');
  if (atc) atc.style.display = getSetting('liveatc_enabled', true) ? '' : 'none';
  document.documentElement.style.setProperty(
    '--night-b', String(getSetting('night_dim_brightness', 0.55)));
  if (typeof renderVoiceMute === 'function') renderVoiceMute();
}

async function saveSetting(key, value) {
  window.SkySettings[key] = value;
  applySettingsToUi();
  try {
    await fetch('/api/settings', { method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ [key]: value }) });
  } catch (e) { console.error('setting save failed:', e); }
}

// ============================================
// SSE LIVE PUSH (falls back to the 1s polling)
// ============================================
let _sse = null;
window.SSE_ACTIVE = false;
window.REPLAY_ACTIVE = false;

function startSse() {
  if (!getSetting('sse_enabled', true) || !window.EventSource || _sse) return;
  try { _sse = new EventSource('/api/stream'); } catch (e) { return; }

  _sse.onopen = () => { window.SSE_ACTIVE = true; SkyDex.isPolling = false; };
  _sse.onmessage = (ev) => {
    if (!ev.data) return;
    try { sseApply(JSON.parse(ev.data)); } catch (e) { /* keepalive line */ }
  };
  _sse.onerror = () => {
    // Drop back to polling; retry SSE in a minute.
    window.SSE_ACTIVE = false;
    SkyDex.isPolling = true;
    if (_sse) { _sse.close(); _sse = null; }
    setTimeout(startSse, 60000);
  };
}

let _lastSseRender = 0;

function sseApply(payload) {
  if (SkyDex.currentView !== 'contacts' || window.REPLAY_ACTIVE) return;
  // Full list+map re-render throttled to ~2s at 1080p — the dead-reckoning
  // glide keeps motion smooth between renders, so 1/s DOM churn buys nothing.
  const now = performance.now();
  if (now - _lastSseRender < 1900) return;
  _lastSseRender = now;
  if (SkyDex.mode === 'air') {
    const contacts = (payload.contacts || []).slice().sort(byDistance);
    SkyDex.contacts = contacts;
    checkForNewCatches(contacts);
    renderContacts(contacts);
    renderRadar(contacts);
    if (_mapMode === 'map') renderMap(contacts);
    const tc = document.getElementById('tracker-count');
    if (tc) tc.textContent = `${contacts.length} aircraft nearby`;
  } else if (SkyDex.mode === 'sea') {
    const vessels = (payload.vessels || []).slice().sort(byDistance);
    SkyDex.contacts = vessels;
    renderVessels(vessels);
    renderRadar(vessels, vesselColor);
    if (_mapMode === 'map') renderMap(vessels, vesselColor);
    const tc = document.getElementById('tracker-count');
    if (tc) tc.textContent = `${vessels.length} vessels nearby`;
  }
}

// ============================================
// AUTO NIGHT DIM (civil dusk -> civil dawn)
// ============================================
let _sunTimes = null;

async function refreshSunTimes() {
  try { _sunTimes = await (await fetch('/api/sun')).json(); }
  catch (e) { /* keep old */ }
}

function nightDimTick() {
  if (!getSetting('night_dim_enabled', true) || !_sunTimes) {
    document.body.classList.remove('night-dim');
    return;
  }
  const now = Date.now() / 1000;
  const dark = (_sunTimes.civil_dusk && now >= _sunTimes.civil_dusk) ||
               (_sunTimes.civil_dawn && now <= _sunTimes.civil_dawn);
  document.body.classList.toggle('night-dim', !!dark);
}

// ============================================
// ISS PASS ALERTS (toast ~10 min before a good pass)
// ============================================
let _upcomingPasses = [];

async function refreshIssPasses() {
  if (!getSetting('iss_toast_enabled', true)) return;
  try {
    const d = await (await fetch('/api/atmo/passes')).json();
    _upcomingPasses = (d && d.passes) || [];
  } catch (e) { /* try again next cycle */ }
}

function issToastTick() {
  if (!getSetting('iss_toast_enabled', true)) return;
  const minEl = getSetting('iss_toast_min_elevation', 30);
  const now = Date.now() / 1000;
  _upcomingPasses.forEach(p => {
    if (!p.start || (p.max_elevation || 0) < minEl) return;
    const lead = p.start - now;
    if (lead <= 0 || lead > 600) return;
    const key = 'iss-toast-' + Math.round(p.start / 60);
    if (localStorage.getItem(key)) return;
    localStorage.setItem(key, '1');
    const mins = Math.max(1, Math.round(lead / 60));
    showToast(`ISS overhead in ~${mins} min — look up! (peaks ${Math.round(p.max_elevation)}°)`, 'shiny');
    if (window.SkyDexAudio && SkyDexAudio.playBeep) SkyDexAudio.playBeep();
  });
}

// ============================================
// LIVEATC — tap-to-listen tower audio
// ============================================
function toggleAtc() {
  const audio = document.getElementById('atc-audio');
  const label = document.getElementById('atc-label');
  const btn = document.getElementById('atc-btn');
  if (!audio) return;
  if (!audio.paused) {
    audio.pause();
    audio.removeAttribute('src');
    audio.load();
    if (label) label.textContent = 'Tower';
    if (btn) btn.classList.remove('atc-live');
    return;
  }
  const url = getSetting('liveatc_url', '');
  if (!url) { showToast('Set the LiveATC URL on the /admin page'); return; }
  audio.src = url + (url.includes('?') ? '&' : '?') + 'nocache=' + Date.now();
  audio.volume = getVolume();
  if (label) label.textContent = '· · · ';
  audio.play().then(() => {
    if (label) label.textContent = 'LIVE';
    if (btn) btn.classList.add('atc-live');
  }).catch(() => {
    if (label) label.textContent = 'Tower';
    showToast('Tower stream unavailable — check the LiveATC URL in /admin');
  });
  audio.onerror = () => {
    if (label) label.textContent = 'Tower';
    if (btn) btn.classList.remove('atc-live');
  };
}

// ============================================
// QUICK-SETTINGS DRAWER (gear button)
// ============================================
// [key, label, default] — the default MUST match what the feature's own code
// assumes, or the pill lies about hidden features.
const DRAWER_TOGGLES = [
  ['night_dim_enabled', 'Auto night dim', true],
  ['antenna_tuner', 'Antenna mode (off-air tuner)', false],
  ['attract_enabled', 'Attract mode', true],
  ['iss_toast_enabled', 'ISS pass alerts', true],
  ['liveatc_enabled', 'Tower audio button', true],
  ['quiz_enabled', 'Quiz button', true],
  ['sse_enabled', 'Live push (SSE)', true],
];

function toggleDrawer() {
  const d = document.getElementById('settings-drawer');
  if (!d) return;
  if (d.classList.contains('hidden')) { renderDrawer(); d.classList.remove('hidden'); }
  else d.classList.add('hidden');
}

function renderDrawer() {
  const body = document.getElementById('drawer-body');
  if (!body) return;
  body.innerHTML = DRAWER_TOGGLES.map(([key, label, def]) => {
    const on = !!getSetting(key, def !== undefined ? def : true);
    return `<div class="drawer-row" onclick="drawerFlip('${key}')">
      <span>${label}</span>
      <span class="drawer-pill ${on ? 'on' : ''}">${on ? 'ON' : 'OFF'}</span>
    </div>`;
  }).join('') + `
    <div class="drawer-row" onclick="openAdminPin()">
      <span>&#128295; Admin Panel</span>
      <span class="drawer-pill">PIN</span>
    </div>`;
}

// ============================================
// ADMIN PIN PAD — kid-lock, not security (the LAN can reach /admin directly).
// Correct PIN sends the kiosk browser to the full admin page.
// ============================================
const ADMIN_PIN = '2874';
let _pinBuf = '';

function openAdminPin() {
  _pinBuf = '';
  const keys = [1, 2, 3, 4, 5, 6, 7, 8, 9, 0];
  showInfoModal('Grown-ups Only',
    `<div id="pin-dots" style="text-align:center;font-size:26px;letter-spacing:10px;min-height:34px;">&nbsp;</div>
     <div class="pin-grid">` +
    keys.map(n => `<button class="pin-btn" onclick="pinPress(${n})">${n}</button>`).join('') +
    `<button class="pin-btn" style="grid-column:span 2;font-size:14px;" onclick="_pinBuf='';pinShow()">clear</button>
     </div>`);
  const d = document.getElementById('pin-dots');
  if (d) d.textContent = '';
}

function pinShow() {
  const d = document.getElementById('pin-dots');
  if (d) d.textContent = '●'.repeat(_pinBuf.length);
}

function pinPress(n) {
  if (window.SkyDexAudio && SkyDexAudio.playBeep) SkyDexAudio.playBeep();
  _pinBuf += String(n);
  pinShow();
  if (_pinBuf.length < ADMIN_PIN.length) return;
  if (_pinBuf === ADMIN_PIN) {
    location.href = '/admin';
  } else {
    _pinBuf = '';
    const d = document.getElementById('pin-dots');
    if (d) { d.textContent = 'nope!'; setTimeout(pinShow, 700); }
  }
}

function drawerFlip(key) {
  const row = DRAWER_TOGGLES.find(t => t[0] === key);
  const def = row && row[2] !== undefined ? row[2] : true;
  saveSetting(key, !getSetting(key, def)).then(() => {
    renderDrawer();
    if (key === 'night_dim_enabled') nightDimTick();
    if (key === 'sse_enabled') {
      if (getSetting('sse_enabled', true)) startSse();
      else if (_sse) { _sse.close(); _sse = null; window.SSE_ACTIVE = false; SkyDex.isPolling = true; }
    }
  });
}

// ============================================
// INIT
// ============================================
(function initControls() {
  loadSkySettings().then(() => {
    startSse();
    refreshSunTimes().then(nightDimTick);
    refreshIssPasses();
  });
  setInterval(nightDimTick, 60000);
  setInterval(refreshSunTimes, 6 * 3600 * 1000);
  setInterval(issToastTick, 60000);
  setInterval(refreshIssPasses, 30 * 60 * 1000);

  // Prefetch the Dex data once the live view has settled, so the first tap on
  // Dex renders instantly from cache instead of a cold fetch.
  setTimeout(() => {
    fetch('/api/dex?limit=1000&sort=detection_count')
      .then(r => (r.ok ? r.json() : null)).then(d => { if (d) SkyDex.dexData = d; }).catch(() => {});
    fetch('/api/vessel-dex?limit=1000')
      .then(r => (r.ok ? r.json() : null)).then(d => { if (d) SkyDex.fleetData = d; }).catch(() => {});
  }, 8000);
})();

// ============================================
// WHO SPOTTED IT? — family credit on rare catches
// ============================================
const SPOTTERS = ['Dad', 'Mom', 'Kid 1', 'Kid 2', 'Kid 3', 'Guest'];
let _spotTimeout = null;

function askSpotter(ident, kind) {
  const m = document.getElementById('info-modal');
  if (!m || !m.classList.contains('hidden')) return;   // don't stomp an open modal
  showInfoModal(
    `&#11088; Who spotted <span style="color:var(--accent-yellow);">${ident}</span>?`,
    `<div class="spotter-grid">` +
    SPOTTERS.map(n =>
      `<button class="spotter-btn" onclick="creditSpotter('${n}','${ident.replace(/'/g, '')}','${kind}')">${n}</button>`
    ).join('') + `</div>
    <p style="color:var(--text-dim);font-size:11px;">Credit goes on the Hall of Fame leaderboard. Closes itself in 45s.</p>`);
  if (_spotTimeout) clearTimeout(_spotTimeout);
  _spotTimeout = setTimeout(closeInfoModal, 45000);
}

function creditSpotter(name, ident, kind) {
  fetch('/api/spotter', { method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, ident, kind }) }).catch(() => {});
  closeInfoModal();
  showToast(`${name} gets the credit for ${ident}! &#127942;`, 'new-catch');
  if (window.SkyDexAudio && SkyDexAudio.playCatchJingle) SkyDexAudio.playCatchJingle();
}

// ============================================
// SEVERE WEATHER TAKEOVER — a warning pops over ANY screen, with details and
// a siren, and stays until somebody acknowledges it. Re-sirens every 5 min
// while ignored. Acknowledged alerts don't re-pop; NEW alerts do.
// ============================================
const WXA_ACK_KEY = 'skydex_wx_acked';
let _wxaTimer = null;

function _alertSiren() {
  try {
    const ctx = window._sirenCtx = window._sirenCtx ||
      new (window.AudioContext || window.webkitAudioContext)();
    const t0 = ctx.currentTime;
    for (let i = 0; i < 3; i++) {
      const o = ctx.createOscillator(), g = ctx.createGain();
      o.type = 'square';
      o.frequency.setValueAtTime(880, t0 + i * 0.5);
      o.frequency.setValueAtTime(660, t0 + i * 0.5 + 0.25);
      g.gain.setValueAtTime(0.12, t0 + i * 0.5);
      g.gain.exponentialRampToValueAtTime(0.001, t0 + i * 0.5 + 0.45);
      o.connect(g); g.connect(ctx.destination);
      o.start(t0 + i * 0.5); o.stop(t0 + i * 0.5 + 0.5);
    }
  } catch (e) { /* no audio context — the visual still takes over */ }
}

async function weatherAlertWatch() {
  let alerts;
  try { alerts = await (await fetch('/api/alerts')).json(); } catch (e) { return; }
  if (!Array.isArray(alerts) || !alerts.length) return;
  const serious = alerts.filter(a => /warning/i.test(a.event || '') ||
    ['Severe', 'Extreme'].includes(a.severity));
  if (!serious.length) return;
  let acked;
  try { acked = JSON.parse(localStorage.getItem(WXA_ACK_KEY)) || []; } catch (e) { acked = []; }
  const key = (a) => (a.event || '') + '|' + (a.onset || '');
  if (!serious.some(a => !acked.includes(key(a)))) return;
  if (document.getElementById('wx-takeover')) return;   // already up

  const others = alerts.filter(a => !serious.includes(a));
  const fmtT = (s) => {
    try {
      return new Date(s).toLocaleString('en-US',
        { weekday: 'short', hour: 'numeric', minute: '2-digit', timeZone: EST_TZ });
    } catch (e) { return ''; }
  };
  const row = (a, big) => `
    <div class="wxa-alert ${big ? 'big' : ''}">
      <div class="wxa-event">${a.severity === 'Extreme' ? '&#128308;' : '&#9888;'} ${_esc(a.event)}
        ${a.severity ? `<span class="wxa-sev">${_esc(a.severity)}</span>` : ''}</div>
      ${a.headline ? `<div class="wxa-head">${_esc(a.headline)}</div>` : ''}
      ${(a.onset || a.ends) ? `<div class="atmo-sub">${a.onset ? 'From ' + fmtT(a.onset) : ''}${a.ends ? ' until ' + fmtT(a.ends) : ''}</div>` : ''}
    </div>`;

  const ov = document.createElement('div');
  ov.id = 'wx-takeover';
  ov.innerHTML = `<div class="wxa-card">
      <div class="wxa-title">&#9888; WEATHER WARNING</div>
      ${serious.map(a => row(a, true)).join('')}
      ${others.length ? `<div class="dex-section-title" style="margin-top:10px;">Also active</div>`
        + others.map(a => row(a, false)).join('') : ''}
      <button class="wxa-ack" onclick="wxAcknowledge()">GOT IT — we're paying attention</button>
    </div>`;
  document.body.appendChild(ov);
  window._wxaKeys = serious.map(key);
  _alertSiren();
  clearInterval(_wxaTimer);
  _wxaTimer = setInterval(() => {
    if (document.getElementById('wx-takeover')) _alertSiren();
    else clearInterval(_wxaTimer);
  }, 300000);
}

function wxAcknowledge() {
  let acked;
  try { acked = JSON.parse(localStorage.getItem(WXA_ACK_KEY)) || []; } catch (e) { acked = []; }
  acked = acked.concat(window._wxaKeys || []).slice(-40);
  localStorage.setItem(WXA_ACK_KEY, JSON.stringify(acked));
  const ov = document.getElementById('wx-takeover');
  if (ov) ov.remove();
  clearInterval(_wxaTimer);
  if (window.SkyDexAudio && SkyDexAudio.playBeep) SkyDexAudio.playBeep();
}

setTimeout(weatherAlertWatch, 15000);
setInterval(weatherAlertWatch, 300000);

// ============================================
// GLOBAL AUDIO STOP — one button in the status bar, kills every stream
// ============================================
const AUDIO_IDS = ['tuner-audio', 'atc-audio', 'scanner-audio'];

// Volume — one slider for all browser audio (radio / tower / scanner).
// Persisted, so the bedtime volume survives a reboot. The Pi-side voice and
// the antenna tuner play through ALSA and aren't affected by this.
const VOL_KEY = 'skydex_volume';

function getVolume() {
  const v = parseFloat(localStorage.getItem(VOL_KEY));
  return isNaN(v) ? 0.85 : Math.max(0, Math.min(1, v));
}

function setVolume(v) {
  v = Math.max(0, Math.min(1, v));
  try { localStorage.setItem(VOL_KEY, String(v)); } catch (e) {}
  AUDIO_IDS.forEach(id => {
    const a = document.getElementById(id);
    if (a) a.volume = v;
  });
}

(function initVolume() {
  const s = document.getElementById('vol-slider');
  if (s) s.value = Math.round(getVolume() * 100);
})();

// Voice mute — toggles the server-side announcer (Piper/espeak plays through
// ALSA, so muting is a setting the server honors, not a browser pause).
const SPEAKER_SVG = '<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3a4.5 4.5 0 0 0-2.5-4v8a4.5 4.5 0 0 0 2.5-4zM14 3.2v2.1a7 7 0 0 1 0 13.4v2.1a9 9 0 0 0 0-17.6z"/></svg>';
const MUTED_SVG = '<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M3 9v6h4l5 5V4L7 9H3zm18.5-1.5L20 6l-2.5 2.5L15 6l-1.5 1.5L16 10l-2.5 2.5L15 14l2.5-2.5L20 14l1.5-1.5L19 10z"/></svg>';

function renderVoiceMute() {
  const btn = document.getElementById('voice-mute');
  if (!btn) return;
  const on = !!getSetting('voice_enabled', true);
  btn.innerHTML = on ? SPEAKER_SVG : MUTED_SVG;
  btn.classList.toggle('muted', !on);
  btn.title = on ? 'Mute the announcer voice' : 'Announcer muted — tap to unmute';
}

function toggleVoiceMute() {
  if (window.SkyDexAudio && SkyDexAudio.playBeep) SkyDexAudio.playBeep();
  const now = !getSetting('voice_enabled', true);
  saveSetting('voice_enabled', now).then(() => {
    renderVoiceMute();
    showToast(now ? 'Announcer voice ON' : 'Announcer voice muted');
  });
}

function stopAllAudio() {
  if (window._tuneAbandon) _tuneAbandon();   // release Name That Tune's grip first
  AUDIO_IDS.forEach(id => {
    const a = document.getElementById(id);
    if (a) { a.onerror = null; if (!a.paused) { a.pause(); a.removeAttribute('src'); a.load(); } }
  });
  // Reset the players' UI state so their buttons match reality.
  const atcLabel = document.getElementById('atc-label');
  if (atcLabel) atcLabel.textContent = 'Tower';
  const atcBtn = document.getElementById('atc-btn');
  if (atcBtn) atcBtn.classList.remove('atc-live');
  const scanLabel = document.getElementById('scanner-label');
  if (scanLabel) scanLabel.textContent = 'Scanner';
  const now = document.getElementById('radio-now');
  if (now) now.innerHTML = 'Stopped. Throw another dart!';
  const std = document.getElementById('std-holder');
  if (std) std.innerHTML = '';
  // The EtherDex live tuner plays server-side (rtl_fm -> Pi speakers), so the
  // browser can't pause it — tell the server to stop and resume sensor-hopping.
  window._listenUntil = 0;
  fetch('/api/ether/listen/stop', { method: 'POST' }).catch(() => {});
  if (window.SkyDexAudio && SkyDexAudio.playBeep) SkyDexAudio.playBeep();
}

/** Show the stop button (with what's playing) whenever any stream is live. */
setInterval(() => {
  const btn = document.getElementById('global-stop');
  if (!btn) return;
  let playing = null;
  AUDIO_IDS.forEach(id => {
    const a = document.getElementById(id);
    if (a && !a.paused && a.currentSrc) playing = id;
  });
  // Server-side live tuner (rtl_fm on the Pi) — expiry-stamped so a server
  // auto-timeout can't leave this label stuck on.
  if (!playing && window._listenUntil && Date.now() < window._listenUntil) playing = 'antenna';
  btn.classList.toggle('hidden', !playing);
  const vw = document.getElementById('vol-wrap');
  if (vw) vw.classList.toggle('hidden', !playing);
  if (playing) {
    const label = document.getElementById('gs-label');
    const names = { 'tuner-audio': 'RADIO', 'atc-audio': 'TOWER', 'scanner-audio': 'SCANNER', 'antenna': 'ANTENNA' };
    if (label) label.textContent = names[playing] || 'AUDIO';
  }
}, 1500);

// ============================================
// INFO MODAL — tap a badge / type pill / rarity / achievement for details
// ============================================
function showInfoModal(title, bodyHtml) {
  const m = document.getElementById('info-modal');
  if (!m) return;
  document.getElementById('info-modal-title').innerHTML = title;
  document.getElementById('info-modal-body').innerHTML = bodyHtml;
  m.classList.remove('hidden');
}

function closeInfoModal() {
  const m = document.getElementById('info-modal');
  if (m) m.classList.add('hidden');
}

/** Dex-detail badge chips (label + definition come from the backend). */
function showChipInfo(labelEnc, titleEnc, color) {
  const label = decodeURIComponent(labelEnc);
  const def = decodeURIComponent(titleEnc) || 'A collectible badge earned by this craft.';
  showInfoModal(
    `<span class="im-chip" style="background:${color}22;border-color:${color};color:${color};">${label}</span> Badge`,
    `<p>${def}</p>`);
}

const TYPE_LORE = {
  rotor:    'Helicopters and other rotorcraft. Around here that usually means Sikorsky — they build them next door.',
  jet:      'Jet-powered fixed-wing aircraft — airliners, regional jets, anything with turbofans.',
  sentinel: 'Military aircraft, identified by military hex codes, callsigns (RCH, RRR…), or operators like the Air Force or Navy.',
  heavy:    'Widebody heavies — 747s, 777s, A330s and friends. Usually high overhead on ocean routes.',
  bizjet:   'Business jets — Gulfstreams, Citations, Challengers. Watch for them slipping into KBDR.',
  voyager:  'High-altitude overflights passing between distant cities — they never land near here.',
  trainer:  'Training aircraft doing laps of the pattern at KBDR — the same plane circling is a student pilot at work.',
  hopper:   'Light general-aviation aircraft on short hops — Cessnas, Pipers, weekend flyers.',
  hauler:   'Cargo aircraft — FedEx, UPS and other freight operators.',
  medevac:  'Air ambulances and medical flights, identified by callsign prefixes like LIF and MED operators.',
  commuter: 'Regulars! Aircraft that show up on a schedule — same day, same time, week after week.',
};

const RARITY_LORE = {
  common:    ['★', 'Seen all the time — the everyday traffic of the Sound and the sky.'],
  uncommon:  ['★★', 'A bit special — shows up now and then.'],
  rare:      ['★★★', 'Genuinely uncommon around here — a good catch.'],
  epic:      ['★★★★', 'A serious find — military hardware, widebodies, superyachts.'],
  legendary: ['★★★★★', 'The rarest of the rare. Screenshot it. Tell your friends.'],
};

function showTypeInfo(typeKey) {
  const t = (typeof AIRCRAFT_TYPES !== 'undefined' && AIRCRAFT_TYPES[typeKey]) || null;
  if (!t) return;
  showInfoModal(
    `<span class="im-chip" style="background:${t.color}33;border-color:${t.color};color:${t.color};">${t.label}</span> Type`,
    `<p>${TYPE_LORE[typeKey] || t.desc || ''}</p>`);
}

function showRarityInfo(rarity) {
  const r = RARITY_LORE[(rarity || 'common').toLowerCase()] || RARITY_LORE.common;
  showInfoModal(`<span style="color:var(--accent-yellow);">${r[0]}</span> ${rarity ? rarity[0].toUpperCase() + rarity.slice(1) : 'Common'} Rarity`,
    `<p>${r[1]}</p><p style="color:var(--text-dim);font-size:12px;">Rarity is based on aircraft/vessel role and size — and how often YOU have logged it.</p>`);
}

/** Achievement chip tap (records.js caches the latest list). */
function showAchievementInfo(id) {
  const list = window._achCache || [];
  const a = list.find(x => x.id === id);
  if (!a) return;
  const earned = a.unlocked && a.earned_at
    ? new Date(a.earned_at * 1000).toLocaleDateString('en-US',
        { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric', timeZone: EST_TZ })
    : null;
  const pct = Math.round(100 * a.progress / a.threshold);
  showInfoModal(
    `<span class="im-chip ${a.unlocked ? 'im-earned' : ''}">${a.icon}</span> ${a.title}`,
    `<p>${a.description}.</p>` +
    (a.unlocked
      ? `<p style="color:var(--accent-green,#4ade80);font-weight:bold;">&#10003; Earned ${earned || ''}</p>`
      : `<p style="color:var(--text-dim);">Progress: <b style="color:var(--text);">${a.progress} / ${a.threshold}</b> (${pct}%)</p>
         <div class="ach-bar" style="height:6px;"><span style="width:${pct}%"></span></div>`) +
    `<p style="color:var(--text-dim);font-size:11px;margin-top:8px;">${
      { air: 'SkyDex achievement', sea: 'SeaDex achievement', atmo: 'AtmoDex achievement', land: 'LandDex achievement' }[a.domain] || ''}</p>`);
}
