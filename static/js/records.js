/* SkyDex records.js — Hall of Fame (records + achievements), weekly almanac,
 * and the Professor's Quiz. Loads after pokedex.js + controls.js. */

// ============================================
// ACHIEVEMENT CELEBRATIONS — unlocks get a MOMENT (banner + confetti + voice).
// First run baselines silently so 30 already-earned badges don't spam.
// ============================================
const ACH_SEEN_KEY = 'skydex_ach_seen';
let _achQueue = [];
let _achShowing = false;

async function achievementWatch() {
  let unlocked;
  try {
    const list = await (await fetch('/api/achievements')).json();
    unlocked = (Array.isArray(list) ? list : (list.achievements || []))
      .filter(a => a.unlocked);
  } catch (e) { return; }
  let seen;
  try { seen = JSON.parse(localStorage.getItem(ACH_SEEN_KEY)); } catch (e) { seen = null; }
  if (!Array.isArray(seen)) {
    // First run: everything already earned is old news.
    localStorage.setItem(ACH_SEEN_KEY, JSON.stringify(unlocked.map(a => a.id)));
  } else {
    const fresh = unlocked.filter(a => !seen.includes(a.id));
    if (fresh.length) {
      localStorage.setItem(ACH_SEEN_KEY, JSON.stringify(unlocked.map(a => a.id)));
      _achQueue.push(...fresh);
    }
  }
  await challengeWatch();
  _achNext();
}

// Challenge completions celebrate too — ids carry the date/week key, so
// tomorrow's re-earn of the same challenge celebrates again (as it should).
const CHAL_SEEN_KEY = 'skydex_chal_seen';

async function challengeWatch() {
  let done;
  try {
    const d = await (await fetch('/api/challenges')).json();
    done = (d.daily || []).map(c => ({ ...c, _kicker: 'DAILY CHALLENGE COMPLETE' }))
      .concat((d.weekly || []).map(c => ({ ...c, _kicker: 'WEEKLY CHALLENGE COMPLETE' })))
      .filter(c => c.unlocked);
  } catch (e) { return; }
  let seen;
  try { seen = JSON.parse(localStorage.getItem(CHAL_SEEN_KEY)); } catch (e) { seen = null; }
  if (!Array.isArray(seen)) {
    localStorage.setItem(CHAL_SEEN_KEY, JSON.stringify(done.map(c => c.id)));
    return;
  }
  const fresh = done.filter(c => !seen.includes(c.id));
  if (!fresh.length) return;
  localStorage.setItem(CHAL_SEEN_KEY,
    JSON.stringify(seen.concat(fresh.map(c => c.id)).slice(-80)));
  fresh.forEach(c => _achQueue.push({
    id: c.id, title: c.title, description: c.description,
    icon: c._kicker.indexOf('DAILY') === 0 ? 'DAY' : 'WEEK',
    domain: c.domain, _kicker: c._kicker,
  }));
}

function _achNext() {
  if (_achShowing || !_achQueue.length) return;
  _achShowing = true;
  const a = _achQueue.shift();
  const overlay = document.createElement('div');
  overlay.className = 'ach-party';
  overlay.innerHTML =
    Array.from({ length: 24 }, (_, i) =>
      `<span class="confetti" style="left:${4 + Math.random() * 92}%;animation-delay:${(Math.random() * 0.9).toFixed(2)}s;background:${['#FFD700', '#30A7D7', '#4ade80', '#ff6b9d', '#ff9f43', '#7859c4'][i % 6]};"></span>`).join('') +
    `<div class="ach-party-card">
       <div class="ach-party-kicker">${a._kicker || 'ACHIEVEMENT UNLOCKED'}</div>
       <div class="ach-party-icon ach-${a.domain}">${a.icon}</div>
       <div class="ach-party-title">${a.title}</div>
       <div class="ach-party-desc">${a.description}</div>
     </div>`;
  document.body.appendChild(overlay);
  if (window.SkyDexAudio && SkyDexAudio.playCatchJingle) {
    try { SkyDexAudio.playCatchJingle(); } catch (e) {}
  }
  fetch('/api/admin/say', { method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text: (a._kicker ? a._kicker.toLowerCase().replace(' complete', '') + ' complete: '
      : 'Achievement unlocked: ') + a.title + '!' }) }).catch(() => {});
  setTimeout(() => {
    overlay.classList.add('ach-party-out');
    setTimeout(() => { overlay.remove(); _achShowing = false; _achNext(); }, 500);
  }, 4500);
}

// Check shortly after boot, then every 5 minutes.
setTimeout(achievementWatch, 20000);
setInterval(achievementWatch, 300000);

// ============================================
// HALL OF FAME
// ============================================
function openRecords() {
  if (window.SkyDexAudio && SkyDexAudio.playBeep) SkyDexAudio.playBeep();
  showView('records');
  loadRecords();
}

function _recDate(epoch) {
  if (!epoch) return '—';
  return new Date(epoch * 1000).toLocaleDateString('en-US',
    { month: 'short', day: 'numeric', year: 'numeric', timeZone: EST_TZ });
}

function _recCard(title, entry, fmtValue, sub, onclick) {
  if (!entry) return '';
  const click = onclick ? ` onclick="${onclick}" style="cursor:pointer;"` : '';
  return `<div class="rec-card"${click}>
      <div class="rec-title">${title}</div>
      <div class="rec-value">${fmtValue}</div>
      <div class="rec-sub">${sub || ''}</div>
    </div>`;
}

async function loadRecords() {
  const el = document.getElementById('records-content');
  try {
    const [rec, ach, chal] = await Promise.all([
      (await fetch('/api/records')).json(),
      (await fetch('/api/achievements')).json(),
      (await fetch('/api/challenges')).json().catch(() => null),
    ]);
    renderRecords(rec, ach, chal);
  } catch (e) {
    el.innerHTML = '<div class="ds-empty">Could not load records.</div>';
  }
}

function _chalRow(c) {
  const pct = Math.round(100 * c.progress / c.threshold);
  return `<div class="chal-row ${c.unlocked ? 'done' : ''}">
      <div class="chal-main">
        <b>${c.title}</b><span>${c.description}</span>
        <div class="chal-bar"><i style="width:${pct}%"></i></div>
      </div>
      <div class="chal-right">${c.unlocked ? '&#127881;' : c.progress + '/' + c.threshold}</div>
    </div>`;
}

function renderRecords(rec, achievements, chal) {
  const el = document.getElementById('records-content');
  const a = rec.air || {}, s = rec.sea || {};
  const ident = (e) => e ? (e.callsign || e.registration || e.name || e.hex || e.mmsi || '') : '';

  let html = '';
  // --- Daily & weekly challenges (self-resetting) ---
  if (chal && (chal.daily || []).length) {
    html += `<div class="dex-section-title">&#9889; Today's Challenges <span class="atmo-sub">— new ones at midnight</span></div>`
      + chal.daily.map(_chalRow).join('')
      + `<div class="dex-section-title" style="margin-top:10px;">&#128197; This Week <span class="atmo-sub">— resets Sunday</span></div>`
      + chal.weekly.map(_chalRow).join('');
  }

  html += `<div class="dex-section-title">Air Records</div><div class="rec-grid">`;
  if (a.fastest) html += _recCard('Fastest', a.fastest,
    `${Math.round(a.fastest.value)} kn`,
    `${ident(a.fastest)} · ${a.fastest.model || ''} · ${_recDate(a.fastest.timestamp)}`,
    `openDex('${a.fastest.hex}')`);
  if (a.highest) html += _recCard('Highest', a.highest,
    `${Math.round(a.highest.value).toLocaleString()} ft`,
    `${ident(a.highest)} · ${a.highest.model || ''}`, `openDex('${a.highest.hex}')`);
  if (a.closest) html += _recCard('Closest Pass', a.closest,
    `${a.closest.value.toFixed(2)} mi`,
    `${ident(a.closest)} · ${a.closest.model || ''}`, `openDex('${a.closest.hex}')`);
  if (a.most_seen) html += _recCard('Most Seen', a.most_seen,
    `${a.most_seen.value}× sightings`,
    `${ident(a.most_seen)} · ${a.most_seen.model || ''}`, `openDex('${a.most_seen.hex}')`);
  if (a.oldest) html += _recCard('Oldest Airframe', a.oldest,
    `Built ${a.oldest.value}`,
    `${ident(a.oldest)} · ${a.oldest.model || ''}`, `openDex('${a.oldest.hex}')`);
  if (a.first_catch) html += _recCard('First Ever Catch', a.first_catch,
    _recDate(a.first_catch.value),
    `${ident(a.first_catch)} · ${a.first_catch.model || ''}`, `openDex('${a.first_catch.hex}')`);
  if (a.busiest_day) html += _recCard('Busiest Day', a.busiest_day,
    `${a.busiest_day.value} sightings`, a.busiest_day.day);
  if (a.longest_visit) html += _recCard('Longest Visit', a.longest_visit,
    `${Math.round(a.longest_visit.value / 60)} min`,
    `${ident(a.longest_visit)} · ${a.longest_visit.model || ''} circling overhead`,
    `openDex('${a.longest_visit.hex}')`);
  html += _recCard('Military Logged', {}, `${a.military_count || 0}`, 'aircraft');
  html += _recCard('Emergencies Seen', {}, `${a.emergencies || 0}`, 'squawk 7x00 events');
  html += `</div>`;

  html += `<div class="dex-section-title">Sea Records</div><div class="rec-grid">`;
  if (s.longest) html += _recCard('Biggest Vessel', s.longest,
    `${Math.round(s.longest.value)} m`,
    `${ident(s.longest)} · ${s.longest.category || ''}`, `openVessel('${s.longest.mmsi}')`);
  if (s.most_seen) html += _recCard('Most Seen', s.most_seen,
    `${s.most_seen.value}× sightings`,
    `${ident(s.most_seen)} · ${s.most_seen.category || ''}`, `openVessel('${s.most_seen.mmsi}')`);
  if (s.closest) html += _recCard('Closest Approach', s.closest,
    `${s.closest.value.toFixed(2)} mi`,
    `${ident(s.closest)} · ${s.closest.category || ''}`, `openVessel('${s.closest.mmsi}')`);
  if (s.first_catch) html += _recCard('First Ever Catch', s.first_catch,
    _recDate(s.first_catch.value), `${ident(s.first_catch)}`, `openVessel('${s.first_catch.mmsi}')`);
  if (s.busiest_day) html += _recCard('Busiest Day', s.busiest_day,
    `${s.busiest_day.value} sightings`, s.busiest_day.day);
  html += _recCard('Flags Collected', {}, `${s.flag_count || 0}`, 'countries');
  html += _recCard('Superyachts', {}, `${s.superyachts || 0}`, 'spotted');
  html += `</div>`;

  const rl = rec.rail || {};
  if (rl.total || rl.fastest) {
    html += `<div class="dex-section-title">Rail Records</div><div class="rec-grid">`;
    if (rl.fastest) html += _recCard('Fastest Train', rl.fastest,
      `${Math.round(rl.fastest.value)} mph`,
      `${rl.fastest.route || 'Amtrak'} #${rl.fastest.train_num}`);
    if (rl.most_seen) html += _recCard('Most Caught', rl.most_seen,
      `${rl.most_seen.value}× passes`,
      `${rl.most_seen.route || 'Amtrak'} #${rl.most_seen.train_num}`);
    html += _recCard('Traindex Size', {}, `${rl.total || 0}`, 'train numbers collected');
    html += `</div>`;
  }

  window._achCache = achievements;   // for the tap-for-details popup
  // --- Family spotter leaderboard ---
  html += `<div class="dex-section-title">Spotter Leaderboard</div>`;
  if ((rec.spotters || []).length) {
    html += `<div class="rec-grid">`;
    rec.spotters.forEach((s, i) => {
      const medal = ['&#129351;', '&#129352;', '&#129353;'][i] || '&#11088;';
      html += `<div class="rec-card" ${i === 0 ? 'style="border-color:#FFD700;"' : ''}>
          <div class="rec-title">${medal} ${s.name}</div>
          <div class="rec-value">${s.catches}</div>
          <div class="rec-sub">rare catch${s.catches !== 1 ? 'es' : ''} called</div>
        </div>`;
    });
    html += `</div>`;
  } else {
    html += `<div class="board-note">No spotters credited yet! When something Epic or
      Legendary flies over, the kiosk asks &ldquo;Who spotted this?&rdquo; &mdash; whoever
      taps their name first gets the credit here. Medals for the top three.</div>`;
  }

  const unlocked = achievements.filter(x => x.unlocked).length;
  html += `<div class="dex-section-title">Achievements (${unlocked}/${achievements.length}) — tap one for details</div>
    <div class="ach-grid">`;
  achievements.forEach(x => {
    const pct = Math.round(100 * x.progress / x.threshold);
    html += `<div class="ach-chip ${x.unlocked ? 'unlocked' : ''} ach-${x.domain}"
        onclick="showAchievementInfo('${x.id}')" style="cursor:pointer;">
        <span class="ach-icon">${x.icon}</span>
        <span class="ach-body"><b>${x.title}</b><small>${x.description}</small>
          ${x.unlocked ? '' : `<span class="ach-bar"><span style="width:${pct}%"></span></span>`}
        </span>
        <span class="ach-count">${x.unlocked ? '&#10003;' : x.progress + '/' + x.threshold}</span>
      </div>`;
  });
  html += `</div>`;
  el.innerHTML = html;
}

// ============================================
// WEEKLY ALMANAC
// ============================================
function openAlmanac() {
  if (window.SkyDexAudio && SkyDexAudio.playBeep) SkyDexAudio.playBeep();
  showView('almanac');
  loadAlmanac();
}

async function loadAlmanac() {
  const el = document.getElementById('almanac-content');
  try {
    renderAlmanac(await (await fetch('/api/almanac')).json());
  } catch (e) {
    el.innerHTML = '<div class="ds-empty">Could not load the almanac.</div>';
  }
}

function _almBars(daily, color) {
  if (!daily || !daily.length) return '<div class="ds-empty">Nothing logged this week.</div>';
  const max = Math.max(...daily.map(d => d.sightings), 1);
  return '<div class="alm-bars">' + daily.map(d => {
    const h = Math.max(6, Math.round(64 * d.sightings / max));
    const dow = new Date(d.day + 'T12:00:00').toLocaleDateString('en-US', { weekday: 'short' });
    return `<div class="alm-col"><div class="alm-num">${d.sightings}</div>
      <div class="alm-bar" style="height:${h}px;background:${color};"></div>
      <div class="alm-dow">${dow}</div></div>`;
  }).join('') + '</div>';
}

function renderAlmanac(d) {
  const el = document.getElementById('almanac-content');
  const range = document.getElementById('almanac-range');
  if (range) range.textContent = `Last ${d.days || 7} days`;

  let html = `<div class="dex-section-title">Air — sightings per day</div>` +
    _almBars(d.daily_air, 'var(--accent-blue)');
  html += `<div class="dex-section-title">Sea — sightings per day</div>` +
    _almBars(d.daily_sea, 'var(--accent-green, #78C850)');

  if (d.week_fastest) {
    html += `<div class="dex-section-title">Fastest This Week</div>
      <div class="atmo-line" onclick="openDex('${d.week_fastest.hex}')" style="cursor:pointer;">
        <span>${d.week_fastest.callsign || d.week_fastest.registration || d.week_fastest.hex}
          · ${d.week_fastest.model || ''}</span>
        <b>${Math.round(d.week_fastest.value)} kn</b></div>`;
  }

  const newList = (items, isAir) => items.length
    ? items.slice(0, 12).map(x => `<div class="atmo-line"
        onclick="${isAir ? `openDex('${x.hex}')` : `openVessel('${x.mmsi}')`}" style="cursor:pointer;">
        <span>${isAir ? (x.registration || x.hex) : (x.name || 'MMSI ' + x.mmsi)}
          · ${isAir ? (x.model || '') : (x.category || '')}</span>
        <b>${(x.rarity || '').toLowerCase() === 'common' ? '' : (x.rarity || '')}</b></div>`).join('')
    : '<div class="ds-empty">None this week.</div>';

  html += `<div class="dex-section-title">New Aircraft (${(d.new_air || []).length})</div>` +
    newList(d.new_air || [], true);
  html += `<div class="dex-section-title">New Vessels (${(d.new_sea || []).length})</div>` +
    newList(d.new_sea || [], false);

  if ((d.top_operators || []).length) {
    html += `<div class="dex-section-title">Top Operators</div>` +
      d.top_operators.map(o => `<div class="atmo-line"><span>${o.name}</span><b>${o.c}×</b></div>`).join('');
  }
  if ((d.top_flags || []).length) {
    html += `<div class="dex-section-title">Top Vessel Flags</div>` +
      d.top_flags.map(o => `<div class="atmo-line"><span>${o.name}</span><b>${o.c}×</b></div>`).join('');
  }
  el.innerHTML = html;
}

// ============================================
// PROFESSOR'S QUIZ
// ============================================
let _quiz = { questions: [], idx: 0, score: 0, locked: false };

function openQuiz() {
  if (window.SkyDexAudio && SkyDexAudio.playBeep) SkyDexAudio.playBeep();
  showView('quiz');
  startQuiz();
}

async function startQuiz() {
  const el = document.getElementById('quiz-content');
  el.innerHTML = '<div class="ds-empty">Shuffling questions…</div>';
  try {
    _quiz = { questions: await (await fetch('/api/quiz?n=5')).json(), idx: 0, score: 0, locked: false };
    renderQuizQuestion();
  } catch (e) {
    el.innerHTML = '<div class="ds-empty">Quiz unavailable.</div>';
  }
}

function renderQuizQuestion() {
  const el = document.getElementById('quiz-content');
  const prog = document.getElementById('quiz-progress');
  const q = _quiz.questions[_quiz.idx];
  if (!q) return renderQuizDone();
  if (prog) prog.textContent = `Question ${_quiz.idx + 1} of ${_quiz.questions.length} · Score ${_quiz.score}`;
  const dom = { air: 'SkyDex', sea: 'SeaDex', atmo: 'AtmoDex' }[q.domain] || '';
  el.innerHTML = `
    <div class="quiz-card">
      <div class="quiz-domain">${dom}</div>
      <div class="quiz-q">${q.question}</div>
      <div class="quiz-opts">
        ${q.options.map((o, i) =>
          `<button class="quiz-opt" id="qopt-${i}" onclick="answerQuiz(${i})">${o}</button>`).join('')}
      </div>
    </div>`;
  _quiz.locked = false;
}

function answerQuiz(i) {
  if (_quiz.locked) return;
  _quiz.locked = true;
  const q = _quiz.questions[_quiz.idx];
  const right = i === q.answer;
  if (right) _quiz.score++;
  document.querySelectorAll('.quiz-opt').forEach((b, idx) => {
    if (idx === q.answer) b.classList.add('correct');
    else if (idx === i) b.classList.add('wrong');
    b.disabled = true;
  });
  if (window.SkyDexAudio && SkyDexAudio.playBeep) SkyDexAudio.playBeep();
  setTimeout(() => { _quiz.idx++; renderQuizQuestion(); }, 1400);
}

function renderQuizDone() {
  const el = document.getElementById('quiz-content');
  const n = _quiz.questions.length;
  const s = _quiz.score;
  const grade = s === n ? 'Perfect! Professor rank!' :
    s >= n - 1 ? 'Excellent spotter!' :
    s >= Math.ceil(n / 2) ? 'Nice work — keep watching the skies!' :
    'The Sound keeps its secrets… try again!';
  el.innerHTML = `
    <div class="quiz-card quiz-done">
      <div class="quiz-score">${s} / ${n}</div>
      <div class="quiz-grade">${grade}</div>
      <button class="day-summary-btn" onclick="startQuiz()">Play Again</button>
      <button class="day-summary-btn" onclick="showView('contacts')">Back to Live</button>
    </div>`;
}

// ============================================
// KBDR OPS BOARD (schedule + observed + tower)
// ============================================
function openKbdr() {
  if (window.SkyDexAudio && SkyDexAudio.playBeep) SkyDexAudio.playBeep();
  showView('kbdr');
  loadKbdr();
}

async function loadKbdr() {
  const el = document.getElementById('kbdr-content');
  try {
    renderKbdr(await (await fetch('/api/airport-board')).json());
  } catch (e) {
    el.innerHTML = '<div class="ds-empty">Board unavailable.</div>';
  }
}

function _boardTime(item) {
  if (item.source === 'observed' && item.time) return fmtTimeEST(item.time);
  if (item.time_local) return item.time_local.slice(11, 16) || item.time_local;
  return '--:--';
}

function _boardRows(items) {
  if (!items.length) return '<div class="board-empty">— none —</div>';
  const sched = items.filter(i => i.source === 'sched');
  const seen = items.filter(i => i.source === 'observed');
  const row = (i) => `
    <div class="board-row ${i.source}" ${i.hex ? `onclick="openDex('${i.hex}')" style="cursor:pointer;"` : ''}>
      <span class="board-time">${_boardTime(i)}</span>
      <span class="board-ident">${i.ident || '—'}</span>
      <span class="board-detail">${[i.model, i.other_airport].filter(Boolean).join(' · ') || i.airline || ''}</span>
      <span class="board-status ${i.source === 'observed' ? 'st-seen' : 'st-sched'}">${i.source === 'observed' ? 'SEEN' : (i.status || 'SCHED').toUpperCase().slice(0, 9)}</span>
    </div>`;
  let html = '';
  if (sched.length) html += sched.map(row).join('');
  if (seen.length) {
    if (sched.length) html += '<div class="board-divider">observed by SkyDex</div>';
    html += seen.slice(0, 12).map(row).join('');
  }
  return html;
}

function renderKbdr(d) {
  const el = document.getElementById('kbdr-content');
  const sub = document.getElementById('kbdr-sub');
  if (sub) sub.textContent =
    `${(d.arrivals || []).length} arrivals · ${(d.departures || []).length} departures · tap Tower to listen`;
  el.innerHTML = `
    <div class="board-cols">
      <div class="board-col">
        <div class="board-head">&#9660; ARRIVALS</div>
        ${_boardRows(d.arrivals || [])}
      </div>
      <div class="board-col">
        <div class="board-head">&#9650; DEPARTURES</div>
        ${_boardRows(d.departures || [])}
      </div>
    </div>
    <div class="board-note">Schedule refreshes a few times a day (AeroDataBox) ·
      "SEEN" rows are aircraft SkyDex actually tracked to/from the field</div>
    ${atcGuideHtml()}`;
}

// ============================================
// TOWER LISTENING GUIDE (KBDR board footer)
// ============================================
const _PHONETIC = [
  'A·Alpha', 'B·Bravo', 'C·Charlie', 'D·Delta', 'E·Echo', 'F·Foxtrot',
  'G·Golf', 'H·Hotel', 'I·India', 'J·Juliett', 'K·Kilo', 'L·Lima',
  'M·Mike', 'N·November', 'O·Oscar', 'P·Papa', 'Q·Quebec', 'R·Romeo',
  'S·Sierra', 'T·Tango', 'U·Uniform', 'V·Victor', 'W·Whiskey', 'X·X-ray',
  'Y·Yankee', 'Z·Zulu',
];

const _ATC_DECODER = [
  ['"Cleared for takeoff"', 'Permission to depart — engines up, here they go'],
  ['"Line up and wait"', 'Taxi onto the runway but hold — someone is still landing/departing'],
  ['"Cleared to land"', 'Permission to land'],
  ['"Cleared for the option"', 'May land OR do a touch-and-go — training flights doing laps'],
  ['"Touch and go"', 'Land and immediately take off again (watch the Trainers on Live!)'],
  ['"Go around"', 'Abort the landing! Climb and circle back — always worth watching'],
  ['"Enter left downwind, runway 24"', 'Pattern legs: upwind → crosswind → downwind → base → final'],
  ['"Hold short"', 'Stop before the runway edge line and wait'],
  ['"Squawk 1200"', 'Set the standard VFR transponder code — this is how SkyDex sees them'],
  ['"Ident"', 'Press the transponder button so the radar screen highlights you'],
  ['"Traffic, two o\'clock, three miles"', 'Another plane is that way — clock position from your nose'],
  ['"Say intentions"', '"What do you want to do?"'],
  ['"Roger" / "Wilco" / "Unable"', 'Understood / will comply / can\'t do that'],
  ['"Niner", "tree", "fife"', '9, 3, 5 — pronounced so numbers can\'t be misheard over radio'],
  ['Runway 24', 'Runways are named by compass heading ÷ 10 — 24 points ~240° (southwest)'],
  ['"Wind 240 at 10"', 'Wind FROM 240° at 10 knots — planes take off into the wind'],
  ['Squawk 7700 / 7600 / 7500', 'Emergency / lost radio / hijack — SkyDex flags these automatically'],
];

function atcGuideHtml() {
  return `
  <details class="atc-guide">
    <summary>Listening Guide — how to decode the tower</summary>
    <div class="guide-grid">
      <div class="guide-card">
        <div class="guide-title">KBDR frequencies</div>
        <div class="guide-line"><b>ATIS 119.15</b><span>recorded weather + runway in use, updated hourly</span></div>
        <div class="guide-line"><b>Ground 121.7</b><span>taxi instructions around the field</span></div>
        <div class="guide-line"><b>Tower 120.9</b><span>runway + traffic pattern — this is the Tower button feed</span></div>
        <div class="guide-line"><b>Runways 6–24 &amp; 11–29</b><span>two crossing strips; wind picks the active one</span></div>
      </div>
      <div class="guide-card">
        <div class="guide-title">A departure, in order</div>
        <div class="guide-step">1&#41; Pilot listens to <b>ATIS</b>, notes the letter ("Information Bravo")</div>
        <div class="guide-step">2&#41; Calls <b>Ground</b>: "Bridgeport Ground, N123AB, taxi with Bravo"</div>
        <div class="guide-step">3&#41; <b>Tower</b>: "N123AB, runway 24, cleared for takeoff"</div>
        <div class="guide-step">4&#41; Seconds later they appear on your <b>Live map</b> — arrivals run the same in reverse</div>
        <div class="guide-step" style="opacity:.8;">Expect student pilots doing laps, Sikorsky test helicopters, and bizjets.</div>
      </div>
    </div>
    <div class="guide-title" style="margin-top:8px;">Phrase decoder</div>
    <div class="decoder">
      ${_ATC_DECODER.map(([p, m]) => `<div class="dec-row"><span class="dec-p">${p}</span><span class="dec-m">${m}</span></div>`).join('')}
    </div>
    <div class="guide-title" style="margin-top:8px;">Phonetic alphabet — spell along with the pilots</div>
    <div class="phon-grid">
      ${_PHONETIC.map(x => { const [l, w] = x.split('·');
        return `<span class="phon"><b>${l}</b>${w}</span>`; }).join('')}
    </div>
    <div class="board-note">Tip: hear a callsign ("November one-two-three Alpha Bravo" = N123AB)?
      Flip to Live and find it on the map.</div>
  </details>`;
}
