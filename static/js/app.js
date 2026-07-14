/**
 * SkyDex Kiosk Frontend
 * Single-page app: contacts list, Planedex, stats, empty state.
 * Pings API every 2s for live aircraft. Touch-optimized for 1024x600.
 */

// ── State ──
const state = {
  view: 'contacts',        // 'contacts' | 'dex' | 'stats'
  contacts: [],
  dexList: [],
  stats: null,
  weather: null,
  facts: [],
  factIndex: 0,
  lastContactCount: 0,
};

const POLL_INTERVAL = 2000;   // ms
const FACT_INTERVAL = 15000;  // ms

// ── Clock ──
function updateClock() {
  const now = new Date();
  const el = document.getElementById('clock');
  if (el) {
    el.textContent = now.toLocaleTimeString('en-US', {
      hour: 'numeric', minute: '2-digit', hour12: true,
    });
  }
  const dateEl = document.getElementById('date');
  if (dateEl) {
    dateEl.textContent = now.toLocaleDateString('en-US', {
      weekday: 'short', month: 'short', day: 'numeric',
    });
  }
}
setInterval(updateClock, 1000);
updateClock();

// ── Weather ──
async function fetchWeather() {
  try {
    const res = await fetch('/api/weather');
    const data = await res.json();
    state.weather = data;
    renderWeather();
  } catch (e) {
    console.debug('Weather fetch failed:', e);
  }
}

function renderWeather() {
  const el = document.getElementById('weather');
  if (!el || !state.weather) return;
  const w = state.weather;
  const parts = [];
  if (w.temp_f != null) parts.push(`<span class="temp">${Math.round(w.temp_f)}F</span>`);
  if (w.condition) parts.push(`<span class="cond">${w.condition}</span>`);
  if (w.wind_speed) parts.push(`Wind ${w.wind_speed}`);
  if (w.wind_direction) parts.push(w.wind_direction);
  if (w.humidity_pct != null) parts.push(`${Math.round(w.humidity_pct)}% humidity`);
  el.innerHTML = parts.join(' <span style="color:var(--text-faint)">|</span> ') || 'Weather unavailable';
}

// ── Contacts ──
async function fetchContacts() {
  try {
    const res = await fetch('/api/contacts');
    state.contacts = await res.json();
    if (state.view === 'contacts') renderContacts();
  } catch (e) {
    console.debug('Contacts fetch failed:', e);
  }
}

function renderContacts() {
  const listEl = document.getElementById('contact-list');
  const emptyEl = document.getElementById('empty-state');
  if (!listEl || !emptyEl) return;

  if (state.contacts.length === 0) {
    listEl.style.display = 'none';
    emptyEl.style.display = 'flex';
    renderEmptyState();
    return;
  }

  listEl.style.display = 'flex';
  emptyEl.style.display = 'none';

  listEl.innerHTML = state.contacts.map(ac => {
    // Determine icon class
    const types = ac.types || [];
    const hasRotor = types.some(t => t.type === 'Rotor');
    const hasMil = types.some(t => t.type === 'Sentinel');
    const hasHeavy = types.some(t => t.type === 'Heavy');
    const iconClass = hasRotor ? 'rotor' : hasMil ? 'mil' : hasHeavy ? 'heavy' : 'jet';
    const iconLetter = hasRotor ? 'R' : hasMil ? 'M' : hasHeavy ? 'H' : 'J';

    // Altitude display
    let altStr = '--';
    if (ac.altitude != null) {
      altStr = `${Math.round(ac.altitude).toLocaleString()}ft`;
    }

    // Speed
    const speedStr = ac.ground_speed ? `${Math.round(ac.ground_speed)}kt` : '';

    // Distance
    const distStr = ac.distance_miles ? `${ac.distance_miles.toFixed(1)}mi` : '';

    // Badges
    const badges = [];
    if (ac.contrail_likely) badges.push('<span class="badge-chip contrail">Contrail</span>');
    if (ac.shiny) badges.push('<span class="badge-chip shiny">Shiny</span>');
    if (ac.dex_number) badges.push(`<span class="badge-chip dex">#${ac.dex_number}</span>`);

    // Route
    const routeParts = [];
    if (ac.origin_icao) routeParts.push(ac.origin_icao);
    if (ac.dest_icao) routeParts.push(ac.dest_icao);
    const routeStr = routeParts.length === 2 ? `${routeParts[0]} → ${routeParts[1]}` : '';

    return `
      <div class="contact-row" onclick="openDex('${ac.hex}')">
        <div class="type-icon ${iconClass}">${iconLetter}</div>
        <div class="info">
          <div class="callsign">${ac.callsign || ac.hex} ${badges.join('')}</div>
          <div class="model">${ac.model || ac.type_code || 'Unknown'} ${ac.operator ? '— ' + ac.operator : ''}</div>
          <div class="route">${routeStr}</div>
        </div>
        <div class="metrics">
          <div class="alt">${altStr}</div>
          <div class="speed">${speedStr}</div>
          <div class="dist">${distStr}</div>
        </div>
      </div>
    `;
  }).join('');
}

// ── Empty State ──
async function fetchFacts() {
  try {
    const res = await fetch('/api/facts?n=3');
    state.facts = await res.json();
    state.factIndex = 0;
  } catch (e) {
    state.facts = ['Scanning the skies over Stratford...'];
  }
}

async function fetchTopRegulars() {
  try {
    const res = await fetch('/api/dex?sort=detection_count&limit=3');
    const data = await res.json();
    const container = document.getElementById('top-regulars');
    if (!container) return;
    if (data.length === 0) {
      container.innerHTML = '<span style="color:var(--text-faint); font-size:12px">No regulars yet. The sky awaits.</span>';
      return;
    }
    container.innerHTML = data.map(a => `
      <div class="regular-card" onclick="openDex('${a.hex}')">
        <div class="count">${a.detection_count}</div>
        <div class="label">${a.registration || a.hex}</div>
        <div class="label" style="font-size:10px">${a.model || 'Unknown'}</div>
      </div>
    `).join('');
  } catch (e) {
    console.debug('Top regulars fetch failed:', e);
  }
}

function renderEmptyState() {
  const factEl = document.getElementById('fact-rotate');
  if (!factEl || state.facts.length === 0) return;
  factEl.style.opacity = '0';
  setTimeout(() => {
    factEl.textContent = state.facts[state.factIndex % state.facts.length];
    factEl.style.opacity = '1';
    state.factIndex++;
  }, 250);
}

// ── Planedex View ──
async function fetchDex() {
  try {
    const res = await fetch('/api/dex?sort=detection_count&limit=100');
    state.dexList = await res.json();
    if (state.view === 'dex') renderDexList();
  } catch (e) {
    console.debug('Dex fetch failed:', e);
  }
}

function renderDexList() {
  const content = document.getElementById('main-content');
  if (!content) return;
  content.innerHTML = '<div class="contact-list" id="dex-list"></div>';
  const listEl = document.getElementById('dex-list');

  if (state.dexList.length === 0) {
    listEl.innerHTML = '<p style="color:var(--text-dim); text-align:center; margin-top:40px">No aircraft collected yet. Wait for one to fly by!</p>';
    return;
  }

  listEl.innerHTML = state.dexList.map(a => {
    const tierColors = {
      Spotted: 'var(--text-dim)',
      Tracked: 'var(--ok)',
      Tagged: 'var(--accent)',
      Bonded: 'var(--warn)',
    };
    const tierColor = tierColors[a.evolution_tier || 'Spotted'] || 'var(--text-dim)';

    return `
      <div class="contact-row" onclick="openDex('${a.hex}')">
        <div class="type-icon unknown" style="font-size:14px">#${a.dex_number || '?'}</div>
        <div class="info">
          <div class="callsign">${a.registration || a.hex}
            <span class="badge-chip dex">${a.detection_count}x</span>
          </div>
          <div class="model">${a.model || 'Unknown'} ${a.operator ? '— ' + a.operator : ''}</div>
        </div>
        <div class="metrics">
          <span class="meta-chip rarity-${a.rarity || 'Common'}" style="font-size:11px">${a.rarity || 'Common'}</span>
          <div style="color:${tierColor}; font-size:11px; margin-top:2px">${a.evolution_tier || 'Spotted'}</div>
        </div>
      </div>
    `;
  }).join('');
}

// ── Stats View ──
async function fetchStats() {
  try {
    const res = await fetch('/api/stats');
    state.stats = await res.json();
    if (state.view === 'stats') renderStats();
  } catch (e) {
    console.debug('Stats fetch failed:', e);
  }
}

function renderStats() {
  const content = document.getElementById('main-content');
  if (!content || !state.stats) return;

  const s = state.stats;
  content.innerHTML = `
    <div style="padding:12px 16px">
      <h2 style="font-size:20px; margin-bottom:12px; color:var(--accent)">SkyDex Stats</h2>

      <div style="display:flex; gap:12px; margin-bottom:16px; flex-wrap:wrap">
        <div class="regular-card" style="min-width:140px">
          <div class="count" style="font-size:28px">${s.total_airframes || 0}</div>
          <div class="label">Airframes Collected</div>
        </div>
        <div class="regular-card" style="min-width:140px">
          <div class="count" style="font-size:28px">${s.total_detections || 0}</div>
          <div class="label">Total Detections</div>
        </div>
        <div class="regular-card" style="min-width:140px">
          <div class="count" style="font-size:28px; color:var(--ok)">${s.live_contacts || 0}</div>
          <div class="label">In Range Now</div>
        </div>
      </div>

      ${s.top_airframe ? `
        <div class="dex-section">
          <h3>Most-Seen Regular</h3>
          <p style="font-size:16px; color:var(--text)">
            #${s.top_airframe.dex_number || '?'} ${s.top_airframe.registration || s.top_airframe.hex}
            — <span style="color:var(--accent)">${s.top_airframe.detection_count} detections</span>
          </p>
          <p style="font-size:13px; color:var(--text-dim)">${s.top_airframe.model || ''}</p>
        </div>
      ` : ''}

      <div class="dex-section">
        <h3>Location</h3>
        <p style="font-size:14px; color:var(--text-dim)">
          ${s.location?.name || 'Stratford, CT'}<br>
          ${s.location?.airport || 'KBDR'} (${s.location?.icao || ''})<br>
          ${s.location?.lat?.toFixed(4) || ''}, ${s.location?.lon?.toFixed(4) || ''}
        </p>
      </div>
    </div>
  `;
}

// ── Navigation ──
function showView(view) {
  state.view = view;

  // Update nav buttons
  document.querySelectorAll('.bottom-nav button').forEach(btn => btn.classList.remove('active'));
  const navBtn = document.getElementById(`nav-${view}`);
  if (navBtn) navBtn.classList.add('active');

  // Restore main content container
  const content = document.getElementById('main-content');
  if (!content) return;

  if (view === 'contacts') {
    content.innerHTML = `
      <div id="contact-list" class="contact-list" style="display:none"></div>
      <div id="empty-state" class="empty-state" style="display:none">
        <div class="sky-icon">&#9729;</div>
        <h2>No contacts in range</h2>
        <p class="fact-rotate" id="fact-rotate">Scanning...</p>
        <div class="top-regulars" id="top-regulars"></div>
      </div>
    `;
    if (state.contacts.length > 0) renderContacts();
    else { renderEmptyState(); fetchTopRegulars(); }
  } else if (view === 'dex') {
    renderDexList();
  } else if (view === 'stats') {
    renderStats();
  }
}

function openDex(hex) {
  window.location.href = `/dex/${hex}`;
}

// ── Polling ──
function tick() {
  fetchContacts();
  if (state.view === 'stats') fetchStats();
}

// ── Init ──
async function init() {
  await fetchWeather();
  await fetchFacts();
  await fetchContacts();
  await fetchDex();
  await fetchStats();

  // Start polling
  setInterval(tick, POLL_INTERVAL);
  setInterval(fetchWeather, 60000);       // Every minute
  setInterval(renderEmptyState, FACT_INTERVAL);  // Rotate facts
}

init();
