/* SkyDex journeys.js — follow tagged planes/ships far beyond the home radius.
 * One shared map draws every followed craft's breadcrumb trail; cards below
 * report last fix, distance from home, and honest "dark" status when a craft
 * is out of coverage (mid-ocean boats, oceanic flights). */

let _journeyMap = null;
let _journeyTimer = null;

const JRNY_COLORS = ['#FFD700', '#30A7D7', '#4ade80', '#ff6b9d', '#ff9f43',
                     '#7859c4', '#98D8D8', '#ff6b6b', '#9db4c8', '#B8B8D0'];

const JRNY_ICONS = {
  air: '<svg viewBox="0 0 24 24" width="20" height="20" fill="CLR"><path d="M21 16v-2l-8-5V3.5a1.5 1.5 0 0 0-3 0V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5z"/></svg>',
  sea: '<svg viewBox="0 0 24 24" width="20" height="20" fill="CLR"><path d="M12 2l6 5v4l3 1-2 8H5L3 12l3-1V7zm0 2.5L8 8v2.5l4-1.3 4 1.3V8z"/></svg>',
};

function openJourneys() {
  if (window.SkyDexAudio && SkyDexAudio.playBeep) SkyDexAudio.playBeep();
  showView('journeys');
  loadJourneys();
  clearInterval(_journeyTimer);
  _journeyTimer = setInterval(() => {
    if (SkyDex.currentView === 'journeys') loadJourneys();
    else clearInterval(_journeyTimer);
  }, 60000);
}

async function followCraft(kind, id, name) {
  if (window.SkyDexAudio && SkyDexAudio.playBeep) SkyDexAudio.playBeep();
  try {
    const r = await fetch('/api/follow', { method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kind: kind, id: id, name: name || '' }) });
    if (!r.ok) { showToast('Follow failed — server error ' + r.status); return; }
    const d = await r.json();
    if (d.error) { showToast(d.error); return; }
    showToast('Following ' + (name || id) + ' — see the Journeys button!', 'success');
  } catch (e) { showToast('Follow failed — no response from server'); }
}

async function unfollowCraft(kind, id) {
  if (window.SkyDexAudio && SkyDexAudio.playBeep) SkyDexAudio.playBeep();
  try {
    await fetch('/api/unfollow', { method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kind: kind, id: id }) });
    showToast('Unfollowed — the trail is kept for a while');
    loadJourneys();
  } catch (e) { showToast('Unfollow failed'); }
}

async function loadJourneys() {
  const el = document.getElementById('journeys-content');
  if (!el) return;
  let d;
  try {
    d = await (await fetch('/api/journeys')).json();
  } catch (e) {
    el.innerHTML = '<div class="ds-empty">Journeys unreachable.</div>';
    return;
  }
  const list = d.followed || [];
  if (!list.length) {
    _journeyMap = null;
    el.innerHTML = `<div class="ds-empty">Nothing followed yet!<br><br>
      Open any plane or ship in the Dex and tap <b>&#128205; Follow</b> — the kiosk will
      track it across the world using thousands of receivers, long after it leaves our sky.
      Up to 10 at a time.</div>`;
    return;
  }

  const ago = (t) => {
    if (!t) return 'no fix yet';
    const m = Math.round((Date.now() / 1000 - t) / 60);
    return m < 1 ? 'just now' : m < 60 ? m + ' min ago' : Math.round(m / 60 * 10) / 10 + ' h ago';
  };
  const chip = (s) => s === 'live'
    ? '<span class="jrny-chip live">LIVE</span>'
    : s === 'dark' ? '<span class="jrny-chip dark">DARK</span>'
    : '<span class="jrny-chip">WAITING</span>';

  let html = `<div id="journeymap"></div>`;
  if (!d.sea_enabled && list.some(f => f.kind === 'sea')) {
    html += `<div class="board-note">Ship tracking needs a second free aisstream.io key in
      <b>.env</b> as <code>SKYDEX_AISSTREAM_KEY2</code> — planes work without it.</div>`;
  }
  html += list.map((f, i) => {
    const c = JRNY_COLORS[i % JRNY_COLORS.length];
    const stats = [];
    if (f.miles_from_home != null) stats.push(`<b>${f.miles_from_home.toLocaleString()}</b> mi from home`);
    if (f.last_alt != null && f.kind === 'air') stats.push(Math.round(f.last_alt).toLocaleString() + ' ft');
    if (f.last_speed != null) stats.push(Math.round(f.last_speed) + (f.kind === 'air' ? ' kt' : ' kn'));
    return `<div class="pass-card" style="border-left:3px solid ${c};">
      <div class="pass-icon">${JRNY_ICONS[f.kind].replace('CLR', c)}</div>
      <div class="pass-body" style="cursor:pointer;" onclick="_jrnyZoom(${f.last_lat != null ? f.last_lat : 'null'},${f.last_lon != null ? f.last_lon : 'null'})">
        <div class="pass-name">${f.name || f.callsign || (f.kind === 'air' ? f.craft_id.toUpperCase() : 'MMSI ' + f.craft_id)} ${chip(f.status)}</div>
        <div class="pass-sub">
          ${f.status === 'waiting' ? 'Searching the world’s receivers…'
            : `Last heard ${ago(f.last_seen)}${f.last_source ? ' via ' + f.last_source : ''} · ${stats.join(' · ')}`}
          ${f.status === 'dark' ? '<br>Out of receiver range — ships mid-ocean and oceanic flights go quiet, then reappear.' : ''}
        </div>
      </div>
      <div class="pass-stats">
        <button class="day-summary-btn" style="margin:0;width:auto;display:inline-flex;padding:5px 11px;font-size:11px;"
          onclick="unfollowCraft('${f.kind}','${f.craft_id}')">&#10005; Unfollow</button>
      </div>
    </div>`;
  }).join('');
  html += `<div class="board-note">Positions from community receiver networks (adsb.lol,
    airplanes.live, OpenSky${d.sea_enabled ? ', AISStream' : ''}) — updated every ~3 minutes.
    Trails are breadcrumbs of everywhere the craft has been heard since you followed it.</div>`;
  el.innerHTML = html;

  // One shared map: home marker + a colored trail per craft.
  const map = L.map('journeymap', { zoomControl: true, attributionControl: false });
  _journeyMap = map;
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    { maxZoom: 18 }).addTo(map);
  const bounds = [];
  L.circleMarker([d.home.lat, d.home.lon], { radius: 6, color: '#fff',
    fillColor: '#FFD700', fillOpacity: 1 }).addTo(map).bindPopup('Home');
  bounds.push([d.home.lat, d.home.lon]);
  list.forEach((f, i) => {
    const c = JRNY_COLORS[i % JRNY_COLORS.length];
    if ((f.trail || []).length > 1) {
      L.polyline(f.trail, { color: c, weight: 2.5, opacity: 0.85 }).addTo(map);
    }
    if (f.last_lat != null && f.last_lon != null) {
      L.marker([f.last_lat, f.last_lon], {
        icon: L.divIcon({ className: 'train-mk', html: JRNY_ICONS[f.kind].replace('CLR', c),
                          iconSize: [20, 20], iconAnchor: [10, 10] }),
      }).addTo(map).bindPopup(`${f.name || f.craft_id} — ${ago(f.last_seen)}`);
      bounds.push([f.last_lat, f.last_lon]);
      (f.trail || []).forEach(p => bounds.push(p));
    }
  });
  if (bounds.length > 1) map.fitBounds(bounds, { padding: [30, 30] });
  else map.setView([d.home.lat, d.home.lon], 8);
}

function _jrnyZoom(lat, lon) {
  if (_journeyMap && lat != null) _journeyMap.flyTo([lat, lon], 7, { duration: 1.2 });
}
