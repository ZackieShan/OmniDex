/* SkyDex landdex.js — LandDex mode: Stratford Metro-North departure board,
 * live Amtrak pass-throughs, and the Traindex collection.
 * Loads after pokedex.js (plain script, shares its globals). */

// Fallback ticker facts until /api/facts?domain=land loads.
window.LAND_FACTS = [
  "The shoreline tracks opened in 1848 — trains have run along this coast for over 175 years.",
  "The New Haven Line is the busiest commuter rail line in the United States.",
  "Acela trains blast through the local stations without stopping — up to 150 mph on straighter track.",
  "Four tracks run along the shoreline: locals outside, Acela overtakes on the inside pair.",
];

const TRAIN_SVG = '<svg viewBox="0 0 24 24" fill="currentColor" width="70%" height="70%"><path d="M12 2c-4.4 0-8 .5-8 4v9.5A2.5 2.5 0 0 0 6.5 18L5 19.5v.5h2.2l1.5-1.5h6.6l1.5 1.5H19v-.5L17.5 18a2.5 2.5 0 0 0 2.5-2.5V6c0-3.5-3.6-4-8-4zM7.5 15a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3zm3.5-6H6V6h5v3zm2 0V6h5v3h-5zm3.5 6a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3z"/></svg>';

let _landTimer = null;

/** SkyDex-native live Metro-North map — MTA GTFS-RT positions on our own
 *  Leaflet, refreshed every 30s while open. traintracker.live at home. */
let _ttTimer = null;
const _trainMaps = {};   // containerId -> { map, trainLayer }
const MNR_LINE_DOT = { Hudson: '#009B3A', Harlem: '#0039A6', 'New Haven': '#EE0034' };

// Map markers: Metro-North = trolley, Amtrak = bullet-train nose.
const TRAIN_MK = {
  trolley: '<svg viewBox="0 0 26 20" width="26" height="20" xmlns="http://www.w3.org/2000/svg">'
    + '<path d="M13 1v3M8 4h10" stroke="currentColor" stroke-width="1.3" fill="none"/>'
    + '<rect x="4" y="4" width="18" height="11" rx="2.5" fill="currentColor"/>'
    + '<rect x="6.5" y="6.5" width="3.6" height="3.6" rx="0.8" fill="#0b0e13" opacity="0.75"/>'
    + '<rect x="11.2" y="6.5" width="3.6" height="3.6" rx="0.8" fill="#0b0e13" opacity="0.75"/>'
    + '<rect x="15.9" y="6.5" width="3.6" height="3.6" rx="0.8" fill="#0b0e13" opacity="0.75"/>'
    + '<circle cx="9" cy="16.6" r="2" fill="currentColor" stroke="#0b0e13" stroke-width="0.8"/>'
    + '<circle cx="17" cy="16.6" r="2" fill="currentColor" stroke="#0b0e13" stroke-width="0.8"/></svg>',
  bullet: '<svg viewBox="0 0 26 20" width="26" height="20" xmlns="http://www.w3.org/2000/svg">'
    + '<path d="M2 14.5c0-4.5 3-8.5 8-8.5h9c3.3 0 5 2.2 5 4.5v2c0 1.4-1 2.5-2.5 2.5H4.5C3 15 2 14.9 2 14.5z" fill="currentColor"/>'
    + '<path d="M4.5 10.5c1.2-2 3-3 5.5-3h3v3.5H4.2z" fill="#0b0e13" opacity="0.7"/>'
    + '<circle cx="8" cy="16.8" r="1.7" fill="currentColor" stroke="#0b0e13" stroke-width="0.8"/>'
    + '<circle cx="14" cy="16.8" r="1.7" fill="currentColor" stroke="#0b0e13" stroke-width="0.8"/>'
    + '<circle cx="20" cy="16.8" r="1.7" fill="currentColor" stroke="#0b0e13" stroke-width="0.8"/></svg>',
};

/** Build (or rebuild) a live train map in a container: tiles, Stratford star,
 *  tappable stations, and a train layer that _loadLiveTrains keeps fresh. */
function _buildTrainMap(containerId, zoom) {
  if (!window.L || !document.getElementById(containerId)) return null;
  if (_trainMaps[containerId]) {
    try { _trainMaps[containerId].map.remove(); } catch (e) {}
    delete _trainMaps[containerId];
  }
  const map = L.map(containerId, { zoomControl: true })
    .setView([41.1965, -73.1310], zoom || 9);   // centered on Stratford
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    { maxZoom: 15, attribution: '&copy; OpenStreetMap' }).addTo(map);
  L.circleMarker([41.1965, -73.1310], { radius: 7, color: '#FFCB05',
    fillColor: '#FFCB05', fillOpacity: 1 }).addTo(map)
    .bindTooltip('Stratford — home turf');
  const inst = { map, trainLayer: L.layerGroup().addTo(map) };
  _trainMaps[containerId] = inst;
  _loadStationsInto(map);
  setTimeout(() => map.invalidateSize(), 80);
  if (!_ttTimer) _ttTimer = setInterval(_loadLiveTrains, 30000);
  _loadLiveTrains();
  return inst;
}

/** Every station as a tappable dot: tap -> trip plan from Stratford. */
async function _loadStationsInto(map) {
  try {
    const stations = await (await fetch('/api/land/stations')).json();
    stations.forEach(s => {
      if (/stratford/i.test(s.name)) return;   // the star already marks home
      const c = MNR_LINE_DOT[s.line] || '#EE0034';
      const m = L.circleMarker([s.lat, s.lon], { radius: 4, color: c, weight: 2,
        fillColor: '#0b0e13', fillOpacity: 1 }).addTo(map);
      m.bindTooltip(s.name, { direction: 'top' });
      m.on('click', () => _showJourney(m, s));
    });
  } catch (e) { console.error('stations load failed:', e); }
}

async function _showJourney(marker, s) {
  marker.bindPopup('<b>' + s.name + '</b><br>Planning your trip…').openPopup();
  try {
    const j = await (await fetch('/api/land/journey?to=' + encodeURIComponent(s.id))).json();
    let html = `<b>Stratford → ${j.name || s.name}</b><br>`;
    if (j.no_service || !j.legs || !j.legs.length) {
      html += 'No more trains today.';
    } else {
      const h = Math.floor(j.minutes / 60), mn = j.minutes % 60;
      html += `<span style="color:#0039A6;font-weight:bold;">Leave ${fmtTimeEST(j.depart)} → arrive ${fmtTimeEST(j.arrive)}</span>`;
      html += ` (${h ? h + 'h ' : ''}${mn}m${j.transfers ? ' · ' + j.transfers + ' change' + (j.transfers > 1 ? 's' : '') : ' · direct'})<br>`;
      j.legs.forEach((l, i) => {
        html += `<span style="font-size:11px;">${i + 1}. ${l.line} Line: ${l.from} ${fmtTimeEST(l.dep)} → ${l.to} ${fmtTimeEST(l.arr)}</span><br>`;
      });
    }
    marker.bindPopup(html, { maxWidth: 260 }).openPopup();
  } catch (e) {
    marker.bindPopup('<b>' + s.name + '</b><br>Trip planner unavailable.').openPopup();
  }
}

/** Refresh train dots on the map — only when someone's actually looking. */
async function _loadLiveTrains() {
  if (SkyDex.currentView !== 'land-history' || !_trainMaps['gctmap']) return;
  try {
    const d = await (await fetch('/api/land/live')).json();
    const trains = d.trains || [];
    Object.values(_trainMaps).forEach(inst => {
      inst.trainLayer.clearLayers();
      trains.forEach(t => {
        let glyph, color, tip;
        if (t.kind === 'amtrak') {
          // Bullet-train nose, gold for Acela
          color = t.acela ? '#FFD700' : '#9db4c8';
          glyph = TRAIN_MK.bullet;
          tip = `${t.line || 'Amtrak'} #${t.label || ''}${t.speed_mph ? ' · ' + t.speed_mph + ' mph' : ''}`;
        } else {
          // Metro-North trolley, colored by line
          color = MNR_LINE_DOT[t.line] || '#EE0034';
          glyph = TRAIN_MK.trolley;
          tip = `${t.line} Line${t.label ? ' · train ' + t.label : ''}`;
        }
        const icon = L.divIcon({
          className: 'train-mk',
          html: `<span style="color:${color};">${glyph}</span>`,
          iconSize: [26, 20], iconAnchor: [13, 10],
        });
        L.marker([t.lat, t.lon], { icon }).addTo(inst.trainLayer)
          .bindTooltip(tip, { direction: 'top' });
      });
    });
  } catch (e) { /* keep last markers */ }
}

/** Steam-loco easter egg: chugs along the bottom, then opens the Traindex. */
function locoChug() {
  const o = document.getElementById('loco-overlay');
  if (o) { o.classList.remove('chug'); void o.offsetWidth; o.classList.add('chug'); }
  try { SkyDexAudio.playBeep(); } catch (e) {}
  setTimeout(() => showView('land-dex'), 1400);
  setTimeout(() => { if (o) o.classList.remove('chug'); }, 3000);
}

// ============================================
// BOARD VIEW (schedule + passing now)
// ============================================
async function fetchLand() {
  const el = document.getElementById('land-content');
  try {
    const d = await (await fetch('/api/land')).json();
    renderLand(d);
  } catch (e) {
    if (el) el.innerHTML = '<div class="ds-empty">Rails unreachable — check the network.</div>';
  }
  // Refresh while the user stays on this view (Amtrak positions move fast).
  if (_landTimer) clearInterval(_landTimer);
  _landTimer = setInterval(() => {
    if (SkyDex.currentView === 'land') fetchLand._quiet();
    else { clearInterval(_landTimer); _landTimer = null; }
  }, 45000);
}
fetchLand._quiet = async function () {
  try { renderLand(await (await fetch('/api/land')).json()); } catch (e) {}
};

function _depRows(deps) {
  if (!deps || !deps.length) return '<div class="board-empty">— no more trains today —</div>';
  const now = Date.now() / 1000;
  return deps.map(d => {
    const mins = Math.round((d.epoch - now) / 60);
    const cd = mins <= 0 ? 'NOW' : mins < 60 ? `${mins} min` : fmtTimeEST(d.epoch);
    const soon = mins <= 10;
    return `<div class="board-row" onclick="openTrain('M8')" style="cursor:pointer;">
        <span class="board-time">${fmtTimeEST(d.epoch)}</span>
        <span class="board-ident">${d.train_num ? '#' + d.train_num : 'Local'}</span>
        <span class="board-detail">${d.headsign || ''}${d.gct_minutes ? ' · ' + d.gct_minutes + ' min ride' : ''}</span>
        <span class="board-status ${soon ? 'st-seen' : 'st-sched'}">${cd}</span>
      </div>`;
  }).join('');
}

function renderLand(d) {
  const el = document.getElementById('land-content');
  if (!el) return;
  const board = d.board || {};
  const passing = d.passing || [];
  const count = document.getElementById('land-count');
  if (count) count.innerHTML =
    `<div style="font-size:22px;font-weight:bold;color:var(--accent-yellow);">${d.collection_count || 0}</div>trains collected`;

  let html = '';
  window._passCache = passing;

  // --- Passing now (the exciting part) ---
  html += `<div class="dex-section-title">Passing Now — Amtrak within 15 mi (tap for details)</div>`;
  if (passing.length) {
    html += passing.map(t => {
      const acela = /acela/i.test(t.route || '');
      return `<div class="pass-card ${acela ? 'pass-acela' : ''}" onclick="openTrain('${t.train_num}')" style="cursor:pointer;">
          <div class="pass-icon" style="color:${acela ? '#FFD700' : 'var(--accent-blue)'};">${TRAIN_SVG}</div>
          <div class="pass-body">
            <div class="pass-name">${t.route || 'Amtrak'} <b>#${t.train_num}</b>${acela ? ' <span class="pass-flash">ACELA!</span>' : ''}</div>
            <div class="pass-sub">${t.origin || '?'} → ${t.dest || '?'}${t.toward ? ' · toward ' + t.toward : ''}</div>
          </div>
          <div class="pass-stats">
            <div class="pass-speed">${t.speed_mph} mph</div>
            <div class="pass-dist">${t.distance_miles} mi away</div>
          </div>
        </div>`;
    }).join('');
  } else {
    html += '<div class="ds-empty">No Amtrak trains nearby right now — Acelas pass every hour or so.</div>';
  }

  // --- Departure board ---
  if (board.have_schedule) {
    html += `<div class="board-cols" style="margin-top:10px;">
        <div class="board-col">
          <div class="board-head">&#8592; TO GRAND CENTRAL</div>
          ${_depRows(board.to_nyc)}
        </div>
        <div class="board-col">
          <div class="board-head">TO NEW HAVEN &#8594;</div>
          ${_depRows(board.to_new_haven)}
        </div>
      </div>`;
  } else {
    html += `<div class="dex-section-title" style="margin-top:10px;">Departures</div>
      <div class="ds-empty">Schedule not loaded yet — the GTFS file downloads on first run (give it a minute, then revisit).</div>`;
  }

  html += `<div class="board-note">Schedule: MTA GTFS (refreshed weekly) · Live trains: Amtraker ·
    Passing trains within 10 mi are logged to the Traindex automatically</div>`;
  el.innerHTML = html;
}

// ============================================
// TRAINDEX (collection)
// ============================================
async function fetchLandDex() {
  const el = document.getElementById('landdex-content');
  try {
    renderLandDex(await (await fetch('/api/land/collection')).json());
  } catch (e) {
    if (el) el.innerHTML = '<div class="ds-empty">Traindex unavailable.</div>';
  }
}

function renderLandDex(trains) {
  const el = document.getElementById('landdex-content');
  const count = document.getElementById('landdex-count');
  if (count) count.textContent = trains.length;
  if (!el) return;
  if (!trains.length) {
    el.innerHTML = `<div class="ds-empty">No trains logged yet.<br><br>
      The watcher checks every 90 seconds — the first Acela or Regional that
      passes within 10 miles starts your collection.</div>`;
    return;
  }
  window._trainCache = trains;
  el.innerHTML = '<div class="rec-grid">' + trains.map(t => {
    const acela = /acela/i.test(t.route || '');
    const rarity = (t.rarity || 'common').toLowerCase();
    return `<div class="rec-card ${acela ? 'pass-acela' : ''}" onclick="openTrain('${t.train_num}')" style="cursor:pointer;">
        <div class="rec-title" style="color:${acela ? '#FFD700' : 'var(--accent-blue)'};">${t.route || 'Amtrak'}</div>
        <div class="rec-value">#${t.train_num}</div>
        <div class="rec-sub">${t.times_seen}× seen · best ${Math.round(t.max_speed || 0)} mph</div>
        ${typeof renderRarityStars === 'function' ? renderRarityStars(rarity) : ''}
      </div>`;
  }).join('') + '</div>';
}

// ============================================
// TRAIN DETAILS — tap any train for equipment lore
// ============================================
const TRAIN_TYPES = {
  acela: {
    name: 'Acela', builder: 'Alstom',
    body: 'Amtrak\'s flagship. The new Avelia Liberty trainsets (entered service 2025) tilt through curves and are rated for 160 mph, though the twisty Connecticut shoreline keeps them under 100 through Stratford. Nine cars, articulated, first-class only by Amtrak standards — and the closest thing America has to a bullet train.',
    stats: ['Top speed: 150-160 mph', 'Power: 25 kV overhead', 'Route: Boston – NYC – Washington', 'Passes Stratford without stopping'],
  },
  regional: {
    name: 'Northeast Regional', builder: 'Siemens / Budd',
    body: 'The workhorse of the corridor: a Siemens ACS-64 "Sprinter" electric locomotive pulling 1970s-vintage Amfleet coaches — stainless steel tubes built by Budd that have covered more miles than almost any passenger car on Earth. New Siemens Airo trainsets are on the way to replace them.',
    stats: ['Top speed: 125 mph', 'Locomotive: ACS-64, 8,600 hp', 'Coaches: Amfleet I (1975-77)', 'Boston – Virginia via NYC'],
  },
  m8: {
    name: 'Metro-North M8', builder: 'Kawasaki',
    body: 'The red-doored electric railcars that run every Stratford local. Built by Kawasaki starting in 2011, each M8 is a dual-power shapeshifter: 12.5 kV from the overhead wire on the New Haven Line, then third-rail DC into Grand Central\'s tunnels. They accelerate 0-30 mph faster than most sports cars.',
    stats: ['Top speed: 100 mph', 'Power: catenary AND third rail', 'Fleet: 400+ cars', 'Stratford → GCT in ~80-90 min'],
  },
  generic: {
    name: 'Amtrak Special', builder: 'Various',
    body: 'Not an Acela, not a Regional — this is something unusual on the corridor: a deadhead move, a maintenance train, the Vermonter making a detour, or an office-car special. Rare catches for the Traindex.',
    stats: ['The corridor hosts ~2,000 movements a day system-wide', 'Freight (CSX / P&W) sneaks through at night'],
  },
};

function _trainTypeKey(route) {
  const r = (route || '').toLowerCase();
  if (r.includes('acela')) return 'acela';
  if (r.includes('regional')) return 'regional';
  if (r.includes('m8') || r.includes('metro')) return 'm8';
  return 'generic';
}

function openTrain(trainNum) {
  const rec = (window._trainCache || []).find(t => t.train_num === String(trainNum))
           || (window._passCache || []).find(t => t.train_num === String(trainNum));
  const key = trainNum === 'M8' ? 'm8' : _trainTypeKey(rec && rec.route);
  const info = TRAIN_TYPES[key];
  let statsHtml = '';
  if (rec) {
    const first = rec.first_seen ? new Date(rec.first_seen * 1000).toLocaleDateString('en-US',
      { month: 'short', day: 'numeric', year: 'numeric', timeZone: EST_TZ }) : null;
    statsHtml = `<p style="color:var(--accent-yellow);font-weight:bold;">Your #${trainNum}:
      ${rec.times_seen ? rec.times_seen + '× caught' : 'passing now'}${rec.max_speed ? ' · best ' + Math.round(rec.max_speed) + ' mph' : ''}${rec.speed_mph ? ' · now ' + rec.speed_mph + ' mph' : ''}${first ? ' · first ' + first : ''}</p>`;
  }
  showInfoModal(
    `${TRAIN_SVG.replace('width="70%" height="70%"', 'width="22" height="22"')} ${info.name}${trainNum !== 'M8' ? ' #' + trainNum : ''}`,
    statsHtml + `<p>${info.body}</p>` +
    `<p style="color:var(--text-dim);font-size:12px;">${info.stats.map(s => '• ' + s).join('<br>')}</p>` +
    `<p style="color:var(--text-dim);font-size:11px;">Builder: ${info.builder}</p>`);
}

// ============================================
// ROAD VIEW — I-95 commutes + scanner audio
// ============================================
async function fetchLandRoad() {
  const el = document.getElementById('road-content');
  try {
    renderRoad(await (await fetch('/api/land/road')).json());
  } catch (e) {
    if (el) el.innerHTML = '<div class="ds-empty">Road data unavailable.</div>';
  }
}

/** Live I-95 corridor map: real route line NYC -> New Haven, the NYC approach
 *  tinted by live DOT speeds, Waze incidents plotted (real coords when they
 *  have them, nearest corridor city otherwise), Stratford starred. */
const I95_WAYPOINTS = [
  ['NYC (Bronx)', 40.828, -73.877], ['New Rochelle', 40.912, -73.778],
  ['Greenwich', 41.028, -73.628], ['Stamford', 41.047, -73.542],
  ['Norwalk', 41.098, -73.421], ['Westport', 41.126, -73.358],
  ['Fairfield', 41.142, -73.263], ['Bridgeport', 41.171, -73.195],
  ['Stratford', 41.192, -73.131], ['Milford', 41.220, -73.057],
  ['New Haven', 41.298, -72.928],
];
let _roadMap = null;

function _buildRoadMap(d) {
  if (!window.L || !document.getElementById('roadmap')) return;
  if (_roadMap) { try { _roadMap.remove(); } catch (e) {} _roadMap = null; }
  _roadMap = L.map('roadmap', { zoomControl: true });
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    { maxZoom: 14, attribution: '&copy; OpenStreetMap' }).addTo(_roadMap);
  const pts = I95_WAYPOINTS.map(w => [w[1], w[2]]);
  _roadMap.fitBounds(L.latLngBounds(pts).pad(0.08));

  // NYC approach segment tinted by live DOT speeds; the CT run in corridor blue.
  const speeds = d.nyc_speeds || [];
  const avg = speeds.length ? speeds.reduce((a, s) => a + s.mph, 0) / speeds.length : null;
  const nycColor = avg == null ? '#5a6470' : avg < 20 ? '#ff6b6b' : avg < 40 ? '#ff9f43' : '#4ade80';
  L.polyline(pts.slice(0, 3), { color: nycColor, weight: 6, opacity: 0.9 }).addTo(_roadMap)
    .bindTooltip(avg != null ? `NYC approach — avg ${Math.round(avg)} mph (live DOT)` : 'NYC approach');
  L.polyline(pts.slice(2), { color: '#30A7D7', weight: 5, opacity: 0.75 }).addTo(_roadMap)
    .bindTooltip('I-95 — the Connecticut run');

  // City dots + the Stratford star.
  I95_WAYPOINTS.forEach(([name, lat, lon]) => {
    if (name === 'Stratford') {
      L.circleMarker([lat, lon], { radius: 8, color: '#FFCB05', fillColor: '#FFCB05',
        fillOpacity: 1 }).addTo(_roadMap).bindTooltip('Stratford — home');
    } else {
      L.circleMarker([lat, lon], { radius: 3.5, color: '#8b949e', fillColor: '#0b0e13',
        fillOpacity: 1, weight: 2 }).addTo(_roadMap).bindTooltip(name);
    }
  });

  // Incidents: real coordinates when Waze gave them, else nearest city match.
  (d.incidents || []).forEach(inc => {
    let lat = inc.lat, lon = inc.lon;
    if (lat == null || lon == null) {
      const w = (inc.where || '').toLowerCase();
      const hit = I95_WAYPOINTS.find(([n]) => w.includes(n.toLowerCase().split(' ')[0]));
      if (hit) { lat = hit[1]; lon = hit[2]; }
    }
    if (lat == null) return;
    L.circleMarker([lat, lon], { radius: 7, color: '#0a0f0a', weight: 1.5,
      fillColor: /jam/i.test(inc.kind) ? '#ff9f43' : '#ff6b6b', fillOpacity: 0.95 })
      .addTo(_roadMap)
      .bindPopup(`<b>${inc.kind}</b>${inc.detail ? ' · ' + inc.detail : ''}<br>${inc.where || ''}`);
  });
  setTimeout(() => { if (_roadMap) _roadMap.invalidateSize(); }, 80);
}

function _driveGrid(list) {
  return '<div class="rec-grid">' + (list || []).map(c => {
    const delay = c.delay_min > 0
      ? `<span style="color:#ff6b6b;font-weight:bold;"> +${c.delay_min}</span>` : '';
    const val = c.minutes == null ? '—'
      : c.minutes >= 90 ? `${Math.floor(c.minutes / 60)}h ${c.minutes % 60}m` : `${c.minutes} min`;
    return `<div class="rec-card">
        <div class="rec-title">${c.name}</div>
        <div class="rec-value">${val}${delay}</div>
        <div class="rec-sub">${c.miles ? c.miles + ' mi' : ''}${c.live ? ' · live' : c.minutes != null ? ' · typical' : ''}</div>
      </div>`;
  }).join('') + '</div>';
}

function renderRoad(d) {
  const el = document.getElementById('road-content');
  if (!el) return;
  const sub = document.getElementById('road-sub');
  if (sub) sub.textContent = d.live_traffic
    ? 'Live traffic (TomTom)' : 'Typical times (TomTom key in /admin unlocks live)';
  const scanBtn = document.getElementById('scanner-btn');
  if (scanBtn) scanBtn.style.display = d.scanner_url ? '' : 'none';
  window._scannerUrl = d.scanner_url || '';

  let html = `<div class="dex-section-title">Drive Times — FROM home</div>`;
  html += _driveGrid(d.commutes_to);
  html += `<div class="dex-section-title">Getting HOME — the drive back</div>`;
  html += _driveGrid(d.commutes_from);

  // --- Train vs Car ---
  if ((d.train_vs_car || []).length) {
    html += `<div class="dex-section-title">Train vs Car</div><div class="rec-grid">`;
    d.train_vs_car.forEach(t => {
      const haveBoth = t.train_min != null && t.car_min != null;
      const trainWins = haveBoth && t.train_min <= t.car_min;
      html += `<div class="rec-card" style="${haveBoth ? `border-color:${trainWins ? '#4ade80' : '#ff9f43'};` : ''}">
          <div class="rec-title">${t.name}</div>
          <div class="rec-value" style="font-size:15px;">
            &#128646; ${t.train_min != null ? t.train_min + 'm' : '—'} &nbsp;vs&nbsp; &#128663; ${t.car_min != null ? t.car_min + 'm' : '—'}
          </div>
          <div class="rec-sub">${haveBoth ? (trainWins ? 'TRAIN wins' : 'car wins') : ''}${t.train_depart ? ' · next train ' + fmtTimeEST(t.train_depart) : ''}</div>
        </div>`;
    });
    html += `</div>`;
  }

  if ((d.incidents || []).length) {
    html += `<div class="dex-section-title">Accidents · Construction · Detours</div>` +
      d.incidents.slice(0, 12).map(i => `<div class="atmo-line">
          <span><b style="color:${/jam/i.test(i.kind) ? '#ff9f43' : '#ff6b6b'};">${i.kind}</b>${i.detail ? ' · ' + i.detail : ''}
            ${i.src ? `<span style="font-size:9px;color:var(--text-dim);border:1px solid #444;border-radius:4px;padding:0 4px;margin-left:5px;vertical-align:middle;">${i.src}</span>` : ''}</span>
          <b style="font-weight:normal;color:var(--text-dim);">${i.where || ''}</b></div>`).join('');
  }

  if ((d.nyc_speeds || []).length) {
    html += `<div class="dex-section-title">Into the City — NYC highway speeds</div>` +
      d.nyc_speeds.map(s => {
        const color = s.mph < 20 ? '#ff6b6b' : s.mph < 40 ? '#ff9f43' : 'var(--accent-green, #4ade80)';
        return `<div class="atmo-line"><span>${s.name}</span><b style="color:${color};">${s.mph} mph</b></div>`;
      }).join('');
  }

  if ((d.news || []).length) {
    html += `<div class="dex-section-title">Road News</div>` +
      d.news.map(n => `<div class="atmo-line"><span>${n.title}</span>
        <b style="font-weight:normal;color:var(--text-dim);white-space:nowrap;">${n.date ? n.date.slice(0, 11) : ''}</b></div>`).join('');
  }

  // --- The live corridor map anchors the bottom of the view ---
  html += `<div class="dex-section-title">The Corridor — Live</div>
    <div id="roadmap"></div>
    <div class="board-note" style="margin:4px 0 6px;">I-95, Bronx to New Haven · NYC approach colored by
      real DOT speeds · red dots = incidents (tap them) · gold star = home</div>`;

  if (!d.scanner_url) {
    html += `<div class="board-note" style="margin-top:8px;">Want highway chatter? Paste a Broadcastify stream URL
      (CT State Police Troop G covers I-95 here) into /admin → Road, and a Scanner button appears up top.</div>`;
  }
  el.innerHTML = html;
  _buildRoadMap(d);   // the innerHTML swap recreated #roadmap — mount the live map
}

function toggleScanner() {
  const audio = document.getElementById('scanner-audio');
  const label = document.getElementById('scanner-label');
  if (!audio) return;
  if (!audio.paused) {
    audio.pause(); audio.removeAttribute('src'); audio.load();
    if (label) label.textContent = 'Scanner';
    return;
  }
  const url = window._scannerUrl || '';
  if (!url) { showToast('Set a scanner stream URL in /admin → Road'); return; }
  audio.src = url + (url.includes('?') ? '&' : '?') + 'nocache=' + Date.now();
  audio.volume = getVolume();
  audio.play().then(() => { if (label) label.textContent = 'LIVE'; })
    .catch(() => showToast('Scanner stream unavailable — check the URL in /admin'));
}

// ============================================
// RAIL HISTORY VIEW — timeline + GCT time + news
// ============================================
const RAIL_HISTORY = [
  ['1848', 'The line arrives', 'The New York & New Haven Railroad lays tracks along the coast, linking the shoreline towns to Manhattan for the first time. Farms become commuter suburbs within a generation.'],
  ['1870s', 'The trolley era', 'Horse-drawn (then electric) trolleys spider out from the harbor cities toward the beach neighborhoods. The great trolley network peaks around 1910, then buses eat it alive by the 1930s.'],
  ['1907', 'Wires go up', 'The New Haven Railroad electrifies the main line with 11 kV overhead catenary — among the first mainline electrifications on Earth. Some of the original gantries still stand.'],
  ['1905', 'The Devon bridge', 'The swing-span railroad bridge over the Housatonic at Devon opens. 120 years later it still pivots for boat traffic — and still occasionally gets stuck, stopping every train on the line.'],
  ['1950s', 'The McGinnis look', 'President Patrick McGinnis gives the New Haven its famous black-orange-white "NH" logo. The railroad goes bankrupt anyway (twice), but the logo lives on Metro-North heritage cars.'],
  ['1969-71', 'Collapse and rescue', 'The New Haven is absorbed into Penn Central, which promptly implodes in the biggest bankruptcy in US history to that point. Amtrak (1971) takes intercity trains; the states take the commuter runs.'],
  ['1983', 'Metro-North is born', 'MTA Metro-North Railroad takes over the New Haven Line. Connecticut and New York split the bills — which is why CT trains wear the old New Haven colors.'],
  ['2000', 'Acela arrives', 'America\'s first high-speed service begins blasting along the shoreline. The catenary from 1907 had to be completely rebuilt to handle it.'],
  ['2011', 'The M8 era', 'Kawasaki\'s red-doored M8s replace 40-year-old cars, and the New Haven Line becomes the busiest commuter line in America.'],
  ['2025', 'Next generation', 'New Avelia Liberty Acelas enter service, and Amtrak\'s Airo trainsets are next. The 1848 right-of-way keeps getting faster.'],
];

// Metro-North official line colors.
const MNR_LINE_COLORS = { Hudson: '#009B3A', Harlem: '#0039A6', 'New Haven': '#EE0034' };

async function fetchLandHistory() {
  const el = document.getElementById('history-content');
  if (!el) return;
  let gct = { board: [], to_gct: null, from_gct: null }, news = [];
  try {
    const d = await (await fetch('/api/land/history')).json();
    gct = d.gct || gct; news = d.news || [];
  } catch (e) {}

  // Two-column at 1080p: content left, live map right (half the screen).
  // Stacks map-on-top at smaller sizes.
  let html = `<div class="gct-layout"><div class="gct-main">`;

  // --- Stratford <-> GCT, both directions (top of the view) ---
  html += `<div class="board-cols">`;
  html += `<div class="fc-record" style="margin:0;">
      <div class="fc-record-title">Stratford &#8594; Grand Central</div>
      ${gct.to_gct
        ? `<div class="fc-record-vals"><span>Departs <b style="color:var(--accent-yellow);">${fmtTimeEST(gct.to_gct.epoch)}</b></span>
           <span>Ride <b style="color:var(--accent-blue);">${gct.to_gct.gct_minutes} min</b></span></div>`
        : '<div class="atmo-sub">No more trains today.</div>'}
    </div>`;
  html += `<div class="fc-record" style="margin:0;">
      <div class="fc-record-title">Grand Central &#8594; Stratford</div>
      ${gct.from_gct
        ? `<div class="fc-record-vals"><span>Leaves GCT <b style="color:var(--accent-yellow);">${fmtTimeEST(gct.from_gct.gct_depart)}</b></span>
           <span>Home by <b style="color:var(--accent-green,#4ade80);">${fmtTimeEST(gct.from_gct.epoch)}</b></span></div>`
        : '<div class="atmo-sub">No more trains home today — hotel time.</div>'}
    </div>`;
  html += `</div>`;

  // --- All-lines departure board out of GCT ---
  if ((gct.board || []).length) {
    html += `<div class="dex-section-title">Departing the Terminal — all lines</div>
      <div class="board-col">` +
      gct.board.map(t => {
        const c = MNR_LINE_COLORS[t.line] || '#888';
        return `<div class="board-row" onclick="openTrain('M8')" style="cursor:pointer;">
            <span class="board-time">${fmtTimeEST(t.epoch)}</span>
            <span class="board-ident"><span class="line-dot" style="background:${c};"></span>${t.line}</span>
            <span class="board-detail">${t.headsign || ''}</span>
            <span class="board-status st-sched">${t.train_num ? '#' + t.train_num : 'MNR'}</span>
          </div>`;
      }).join('') + `</div>`;
  }

  // --- Subway connections at GCT ---
  html += `<div class="dex-section-title">Connections at Grand Central</div>
    <div class="subway-row">
      <span class="sub-bullet" style="background:#00933C;">4</span>
      <span class="sub-bullet" style="background:#00933C;">5</span>
      <span class="sub-bullet" style="background:#00933C;">6</span>
      <span class="sub-bullet" style="background:#B933AD;">7</span>
      <span class="sub-bullet" style="background:#808183;">S</span>
      <span class="atmo-sub">Lexington Ave lines · Flushing line · Times Square Shuttle — plus LIRR downstairs at Grand Central Madison</span>
    </div>`;

  if (news.length) {
    html += `<div class="dex-section-title">Metro-North in the News</div>`;
    html += news.map(n => `<div class="atmo-line"><span>${n.title}</span>
      <b style="font-weight:normal;color:var(--text-dim);white-space:nowrap;">${n.date ? n.date.slice(0, 11) : ''}</b></div>`).join('');
  }

  // --- The timeline stays (it's good!) ---
  html += `<div class="dex-section-title">The Line Through Time</div>`;
  html += RAIL_HISTORY.map(([era, title, text]) => `
    <div class="hist-card">
      <div class="hist-era">${era}</div>
      <div class="hist-body"><b>${title}</b><p>${text}</p></div>
    </div>`).join('');

  // Close the content column; the map takes the other half (sticky at 1080p).
  html += `</div><div class="gct-side">
      <div id="gctmap"></div>
      <div class="board-note" style="margin:4px 0 2px;">Tap any station for the trip from Stratford ·
        filled dots are live trains (30s refresh) · gold star = home</div>
    </div></div>`;

  el.innerHTML = html;
  // The innerHTML swap destroyed any previous map's container — rebuild it.
  _buildTrainMap('gctmap', 9);
}
