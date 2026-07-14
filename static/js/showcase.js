/* SkyDex showcase.js — attract mode (idle showcase), day replay on the map,
 * and tap-a-plane route lines. Loads after pokedex.js + controls.js. */

// ============================================
// ROUTE LINES — tap an aircraft marker on the map
// ============================================
let _routeLayers = [];

function _clearRouteLayers() {
  _routeLayers.forEach(l => { try { _map.removeLayer(l); } catch (e) {} });
  _routeLayers = [];
}

window.onMapMarkerTap = function (c) {
  if (SkyDex.mode !== 'air' || !c.hex || !_map) return;
  _clearRouteLayers();
  fetch(`/api/route-coords/${c.hex}`).then(r => r.ok ? r.json() : null).then(d => {
    if (!d || (!d.origin && !d.dest)) {
      showToast('No route known for ' + (c.callsign || c.hex));
      return;
    }
    const here = [c.lat, c.lon];
    const mk = (pt, label, color) => {
      const m = L.circleMarker([pt.lat, pt.lon],
        { radius: 6, color, fillColor: color, fillOpacity: 0.9, weight: 2 })
        .addTo(_map).bindTooltip(`${label}: ${pt.label || pt.code}`, { permanent: false });
      _routeLayers.push(m);
    };
    if (d.origin) {
      _routeLayers.push(L.polyline([[d.origin.lat, d.origin.lon], here],
        { color: '#4ade80', weight: 2, opacity: 0.7 }).addTo(_map));
      mk(d.origin, 'From', '#4ade80');
    }
    if (d.dest) {
      _routeLayers.push(L.polyline([here, [d.dest.lat, d.dest.lon]],
        { color: '#FFCB05', weight: 2, opacity: 0.7, dashArray: '8,6' }).addTo(_map));
      mk(d.dest, 'To', '#FFCB05');
    }
    // Route lines fade out on their own after 25s.
    setTimeout(_clearRouteLayers, 25000);
  }).catch(() => {});
};

// ============================================
// DAY REPLAY — time-lapse of today's air traffic
// ============================================
let _replay = null;   // {tracks, start, end, sim, speed, timer, layer}

function startReplay() {
  if (window.SkyDexAudio && SkyDexAudio.playBeep) SkyDexAudio.playBeep();
  if (SkyDex.mode === 'sea') { showToast('Replay covers aircraft (position history is air-only)'); }
  fetch('/api/replay').then(r => r.json()).then(d => {
    if (!d.tracks || !d.tracks.length) { showToast('No tracks logged yet today'); return; }
    showMapMode('map');
    if (!_map) return;
    window.REPLAY_ACTIVE = true;
    SkyDex.isPolling = false;
    if (_mapTimer) { clearInterval(_mapTimer); _mapTimer = null; }
    _mapMarkers.forEach(m => { try { _map.removeLayer(m); } catch (e) {} });
    _mapMarkers = [];

    const layer = L.layerGroup().addTo(_map);
    const DURATION_S = 45;                        // whole day plays in ~45s
    const speed = (d.end - d.start) / DURATION_S; // sim-seconds per real second
    _replay = { tracks: d.tracks, start: d.start, end: d.end,
                sim: d.start, speed, layer, dots: {}, trails: {} };

    d.tracks.forEach(t => {
      const color = (AIRCRAFT_TYPES[(t.primary_type || 'jet').toLowerCase()] || AIRCRAFT_TYPES.jet).color;
      _replay.trails[t.hex] = L.polyline([], { color, weight: 2, opacity: 0.5 }).addTo(layer);
      _replay.dots[t.hex] = L.circleMarker([0, 0],
        { radius: 5, color, fillColor: color, fillOpacity: 0.95, weight: 1 })
        .bindTooltip(t.callsign || t.registration || t.hex);
    });

    document.getElementById('replay-bar').classList.remove('hidden');
    _replay.timer = setInterval(_replayTick, 100);
  }).catch(() => showToast('Replay unavailable'));
}

function _replayTick() {
  const r = _replay;
  if (!r) return;
  r.sim += r.speed * 0.1;
  if (r.sim >= r.end) { r.sim = r.end; stopReplay(true); return; }

  r.tracks.forEach(t => {
    const pts = t.points;
    // points visible so far
    let upto = 0;
    while (upto < pts.length && pts[upto][0] <= r.sim) upto++;
    const dot = r.dots[t.hex], trail = r.trails[t.hex];
    if (upto === 0) { if (r.layer.hasLayer(dot)) r.layer.removeLayer(dot); trail.setLatLngs([]); return; }
    const seen = pts.slice(Math.max(0, upto - 40), upto).map(p => [p[1], p[2]]);
    trail.setLatLngs(seen);
    const last = pts[upto - 1];
    // Hide the dot once the aircraft's data has been gone > 10 sim-minutes.
    if (r.sim - last[0] > 600) { if (r.layer.hasLayer(dot)) r.layer.removeLayer(dot); return; }
    if (!r.layer.hasLayer(dot)) dot.addTo(r.layer);
    dot.setLatLng([last[1], last[2]]);
  });

  const pct = 100 * (r.sim - r.start) / Math.max(1, r.end - r.start);
  const bar = document.getElementById('replay-progress');
  if (bar) bar.style.width = pct.toFixed(1) + '%';
  const clock = document.getElementById('replay-clock');
  if (clock) clock.textContent = fmtTimeEST(r.sim);
}

function stopReplay(finished) {
  if (_replay) {
    clearInterval(_replay.timer);
    try { _map.removeLayer(_replay.layer); } catch (e) {}
    _replay = null;
  }
  document.getElementById('replay-bar').classList.add('hidden');
  window.REPLAY_ACTIVE = false;
  if (!window.SSE_ACTIVE) SkyDex.isPolling = true;
  if (finished) showToast("That was today so far — back to live");
  fetchContacts();
}

// ============================================
// ATTRACT MODE — idle showcase
// ============================================
let _lastTouch = Date.now();
let _attract = { showing: false, timer: null, cardIdx: 0, cards: [] };

['pointerdown', 'touchstart', 'keydown'].forEach(ev =>
  document.addEventListener(ev, () => {
    _lastTouch = Date.now();
    if (_attract.showing) dismissAttract();
  }, { passive: true }));

function _attractCheck() {
  if (_attract.showing || window.REPLAY_ACTIVE) return;
  if (!getSetting('attract_enabled', true)) return;
  const idleMin = getSetting('attract_idle_minutes', 10);
  if ((Date.now() - _lastTouch) / 60000 >= idleMin) startAttract();
}

async function startAttract() {
  _attract.showing = true;
  _attract.cards = await _buildAttractCards();
  _attract.cardIdx = 0;
  const ov = document.getElementById('attract-overlay');
  ov.classList.remove('hidden');
  _showAttractCard();
  _attract.timer = setInterval(() => {
    _attract.cardIdx = (_attract.cardIdx + 1) % Math.max(1, _attract.cards.length);
    _showAttractCard();
  }, 12000);
}

function dismissAttract() {
  _attract.showing = false;
  if (_attract.timer) { clearInterval(_attract.timer); _attract.timer = null; }
  document.getElementById('attract-overlay').classList.add('hidden');
}

function _showAttractCard() {
  const card = document.getElementById('attract-card');
  if (!card || !_attract.cards.length) return;
  card.style.opacity = '0';
  setTimeout(() => {
    card.innerHTML = _attract.cards[_attract.cardIdx];
    card.style.opacity = '1';
  }, 350);
}

async function _buildAttractCards() {
  const cards = [];

  // 1. Nearest live contact right now
  const c = (SkyDex.contacts || [])[0];
  if (c) {
    const ident = c.callsign || c.registration || c.name || c.hex || c.mmsi || '';
    const what = c.model || c.category || 'contact';
    cards.push(`<div class="att-kicker">RIGHT NOW</div>
      <div class="att-big">${ident}</div>
      <div class="att-sub">${what} · ${formatDistance ? formatDistance(c.distance_miles) : ''} away</div>`);
  }

  // 2. A record
  try {
    const rec = await (await fetch('/api/records')).json();
    const f = rec.air && rec.air.fastest;
    if (f) cards.push(`<div class="att-kicker">HALL OF FAME</div>
      <div class="att-big">${Math.round(f.value)} kn</div>
      <div class="att-sub">fastest ever · ${f.callsign || f.registration || f.hex} (${f.model || ''})</div>`);
    const big = rec.sea && rec.sea.longest;
    if (big) cards.push(`<div class="att-kicker">BIGGEST VESSEL</div>
      <div class="att-big">${Math.round(big.value)} m</div>
      <div class="att-sub">${big.name || ''} · ${big.category || ''}</div>`);
  } catch (e) {}

  // 3. Tonight's sky
  try {
    const atmo = await (await fetch('/api/atmo')).json();
    if (atmo.moon) cards.push(`<div class="att-kicker">TONIGHT'S SKY</div>
      <div class="att-big">${atmo.moon.phase}</div>
      <div class="att-sub">${atmo.moon.illumination}% lit ·
        ${(atmo.planets || []).slice(0, 3).map(p => p.name).join(' · ') || 'no planets well-placed'}</div>`);
  } catch (e) {}

  // 4. A random fact
  const facts = (typeof factPool === 'function') ? factPool() : [];
  if (facts.length) {
    const f = facts[Math.floor(Math.random() * facts.length)];
    cards.push(`<div class="att-kicker">DID YOU KNOW</div><div class="att-fact">${f}</div>`);
  }

  // 5. NASA picture of the day
  try {
    const apod = await (await fetch('/api/atmo/apod')).json();
    if (apod && apod.url && (apod.media_type === 'image' || !apod.media_type)) {
      cards.push(`<div class="att-kicker">NASA PICTURE OF THE DAY</div>
        <img class="att-img" src="${apod.url}" alt="">
        <div class="att-sub">${apod.title || ''}</div>`);
    }
  } catch (e) {}

  if (!cards.length) cards.push(`<div class="att-big">SkyDex</div>
    <div class="att-sub">watching the skies over Stratford, CT</div>`);
  return cards;
}

setInterval(_attractCheck, 30000);

// ============================================
// MODE EASTER EGGS — biplane (Sky) & kraken (Sea), same spirit as the UFO
// ============================================
function biplaneZoom() {
  const o = document.getElementById('biplane-overlay');
  if (o) { o.classList.remove('fly'); void o.offsetWidth; o.classList.add('fly'); }
  try { SkyDexAudio.playBeep(); } catch (e) {}
  setTimeout(() => openRecords(), 1100);
  setTimeout(() => { if (o) o.classList.remove('fly'); }, 2400);
}

function krakenRise() {
  const o = document.getElementById('kraken-overlay');
  if (o) { o.classList.remove('rise'); void o.offsetWidth; o.classList.add('rise'); }
  try { SkyDexAudio.playBeep(); } catch (e) {}
  setTimeout(() => openRecords(), 1400);
  setTimeout(() => { if (o) o.classList.remove('rise'); }, 2600);
}

// ============================================
// STORMDEX — weather catches (record breakers, named storms, wild days)
// ============================================
const STORM_KINDS = {
  record_high: { label: 'RECORD HIGH', color: '#ff6b6b',
    svg: '<svg viewBox="0 0 24 24" width="70%" height="70%" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M10 4a2 2 0 0 1 4 0v9.5a4 4 0 1 1-4 0z"/><circle cx="12" cy="17" r="1.8" fill="currentColor" stroke="none"/><path d="M12 14v-8" stroke-width="2.4"/></svg>' },
  record_low: { label: 'RECORD LOW', color: '#74b9ff',
    svg: '<svg viewBox="0 0 24 24" width="70%" height="70%" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M10 4a2 2 0 0 1 4 0v9.5a4 4 0 1 1-4 0z"/><circle cx="12" cy="17" r="1.8" fill="currentColor" stroke="none"/></svg>' },
  near_record: { label: 'NEAR RECORD', color: '#ff9f43',
    svg: '<svg viewBox="0 0 24 24" width="70%" height="70%" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M10 4a2 2 0 0 1 4 0v9.5a4 4 0 1 1-4 0z"/><circle cx="12" cy="17" r="1.8" fill="currentColor" stroke="none"/><path d="M12 14v-5"/></svg>' },
  named_storm: { label: 'NAMED STORM', color: '#FFD700',
    svg: '<svg viewBox="0 0 24 24" width="70%" height="70%" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"><path d="M12 3a9 9 0 0 1 9 9c0 5-4 8-8 9 2.5-2 3.5-4 3-6"/><path d="M12 21a9 9 0 0 1-9-9c0-5 4-8 8-9-2.5 2-3.5 4-3 6"/><circle cx="12" cy="12" r="2.4" fill="currentColor" stroke="none"/></svg>' },
  alert: { label: 'EXTREME ALERT', color: '#ff6b6b',
    svg: '<svg viewBox="0 0 24 24" width="70%" height="70%" fill="currentColor"><path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/></svg>' },
  snow: { label: 'BIG SNOW', color: '#bfe3ff',
    svg: '<svg viewBox="0 0 24 24" width="70%" height="70%" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"><path d="M12 2v20M4 6l16 12M20 6L4 18M12 5l-2-2M12 5l2-2M12 19l-2 2M12 19l2 2"/></svg>' },
};

function _stormDate(iso) {
  try {
    return new Date(iso + 'T12:00:00').toLocaleDateString('en-US',
      { weekday: 'short', month: 'long', day: 'numeric', year: 'numeric' });
  } catch (e) { return iso; }
}

function _stormStats(stats_json) {
  if (!stats_json) return '';
  try {
    const s = JSON.parse(stats_json);
    const bits = [];
    if (s.high_f != null) bits.push('High ' + Math.round(s.high_f) + '°F');
    if (s.low_f != null) bits.push('Low ' + Math.round(s.low_f) + '°F');
    if (s.rain_in) bits.push(Number(s.rain_in).toFixed(2) + '" rain');
    if (s.snow_in) bits.push(Number(s.snow_in).toFixed(1) + '" snow');
    if (s.gust_mph) bits.push('gusts ' + Math.round(s.gust_mph) + ' mph');
    return bits.length
      ? '<div class="storm-stats">' + bits.map(b => `<span>${b}</span>`).join('') + '</div>' : '';
  } catch (e) { return ''; }
}

async function fetchStorms() {
  const el = document.getElementById('storms-content');
  if (!el) return;
  try {
    renderStorms(await (await fetch('/api/weather-log')).json());
  } catch (e) {
    el.innerHTML = '<div class="ds-empty">Storm log unavailable.</div>';
  }
}

function renderStorms(d) {
  const el = document.getElementById('storms-content');
  if (!el) return;
  const events = d.events || [];
  const otd = d.on_this_day || [];
  let html = '';

  // "On this day in..." — history the kiosk wrote itself.
  if (otd.length) {
    html += `<div class="fc-record" style="border-color:#FFD700;">
        <div class="fc-record-title" style="color:#FFD700;">On This Day</div>` +
      otd.map(e => `<div class="atmo-line">
          <span><b style="color:var(--text);">${e.event_date.slice(0, 4)}</b> — ${e.title}</span></div>`).join('') +
      `</div>`;
    // Fuel the ticker with the best one.
    if (SkyDex.mode === 'atmo' && SkyDex.facts && SkyDex.facts.length) {
      const line = `On this day in ${otd[0].event_date.slice(0, 4)}: ${otd[0].title}.`;
      if (!SkyDex.facts.includes(line)) SkyDex.facts.unshift(line);
    }
  }

  if (!events.length) {
    html += `<div class="ds-empty">No weather catches yet.<br><br>
      The watcher checks every 30 minutes — the first record-breaker, named storm,
      big snow, or extreme alert lands here automatically and stays forever.</div>`;
    el.innerHTML = html;
    return;
  }

  html += events.map(e => {
    const k = STORM_KINDS[e.kind] || STORM_KINDS.alert;
    const epic = e.kind === 'named_storm' || e.kind === 'record_high' || e.kind === 'record_low';
    return `<div class="pass-card ${epic ? 'pass-acela' : ''}">
        <div class="pass-icon" style="color:${k.color};">${k.svg}</div>
        <div class="pass-body">
          <div class="pass-name">${e.title || ''} <span class="sat-type" style="color:${k.color};">${k.label}</span></div>
          <div class="pass-sub">${_stormDate(e.event_date)}${e.detail ? ' — ' + e.detail : ''}</div>
          ${_stormStats(e.stats_json)}
        </div>
      </div>`;
  }).join('');
  el.innerHTML = html;
}
