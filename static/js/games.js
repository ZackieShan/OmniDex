/* SkyDex games.js — the Games arcade + trainer cards.
 * Who's That Plane (from the family's OWN dex photos), Who's That Country,
 * Flag Match (memory pairs), the daily Weather Guess, and the Professor's
 * Quiz. Top-3 scores per kid per game live on their trainer card as trophies. */

let _player = localStorage.getItem('skydex_player') || 'Guest';
let _profiles = [];

const GAME_LABELS = { plane: "Who's That Plane", flags: "Who's That Country",
                      match: 'Flag Match', what: 'What Is This', ispy: 'iSpy',
                      tune: 'Name That Tune', lang: 'Guess the Language',
                      years: 'Time Machine', morse: 'Morse Academy',
                      clouds: 'Cloud Spotter', storm: 'Storm School',
                      mapm: 'Map Master', post: 'Postcard Detective', quiz: 'Quiz' };

/** Resolves true only when an image URL actually loads — no broken-photo rounds. */
function _preload(url) {
  return new Promise(res => {
    const im = new Image();
    im.onload = () => res(true);
    im.onerror = () => res(false);
    im.src = url;
    setTimeout(() => res(false), 8000);
  });
}

const AVATARS = {
  plane: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M21 16v-2l-8-5V3.5a1.5 1.5 0 0 0-3 0V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5z"/></svg>',
  boat: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l6 5v4l3 1-2 8H5L3 12l3-1V7zm0 2.5L8 8v2.5l4-1.3 4 1.3V8z"/></svg>',
  train: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C8 2 4 2.5 4 6v9.5A3.5 3.5 0 0 0 7.5 19L6 20.5V21h12v-.5L16.5 19a3.5 3.5 0 0 0 3.5-3.5V6c0-3.5-4-4-8-4zM7.5 17a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3zm3.5-7H6V6h5v4zm2 0V6h5v4h-5zm3.5 7a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3z"/></svg>',
  star: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l2.4 4.9 5.4.8-3.9 3.8.9 5.4L12 14.3 7.2 16.9l.9-5.4L4.2 7.7l5.4-.8L12 2z"/></svg>',
  bolt: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M13 2L4.5 13.5H10L8.5 22 17.5 9.5H12z"/></svg>',
  moon: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M21 12.8A9 9 0 1 1 11.2 3 7 7 0 0 0 21 12.8z"/></svg>',
  heart: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 21S3 14 3 8.5A4.5 4.5 0 0 1 12 6a4.5 4.5 0 0 1 9 2.5C21 14 12 21 12 21z"/></svg>',
  pig: '<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="8"/><circle cx="9" cy="10" r="1.3" fill="#141a22"/><circle cx="15" cy="10" r="1.3" fill="#141a22"/><ellipse cx="12" cy="14.5" rx="3" ry="2.2" fill="#141a22"/><circle cx="10.8" cy="14.5" r="0.7" fill="currentColor"/><circle cx="13.2" cy="14.5" r="0.7" fill="currentColor"/></svg>',
};

function openGames() {
  if (window.SkyDexAudio && SkyDexAudio.playBeep) SkyDexAudio.playBeep();
  showView('games');
  renderGamesHub();
}

async function renderGamesHub() {
  const el = document.getElementById('games-content');
  if (!el) return;
  if (window._tuneAbandon) _tuneAbandon();   // leaving a game releases the tuner
  try {
    _profiles = (await (await fetch('/api/profiles')).json()).profiles || [];
  } catch (e) { _profiles = []; }

  const cards = _profiles.map(p => {
    const av = AVATARS[p.avatar] || AVATARS.star;
    const active = p.name === _player;
    const trophies = Object.entries(p.best || {}).map(([g, s]) =>
      `<span class="trophy" title="${GAME_LABELS[g] || g}">&#127942; ${(GAME_LABELS[g] || g).split(' ').pop()}: <b>${Math.round(s)}</b></span>`).join('');
    return `<div class="trainer-card ${active ? 'active' : ''}" onclick="pickPlayer('${p.name}')">
      <div class="trainer-avatar">${av}</div>
      <div class="trainer-body">
        <div class="trainer-name">${p.name}${active ? ' <span class="playing-chip">PLAYING</span>' : ''}</div>
        <div class="trainer-stats">&#11088; ${p.credits} spotter call${p.credits !== 1 ? 's' : ''}
          ${p.wx_wins ? ` · &#9728; ${p.wx_wins} weather win${p.wx_wins !== 1 ? 's' : ''}` : ''}</div>
        <div class="trainer-trophies">${trophies || '<span class="atmo-sub">no trophies yet — play below!</span>'}</div>
      </div>
      <button class="avatar-edit" onclick="event.stopPropagation();pickAvatar('${p.name}')">&#9998;</button>
    </div>`;
  }).join('');

  el.innerHTML = `
    <div class="dex-section-title">Trainer Cards — tap yours to play as you</div>
    <div class="trainer-grid">${cards}</div>
    <div class="dex-section-title">Games</div>
    <div class="game-tiles">
      <button class="game-tile" style="border-color:rgba(255,203,5,0.4);" onclick="startWhatIsThis()">
        <b>What Is This?</b><span>Super easy — for the littlest spotters! Planes, trains, boats &amp; trucks.</span></button>
      <button class="game-tile" onclick="startWhosPlane()">
        <b>Who's That Plane?</b><span>Photos from OUR dex — name the plane. 5 rounds.</span></button>
      <button class="game-tile" onclick="startWhosCountry()">
        <b>Who's That Country?</b><span>Name the flag! 10 rounds, the whole world.</span></button>
      <button class="game-tile" onclick="startFlagMatch()">
        <b>Flag Match</b><span>Memory game — find the 6 matching flag pairs.</span></button>
      <button class="game-tile" onclick="openWxGame()">
        <b>Weather Guess</b><span>Predict tomorrow's high. Winner announced daily!</span></button>
      <button class="game-tile" onclick="startTune()">
        <b>Name That Tune</b><span>A mystery country's radio plays — the music is your clue!</span></button>
      <button class="game-tile" onclick="startLang()">
        <b>Guess the Language</b><span>Hello, thank you, I love you — but in WHAT language?</span></button>
      <button class="game-tile" onclick="startTimeMachine()">
        <b>Weather Time Machine</b><span>Two years, same date, OUR backyard — which was hotter?</span></button>
      <button class="game-tile" onclick="startMorse()">
        <b>Morse Academy</b><span>See the code, hear the beeps, pick the letter!</span></button>
      <button class="game-tile" onclick="startClouds()">
        <b>Cloud Spotter</b><span>Name that cloud — and know what weather it brings.</span></button>
      <button class="game-tile" onclick="startStormSchool()">
        <b>Storm School</b><span>How does thunder happen? Why is the sky blue? Find out!</span></button>
      <button class="game-tile" onclick="startMapMaster()">
        <b>Map Master</b><span>Tap where FRANCE is! Closer tap = more points.</span></button>
      <button class="game-tile" onclick="startPostcards()">
        <b>Postcard Detective</b><span>Three photos, one mystery country. Where are we?</span></button>
      <button class="game-tile" onclick="openQuiz()">
        <b>Professor's Quiz</b><span>The classic — planes, boats &amp; sky trivia.</span></button>
    </div>
    <div id="game-stage"></div>`;
}

function pickPlayer(name) {
  if (window.SkyDexAudio && SkyDexAudio.playBeep) SkyDexAudio.playBeep();
  _player = name;
  localStorage.setItem('skydex_player', name);
  showToast(name + ' is playing!', 'success');
  renderGamesHub();
}

function pickAvatar(name) {
  showInfoModal('Pick an avatar for ' + name,
    `<div class="avatar-grid">` + Object.entries(AVATARS).map(([k, svg]) =>
      `<button class="avatar-btn" onclick="setAvatar('${name}','${k}')">${svg}</button>`).join('') +
    `</div>`);
}

function setAvatar(name, avatar) {
  fetch('/api/profile/avatar', { method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, avatar }) }).then(() => {
    closeInfoModal();
    renderGamesHub();
  }).catch(() => showToast('Could not save avatar'));
}

async function endGame(game, score) {
  const stage = document.getElementById('game-stage');
  let best = false;
  try {
    const d = await (await fetch('/api/game/score', { method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: _player, game: game, score: score }) })).json();
    best = !!d.personal_best;
  } catch (e) {}
  if (stage) stage.innerHTML = `
    <div class="game-over">
      <div class="ach-party-kicker">${_esc(GAME_LABELS[game] || game).toUpperCase()}</div>
      <div class="game-score">${Math.round(score)}</div>
      <div class="atmo-sub">${_player}'s score${best ? ' — <b style="color:var(--accent-yellow);">NEW PERSONAL BEST! &#127942;</b>' : ''}</div>
      <div class="tuner-row" style="justify-content:center;margin-top:12px;">
        <button class="day-summary-btn" style="margin:0;width:auto;display:inline-flex;" onclick="renderGamesHub()">Back to Games</button>
      </div>
    </div>`;
  if (best && window.SkyDexAudio && SkyDexAudio.playCatchJingle) {
    try { SkyDexAudio.playCatchJingle(); } catch (e) {}
  }
  stage.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function _shuffle(a) {
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

// ============================================
// WHO'S THAT PLANE — photos from the family's own catches
// ============================================
let _wtp = null;
const PAD_MODELS = ['Boeing 737-800', 'Airbus A320', 'Cessna 172', 'Gulfstream G650',
                    'Sikorsky UH-60 Black Hawk', 'Embraer E175'];

const WTP_ROUNDS = 5;

function startWhosPlane() {
  if (window.SkyDexAudio && SkyDexAudio.playBeep) SkyDexAudio.playBeep();
  _wtp = { round: 0, score: 0, retries: 0 };
  nextWhosPlane();
}

async function nextWhosPlane() {
  const stage = document.getElementById('game-stage');
  if (!stage) return;
  if (_wtp.round >= WTP_ROUNDS) return endGame('plane', _wtp.score * 20);
  stage.innerHTML = '<div class="ds-empty">Picking a plane from our dex…</div>';
  // Some catches have a photo_url on file whose image no longer loads —
  // preload and quietly skip those instead of showing a broken frame.
  let q = null;
  for (let tries = 0; tries < 4 && !q; tries++) {
    let cand;
    try { cand = await (await fetch('/api/game/plane')).json(); } catch (e) { cand = { error: 'no connection' }; }
    if (cand.error) { stage.innerHTML = `<div class="ds-empty">${_esc(cand.error)}</div>`; return; }
    if (await _preload('/api/photo/' + cand.hex)) q = cand;
  }
  if (!q) {
    // Never dead-end the game: keep drawing fresh planes, and if the photos
    // are truly unreachable, end gracefully with the score banked so far.
    if (++_wtp.retries >= 3) return endGame('plane', _wtp.score * 20);
    stage.innerHTML = '<div class="ds-empty">That photo was camera-shy — drawing another plane…</div>';
    setTimeout(nextWhosPlane, 900);
    return;
  }
  _wtp.retries = 0;
  const choices = [q.answer, ...(q.decoys || [])];
  for (const p of PAD_MODELS) { if (choices.length >= 4) break; if (!choices.includes(p)) choices.push(p); }
  _shuffle(choices);
  _wtp.q = q;
  stage.innerHTML = `
    <div class="game-head">Round ${_wtp.round + 1}/${WTP_ROUNDS} · Score ${_wtp.score} · ${_esc(_player)}</div>
    <div class="wtp-photo"><img src="/api/photo/${q.hex}" alt=""></div>
    <div class="game-head" style="font-size:17px;">Who's&nbsp;that&nbsp;plane?!</div>
    <div class="game-answers">${choices.map(c =>
      `<button class="game-answer" onclick="answerWhosPlane(this,'${String(c).replace(/'/g, '')}')">${_esc(c)}</button>`).join('')}</div>`;
  stage.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function answerWhosPlane(btn, choice) {
  const q = _wtp.q;
  const right = choice === String(q.answer).replace(/'/g, '');
  if (right) _wtp.score++;
  document.querySelectorAll('.game-answer').forEach(b => {
    b.disabled = true;
    if (b.textContent.trim() === q.answer) b.classList.add('right');
  });
  if (!right) btn.classList.add('wrong');
  if (window.SkyDexAudio && SkyDexAudio.playBeep) SkyDexAudio.playBeep();
  const stage = document.getElementById('game-stage');
  stage.insertAdjacentHTML('beforeend', `
    <div class="atmo-tip" style="margin-top:8px;">${right ? "&#10004; It's" : "It was"} a <b>${_esc(q.answer)}</b>${q.registration ? ' (' + _esc(q.registration) + ')' : ''}${q.operator ? ' flown by ' + _esc(q.operator) : ''} — this exact plane flew over OUR house.</div>
    <div class="tuner-row" style="justify-content:center;margin-top:8px;">
      <button class="day-summary-btn" style="margin:0;width:auto;display:inline-flex;" onclick="_wtp.round++;nextWhosPlane()">Next &#9654;</button>
    </div>`);
}

// ============================================
// WHO'S THAT COUNTRY — flags of the world
// ============================================
let _wtc = null;
const FLAG_FALLBACK = [['US', 'United States'], ['JP', 'Japan'], ['FR', 'France'],
  ['GB', 'United Kingdom'], ['MX', 'Mexico'], ['BR', 'Brazil'], ['IT', 'Italy'],
  ['AU', 'Australia'], ['IN', 'India'], ['IS', 'Iceland'], ['KE', 'Kenya'],
  ['KR', 'South Korea'], ['CA', 'Canada'], ['DE', 'Germany'], ['ES', 'Spain'],
  ['GR', 'Greece'], ['EG', 'Egypt'], ['CN', 'China'], ['AR', 'Argentina'],
  ['SE', 'Sweden'], ['CH', 'Switzerland'], ['TR', 'Turkey'], ['ZA', 'South Africa'],
  ['NZ', 'New Zealand'], ['NO', 'Norway'], ['PT', 'Portugal'], ['IE', 'Ireland'],
  ['TH', 'Thailand'], ['VN', 'Vietnam'], ['CO', 'Colombia'], ['PE', 'Peru'],
  ['CL', 'Chile'], ['MA', 'Morocco'], ['NG', 'Nigeria'], ['PH', 'Philippines'],
  ['ID', 'Indonesia'], ['PL', 'Poland'], ['NL', 'Netherlands'], ['BE', 'Belgium'],
  ['AT', 'Austria'], ['FI', 'Finland'], ['DK', 'Denmark'], ['UA', 'Ukraine'],
  ['CU', 'Cuba'], ['JM', 'Jamaica'], ['PA', 'Panama'], ['CR', 'Costa Rica']];

async function _flagPool() {
  // Radio-Browser's country list = a deep well (~150). Falls back to 47 staples.
  try {
    if (window.rbFetch) {
      const cs = (await rbFetch('/json/countries'))
        .filter(c => c.stationcount > 3 && /^[A-Z]{2}$/.test(c.iso_3166_1 || ''));
      if (cs.length > 40) return cs.map(c => [c.iso_3166_1, c.name]);
    }
  } catch (e) {}
  return FLAG_FALLBACK;
}

async function startWhosCountry() {
  if (window.SkyDexAudio && SkyDexAudio.playBeep) SkyDexAudio.playBeep();
  const pool = await _flagPool();
  _wtc = { round: 0, score: 0, pool: _shuffle(pool.slice()), used: [] };
  nextWhosCountry();
}

function nextWhosCountry() {
  const stage = document.getElementById('game-stage');
  if (!stage) return;
  if (_wtc.round >= 10) return endGame('flags', _wtc.score * 10);
  const answer = _wtc.pool[_wtc.round % _wtc.pool.length];
  const others = _shuffle(_wtc.pool.filter(c => c[0] !== answer[0]).slice()).slice(0, 3);
  const choices = _shuffle([answer, ...others]);
  _wtc.answer = answer;
  stage.innerHTML = `
    <div class="game-head">Round ${_wtc.round + 1}/10 · Score ${_wtc.score} · ${_esc(_player)}</div>
    <div class="wtc-flag"><img src="https://flagcdn.com/w320/${answer[0].toLowerCase()}.png" alt=""></div>
    <div class="game-head" style="font-size:17px;">Whose flag is this?</div>
    <div class="game-answers">${choices.map(c =>
      `<button class="game-answer" onclick="answerWhosCountry(this,'${c[0]}')">${_esc(c[1])}</button>`).join('')}</div>`;
  stage.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function answerWhosCountry(btn, code) {
  const right = code === _wtc.answer[0];
  if (right) _wtc.score++;
  document.querySelectorAll('.game-answer').forEach(b => {
    b.disabled = true;
    if (b.textContent.trim() === _wtc.answer[1]) b.classList.add('right');
  });
  if (!right) btn.classList.add('wrong');
  if (window.SkyDexAudio && SkyDexAudio.playBeep) SkyDexAudio.playBeep();
  document.getElementById('game-stage').insertAdjacentHTML('beforeend', `
    <div class="tuner-row" style="justify-content:center;margin-top:10px;">
      <span class="atmo-sub" style="align-self:center;">${right ? '&#10004; Yes —' : "That's"} <b>${_esc(_wtc.answer[1])}</b>!</span>
      <button class="day-summary-btn" style="margin:0;width:auto;display:inline-flex;" onclick="_wtc.round++;nextWhosCountry()">Next &#9654;</button>
    </div>`);
}

// ============================================
// FLAG MATCH — memory pairs
// ============================================
let _fm = null;

async function startFlagMatch() {
  if (window.SkyDexAudio && SkyDexAudio.playBeep) SkyDexAudio.playBeep();
  const pool = _shuffle((await _flagPool()).slice()).slice(0, 6);
  const cards = _shuffle([...pool, ...pool].map((c, i) => ({ code: c[0], name: c[1], id: i })));
  _fm = { cards, open: [], matched: new Set(), flips: 0, lock: false };
  _renderFlagMatch();
}

function _renderFlagMatch() {
  const stage = document.getElementById('game-stage');
  if (!stage) return;
  stage.innerHTML = `
    <div class="game-head">Flag Match · ${_fm.matched.size / 2 | 0}${''}/6 pairs · ${_fm.flips} flips · ${_esc(_player)}</div>
    <div class="fm-grid">${_fm.cards.map((c, i) => {
      const up = _fm.open.includes(i) || _fm.matched.has(i);
      return `<button class="fm-card ${up ? 'up' : ''} ${_fm.matched.has(i) ? 'won' : ''}" onclick="flipCard(${i})">
        ${up ? `<img src="https://flagcdn.com/w160/${c.code.toLowerCase()}.png" alt=""><small>${_esc(c.name)}</small>` : '?'}
      </button>`;
    }).join('')}</div>`;
}

function flipCard(i) {
  if (_fm.lock || _fm.open.includes(i) || _fm.matched.has(i)) return;
  if (window.SkyDexAudio && SkyDexAudio.playBeep) SkyDexAudio.playBeep();
  _fm.open.push(i);
  _fm.flips++;
  _renderFlagMatch();
  if (_fm.open.length === 2) {
    const [a, b] = _fm.open;
    if (_fm.cards[a].code === _fm.cards[b].code) {
      _fm.matched.add(a); _fm.matched.add(b);
      _fm.open = [];
      _renderFlagMatch();
      if (_fm.matched.size === 12) {
        const score = Math.max(10, 100 - (_fm.flips - 12) * 5);
        setTimeout(() => endGame('match', score), 700);
      }
    } else {
      _fm.lock = true;
      setTimeout(() => { _fm.open = []; _fm.lock = false; _renderFlagMatch(); }, 850);
    }
  }
}

// ============================================
// WHAT IS THIS? — the little-kids game (ages ~5 and under).
// One picture, three GIANT icon+word buttons. Photos come live from
// Wikipedia article thumbnails, so the well stays deep and fresh.
// ============================================
const LITTLE_CATS = [
  ['Propeller Plane', 'prop',    ['Piper J-3 Cub', 'Cessna 172', 'Douglas DC-3', 'De Havilland Canada DHC-2 Beaver']],
  ['Jet Plane',       'jet',     ['Boeing 747', 'Airbus A320', 'Concorde', 'Boeing 787 Dreamliner']],
  ['Helicopter',      'heli',    ['Sikorsky UH-60 Black Hawk', 'Bell 407', 'Robinson R44', 'Sikorsky S-92']],
  ['Train',           'train',   ['Steam locomotive', 'Acela', 'TGV', 'Rail freight transport']],
  ['Subway',          'subway',  ['New York City Subway', 'London Underground', 'Paris Métro']],
  ['Truck',           'truck',   ['Fire engine', 'Dump truck', 'Garbage truck', 'Semi-trailer truck', 'Monster truck']],
  ['Car',             'car',     ['Volkswagen Beetle', 'Ford Model T', 'Police car', 'Taxicab']],
  ['Hot Air Balloon', 'balloon', ['Hot air balloon', 'Gas balloon']],
  ['Big Ship',        'ship',    ['Container ship', 'Cruise ship', 'Oil tanker', 'RMS Queen Mary 2']],
  ['Tugboat',         'tug',     ['Tugboat']],
  ['Sailboat',        'sail',    ['Sailboat', 'Schooner', 'Sloop']],
  ['Rocket',          'rocket',  ['Falcon 9', 'Saturn V', 'Space Shuttle']],
];

const LITTLE_ICONS = {
  prop: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M21 16v-2l-8-5V5.5L15 3h-6l2 2.5V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5z"/><circle cx="12" cy="4" r="1.6"/></svg>',
  jet: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M21 16v-2l-8-5V3.5a1.5 1.5 0 0 0-3 0V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5z"/></svg>',
  heli: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M3 4h18v1.6H3zM11 5.6h2V9h4a4 4 0 0 1 4 4v2a3 3 0 0 1-3 3h-3l-2 2h-3l2-2H8a5 5 0 0 1-5-5v-1h2v1a3 3 0 0 0 3 3h10a1 1 0 0 0 1-1v-2a2 2 0 0 0-2-2h-6z"/></svg>',
  train: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C8 2 4 2.5 4 6v9.5A3.5 3.5 0 0 0 7.5 19L6 20.5V21h12v-.5L16.5 19a3.5 3.5 0 0 0 3.5-3.5V6c0-3.5-4-4-8-4zM7.5 17a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3zm3.5-7H6V6h5v4zm2 0V6h5v4h-5zm3.5 7a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3z"/></svg>',
  subway: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M4 8a4 4 0 0 1 4-4h8a4 4 0 0 1 4 4v8a3 3 0 0 1-3 3l1.5 1.5V21h-3L14 19.5h-4L8.5 21h-3v-.5L7 19a3 3 0 0 1-3-3zm3-1v4h10V7zm1.5 9.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3zm7 0a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3z"/></svg>',
  truck: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M2 6h11v9H2zM13 9h4l3 3v3h-7zM6 19a2 2 0 1 1 0-4 2 2 0 0 1 0 4zm11 0a2 2 0 1 1 0-4 2 2 0 0 1 0 4z"/></svg>',
  car: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M5 11l1.5-4.5A2 2 0 0 1 8.4 5h7.2a2 2 0 0 1 1.9 1.5L19 11a2 2 0 0 1 2 2v4h-2a2 2 0 1 1-4 0H9a2 2 0 1 1-4 0H3v-4a2 2 0 0 1 2-2zm2.1 0h9.8l-1-3H8.1z"/></svg>',
  balloon: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2a7 7 0 0 1 7 7c0 3.5-3 6.5-5.5 8H14l-.5 2h-3L10 17h.5C8 15.5 5 12.5 5 9a7 7 0 0 1 7-7zM10 21h4v1.5h-4z"/></svg>',
  ship: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l6 5v4l3 1-2 8H5L3 12l3-1V7zm0 2.5L8 8v2.5l4-1.3 4 1.3V8z"/></svg>',
  tug: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M8 4h4v3h3l1 4 5 1.5-2 6.5H5L3 12l5-1zM9.5 5.5V7h1V5.5z"/></svg>',
  sail: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2v13H5c0-6 3-11 7-13zm1.5 3c2.5 2 4 6 4 10h-4zM3 17h18l-1.5 4h-15z"/></svg>',
  rocket: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2c3 2 4.5 6 4.5 10l2.5 3-2 1-1.5-1.5c-.5 1.5-1.5 3-3.5 4.5-2-1.5-3-3-3.5-4.5L7 16l-2-1 2.5-3C7.5 8 9 4 12 2zm0 6.5a1.6 1.6 0 1 0 0 3.2 1.6 1.6 0 0 0 0-3.2zM10 19.5c.6 1 1.3 1.8 2 2.5.7-.7 1.4-1.5 2-2.5z"/></svg>',
};

let _wit = null;

function startWhatIsThis() {
  if (window.SkyDexAudio && SkyDexAudio.playBeep) SkyDexAudio.playBeep();
  _wit = { round: 0, score: 0, used: [] };
  nextWhatIsThis();
}

async function nextWhatIsThis() {
  const stage = document.getElementById('game-stage');
  if (!stage) return;
  if (_wit.round >= 8) return endGame('what', Math.round(_wit.score * 12.5));
  stage.innerHTML = '<div class="ds-empty">Finding a picture…</div>';

  let cat = null, pic = null;
  for (let tries = 0; tries < 6 && !pic; tries++) {
    const c = LITTLE_CATS[Math.floor(Math.random() * LITTLE_CATS.length)];
    const articles = c[2].filter(a => !_wit.used.includes(a));
    const art = (articles.length ? articles : c[2])[
      Math.floor(Math.random() * (articles.length ? articles.length : c[2].length))];
    try {
      const d = await (await fetch('https://en.wikipedia.org/api/rest_v1/page/summary/' +
        encodeURIComponent(art))).json();
      const url = (d.thumbnail && d.thumbnail.source) || (d.originalimage && d.originalimage.source);
      if (url && await _preload(url)) { cat = c; pic = url; _wit.used.push(art); }
    } catch (e) { /* next spin */ }
  }
  if (!pic) { stage.innerHTML = '<div class="ds-empty">Pictures are hiding — try again in a minute.</div>'; return; }

  const others = _shuffle(LITTLE_CATS.filter(c => c[0] !== cat[0]).slice()).slice(0, 2);
  const choices = _shuffle([cat, ...others]);
  _wit.answer = cat[0];
  stage.innerHTML = `
    <div class="game-head">Round ${_wit.round + 1}/8 · ${_wit.score} right · ${_esc(_player)}</div>
    <div class="wtp-photo"><img src="${pic}" alt=""></div>
    <div class="game-head" style="font-size:19px;">What is this?</div>
    <div class="wit-answers">${choices.map(c =>
      `<button class="wit-answer" onclick="answerWhatIsThis(this,'${c[0].replace(/'/g, '')}')">
         <span class="wit-ic">${LITTLE_ICONS[c[1]] || ''}</span>${_esc(c[0])}</button>`).join('')}</div>`;
  stage.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function answerWhatIsThis(btn, choice) {
  const right = choice === _wit.answer.replace(/'/g, '');
  if (right) _wit.score++;
  document.querySelectorAll('.wit-answer').forEach(b => {
    b.disabled = true;
    if (b.textContent.trim() === _wit.answer) b.classList.add('right');
  });
  if (!right) btn.classList.add('wrong');
  if (right && window.SkyDexAudio && SkyDexAudio.playCatchJingle) {
    try { SkyDexAudio.playCatchJingle(); } catch (e) {}
  } else if (window.SkyDexAudio && SkyDexAudio.playBeep) SkyDexAudio.playBeep();
  document.getElementById('game-stage').insertAdjacentHTML('beforeend', `
    <div class="tuner-row" style="justify-content:center;margin-top:10px;">
      <span class="atmo-sub" style="align-self:center;font-size:15px;">${right ? '&#127881; YES! A' : "It's a"} <b>${_esc(_wit.answer)}</b>!</span>
      <button class="day-summary-btn" style="margin:0;width:auto;display:inline-flex;padding:12px 22px;font-size:15px;" onclick="_wit.round++;nextWhatIsThis()">Next &#9654;</button>
    </div>`);
}

// ============================================
// WEATHER GUESS — predict tomorrow's high
// ============================================
let _wxg = { temp: 75 };

async function openWxGame() {
  if (window.SkyDexAudio && SkyDexAudio.playBeep) SkyDexAudio.playBeep();
  const stage = document.getElementById('game-stage');
  if (!stage) return;
  stage.innerHTML = '<div class="ds-empty">Checking the weather desk…</div>';
  let d;
  try { d = await (await fetch('/api/wxgame')).json(); } catch (e) {
    stage.innerHTML = '<div class="ds-empty">Weather desk unreachable.</div>'; return;
  }
  _wxg.temp = Math.round(d.guesses[_player] != null ? d.guesses[_player] : (d.hint || 75));
  const locked = Object.entries(d.guesses || {});
  let lastHtml = '';
  const lr = d.last_result;
  if (lr) {
    lastHtml = `<div class="dex-section-title">Last round — ${_esc(lr.date)} (high was ${Math.round(lr.actual)}°)</div>` +
      lr.guesses.map(g => `<div class="atmo-line"><span>${g.won ? '&#127942; ' : ''}${_esc(g.name)}</span><b>${Math.round(g.guess)}°</b></div>`).join('');
  }
  // The Robot Forecast-Off: rival weather models disagree — who do you trust?
  const robots = (d.robots || []).slice();
  if (d.hint != null) robots.unshift({ label: 'Local robot (NWS)', high: Math.round(d.hint) });
  const robotHtml = robots.length ? `
    <div class="robot-row">${robots.map(r =>
      `<div class="robot-card"><div class="robot-name">${_esc(r.label)}</div><b>${Math.round(r.high)}&deg;</b></div>`).join('')}</div>
    <div class="atmo-sub" style="text-align:center;margin-bottom:6px;">${robots.length} forecast robots,
      ${new Set(robots.map(r => Math.round(r.high))).size > 1 ? "and they DON'T agree" : 'all saying the same thing'} —
      who do YOU trust?</div>` : '';
  stage.innerHTML = `
    <div class="game-head">Weather Guess · ${_esc(_player)}</div>
    <div class="atmo-tip">What will tomorrow's HIGH be at our house?</div>
    ${robotHtml}
    <div class="wx-dial">
      <button class="wx-step" onclick="wxStep(-1)">&minus;</button>
      <div class="wx-temp" id="wx-temp">${_wxg.temp}&deg;</div>
      <button class="wx-step" onclick="wxStep(1)">+</button>
    </div>
    <div class="tuner-row" style="justify-content:center;">
      <button class="day-summary-btn" style="margin:0;width:auto;display:inline-flex;padding:12px 26px;font-size:15px;" onclick="wxLockIn()">&#128274; Lock it in!</button>
    </div>
    ${locked.length ? `<div class="dex-section-title">Locked in for tomorrow</div>` +
      locked.map(([n, t]) => `<div class="atmo-line"><span>${_esc(n)}</span><b>${Math.round(t)}°</b></div>`).join('') : ''}
    ${lastHtml}
    <div class="board-note">Closest guess wins when tomorrow's real high comes in — the kiosk announces the winner out loud. Wins collect on your trainer card.</div>`;
  stage.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function wxStep(d) {
  if (window.SkyDexAudio && SkyDexAudio.playBeep) SkyDexAudio.playBeep();
  _wxg.temp = Math.max(-20, Math.min(120, _wxg.temp + d));
  const el = document.getElementById('wx-temp');
  if (el) el.innerHTML = _wxg.temp + '&deg;';
}

async function wxLockIn() {
  try {
    const d = await (await fetch('/api/wxgame/guess', { method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: _player, temp: _wxg.temp }) })).json();
    if (d.error) return showToast(d.error);
    showToast(`${_player} says ${_wxg.temp}° tomorrow — locked in!`, 'success');
    openWxGame();
  } catch (e) { showToast('Could not reach the weather desk'); }
}

// ============================================
// NAME THAT TUNE — a mystery country's radio plays; the music is the evidence.
// ============================================
let _tune = null;

function startTune() {
  if (window.SkyDexAudio && SkyDexAudio.playBeep) SkyDexAudio.playBeep();
  _tune = { round: 0, score: 0, fails: 0 };
  nextTune();
}

function _tuneStop() {
  const a = document.getElementById('tuner-audio');
  if (a) { a.onerror = null; a.pause(); a.removeAttribute('src'); a.load(); }
  if (_tune) clearTimeout(_tune.watch);
}

/** Start (or restart) the current round's station, with a dead-air watchdog:
 *  if the stream errors or never starts flowing, hop to the next station
 *  from the SAME country — the round and answer stay intact. */
function _tunePlay() {
  const audio = document.getElementById('tuner-audio');
  const st = _tune && _tune.list && _tune.list[_tune.idx];
  if (!audio || !st) return;
  _tune.station = st;
  audio.onerror = null;                  // never let a src change fire the OLD handler
  audio.src = st.url_resolved || st.url;
  audio.volume = getVolume();
  audio.onerror = () => _tuneSwap();
  audio.play().catch(() => _tuneSwap());
  clearTimeout(_tune.watch);
  _tune.watch = setTimeout(() => {
    if (audio.paused || audio.currentTime < 1.5) _tuneSwap();
  }, 8000);
}

/** A dead station fires MULTIPLE failure signals (error event + rejected play
 *  + watchdog) — the swapLock collapses them into ONE swap. Hard caps mean a
 *  bad-internet day ends the game gracefully instead of spiraling. */
function _tuneSwap() {
  if (!_tune || !_tune.list || _tune.answered || _tune.swapLock) return;
  _tune.swapLock = true;
  setTimeout(() => { if (_tune) _tune.swapLock = false; }, 1500);
  clearTimeout(_tune.watch);
  const a = document.getElementById('tuner-audio');
  if (a) a.onerror = null;
  _tune.swaps = (_tune.swaps || 0) + 1;
  _tune.totalSwaps = (_tune.totalSwaps || 0) + 1;
  if (_tune.totalSwaps > 10) {
    _tune.answered = true;
    showToast('The radio gods are grumpy — banking your score!');
    return endGame('tune', _tune.score * 20);
  }
  if (_tune.idx + 1 < _tune.list.length && _tune.swaps <= 4) {
    _tune.idx++;
    showToast('That station was sleeping — trying another…');
    _tunePlay();
  } else {
    // Whole country came up silent — re-roll the round elsewhere.
    _tune.fails = (_tune.fails || 0) + 1;
    if (_tune.fails >= 3) {
      _tune.answered = true;
      return endGame('tune', _tune.score * 20);
    }
    nextTune();
  }
}

/** Called by ANYTHING else that takes over the shared tuner audio (World
 *  Radio, stop button, back to hub) — fully releases the game's grip. */
function _tuneAbandon() {
  if (!_tune) return;
  _tune.answered = true;                 // no more swaps, ever
  clearTimeout(_tune.watch);
  const a = document.getElementById('tuner-audio');
  if (a) a.onerror = null;
}

// Curated with per-country EVIDENCE strategies. Western pop radio sounds the
// same everywhere (ask Croatia about Ms. Jackson), so for Western countries we
// hunt NEWS/TALK stations — the spoken language is the clue. Where the musical
// tradition is unmistakable (Asia, Middle East, Latin America, Caribbean), the
// MUSIC is the clue. Tags are tried in order, each with the language filter.
const TUNE_POOL = [
  // --- music IS the evidence ---
  ['MX', 'Mexico',        { language: 'spanish',    tags: ['ranchera', 'mariachi'] }],
  ['CU', 'Cuba',          { language: 'spanish',    tags: ['salsa', 'cuban'] }],
  ['BR', 'Brazil',        { language: 'portuguese', tags: ['samba', 'mpb'] }],
  ['JM', 'Jamaica',       {                          tags: ['reggae'] }],
  ['IE', 'Ireland',       {                          tags: ['celtic', 'folk'] }],
  ['IN', 'India',         { language: 'hindi',      tags: ['bollywood'] }],
  ['JP', 'Japan',         { language: 'japanese',   tags: ['jpop'] }],
  ['KR', 'South Korea',   { language: 'korean',     tags: ['kpop'] }],
  ['TH', 'Thailand',      { language: 'thai',       tags: [] }],
  ['VN', 'Vietnam',       { language: 'vietnamese', tags: [] }],
  ['ID', 'Indonesia',     { language: 'indonesian', tags: ['dangdut'] }],
  ['EG', 'Egypt',         { language: 'arabic',     tags: ['oriental'] }],
  ['KE', 'Kenya',         { language: 'swahili',    tags: [] }],
  ['US', 'United States', {                          tags: ['country', 'bluegrass'] }],
  // --- TALKING is the evidence (news / public radio) ---
  ['FR', 'France',        { language: 'french',     tags: ['news', 'talk'] }],
  ['DE', 'Germany',       { language: 'german',     tags: ['news', 'talk'] }],
  ['IT', 'Italy',         { language: 'italian',    tags: ['news', 'talk'] }],
  ['ES', 'Spain',         { language: 'spanish',    tags: ['news', 'talk'] }],
  ['GR', 'Greece',        { language: 'greek',      tags: ['news'] }],
  ['TR', 'Turkey',        { language: 'turkish',    tags: ['news'] }],
  ['RU', 'Russia',        { language: 'russian',    tags: ['news'] }],
  ['UA', 'Ukraine',       { language: 'ukrainian',  tags: ['news'] }],
  ['PL', 'Poland',        { language: 'polish',     tags: ['news'] }],
  ['SE', 'Sweden',        { language: 'swedish',    tags: ['news', 'public radio'] }],
  ['IS', 'Iceland',       { language: 'icelandic',  tags: ['news'] }],
];

async function nextTune() {
  const stage = document.getElementById('game-stage');
  if (!stage) return;
  _tuneStop();
  if (_tune.round >= 5) return endGame('tune', _tune.score * 20);
  stage.innerHTML = '<div class="ds-empty">Tuning a mystery radio…</div>';
  let st = null, answer = null;
  for (let tries = 0; tries < 5 && !st; tries++) {
    const c = TUNE_POOL[Math.floor(Math.random() * TUNE_POOL.length)];
    const meta = c[2] || {};
    // Best evidence first: strategy tag + local language, then language alone,
    // then bare tags, then any top station as a last resort.
    const langQ = meta.language ? '&language=' + encodeURIComponent(meta.language) : '';
    const filters = [];
    (meta.tags || []).forEach(t => filters.push('&tag=' + encodeURIComponent(t) + langQ));
    if (langQ) filters.push(langQ);
    (meta.tags || []).forEach(t => filters.push('&tag=' + encodeURIComponent(t)));
    filters.push('');
    for (const extra of filters) {
      try {
        const list = await rbFetch('/json/stations/search?countrycode=' + c[0] + extra +
          '&order=votes&reverse=true&limit=10&hidebroken=true');
        if (list && list.length) {
          st = _shuffle(list.slice());   // keep the whole list — silence backups
          answer = c;
          break;
        }
      } catch (e) { /* next filter */ }
    }
  }
  if (!st) {
    if (++_tune.fails >= 3) return endGame('tune', _tune.score * 20);
    stage.innerHTML = '<div class="ds-empty">Static… retuning…</div>';
    setTimeout(nextTune, 900);
    return;
  }
  _tune.fails = 0;
  _tune.answer = answer;
  _tune.list = st;
  _tune.idx = 0;
  _tune.swaps = 0;
  _tune.answered = false;
  _tunePlay();
  // Decoys avoid the answer's language — Spanish audio with three Spanish-
  // speaking countries on the board isn't a fair puzzle.
  const lang = (answer[2] || {}).language || '';
  const others = _shuffle(TUNE_POOL.filter(c =>
    c[0] !== answer[0] && (!lang || ((c[2] || {}).language || '') !== lang)).slice()).slice(0, 3);
  const choices = _shuffle([answer, ...others]);
  stage.innerHTML = `
    <div class="game-head">Round ${_tune.round + 1}/5 · Score ${_tune.score} · ${_esc(_player)}</div>
    <div class="game-head" style="font-size:18px;">&#127911; Listen… whose radio is this?</div>
    <div class="atmo-sub" style="text-align:center;margin-bottom:8px;">The language, the music, the announcer — it's all evidence.</div>
    <div class="country-grid">${choices.map(c =>
      `<button class="country-card" onclick="answerTune(this,'${c[0]}')">
         <img src="https://flagcdn.com/w80/${c[0].toLowerCase()}.png" alt="" loading="lazy">
         <span>${_esc(c[1])}</span></button>`).join('')}</div>
    <div class="tuner-row" style="justify-content:center;">
      <button class="band-chip" onclick="_tuneSwap()">&#128263; Hear nothing? Try another station</button>
    </div>`;
  stage.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function answerTune(btn, code) {
  _tune.answered = true;
  clearTimeout(_tune.watch);
  const right = code === _tune.answer[0];
  if (right) _tune.score++;
  document.querySelectorAll('#game-stage .country-card').forEach(b => {
    b.disabled = true;
    b.onclick = null;
    if (b.textContent.trim() === _tune.answer[1]) b.style.borderColor = '#4ade80';
  });
  if (!right) btn.style.borderColor = '#ff6b6b';
  if (right && window.SkyDexAudio && SkyDexAudio.playCatchJingle) {
    try { SkyDexAudio.playCatchJingle(); } catch (e) {}
  }
  document.getElementById('game-stage').insertAdjacentHTML('beforeend', `
    <div class="tuner-row" style="justify-content:center;margin-top:10px;">
      <span class="atmo-sub" style="align-self:center;">${right ? '&#127881; YES —' : 'It was'}
        <b>${_esc(_tune.answer[1])}</b>! You're hearing <b>${_esc(_tune.station.name || '')}</b>. Keep listening or…</span>
      <button class="day-summary-btn" style="margin:0;width:auto;display:inline-flex;"
        onclick="_tune.round++;nextTune()">Next &#9654;</button>
    </div>`);
}

// ============================================
// GUESS THE LANGUAGE — hello / goodbye / thank you / I love you /
// "hello, my name is {player}" — spoken by the robot, in a mystery tongue.
// ============================================
const LANGS = [
  ['es', 'Spanish',    ['Hola', 'Adiós', 'Gracias', 'Te quiero', 'Hola, me llamo {n}']],
  ['fr', 'French',     ['Bonjour', 'Au revoir', 'Merci', "Je t'aime", 'Bonjour, je m’appelle {n}']],
  ['de', 'German',     ['Hallo', 'Auf Wiedersehen', 'Danke', 'Ich liebe dich', 'Hallo, ich heiße {n}']],
  ['it', 'Italian',    ['Ciao', 'Arrivederci', 'Grazie', 'Ti voglio bene', 'Ciao, mi chiamo {n}']],
  ['pt', 'Portuguese', ['Olá', 'Tchau', 'Obrigado', 'Eu te amo', 'Olá, meu nome é {n}']],
  ['ja', 'Japanese',   ['こんにちは', 'さようなら', 'ありがとう', '大好きです', '私の名前は {n} です']],
  ['ru', 'Russian',    ['Привет', 'До свидания', 'Спасибо', 'Я тебя люблю', 'Меня зовут {n}']],
  ['hi', 'Hindi',      ['नमस्ते', 'अलविदा', 'धन्यवाद', 'मैं तुमसे प्यार करता हूँ', 'मेरा नाम {n} है']],
  ['sv', 'Swedish',    ['Hej', 'Hej då', 'Tack', 'Jag älskar dig', 'Hej, jag heter {n}']],
  ['tr', 'Turkish',    ['Merhaba', 'Hoşça kal', 'Teşekkürler', 'Seni seviyorum', 'Benim adım {n}']],
  ['sw', 'Swahili',    ['Jambo', 'Kwaheri', 'Asante', 'Nakupenda', 'Jina langu ni {n}']],
  ['nl', 'Dutch',      ['Hallo', 'Tot ziens', 'Dank je', 'Ik hou van jou', 'Hallo, ik heet {n}']],
];
const LANG_MEANINGS = ['Hello', 'Goodbye', 'Thank you', 'I love you', 'Hello, my name is {n}'];
let _lng = null;

function startLang() {
  if (window.SkyDexAudio && SkyDexAudio.playBeep) SkyDexAudio.playBeep();
  _lng = { round: 0, score: 0 };
  nextLang();
}

function _langSpeak() {
  if (!_lng || !_lng.text) return;
  const a = new Audio('/api/tts?voice=' + _lng.answer[0] + '&text=' + encodeURIComponent(_lng.text));
  a.volume = getVolume();
  a.play().catch(() => showToast('The robot lost its voice — tap the speaker again'));
}

function nextLang() {
  const stage = document.getElementById('game-stage');
  if (!stage) return;
  if (_lng.round >= 5) return endGame('lang', _lng.score * 20);
  const answer = LANGS[Math.floor(Math.random() * LANGS.length)];
  const pi = Math.floor(Math.random() * 5);
  const name = _player;
  _lng.answer = answer;
  _lng.text = answer[2][pi].replace('{n}', name);
  _lng.meaning = LANG_MEANINGS[pi].replace('{n}', name);
  const others = _shuffle(LANGS.filter(l => l[0] !== answer[0]).slice()).slice(0, 3);
  const choices = _shuffle([answer, ...others]);
  stage.innerHTML = `
    <div class="game-head">Round ${_lng.round + 1}/5 · Score ${_lng.score} · ${_esc(_player)}</div>
    <div class="game-head" style="font-size:18px;">The robot says: <b>&ldquo;${_esc(_lng.meaning)}&rdquo;</b>… but in WHAT language?</div>
    <div class="tuner-row" style="justify-content:center;">
      <button class="day-summary-btn" style="margin:0;width:auto;display:inline-flex;padding:14px 28px;font-size:16px;"
        onclick="_langSpeak()">&#128266; Play it</button>
    </div>
    <div class="game-answers">${choices.map(l =>
      `<button class="game-answer" onclick="answerLang(this,'${l[0]}')">${_esc(l[1])}</button>`).join('')}</div>`;
  setTimeout(_langSpeak, 400);
  stage.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function answerLang(btn, code) {
  const right = code === _lng.answer[0];
  if (right) _lng.score++;
  document.querySelectorAll('.game-answer').forEach(b => {
    b.disabled = true;
    if (b.textContent.trim() === _lng.answer[1]) b.classList.add('right');
  });
  if (!right) btn.classList.add('wrong');
  if (right && window.SkyDexAudio && SkyDexAudio.playCatchJingle) {
    try { SkyDexAudio.playCatchJingle(); } catch (e) {}
  }
  document.getElementById('game-stage').insertAdjacentHTML('beforeend', `
    <div class="atmo-tip" style="margin-top:8px;">${right ? '&#127881; YES —' : 'That was'} <b>${_esc(_lng.answer[1])}</b>!
      They say <b>&ldquo;${_esc(_lng.text)}&rdquo;</b> — it means &ldquo;${_esc(_lng.meaning)}&rdquo;.</div>
    <div class="tuner-row" style="justify-content:center;margin-top:8px;">
      <button class="day-summary-btn" style="margin:0;width:auto;display:inline-flex;" onclick="_langSpeak()">&#128266; Hear it again</button>
      <button class="day-summary-btn" style="margin:0;width:auto;display:inline-flex;" onclick="_lng.round++;nextLang()">Next &#9654;</button>
    </div>`);
}

// ============================================
// WEATHER TIME MACHINE — same date, two years, OUR backyard. Which was hotter?
// ============================================
let _tm = null;

function startTimeMachine() {
  if (window.SkyDexAudio && SkyDexAudio.playBeep) SkyDexAudio.playBeep();
  _tm = { round: 0, score: 0 };
  nextTimeMachine();
}

async function nextTimeMachine() {
  const stage = document.getElementById('game-stage');
  if (!stage) return;
  if (_tm.round >= 5) return endGame('years', _tm.score * 20);
  stage.innerHTML = '<div class="ds-empty">Spinning the time machine…</div>';
  let d;
  try { d = await (await fetch('/api/game/timemachine')).json(); } catch (e) { d = { error: 'time machine offline' }; }
  if (d.error) {
    stage.innerHTML = `<div class="ds-empty">${_esc(d.error)}</div>
      <div class="tuner-row" style="justify-content:center;">
        <button class="day-summary-btn" style="margin:0;width:auto;display:inline-flex;" onclick="nextTimeMachine()">Spin again</button></div>`;
    return;
  }
  // Tolerate an older server that still sends {high} instead of {value}.
  ['a', 'b'].forEach(k => { if (d[k] && d[k].value == null) d[k].value = d[k].high; });
  if (!d.a || d.a.value == null || !d.b || d.b.value == null) {
    stage.innerHTML = `<div class="ds-empty">The time machine came back empty-handed.</div>
      <div class="tuner-row" style="justify-content:center;">
        <button class="day-summary-btn" style="margin:0;width:auto;display:inline-flex;" onclick="nextTimeMachine()">Spin again</button></div>`;
    return;
  }
  _tm.q = d;
  stage.innerHTML = `
    <div class="game-head">Round ${_tm.round + 1}/5 · Score ${_tm.score} · ${_esc(_player)}</div>
    <div class="game-head" style="font-size:19px;">&#128197; <b>${_esc(d.date_label)}</b> — right here at home.<br>Which year was ${_esc(d.ask || 'HOTTER')}?</div>
    <div class="wit-answers" style="grid-template-columns:1fr 1fr;">
      <button class="wit-answer" onclick="answerTimeMachine(this,'a')"><b style="font-size:26px;">${d.a.year}</b></button>
      <button class="wit-answer" onclick="answerTimeMachine(this,'b')"><b style="font-size:26px;">${d.b.year}</b></button>
    </div>
    <div class="atmo-sub" style="text-align:center;margin-top:6px;">Real measurements from our own sky, back to 1950 — heat, wind, rain &amp; snow.</div>`;
  stage.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function answerTimeMachine(btn, pick) {
  const q = _tm.q;
  const unit = q.unit || '°';
  const tie = q.a.value === q.b.value;
  const winner = q.a.value >= q.b.value ? 'a' : 'b';
  const right = tie || pick === winner;
  if (right) _tm.score++;
  document.querySelectorAll('.wit-answer').forEach((b, i) => {
    b.disabled = true;
    const key = i === 0 ? 'a' : 'b';
    b.insertAdjacentHTML('beforeend', `<span style="font-size:15px;color:var(--text-dim);">&nbsp;${q[key].value}${unit}</span>`);
    if (key === winner || tie) b.classList.add('right');
  });
  if (!right) btn.classList.add('wrong');
  if (right && window.SkyDexAudio && SkyDexAudio.playCatchJingle) {
    try { SkyDexAudio.playCatchJingle(); } catch (e) {}
  }
  document.getElementById('game-stage').insertAdjacentHTML('beforeend', `
    <div class="tuner-row" style="justify-content:center;margin-top:10px;">
      <span class="atmo-sub" style="align-self:center;">${tie ? '&#129309; A TIE — both count!' : right ? '&#127881; Right!' : 'Nope —'}
        ${_esc(q.date_label)}'s ${(q.ask || 'HOTTER').toLowerCase().replace('ier', 'iest').replace('hotter', 'hottest')} year was <b>${q.a.value >= q.b.value ? q.a.year : q.b.year}</b> (${Math.max(q.a.value, q.b.value)}${unit}).</span>
      <button class="day-summary-btn" style="margin:0;width:auto;display:inline-flex;" onclick="_tm.round++;nextTimeMachine()">Next &#9654;</button>
    </div>`);
}

// ============================================
// MORSE ACADEMY — decode beeps: letters, then words, then family names.
// ============================================
const MORSE = { A: '.-', B: '-...', C: '-.-.', D: '-..', E: '.', F: '..-.', G: '--.',
  H: '....', I: '..', J: '.---', K: '-.-', L: '.-..', M: '--', N: '-.', O: '---',
  P: '.--.', Q: '--.-', R: '.-.', S: '...', T: '-', U: '..-', V: '...-', W: '.--',
  X: '-..-', Y: '-.--', Z: '--..' };
const NATO = { A: 'Alfa', B: 'Bravo', C: 'Charlie', D: 'Delta', E: 'Echo', F: 'Foxtrot',
  G: 'Golf', H: 'Hotel', I: 'India', J: 'Juliett', K: 'Kilo', L: 'Lima', M: 'Mike',
  N: 'November', O: 'Oscar', P: 'Papa', Q: 'Quebec', R: 'Romeo', S: 'Sierra',
  T: 'Tango', U: 'Uniform', V: 'Victor', W: 'Whiskey', X: 'X-ray', Y: 'Yankee', Z: 'Zulu' };
const MORSE_WORDS = ['SOS', 'CAT', 'DOG', 'SKY', 'SUN', 'MOM', 'DAD', 'ZAP', 'JET', 'SEA'];
let _mrs = null;

/** Dots and dashes as big friendly symbols: ● ▬ */
function morseGlyphs(str) {
  return [...String(str).toUpperCase()].map(ch =>
    (MORSE[ch] || '').replace(/\./g, '&#9679;').replace(/-/g, '&#9644;')).join('&nbsp;&nbsp;/&nbsp;&nbsp;');
}

function morsePlay(str) {
  try {
    const ctx = window._morseCtx = window._morseCtx ||
      new (window.AudioContext || window.webkitAudioContext)();
    let t = ctx.currentTime + 0.1;
    // Kid tempo — roomy gaps so each beep registers.
    const DIT = 0.13, DAH = 0.39, GAP = 0.13, LGAP = 0.5;
    for (const ch of String(str).toUpperCase()) {
      const code = MORSE[ch];
      if (!code) { t += LGAP; continue; }
      for (const sym of code) {
        const dur = sym === '.' ? DIT : DAH;
        const o = ctx.createOscillator(), g = ctx.createGain();
        o.frequency.value = 620;
        g.gain.setValueAtTime(0.18 * getVolume(), t);
        g.gain.setValueAtTime(0.0001, t + dur);
        o.connect(g); g.connect(ctx.destination);
        o.start(t); o.stop(t + dur + 0.01);
        t += dur + GAP;
      }
      t += LGAP;
    }
  } catch (e) {}
}

function startMorse() {
  if (window.SkyDexAudio && SkyDexAudio.playBeep) SkyDexAudio.playBeep();
  _mrs = { round: 0, score: 0 };
  nextMorse();
}

function nextMorse() {
  const stage = document.getElementById('game-stage');
  if (!stage) return;
  if (_mrs.round >= 8) return endGame('morse', Math.round(_mrs.score * 12.5));
  const r = _mrs.round;
  // One letter at a time: SEE the code big, HEAR the beeps, pick the letter.
  // Each choice shows its own pattern, so it's solvable by matching — and the
  // phonetic alphabet is the prize on a right answer.
  const abc = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
  const answer = abc[Math.floor(Math.random() * 26)];
  const set = new Set([answer]);
  while (set.size < 3) set.add(abc[Math.floor(Math.random() * 26)]);
  const choices = _shuffle([...set]);
  _mrs.answer = answer;
  // Sound-only question — the kid matches what they HEAR to the printed
  // pattern+letter on each button. No spoiler pattern up top.
  stage.innerHTML = `
    <div class="game-head">Round ${r + 1}/8 · ${_mrs.score} decoded · ${_esc(_player)}</div>
    <div class="game-head" style="font-size:18px;">&#128066; Listen close… which letter did you hear?</div>
    <div class="tuner-row" style="justify-content:center;">
      <button class="day-summary-btn" style="margin:0;width:auto;display:inline-flex;padding:14px 30px;font-size:16px;"
        onclick="morsePlay('${answer}')">&#128266; Play it again</button>
    </div>
    <div class="game-answers" style="grid-template-columns:repeat(3,1fr);">${choices.map(c =>
      `<button class="game-answer" onclick="answerMorse(this,'${c}')" data-m="${c}">
         <span style="font-size:30px;">${c}</span>
         <div class="morse-mini" style="font-size:16px;">${morseGlyphs(c)}</div>
       </button>`).join('')}</div>`;
  setTimeout(() => morsePlay(answer), 500);
  stage.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function answerMorse(btn, choice) {
  const right = choice === _mrs.answer;
  if (right) _mrs.score++;
  document.querySelectorAll('.game-answer').forEach(b => {
    b.disabled = true;
    if (b.dataset.m === _mrs.answer) b.classList.add('right');
  });
  if (!right) btn.classList.add('wrong');
  if (right && window.SkyDexAudio && SkyDexAudio.playCatchJingle) {
    try { SkyDexAudio.playCatchJingle(); } catch (e) {}
  }
  const a = _mrs.answer;
  document.getElementById('game-stage').insertAdjacentHTML('beforeend', `
    <div class="atmo-tip" style="margin-top:8px;text-align:center;">
      ${right ? '&#127881; Decoded! ' : 'It was '} <b style="font-size:20px;">${a}</b> —
      pilots and hams call it <b style="color:var(--accent-yellow);font-size:18px;">&ldquo;${NATO[a]}&rdquo;</b>
      <span style="letter-spacing:3px;">(${morseGlyphs(a)})</span><br>
      <span class="atmo-sub">They say &ldquo;${NATO[a]}&rdquo; on the radio so ${a} can never be misheard.</span></div>
    <div class="tuner-row" style="justify-content:center;margin-top:8px;">
      <button class="day-summary-btn" style="margin:0;width:auto;display:inline-flex;" onclick="morsePlay('${a}')">&#128266; Replay</button>
      <button class="day-summary-btn" style="margin:0;width:auto;display:inline-flex;" onclick="_mrs.round++;nextMorse()">Next &#9654;</button>
    </div>`);
}

// ============================================
// CLOUD SPOTTER — name the cloud, learn what weather it brings.
// ============================================
const CLOUDS = [
  ['Cumulus', 'Cumulus cloud', 'The puffy cotton-ball cloud. Fair weather — perfect for cloud-watching!'],
  ['Cumulonimbus', 'Cumulonimbus cloud', 'The THUNDERSTORM tower — flat anvil top, lightning inside, maybe hail. StormDex material.'],
  ['Cirrus', 'Cirrus cloud', 'Wispy horse-tails way up high, made of ice. Nice now — change might come tomorrow.'],
  ['Stratus', 'Stratus cloud', 'A flat gray blanket over the whole sky. Gray day, maybe drizzle.'],
  ['Altocumulus', 'Altocumulus cloud', 'A sky full of little sheep. Often means the weather is about to change.'],
  ['Nimbostratus', 'Nimbostratus cloud', 'The thick dark rain blanket — steady rain or snow for HOURS.'],
  ['Lenticular', 'Lenticular cloud', 'The UFO cloud! Wind flowing over mountains shapes it — pilots steer around them.'],
  ['Mammatus', 'Mammatus cloud', 'Bubbly pouches hanging under a storm — a BIG storm is very close.'],
  ['Fog', 'Fog', "A cloud sitting on the ground. Walk in it and you're INSIDE a cloud."],
  ['Contrail', 'Contrail', "Not weather — a jet's ice-crystal trail! SkyDex predicts these on plane cards."],
];
let _cld = null;

function startClouds() {
  if (window.SkyDexAudio && SkyDexAudio.playBeep) SkyDexAudio.playBeep();
  _cld = { round: 0, score: 0, used: [] };
  nextCloud();
}

async function nextCloud() {
  const stage = document.getElementById('game-stage');
  if (!stage) return;
  if (_cld.round >= 5) return endGame('clouds', _cld.score * 20);
  stage.innerHTML = '<div class="ds-empty">Looking up…</div>';
  let answer = null, pic = null;
  for (let tries = 0; tries < 6 && !pic; tries++) {
    const c = CLOUDS[Math.floor(Math.random() * CLOUDS.length)];
    if (_cld.used.includes(c[0])) continue;
    try {
      const d = await (await fetch('https://en.wikipedia.org/api/rest_v1/page/summary/' +
        encodeURIComponent(c[1]))).json();
      const url = (d.thumbnail && d.thumbnail.source) || '';
      if (url && await _preload(url)) { answer = c; pic = url; _cld.used.push(c[0]); }
    } catch (e) { /* next */ }
  }
  if (!pic) { stage.innerHTML = '<div class="ds-empty">The clouds are hiding — try again in a minute.</div>'; return; }
  _cld.answer = answer;
  const others = _shuffle(CLOUDS.filter(c => c[0] !== answer[0]).slice()).slice(0, 3);
  const choices = _shuffle([answer, ...others]);
  stage.innerHTML = `
    <div class="game-head">Round ${_cld.round + 1}/5 · Score ${_cld.score} · ${_esc(_player)}</div>
    <div class="wtp-photo"><img src="${pic}" alt=""></div>
    <div class="game-head" style="font-size:18px;">&#9729; What cloud is that?</div>
    <div class="game-answers">${choices.map(c =>
      `<button class="game-answer" onclick="answerCloud(this,'${c[0]}')">${_esc(c[0])}</button>`).join('')}</div>`;
  stage.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function answerCloud(btn, pick) {
  const right = pick === _cld.answer[0];
  if (right) _cld.score++;
  document.querySelectorAll('.game-answer').forEach(b => {
    b.disabled = true;
    if (b.textContent.trim() === _cld.answer[0]) b.classList.add('right');
  });
  if (!right) btn.classList.add('wrong');
  if (right && window.SkyDexAudio && SkyDexAudio.playCatchJingle) {
    try { SkyDexAudio.playCatchJingle(); } catch (e) {}
  }
  document.getElementById('game-stage').insertAdjacentHTML('beforeend', `
    <div class="atmo-tip" style="margin-top:8px;">${right ? '&#127881; YES —' : "That's"} <b>${_esc(_cld.answer[0])}</b>! ${_esc(_cld.answer[2])}</div>
    <div class="tuner-row" style="justify-content:center;margin-top:8px;">
      <button class="day-summary-btn" style="margin:0;width:auto;display:inline-flex;" onclick="_cld.round++;nextCloud()">Next &#9654;</button>
    </div>`);
}

// ============================================
// STORM SCHOOL — how weather actually works, one "whoa" at a time.
// [question, [choices], answerIndex, the-why]
// ============================================
const STORM_QS = [
  ['What IS thunder?', ['Clouds bumping together', 'Air exploding from lightning heat', 'The sky cracking', 'Giant fans'], 1,
   'Lightning heats the air to 5x hotter than the SUN\'s surface — the air explodes outward, and that BOOM is thunder.'],
  ['Lightning or thunder — which happens first?', ['Thunder', 'Same moment', 'Lightning', 'Depends on the storm'], 2,
   'They happen together, but light travels almost instantly while sound is slow — so you SEE it before you HEAR it.'],
  ['You see lightning, then count 10 seconds until thunder. How far away is the storm?', ['10 miles', 'About 2 miles', 'Half a mile', '100 miles'], 1,
   'Sound travels a mile every ~5 seconds. Count the gap, divide by 5. Ten seconds = two miles. Real storm-spotter math!'],
  ['What do you need to see a rainbow?', ['Sun behind you + rain in front', 'A full moon', 'Really cold air', 'Two clouds touching'], 0,
   'Sunlight enters raindrops and splits into colors. Sun at your back, rain ahead — rainbow!'],
  ['How many sides does every snowflake have?', ['4', '5', '6', '8'], 2,
   'Always six — because of how water molecules lock together when they freeze. No two flakes identical, all six-sided.'],
  ['What is the "eye" of a hurricane like?', ['The windiest part', 'Calm and often sunny', 'Full of lightning', 'Frozen solid'], 1,
   'Dead calm, sometimes blue sky — with a wall of the fiercest wind spinning right around it.'],
  ['Why is the sky blue?', ['The ocean reflects up', 'Air scatters blue light most', "It's painted", 'Blue is the sun\'s real color'], 1,
   'Sunlight is every color mixed. Air molecules bounce BLUE around the sky more than any other color.'],
  ['What is fog?', ['Smoke', 'A cloud on the ground', 'Steam from cars', 'Dust'], 1,
   'Exactly the same thing as a cloud — just lying on the ground where you can walk through it.'],
  ['What makes wind?', ['Trees waving', 'Air moving from high to low pressure', 'The Earth breathing', 'Planes flying'], 1,
   'Air rushes from where pressure is high to where it\'s low. Bigger difference = stronger wind.'],
  ['The barometer is falling fast. What\'s coming?', ['Sunshine', 'Nothing', 'A storm', 'Fog'], 2,
   'Falling pressure means storms brew. Sailors have trusted this trick for 300 years.'],
  ['Where does hail come from?', ['Freezers in space', 'Thunderstorm updrafts', 'Snow that got lost', 'Very cold rain'], 1,
   'Storm winds yo-yo raindrops up into freezing air over and over, adding ice layers until they fall as hailstones.'],
  ['What makes the tides go in and out?', ['Whales', 'The Moon\'s gravity', 'Wind', 'Ships'], 1,
   'The Moon pulls the ocean toward it as Earth spins — our tide widget tracks that pull every day.'],
  ['What does weather radar actually see?', ['Clouds', 'Rain and snow falling', 'Wind', 'Birds only'], 1,
   'Radar pings bounce off raindrops and snowflakes. (Big flocks of birds DO show up sometimes!)'],
  ['A meteorologist studies…', ['Meteors', 'Weather', 'Metals', 'Maps'], 1,
   'Weather! The name comes from an old Greek word for "things in the sky". Meteor-watchers are astronomers.'],
  ['Which cloud makes thunderstorms?', ['Cirrus', 'Stratus', 'Cumulonimbus', 'Fog'], 2,
   'Cumulonimbus — the anvil-topped tower. If it\'s tall and dark with a flat top, count the seconds.'],
  ['What does an anemometer measure?', ['Rain', 'Wind speed', 'Snow depth', 'Lightning'], 1,
   'The little spinning-cup gadget on weather stations — EtherDex hears your neighbors\' ones reporting in.'],
  ['Why do you see your breath on cold days?', ['It freezes', 'Water vapor condenses into a tiny cloud', 'It\'s smoke', 'Magic'], 1,
   'Your warm wet breath hits cold air and the vapor condenses — you\'re literally making a tiny cloud.'],
  ['What season has the most thunderstorms here in Connecticut?', ['Winter', 'Spring', 'Summer', 'Fall'], 2,
   'Summer — hot humid air is storm fuel. That\'s why StormDex gets busy in July.'],
  ['Hurricanes get names because…', ['They like them', 'Names make warnings clearer', 'Scientists get bored', 'It\'s a law of nature'], 1,
   '"Hurricane Maria is coming" beats "storm #7" for getting people to listen. Lists repeat every 6 years.'],
  ['What\'s a contrail made of?', ['Smoke', 'Ice crystals', 'Cotton', 'Fuel'], 1,
   'Jet exhaust has water vapor that freezes instantly in the cold up there — an instant human-made cirrus cloud.'],
];
let _ss = null;

function startStormSchool() {
  if (window.SkyDexAudio && SkyDexAudio.playBeep) SkyDexAudio.playBeep();
  _ss = { round: 0, score: 0, qs: _shuffle(STORM_QS.slice()).slice(0, 5) };
  nextStormQ();
}

function nextStormQ() {
  const stage = document.getElementById('game-stage');
  if (!stage) return;
  if (_ss.round >= 5) return endGame('storm', _ss.score * 20);
  const q = _ss.qs[_ss.round];
  _ss.q = q;
  stage.innerHTML = `
    <div class="game-head">Round ${_ss.round + 1}/5 · Score ${_ss.score} · ${_esc(_player)}</div>
    <div class="game-head" style="font-size:18px;">&#9928; ${_esc(q[0])}</div>
    <div class="game-answers">${q[1].map((c, i) =>
      `<button class="game-answer" onclick="answerStormQ(this,${i})">${_esc(c)}</button>`).join('')}</div>`;
  stage.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function answerStormQ(btn, i) {
  const q = _ss.q;
  const right = i === q[2];
  if (right) _ss.score++;
  document.querySelectorAll('.game-answer').forEach((b, j) => {
    b.disabled = true;
    if (j === q[2]) b.classList.add('right');
  });
  if (!right) btn.classList.add('wrong');
  if (right && window.SkyDexAudio && SkyDexAudio.playCatchJingle) {
    try { SkyDexAudio.playCatchJingle(); } catch (e) {}
  }
  document.getElementById('game-stage').insertAdjacentHTML('beforeend', `
    <div class="atmo-tip" style="margin-top:8px;">${right ? '&#127881; Right!' : 'Not quite —'} ${_esc(q[3])}</div>
    <div class="tuner-row" style="justify-content:center;margin-top:8px;">
      <button class="day-summary-btn" style="margin:0;width:auto;display:inline-flex;" onclick="_ss.round++;nextStormQ()">Next &#9654;</button>
    </div>`);
}

// ============================================
// MAP MASTER — "Tap where FRANCE is!" Distance decides the points.
// ============================================
const MAP_TARGETS = [
  ['France', 46.6, 2.4], ['Brazil', -10, -52], ['Japan', 36, 138], ['Egypt', 26, 30],
  ['Australia', -25, 134], ['India', 22, 79], ['Mexico', 23, -102], ['Canada', 56, -106],
  ['Russia', 60, 90], ['China', 35, 104], ['Italy', 42.8, 12.5], ['Spain', 40, -3.7],
  ['Kenya', 0.4, 37.9], ['Argentina', -34, -64], ['Iceland', 65, -18], ['Turkey', 39, 35],
  ['Thailand', 15, 101], ['Sweden', 62, 15], ['South Africa', -29, 24], ['Peru', -9.2, -75],
  ['United Kingdom', 54, -2.5], ['Indonesia', -2.5, 118], ['Nigeria', 9.1, 8.7],
  ['Mongolia', 46.9, 103.8], ['Madagascar', -19, 47], ['Greenland', 72, -40],
];
let _mm = null;

function startMapMaster() {
  if (window.SkyDexAudio && SkyDexAudio.playBeep) SkyDexAudio.playBeep();
  _mm = { round: 0, score: 0, pool: _shuffle(MAP_TARGETS.slice()) };
  nextMapMaster();
}

function nextMapMaster() {
  const stage = document.getElementById('game-stage');
  if (!stage) return;
  if (_mm.round >= 5) return endGame('mapm', _mm.score);
  const t = _mm.pool[_mm.round % _mm.pool.length];
  _mm.t = t;
  _mm.locked = false;
  stage.innerHTML = `
    <div class="game-head">Round ${_mm.round + 1}/5 · Score ${_mm.score} · ${_esc(_player)}</div>
    <div class="game-head" style="font-size:19px;">&#127757; Tap where <b>${_esc(t[0]).toUpperCase()}</b> is!</div>
    <div id="mm-map" class="mapm-map"></div>
    <div class="atmo-sub" style="text-align:center;margin-top:4px;">Bullseye &lt;500 km = 20 pts · &lt;1500 km = 12 · &lt;3000 km = 6</div>
    <div id="mm-result"></div>`;
  setTimeout(() => {
    try {
      const m = L.map('mm-map', { zoomControl: true, attributionControl: false, worldCopyJump: true })
        .setView([22, 0], 2);
      L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png',
        { maxZoom: 6 }).addTo(m);
      _mm.map = m;
      m.on('click', (e) => mapMasterGuess(e.latlng));
    } catch (e) {}
  }, 60);
  stage.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function mapMasterGuess(ll) {
  if (!_mm || _mm.locked || !_mm.map) return;
  _mm.locked = true;
  const t = _mm.t;
  const truth = L.latLng(t[1], t[2]);
  const km = Math.round(ll.distanceTo(truth) / 1000);
  const pts = km < 500 ? 20 : km < 1500 ? 12 : km < 3000 ? 6 : 0;
  _mm.score += pts;
  const m = _mm.map;
  L.circleMarker(ll, { radius: 7, color: '#fff', fillColor: '#ff6b6b', fillOpacity: 1 })
    .addTo(m).bindTooltip('Your tap');
  L.circleMarker(truth, { radius: 8, color: '#fff', fillColor: '#4ade80', fillOpacity: 1 })
    .addTo(m).bindTooltip(t[0]).openTooltip();
  L.polyline([ll, truth], { color: '#FFCB05', weight: 2, dashArray: '6 6' }).addTo(m);
  m.fitBounds(L.latLngBounds([ll, truth]), { padding: [40, 40], maxZoom: 4 });
  if (pts >= 12 && window.SkyDexAudio && SkyDexAudio.playCatchJingle) {
    try { SkyDexAudio.playCatchJingle(); } catch (e) {}
  }
  document.getElementById('mm-result').innerHTML = `
    <div class="tuner-row" style="justify-content:center;margin-top:8px;">
      <span class="atmo-sub" style="align-self:center;font-size:15px;">
        ${pts === 20 ? '&#127919; BULLSEYE!' : pts ? '&#128076; Close!' : '&#129517; Way off —'}
        <b>${km.toLocaleString()} km</b> away · <b>+${pts}</b> points</span>
      <button class="day-summary-btn" style="margin:0;width:auto;display:inline-flex;"
        onclick="_mm.round++;nextMapMaster()">Next &#9654;</button>
    </div>`;
}

// ============================================
// POSTCARD DETECTIVE — three photos, one country. Where are we?
// ============================================
let _pd = null;

async function startPostcards() {
  if (window.SkyDexAudio && SkyDexAudio.playBeep) SkyDexAudio.playBeep();
  const pool = await _flagPool();
  _pd = { round: 0, score: 0, pool: _shuffle(pool.slice()) };
  nextPostcard();
}

async function nextPostcard() {
  const stage = document.getElementById('game-stage');
  if (!stage) return;
  if (_pd.round >= 5) return endGame('post', _pd.score * 20);
  stage.innerHTML = '<div class="ds-empty">Collecting postcards…</div>';
  let answer = null, pics = [];
  for (let tries = 0; tries < 5 && pics.length < 2; tries++) {
    const c = _pd.pool[(_pd.round + tries * 7) % _pd.pool.length];
    try {
      const d = await (await fetch('https://en.wikipedia.org/api/rest_v1/page/media-list/' +
        encodeURIComponent(c[1]))).json();
      const cand = (d.items || [])
        .filter(x => x.type === 'image' && x.srcset && x.srcset[0] &&
          !/flag|coat|arms|locator|map|logo|icon|seal|emblem|banner|\.svg/i.test(x.title || ''))
        .slice(0, 3)
        .map(x => x.srcset[0].src.replace(/^\/\//, 'https://'));
      if (cand.length >= 2 && await _preload(cand[0])) { answer = c; pics = cand; }
    } catch (e) { /* next country */ }
  }
  if (!answer) { stage.innerHTML = '<div class="ds-empty">The mail is late — try again in a minute.</div>'; return; }
  _pd.answer = answer;
  const others = _shuffle(_pd.pool.filter(c => c[0] !== answer[0]).slice()).slice(0, 3);
  const choices = _shuffle([answer, ...others]);
  stage.innerHTML = `
    <div class="game-head">Round ${_pd.round + 1}/5 · Score ${_pd.score} · ${_esc(_player)}</div>
    <div class="postcards" style="justify-content:center;">${pics.map(u => `<img src="${u}" loading="lazy" alt="">`).join('')}</div>
    <div class="game-head" style="font-size:18px;">&#128231; These postcards all came from ONE country… which?</div>
    <div class="country-grid">${choices.map(c =>
      `<button class="country-card" onclick="answerPostcard(this,'${c[0]}')">
         <img src="https://flagcdn.com/w80/${c[0].toLowerCase()}.png" alt="" loading="lazy">
         <span>${_esc(c[1])}</span></button>`).join('')}</div>`;
  stage.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function answerPostcard(btn, code) {
  const right = code === _pd.answer[0];
  if (right) _pd.score++;
  document.querySelectorAll('#game-stage .country-card').forEach(b => {
    b.disabled = true;
    b.onclick = null;
    if (b.textContent.trim() === _pd.answer[1]) b.style.borderColor = '#4ade80';
  });
  if (!right) btn.style.borderColor = '#ff6b6b';
  if (right && window.SkyDexAudio && SkyDexAudio.playCatchJingle) {
    try { SkyDexAudio.playCatchJingle(); } catch (e) {}
  }
  document.getElementById('game-stage').insertAdjacentHTML('beforeend', `
    <div class="tuner-row" style="justify-content:center;margin-top:10px;">
      <span class="atmo-sub" style="align-self:center;">${right ? '&#127881; YES —' : 'They were from'} <b>${_esc(_pd.answer[1])}</b>!</span>
      <button class="day-summary-btn" style="margin:0;width:auto;display:inline-flex;" onclick="_pd.round++;nextPostcard()">Next &#9654;</button>
    </div>`);
}
