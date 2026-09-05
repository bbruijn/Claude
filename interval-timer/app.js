/* Interval Timer — werk/rust intervallen met rondes en oefeningen. */
(() => {
  'use strict';

  const STORE_CONFIG = 'it.config.v1';
  const STORE_SAVED = 'it.saved.v1';
  const STORE_SOUND = 'it.sound.v1';

  const DEFAULTS = { work: 60, rest: 90, exercises: 1, rounds: 8, resetRound: 0 };

  const FIELDS = {
    work:       { title: 'Werk',           kind: 'time',  min: 1, max: 3600, step: 5, presets: [15, 20, 30, 40, 45, 60, 90, 120] },
    rest:       { title: 'Uitrusten',      kind: 'time',  min: 0, max: 3600, step: 5, presets: [0, 10, 15, 20, 30, 45, 60, 90] },
    exercises:  { title: 'Oefeningen',     kind: 'count', min: 1, max: 50,   step: 1, presets: [1, 2, 3, 4, 5, 6, 8, 10] },
    rounds:     { title: 'Rondes',         kind: 'count', min: 1, max: 99,   step: 1, presets: [1, 2, 3, 4, 5, 6, 8, 10] },
    resetRound: { title: 'Ronde resetten', kind: 'time',  min: 0, max: 1800, step: 5, presets: [0, 15, 30, 45, 60, 90, 120, 180] }
  };

  const $ = (id) => document.getElementById(id);

  const el = {
    hero: $('hero'), phase: $('phaseLabel'), meta: $('heroMeta'),
    metaRound: $('metaRound'), metaExercise: $('metaExercise'),
    clock: $('clock'), totalLeft: $('totalLeft'), progressBar: $('progressBar'),
    play: $('playBtn'),
    valWork: $('valWork'), valRest: $('valRest'), valExercises: $('valExercises'),
    valRounds: $('valRounds'), valResetRound: $('valResetRound'),
    rowWork: $('rowWork'), rowRest: $('rowRest'), rowExercises: $('rowExercises'),
    rowRounds: $('rowRounds'), rowResetRound: $('rowResetRound'), rowLoad: $('rowLoad'),
    btnReset: $('btnReset'), btnSave: $('btnSave'), btnSound: $('btnSound'),
    sheetWrap: $('sheetWrap'), scrim: $('scrim'), sheetTitle: $('sheetTitle'),
    stepValue: $('stepValue'), stepUp: $('stepUp'), stepDown: $('stepDown'),
    presets: $('presets'), sheetOk: $('sheetOk'), sheetCancel: $('sheetCancel'),
    loadWrap: $('loadWrap'), loadScrim: $('loadScrim'), savedList: $('savedList'), loadClose: $('loadClose')
  };

  const ROW_FOR_PHASE = { work: el.rowWork, rest: el.rowRest, reset: el.rowResetRound };

  /* ── Opslag ───────────────────────────────────────────────────── */
  const readJSON = (key, fallback) => {
    try {
      const raw = localStorage.getItem(key);
      return raw ? JSON.parse(raw) : fallback;
    } catch { return fallback; }
  };
  const writeJSON = (key, value) => {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* private mode */ }
  };

  const clampConfig = (raw) => {
    const out = { ...DEFAULTS };
    for (const [key, spec] of Object.entries(FIELDS)) {
      const n = Math.round(Number(raw && raw[key]));
      if (Number.isFinite(n)) out[key] = Math.min(spec.max, Math.max(spec.min, n));
    }
    return out;
  };

  let config = clampConfig(readJSON(STORE_CONFIG, DEFAULTS));
  let soundOn = readJSON(STORE_SOUND, true) !== false;

  /* ── Opmaak ───────────────────────────────────────────────────── */
  const two = (n) => String(n).padStart(2, '0');

  const fmt = (seconds) => {
    const s = Math.max(0, Math.round(seconds));
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const r = s % 60;
    return h ? `${h}:${two(m)}:${two(r)}` : `${two(m)}:${two(r)}`;
  };

  /* ── Programma opbouwen ───────────────────────────────────────── */
  // Per ronde: elke oefening krijgt werk + rust. De allerlaatste rust
  // vervalt, en tussen rondes komt eventueel een reset-pauze.
  const buildSegments = (c) => {
    const segments = [];
    for (let round = 1; round <= c.rounds; round++) {
      for (let ex = 1; ex <= c.exercises; ex++) {
        segments.push({ phase: 'work', label: 'Werk', duration: c.work, round, exercise: ex });
        if (c.rest > 0) segments.push({ phase: 'rest', label: 'Uitrusten', duration: c.rest, round, exercise: ex });
      }
      if (round < c.rounds && c.resetRound > 0) {
        segments.push({ phase: 'reset', label: 'Ronde resetten', duration: c.resetRound, round, exercise: c.exercises });
      }
    }
    while (segments.length && segments[segments.length - 1].phase !== 'work') segments.pop();
    return segments;
  };

  const totalOf = (segments) => segments.reduce((sum, s) => sum + s.duration, 0);

  /* ── Toestand ─────────────────────────────────────────────────── */
  const state = {
    segments: buildSegments(config),
    index: 0,
    remaining: 0,      // resterende seconden in het huidige segment
    elapsedBefore: 0,  // verstreken seconden vóór het huidige segment
    running: false,
    finished: false,
    anchor: 0,         // Date.now() bij (her)start
    anchorRemaining: 0,
    lastBeep: null,
    raf: 0
  };

  const resetProgram = () => {
    state.segments = buildSegments(config);
    state.index = 0;
    state.remaining = state.segments.length ? state.segments[0].duration : 0;
    state.elapsedBefore = 0;
    state.running = false;
    state.finished = false;
    state.lastBeep = null;
  };

  /* ── Geluid ───────────────────────────────────────────────────── */
  let audioCtx = null;
  let silentTrack = null;

  // Een korte stille WAV als data-URI, opgebouwd zonder losse bestanden.
  const silentWav = () => {
    const samples = 2000; // 0,25 s bij 8 kHz
    const bytes = new Uint8Array(44 + samples).fill(128); // 128 = stilte bij 8-bit
    const view = new DataView(bytes.buffer);
    const ascii = (offset, text) => [...text].forEach((c, i) => view.setUint8(offset + i, c.charCodeAt(0)));
    ascii(0, 'RIFF'); view.setUint32(4, 36 + samples, true);
    ascii(8, 'WAVEfmt '); view.setUint32(16, 16, true);
    view.setUint16(20, 1, true); view.setUint16(22, 1, true);
    view.setUint32(24, 8000, true); view.setUint32(28, 8000, true);
    view.setUint16(32, 1, true); view.setUint16(34, 8, true);
    ascii(36, 'data'); view.setUint32(40, samples, true);
    let binary = '';
    bytes.forEach((b) => { binary += String.fromCharCode(b); });
    return `data:audio/wav;base64,${btoa(binary)}`;
  };

  // iOS dempt Web Audio zodra het belschuifje op stil staat. Een lopend
  // media-element zet de audiosessie op 'playback', en dan klinkt de timer
  // ook in stille stand.
  const holdAudioSession = () => {
    try {
      if (navigator.audioSession) navigator.audioSession.type = 'playback';
    } catch { /* alleen iOS 16.4+ */ }
    try {
      if (!silentTrack) {
        silentTrack = new Audio(silentWav());
        silentTrack.loop = true;
        silentTrack.preload = 'auto';
        silentTrack.setAttribute('playsinline', '');
      }
      silentTrack.play().catch(() => { /* mag geweigerd worden */ });
    } catch { /* geen media-element beschikbaar */ }
  };

  const releaseAudioSession = () => {
    if (silentTrack) try { silentTrack.pause(); } catch {}
  };

  const unlockAudio = () => {
    if (!soundOn) return;
    holdAudioSession();
    try {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      if (!Ctx) return;
      if (!audioCtx) audioCtx = new Ctx();
      if (audioCtx.state === 'suspended') audioCtx.resume();
      // stil buffertje: Safari geeft pas geluid na een gebruikersgebaar
      const buf = audioCtx.createBuffer(1, 1, 22050);
      const src = audioCtx.createBufferSource();
      src.buffer = buf;
      src.connect(audioCtx.destination);
      src.start(0);
    } catch { /* geen audio beschikbaar */ }
  };

  // De eerste toon valt weg als de context nog aan het hervatten is.
  const whenAudioReady = (play) => {
    if (!audioCtx || audioCtx.state !== 'suspended') { play(); return; }
    audioCtx.resume().then(play, play);
  };

  const beep = (frequency, duration = 0.16, gain = 0.5) => {
    if (!soundOn || !audioCtx) return;
    try {
      const now = audioCtx.currentTime;
      const osc = audioCtx.createOscillator();
      const amp = audioCtx.createGain();
      osc.type = 'triangle';
      osc.frequency.setValueAtTime(frequency, now);
      amp.gain.setValueAtTime(0.0001, now);
      amp.gain.exponentialRampToValueAtTime(gain, now + 0.015);
      amp.gain.exponentialRampToValueAtTime(0.0001, now + duration);
      osc.connect(amp).connect(audioCtx.destination);
      osc.start(now);
      osc.stop(now + duration + 0.02);
    } catch { /* negeer */ }
  };

  const buzz = (pattern) => { if (navigator.vibrate) try { navigator.vibrate(pattern); } catch {} };

  const cue = {
    tick: () => { beep(760, 0.12, 0.4); buzz(30); },
    work: () => { beep(980, 0.3, 0.55); setTimeout(() => beep(1240, 0.26, 0.5), 130); buzz([60, 40, 60]); },
    rest: () => { beep(480, 0.34, 0.5); buzz(90); },
    reset: () => { beep(620, 0.3, 0.45); buzz(60); },
    done: () => { [0, 180, 360].forEach((d, i) => setTimeout(() => beep(880 + i * 220, 0.32, 0.55), d)); buzz([100, 60, 100, 60, 200]); }
  };

  /* ── Scherm wakker houden ─────────────────────────────────────── */
  let wakeLock = null;

  const requestWakeLock = async () => {
    if (!('wakeLock' in navigator)) return;
    try {
      wakeLock = await navigator.wakeLock.request('screen');
      wakeLock.addEventListener('release', () => { wakeLock = null; });
    } catch { /* geweigerd of niet ondersteund */ }
  };

  const releaseWakeLock = () => {
    if (wakeLock) { try { wakeLock.release(); } catch {} wakeLock = null; }
  };

  /* ── Weergave ─────────────────────────────────────────────────── */
  const renderConfig = () => {
    el.valWork.textContent = fmt(config.work);
    el.valRest.textContent = fmt(config.rest);
    el.valExercises.textContent = String(config.exercises);
    el.valRounds.textContent = `${config.rounds}X`;
    el.valResetRound.textContent = fmt(config.resetRound);
  };

  const setHeroPhase = (phase) => {
    el.hero.classList.remove('is-work', 'is-rest', 'is-reset', 'is-done');
    if (phase) el.hero.classList.add(`is-${phase}`);
    Object.values(ROW_FOR_PHASE).forEach((row) => row.classList.remove('is-active'));
    const active = ROW_FOR_PHASE[phase];
    if (active && state.running) active.classList.add('is-active');
  };

  const render = () => {
    const total = totalOf(state.segments);
    const seg = state.segments[state.index];
    const started = state.running || state.elapsedBefore > 0 || (seg && state.remaining < seg.duration);

    el.hero.classList.toggle('is-paused', started && !state.running && !state.finished);
    el.play.classList.toggle('running', state.running);
    el.play.setAttribute('aria-label', state.running ? 'Pauzeren' : 'Starten');

    if (state.finished) {
      setHeroPhase('done');
      el.phase.textContent = 'Klaar!';
      el.meta.hidden = true;
      el.clock.textContent = fmt(0);
      el.totalLeft.textContent = `Training van ${fmt(total)} afgerond`;
      el.progressBar.style.width = '100%';
      document.title = 'Klaar! · Interval Timer';
      return;
    }

    if (!seg) {
      setHeroPhase(null);
      el.phase.textContent = 'Interval Timer';
      el.meta.hidden = true;
      el.clock.textContent = fmt(0);
      el.totalLeft.textContent = 'Geen intervallen ingesteld';
      el.progressBar.style.width = '0%';
      return;
    }

    const elapsed = state.elapsedBefore + (seg.duration - state.remaining);
    setHeroPhase(started ? seg.phase : null);
    el.phase.textContent = started ? seg.label : 'Interval Timer';
    el.meta.hidden = !started;
    el.metaRound.textContent = `Ronde ${seg.round}/${config.rounds}`;
    el.metaExercise.textContent = `Oefening ${seg.exercise}/${config.exercises}`;
    el.clock.textContent = fmt(started ? state.remaining : total);
    el.totalLeft.textContent = started
      ? `Nog ${fmt(total - elapsed)} van ${fmt(total)}`
      : `Totaal ${fmt(total)}`;
    el.progressBar.style.width = `${total ? Math.min(100, (elapsed / total) * 100) : 0}%`;
    document.title = started
      ? `${fmt(state.remaining)} ${seg.label} · Interval Timer`
      : 'Interval Timer';
  };

  /* ── Klok ─────────────────────────────────────────────────────── */
  const advance = () => {
    const seg = state.segments[state.index];
    state.elapsedBefore += seg.duration;
    state.index += 1;
    const next = state.segments[state.index];

    if (!next) {
      state.running = false;
      state.finished = true;
      state.remaining = 0;
      releaseWakeLock();
      cue.done();
      render();
      return false;
    }

    state.remaining = next.duration;
    state.anchor = Date.now();
    state.anchorRemaining = next.duration;
    state.lastBeep = null;
    whenAudioReady(cue[next.phase]);
    return true;
  };

  const tick = () => {
    if (!state.running) return;

    const seg = state.segments[state.index];
    if (!seg) return;

    const left = state.anchorRemaining - (Date.now() - state.anchor) / 1000;
    state.remaining = Math.max(0, left);

    const whole = Math.ceil(state.remaining);
    if (whole > 0 && whole <= 3 && state.lastBeep !== whole) {
      state.lastBeep = whole;
      cue.tick();
    }

    if (left <= 0) {
      const overshoot = -left;
      if (!advance()) return;
      // Kalibreer op de echte klok zodat drift niet oploopt.
      state.anchor = Date.now() - overshoot * 1000;
      state.remaining = Math.max(0, state.anchorRemaining - overshoot);
    }

    render();
    state.raf = requestAnimationFrame(tick);
  };

  const start = () => {
    if (state.finished) resetProgram();
    if (!state.segments.length) return;
    unlockAudio();
    const seg = state.segments[state.index];
    if (state.remaining <= 0) state.remaining = seg.duration;
    const fresh = state.elapsedBefore === 0 && state.remaining === seg.duration;
    state.running = true;
    state.anchor = Date.now();
    state.anchorRemaining = state.remaining;
    state.lastBeep = null;
    requestWakeLock();
    if (fresh) whenAudioReady(cue[seg.phase]);
    cancelAnimationFrame(state.raf);
    state.raf = requestAnimationFrame(tick);
    render();
  };

  const pause = () => {
    state.running = false;
    cancelAnimationFrame(state.raf);
    releaseWakeLock();
    releaseAudioSession();
    render();
  };

  const toggle = () => (state.running ? pause() : start());

  const hardReset = () => {
    cancelAnimationFrame(state.raf);
    releaseWakeLock();
    releaseAudioSession();
    resetProgram();
    render();
  };

  /* ── Bewerk-sheet ─────────────────────────────────────────────── */
  let editing = null;
  let draft = 0;

  const paintSheet = () => {
    const spec = FIELDS[editing];
    el.stepValue.textContent = spec.kind === 'time' ? fmt(draft) : String(draft);
    [...el.presets.children].forEach((btn) => {
      btn.setAttribute('aria-pressed', String(Number(btn.dataset.value) === draft));
    });
  };

  const openSheet = (field) => {
    editing = field;
    draft = config[field];
    const spec = FIELDS[field];
    el.sheetTitle.textContent = spec.title;
    el.presets.innerHTML = '';
    spec.presets.forEach((value) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'preset';
      btn.dataset.value = String(value);
      btn.textContent = spec.kind === 'time' ? fmt(value) : `${value}X`;
      btn.addEventListener('click', () => { draft = value; paintSheet(); });
      el.presets.appendChild(btn);
    });
    paintSheet();
    el.sheetWrap.hidden = false;
  };

  const closeSheet = () => { el.sheetWrap.hidden = true; editing = null; };

  const nudge = (direction) => {
    const spec = FIELDS[editing];
    const next = draft + direction * spec.step;
    draft = Math.min(spec.max, Math.max(spec.min, next));
    paintSheet();
  };

  const commitSheet = () => {
    if (!editing) return;
    config[editing] = draft;
    writeJSON(STORE_CONFIG, config);
    closeSheet();
    renderConfig();
    hardReset();
  };

  /* ── Opgeslagen trainingen ────────────────────────────────────── */
  const describe = (c) => {
    const total = totalOf(buildSegments(c));
    return `${fmt(c.work)} werk · ${fmt(c.rest)} rust · ${c.exercises} oef. · ${c.rounds}X · ${fmt(total)}`;
  };

  const saveTraining = () => {
    const list = readJSON(STORE_SAVED, []);
    const stamp = new Date();
    const entry = {
      id: `${stamp.getTime()}`,
      name: stamp.toLocaleDateString('nl-NL', { day: 'numeric', month: 'short' }) +
            ' ' + stamp.toLocaleTimeString('nl-NL', { hour: '2-digit', minute: '2-digit' }),
      config: { ...config }
    };
    const next = [entry, ...list.filter((item) => describe(item.config) !== describe(entry.config))].slice(0, 12);
    writeJSON(STORE_SAVED, next);
    flash(el.btnSave, 'Opgeslagen');
  };

  const flash = (button, text) => {
    const original = button.textContent;
    button.textContent = text;
    setTimeout(() => { button.textContent = original; }, 1200);
  };

  const openLoad = () => {
    const list = readJSON(STORE_SAVED, []);
    el.savedList.innerHTML = '';
    if (!list.length) {
      const empty = document.createElement('p');
      empty.className = 'saved-empty';
      empty.textContent = 'Nog geen trainingen opgeslagen. Tik op “Training opslaan”.';
      el.savedList.appendChild(empty);
    } else {
      list.forEach((item) => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'saved-item';
        btn.innerHTML = `<span><strong>${item.name}</strong><small>${describe(item.config)}</small></span><span aria-hidden="true">»</span>`;
        btn.addEventListener('click', () => {
          config = clampConfig(item.config);
          writeJSON(STORE_CONFIG, config);
          renderConfig();
          hardReset();
          el.loadWrap.hidden = true;
        });
        el.savedList.appendChild(btn);
      });
    }
    el.loadWrap.hidden = false;
  };

  /* ── Gebeurtenissen ───────────────────────────────────────────── */
  el.play.addEventListener('click', toggle);
  el.btnReset.addEventListener('click', hardReset);
  el.btnSave.addEventListener('click', saveTraining);

  el.btnSound.addEventListener('click', () => {
    soundOn = !soundOn;
    writeJSON(STORE_SOUND, soundOn);
    el.btnSound.textContent = soundOn ? 'Geluid aan' : 'Geluid uit';
    el.btnSound.setAttribute('aria-pressed', String(soundOn));
    if (soundOn) { unlockAudio(); whenAudioReady(() => beep(880, 0.18)); } else { releaseAudioSession(); }
  });

  [el.rowWork, el.rowRest, el.rowExercises, el.rowRounds, el.rowResetRound]
    .forEach((row) => row.addEventListener('click', () => openSheet(row.dataset.field)));

  el.rowLoad.addEventListener('click', openLoad);
  el.loadClose.addEventListener('click', () => { el.loadWrap.hidden = true; });
  el.loadScrim.addEventListener('click', () => { el.loadWrap.hidden = true; });

  el.stepUp.addEventListener('click', () => nudge(1));
  el.stepDown.addEventListener('click', () => nudge(-1));
  el.sheetOk.addEventListener('click', commitSheet);
  el.sheetCancel.addEventListener('click', closeSheet);
  el.scrim.addEventListener('click', closeSheet);

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') { closeSheet(); el.loadWrap.hidden = true; }
    if (event.code === 'Space' && el.sheetWrap.hidden && el.loadWrap.hidden) {
      event.preventDefault();
      toggle();
    }
  });

  // Terug uit de achtergrond: opnieuw uitrekenen waar we horen te zijn.
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState !== 'visible') return;
    if (wakeLock === null && state.running) requestWakeLock();
    if (state.running) { holdAudioSession(); if (audioCtx && audioCtx.state === 'suspended') audioCtx.resume(); }
    if (!state.running) return;
    let guard = 0;
    while (state.anchorRemaining - (Date.now() - state.anchor) / 1000 <= 0 && guard++ < 10000) {
      const overshoot = -(state.anchorRemaining - (Date.now() - state.anchor) / 1000);
      if (!advance()) return;
      state.anchor = Date.now() - overshoot * 1000;
    }
    tick();
  });

  window.addEventListener('beforeunload', () => { releaseWakeLock(); releaseAudioSession(); });

  /* ── Start ────────────────────────────────────────────────────── */
  el.btnSound.textContent = soundOn ? 'Geluid aan' : 'Geluid uit';
  el.btnSound.setAttribute('aria-pressed', String(soundOn));
  renderConfig();
  hardReset();

  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('sw.js').catch(() => { /* offline blijft optioneel */ });
    });
  }
})();
