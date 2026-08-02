// Variables used by Scriptable.
// These must be at the very top of the file. Do not edit.
// icon-color: teal; icon-glyph: chart-pie;

// ╔══════════════════════════════════════════════════════════════════╗
// ║  TICS DASHBOARD — Qubetics staking widget for Scriptable         ║
// ║                                                                  ║
// ║  Small  : total value + staked / rewards / price                 ║
// ║  Medium : hero total + Staked / Rewards / Available rows         ║
// ║  Large  : hero total + 7d sparkline + 4 cards + validator list   ║
// ║                                                                  ║
// ║  Privacy: only the Qubetics REST node and CoinGecko are called.  ║
// ║  No wallet address ever appears in a tap-through URL.            ║
// ║                                                                  ║
// ║  SETUP                                                           ║
// ║  1. Put your address in MY_ADDRESS below (0x… or qubetics1…).    ║
// ║  2. Add a Scriptable widget, pick this script.                   ║
// ║  3. Optional: type an address in the widget's "Parameter" field  ║
// ║     to override MY_ADDRESS for that one widget.                  ║
// ╚══════════════════════════════════════════════════════════════════╝

// ─── CONFIG ────────────────────────────────────────────────────────
// Your address stays on your device — keep it out of any repo you push.
const MY_ADDRESS = "INSERT YOUR ADDRESS HERE";

const CFG = {
  restEndpoint: "https://swagger.qubetics.com",
  coingeckoId:  "qubetics",
  baseDenom:    "attics", // on-chain base denom
  decimals:     18,       // 1 TICS = 10^18 attics
  ticker:       "TICS",
  refreshMin:   10,       // iOS treats this as a hint, not a promise
  sparklineDays: 7,
  showSparkline: true,
  maxValidators: 3,       // rows in the large-widget validator list
  // Rewards + Available light up once their combined TICS hits this — the
  // cue to compound. Set to 0 to always show it, Infinity to disable.
  compoundThreshold: 1000,
  // Global multiplier for the big numbers only (labels stay put). Nudge to
  // 1.1 / 1.2 if they still read small on your phone, 0.9 to pull them back.
  fontScale:     1.0,
  showValueUsd:  true,    // small USD line under each card value (large only)
  tapUrl:        null,    // e.g. "https://ticsscan.com" — null keeps it private
};
// ───────────────────────────────────────────────────────────────────

// ══ BECH32 ═════════════════════════════════════════════════════════
const B32_CS  = "qpzry9x8gf2tvdw0s3jn54khce6mua7l";
const B32_GEN = [0x3b6a57b2, 0x26508e6d, 0x1ea119fa, 0x3d4233dd, 0x2a1462b3];

function b32Polymod(values) {
  let chk = 1;
  for (const v of values) {
    const top = chk >> 25;
    chk = ((chk & 0x1ffffff) << 5) ^ v;
    for (let i = 0; i < 5; i++) if ((top >> i) & 1) chk ^= B32_GEN[i];
  }
  return chk;
}

function b32HrpExpand(hrp) {
  const out = [];
  for (const ch of hrp) out.push(ch.charCodeAt(0) >> 5);
  out.push(0);
  for (const ch of hrp) out.push(ch.charCodeAt(0) & 31);
  return out;
}

function b32Checksum(hrp, data) {
  const values = b32HrpExpand(hrp).concat(data, [0, 0, 0, 0, 0, 0]);
  const mod = b32Polymod(values) ^ 1;
  const out = [];
  for (let i = 0; i < 6; i++) out.push((mod >> (5 * (5 - i))) & 31);
  return out;
}

function b32Encode(hrp, data) {
  const combined = data.concat(b32Checksum(hrp, data));
  return hrp + "1" + combined.map(d => B32_CS[d]).join("");
}

function convertBits(data, fromBits, toBits, pad) {
  let acc = 0, bits = 0;
  const out = [], maxv = (1 << toBits) - 1;
  for (const value of data) {
    if (value < 0 || (value >> fromBits) !== 0) return null;
    acc = (acc << fromBits) | value;
    bits += fromBits;
    while (bits >= toBits) {
      bits -= toBits;
      out.push((acc >> bits) & maxv);
    }
  }
  if (pad) {
    if (bits > 0) out.push((acc << (toBits - bits)) & maxv);
  } else if (bits >= fromBits || ((acc << (toBits - bits)) & maxv) !== 0) {
    return null;
  }
  return out;
}

function evmToNative(addr) {
  const hex = addr.replace(/^0x/i, "").toLowerCase();
  if (hex.length !== 40 || !/^[0-9a-f]+$/.test(hex)) return null;
  const bytes = [];
  for (let i = 0; i < hex.length; i += 2) bytes.push(parseInt(hex.slice(i, i + 2), 16));
  const words = convertBits(bytes, 8, 5, true);
  return words ? b32Encode("qubetics", words) : null;
}

const PLACEHOLDER = "INSERT YOUR ADDRESS HERE";

function toNativeAddress(addr) {
  const a = String(addr || "").trim();
  if (!a || a === PLACEHOLDER) return null;
  if (a.startsWith("qubetics1")) return a;
  if (/^0x/i.test(a)) return evmToNative(a);
  return null;
}

// ══ NETWORK ════════════════════════════════════════════════════════
async function fetchJSON(url, timeout = 12) {
  try {
    const req = new Request(url);
    req.timeoutInterval = timeout;
    req.headers = { Accept: "application/json" };
    return await req.loadJSON();
  } catch (e) {
    return null;
  }
}

// ══ CACHE ══════════════════════════════════════════════════════════
// Widgets refresh on iOS's schedule and CoinGecko rate-limits hard, so a
// failed call should show slightly stale numbers rather than a wall of "--".
const fm = FileManager.local();
const CACHE_PATH = fm.joinPath(fm.cacheDirectory(), "tics-dashboard-cache.json");
const CACHE_MAX_AGE_MS = 6 * 60 * 60 * 1000; // past this, show "--" instead of lying

function readCache() {
  try {
    if (!fm.fileExists(CACHE_PATH)) return null;
    return JSON.parse(fm.readString(CACHE_PATH));
  } catch (e) {
    return null;
  }
}

function writeCache(obj) {
  try {
    fm.writeString(CACHE_PATH, JSON.stringify(obj));
  } catch (e) { /* cache is best-effort */ }
}

// ══ AMOUNT PARSING ═════════════════════════════════════════════════
const UNIT = Math.pow(10, CFG.decimals);

// Cosmos returns amounts as strings; rewards come back as decimals with
// 18 extra places. Accepts a string, a {denom, amount} coin, or null.
function coinAmount(coin) {
  if (coin == null) return 0;
  if (typeof coin === "string" || typeof coin === "number") return Number(coin) / UNIT;
  if (coin.amount === undefined) return 0;
  if (coin.denom && coin.denom !== CFG.baseDenom && !/tics$/i.test(coin.denom)) return 0;
  const n = Number(coin.amount);
  return isFinite(n) ? n / UNIT : 0;
}

function sumCoins(arr) {
  if (!Array.isArray(arr)) return 0;
  return arr.reduce((t, c) => t + coinAmount(c), 0);
}

// ══ FORMATTING ═════════════════════════════════════════════════════
// Abbreviate only once the digits stop fitting — a 4-digit stake is more
// useful as "2,585" than as "2.6K".
function fmtNum(n) {
  if (n == null || !isFinite(n)) return "--";
  if (n >= 1e9) return (n / 1e9).toFixed(2) + "B";
  if (n >= 1e6) return (n / 1e6).toFixed(2) + "M";
  if (n >= 1e4) return (n / 1e3).toFixed(1) + "K";
  if (n >= 1e3) return Math.round(n).toLocaleString("en-US");
  if (n >= 1)   return n.toFixed(2);
  if (n > 0)    return n.toFixed(4);
  return "0";
}

function fmtUsd(n) {
  if (n == null || !isFinite(n)) return "--";
  if (n >= 1e6) return "$" + (n / 1e6).toFixed(2) + "M";
  if (n >= 1e3) return "$" + (n / 1e3).toFixed(2) + "K";
  if (n > 0 && n < 0.01) return "$" + n.toFixed(6);
  return "$" + n.toFixed(2);
}

function fmtPrice(n) {
  if (n == null || !isFinite(n)) return "--";
  const dp = n >= 100 ? 2 : n >= 1 ? 3 : 4;
  return "$" + Number(n).toFixed(dp);
}

function fmtPct(n) {
  if (n == null || !isFinite(n)) return "--";
  return (n >= 0 ? "+" : "") + n.toFixed(2) + "%";
}

// Shrink the font as the string grows so long balances never truncate. Kept
// gentle — iOS also auto-scales to fit, so being aggressive here just makes
// every number small for no reason.
function valueFont(str, base) {
  const L = String(str || "").length;
  const f = L <= 6 ? 1 : L <= 9 ? 0.94 : L <= 12 ? 0.86 : 0.72;
  return Math.round(base * f);
}

// ══ FETCH ══════════════════════════════════════════════════════════
const FAMILY  = config.widgetFamily || "medium";
const SMALL   = FAMILY === "small";
const LARGE   = FAMILY === "large";

const inputAddr  = (args.widgetParameter || MY_ADDRESS || "").trim();
const nativeAddr = toNativeAddress(inputAddr);

const state = {
  staked: null, rewards: null, liquid: null, unbonding: null,
  price: null, change24h: null, spark: null, validators: [],
  stale: false, ok: false, cacheAge: 0,
};

if (nativeAddr) {
  const base = CFG.restEndpoint.replace(/\/+$/, "");
  // Only large renders the sparkline, so only large should pay for the chart.
  const wantSpark = CFG.showSparkline && LARGE;

  const jobs = [
    fetchJSON(`${base}/cosmos/staking/v1beta1/delegations/${nativeAddr}?pagination.limit=200`),
    fetchJSON(`${base}/cosmos/distribution/v1beta1/delegators/${nativeAddr}/rewards`),
    fetchJSON(`${base}/cosmos/bank/v1beta1/balances/${nativeAddr}`),
    fetchJSON(`${base}/cosmos/staking/v1beta1/delegators/${nativeAddr}/unbonding_delegations`),
    fetchJSON(`https://api.coingecko.com/api/v3/simple/price?ids=${CFG.coingeckoId}&vs_currencies=usd&include_24hr_change=true`),
    wantSpark
      ? fetchJSON(`https://api.coingecko.com/api/v3/coins/${CFG.coingeckoId}/market_chart?vs_currency=usd&days=${CFG.sparklineDays}`)
      : Promise.resolve(null),
    LARGE
      ? fetchJSON(`${base}/cosmos/staking/v1beta1/validators?status=BOND_STATUS_BONDED&pagination.limit=300`)
      : Promise.resolve(null),
  ];

  const [deleg, rewards, balances, unbond, price, chart, vals] = await Promise.all(jobs);

  // Staked, plus per-validator amounts for the large layout.
  const perValidator = [];
  if (Array.isArray(deleg?.delegation_responses)) {
    state.staked = deleg.delegation_responses.reduce((sum, d) => {
      const amt = coinAmount(d.balance);
      const op  = d.delegation?.validator_address;
      if (op) perValidator.push({ op, amt });
      return sum + amt;
    }, 0);
  }

  if (rewards?.total) state.rewards = sumCoins(rewards.total);
  if (balances?.balances) state.liquid = sumCoins(balances.balances);

  if (Array.isArray(unbond?.unbonding_responses)) {
    state.unbonding = unbond.unbonding_responses.reduce((sum, u) => {
      const entries = Array.isArray(u.entries) ? u.entries : [];
      return sum + entries.reduce((s, e) => s + Number(e.balance || 0) / UNIT, 0);
    }, 0);
  }

  const pd = price?.[CFG.coingeckoId];
  if (pd) {
    state.price     = pd.usd ?? null;
    state.change24h = pd.usd_24h_change ?? null;
  }

  if (Array.isArray(chart?.prices) && chart.prices.length > 1) {
    state.spark = chart.prices.map(p => p[1]).filter(v => isFinite(v));
  }

  // Map operator address → moniker so the list shows names, not bech32 blobs.
  if (perValidator.length && Array.isArray(vals?.validators)) {
    const names = {};
    for (const v of vals.validators) {
      if (v.operator_address) names[v.operator_address] = v.description?.moniker || null;
    }
    state.validators = perValidator
      .sort((a, b) => b.amt - a.amt)
      .slice(0, CFG.maxValidators)
      .map(v => ({ name: names[v.op] || (v.op.slice(0, 14) + "…"), amt: v.amt }));
  }

  const gotLiveData = state.staked != null || state.rewards != null || state.price != null;

  // Backfill missing fields from cache BEFORE writing it back, otherwise a run
  // where only one API answered would overwrite good values with nulls.
  const cached = readCache();
  const cacheAge = cached ? Date.now() - (cached.ts || 0) : Infinity;
  if (cached && cacheAge < CACHE_MAX_AGE_MS) {
    for (const k of ["staked", "rewards", "liquid", "unbonding", "price", "change24h", "spark"]) {
      if (state[k] == null && cached[k] != null) { state[k] = cached[k]; state.stale = true; }
    }
    if (!state.validators.length && Array.isArray(cached.validators) && cached.validators.length) {
      state.validators = cached.validators;
      state.stale = true;
    }
    if (state.stale) state.cacheAge = cacheAge;
  }

  // Only refresh the cache when something live came back; a fully failed run
  // must leave the old timestamp alone so the data can age out.
  if (gotLiveData) {
    writeCache({
      ts: Date.now(),
      staked: state.staked, rewards: state.rewards, liquid: state.liquid,
      unbonding: state.unbonding, price: state.price, change24h: state.change24h,
      spark: state.spark, validators: state.validators,
    });
  }
  state.ok = gotLiveData;
}

// A total of 0 must mean "the wallet is empty", never "every call failed" —
// so if no component resolved, the total stays unknown.
const parts = ["staked", "rewards", "liquid", "unbonding"].map(k => state[k]);
const totalTics = parts.some(v => v != null)
  ? parts.reduce((t, v) => t + (v || 0), 0)
  : null;
const totalUsd  = (totalTics != null && state.price != null) ? totalTics * state.price : null;
const rewardsUsd = (state.rewards != null && state.price != null) ? state.rewards * state.price : null;

// What could be claimed and re-staked right now. A failed call leaves its part
// at 0, which can only understate the total — so the marker never lights up on
// incomplete data.
const compoundable = (state.rewards || 0) + (state.liquid || 0);
const readyToCompound = compoundable >= CFG.compoundThreshold;

// The small USD line under a card value, or null when it can't be computed
// or the user turned it off to give the numbers more room.
const usdSub = (tics) =>
  (CFG.showValueUsd && tics != null && state.price != null) ? fmtUsd(tics * state.price) : null;

// ══ THEME ══════════════════════════════════════════════════════════
const UP   = "#22c55e";
const DOWN = "#ff5f87";
const FLAT = "#7a98c4";

const C = {
  bg1:     new Color("#070e1a"),
  bg2:     new Color("#0d1a2e"),
  cardBg:  new Color("#0b1628", 0.95),
  cardBor: new Color("#1e3a5f", 0.6),
  title:   new Color("#e2eeff"),
  sub:     new Color("#ffffff", 0.55),
  foot:    new Color("#ffffff", 0.45),
  text:    new Color("#ffffff"),
  staked:  "#22c55e",
  rewards: "#4f8ef7",
  liquid:  "#00e5c8",
  unbond:  "#a78bfa",
  usd:     "#ff9f0a",
  error:   new Color("#f43f5e"),
};

const trend = state.change24h == null ? FLAT
            : state.change24h > 0 ? UP
            : state.change24h < 0 ? DOWN : FLAT;

// ══ LAYOUT CONSTANTS ═══════════════════════════════════════════════
const SCALE  = LARGE ? 1.35 : 1;
// Large packs the most in, so it gets tighter padding than SCALE would give —
// the reclaimed height is what stops iOS auto-shrinking the numbers to fit.
const GAP    = SMALL ? 5 : LARGE ? 8  : 7;
const PAD_V  = SMALL ? 6 : LARGE ? 9  : 8;
const PAD_H  = SMALL ? 8 : LARGE ? 12 : 10;
const WIDTH  = SMALL ? 155 : 338;
const CARD_W = Math.floor((WIDTH - GAP - (SMALL ? 22 : 28)) / 2);

const f  = (size, weight = "bold") => {
  const s = Math.round(size * SCALE);
  return weight === "bold"     ? Font.boldRoundedSystemFont(s)
       : weight === "semibold" ? Font.semiboldRoundedSystemFont(s)
       : weight === "medium"   ? Font.mediumRoundedSystemFont(s)
       :                         Font.regularRoundedSystemFont(s);
};

// ══ WIDGET SHELL ═══════════════════════════════════════════════════
const w = new ListWidget();
const grad = new LinearGradient();
grad.colors = [C.bg1, C.bg2];
grad.locations = [0, 1];
w.backgroundGradient = grad;
w.backgroundColor = C.bg1;
w.setPadding(SMALL ? 10 : 13, SMALL ? 11 : 14, SMALL ? 10 : 12, SMALL ? 11 : 14);
w.refreshAfterDate = new Date(Date.now() + CFG.refreshMin * 60 * 1000);
if (CFG.tapUrl) w.url = CFG.tapUrl;

// ══ COMPONENTS ═════════════════════════════════════════════════════
function symbol(name, size, color) {
  const sym = SFSymbol.named(name) || SFSymbol.named("circle.fill");
  return { image: sym.image, size: new Size(size, size), color };
}

function addSymbol(stack, name, size, color) {
  const s = symbol(name, size, color);
  const img = stack.addImage(s.image);
  img.imageSize = s.size;
  img.tintColor = s.color;
  return img;
}

// Small rounded pill: icon + label, used for headers and card badges.
function addPill(stack, colorHex, icon, label, fontSize) {
  const pill = stack.addStack();
  pill.setPadding(2, 6, 2, 6);
  pill.cornerRadius = 8;
  pill.backgroundColor = new Color(colorHex, 0.18);
  pill.borderWidth = 1;
  pill.borderColor = new Color(colorHex, 0.32);
  pill.centerAlignContent();
  if (icon) {
    addSymbol(pill, icon, Math.round(fontSize * 1.05), new Color(colorHex));
    pill.addSpacer(3);
  }
  const t = pill.addText(label);
  t.font = f(fontSize, "semibold");
  t.textColor = new Color("#ffffff", 0.9);
  t.lineLimit = 1;
  t.minimumScaleFactor = 0.6;
  return pill;
}

function addCard(parent, colorHex, icon, label, value, sub, glow) {
  const outer = parent.addStack();
  outer.layoutVertically();

  let host = outer;
  if (glow) {
    const halo = outer.addStack();
    halo.layoutVertically();
    halo.backgroundColor = new Color(colorHex, 0.1);
    halo.borderWidth = 1;
    halo.borderColor = new Color(colorHex, 0.55);
    halo.cornerRadius = 16;
    halo.setPadding(1.5, 1.5, 1.5, 1.5);
    host = halo;
  }

  const card = host.addStack();
  card.layoutVertically();
  card.spacing = 3;
  card.backgroundColor = C.cardBg;
  card.cornerRadius = glow ? 15 : 14;
  card.borderWidth = 1;
  card.borderColor = glow ? new Color(colorHex, 0.35) : C.cardBor;
  card.setPadding(PAD_V, PAD_H, PAD_V, PAD_H);

  addPill(card, colorHex, icon, label, SMALL ? 9 : 10);

  const val = card.addText(String(value || "--"));
  val.font = Font.boldRoundedSystemFont(
    valueFont(value, Math.round((SMALL ? 18 : 22) * SCALE * CFG.fontScale)));
  val.textColor = C.text;
  val.lineLimit = 1;
  val.minimumScaleFactor = 0.7;

  if (sub) {
    const s = card.addText(sub);
    s.font = f(SMALL ? 8 : LARGE ? 7 : 9, "medium");
    s.textColor = C.sub;
    s.lineLimit = 1;
    s.minimumScaleFactor = 0.6;
  }
  return outer;
}

// Filled sparkline drawn with DrawContext — no external chart library.
function sparkline(values, width, height, colorHex) {
  if (!Array.isArray(values) || values.length < 2) return null;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const pad = 2;
  const x = i => (i / (values.length - 1)) * (width - pad * 2) + pad;
  const y = v => height - pad - ((v - min) / span) * (height - pad * 2);

  const ctx = new DrawContext();
  ctx.size = new Size(width, height);
  ctx.opaque = false;
  ctx.respectScreenScale = true;

  const fill = new Path();
  fill.move(new Point(x(0), height));
  values.forEach((v, i) => fill.addLine(new Point(x(i), y(v))));
  fill.addLine(new Point(x(values.length - 1), height));
  fill.closeSubpath();
  ctx.setFillColor(new Color(colorHex, 0.18));
  ctx.addPath(fill);
  ctx.fillPath();

  const line = new Path();
  line.move(new Point(x(0), y(values[0])));
  values.forEach((v, i) => { if (i) line.addLine(new Point(x(i), y(v))); });
  ctx.setStrokeColor(new Color(colorHex, 0.95));
  ctx.setLineWidth(2);
  ctx.addPath(line);
  ctx.strokePath();

  return ctx.getImage();
}

// ══ RENDER ═════════════════════════════════════════════════════════
if (!nativeAddr) {
  w.addSpacer();
  const unset = !inputAddr || inputAddr === PLACEHOLDER;
  const e1 = w.addText(unset ? "⚠️ Address not set" : "⚠️ Invalid address");
  e1.font = f(12);
  e1.textColor = C.error;
  e1.centerAlignText();
  const e2 = w.addText(unset
    ? "Edit the script and set MY_ADDRESS to your 0x… or qubetics1… address"
    : "Could not parse: " + inputAddr);
  e2.font = f(9, "regular");
  e2.textColor = C.sub;
  e2.centerAlignText();
  e2.lineLimit = 2;
  w.addSpacer();
} else if (SMALL) {
  // ── SMALL ────────────────────────────────────────────────────────
  const head = w.addStack();
  head.centerAlignContent();
  const ht = head.addText(CFG.ticker);
  ht.font = f(10, "semibold");
  ht.textColor = C.title;
  head.addSpacer();
  const ch = head.addText(fmtPct(state.change24h));
  ch.font = f(9, "semibold");
  ch.textColor = new Color(trend);

  w.addSpacer(4);

  const hero = w.addText(fmtUsd(totalUsd));
  hero.font = Font.boldRoundedSystemFont(valueFont(fmtUsd(totalUsd), Math.round(25 * CFG.fontScale)));
  hero.textColor = C.text;
  hero.lineLimit = 1;
  hero.minimumScaleFactor = 0.5;

  const heroSub = w.addText(fmtNum(totalTics) + " " + CFG.ticker);
  heroSub.font = f(9, "medium");
  heroSub.textColor = C.sub;
  heroSub.lineLimit = 1;

  w.addSpacer(7);

  function addRow(colorHex, icon, label, value) {
    const row = w.addStack();
    row.centerAlignContent();
    addSymbol(row, icon, 10, new Color(colorHex));
    row.addSpacer(5);
    const l = row.addText(label);
    l.font = f(10, "medium");
    l.textColor = new Color("#ffffff", 0.7);
    l.lineLimit = 1;
    row.addSpacer();
    const v = row.addText(String(value));
    v.font = Font.boldRoundedSystemFont(11);
    v.textColor = C.text;
    v.lineLimit = 1;
    v.minimumScaleFactor = 0.6;
    w.addSpacer(5);
  }

  addRow(C.staked,  "lock.fill",                 "Staked",  fmtNum(state.staked));
  addRow(C.rewards, "gift.fill",                 "Rewards", fmtNum(state.rewards));
  addRow(trend,     "chart.line.uptrend.xyaxis", "Price",   fmtPrice(state.price));
  w.addSpacer();
} else {
  // ── MEDIUM & LARGE ───────────────────────────────────────────────
  const head = w.addStack();
  head.centerAlignContent();
  const ht = head.addText(LARGE ? "TICS Delegator Dashboard" : "TICS Dashboard");
  ht.font = f(11, "semibold");
  ht.textColor = C.title;
  ht.lineLimit = 1;
  ht.minimumScaleFactor = 0.6;
  head.addSpacer();
  const pillLabel = state.price == null
    ? "price n/a"
    : fmtPrice(state.price) + (state.change24h != null ? "  " + fmtPct(state.change24h) : "");
  addPill(head, trend,
    state.change24h == null ? "minus" : state.change24h >= 0 ? "arrow.up.right" : "arrow.down.right",
    pillLabel, SMALL ? 9 : 10);

  w.addSpacer(LARGE ? 10 : 7);

  if (LARGE) {
    // Hero row: total value on the left, 7d sparkline on the right.
    const heroRow = w.addStack();
    heroRow.centerAlignContent();

    const left = heroRow.addStack();
    left.layoutVertically();
    const lbl = left.addText("TOTAL VALUE");
    lbl.font = f(9, "semibold");
    lbl.textColor = C.sub;
    const hero = left.addText(fmtUsd(totalUsd));
    hero.font = Font.boldRoundedSystemFont(Math.round(36 * CFG.fontScale));
    hero.textColor = C.text;
    hero.lineLimit = 1;
    hero.minimumScaleFactor = 0.5;
    const heroSub = left.addText(fmtNum(totalTics) + " " + CFG.ticker);
    heroSub.font = f(10, "medium");
    heroSub.textColor = C.sub;

    heroRow.addSpacer();

    const img = sparkline(state.spark, 150, 62, trend);
    if (img) {
      const sparkStack = heroRow.addStack();
      sparkStack.layoutVertically();
      const si = sparkStack.addImage(img);
      si.imageSize = new Size(150, 62);
      const cap = sparkStack.addText(CFG.sparklineDays + "d");
      cap.font = f(8, "medium");
      cap.textColor = C.foot;
      cap.rightAlignText();
    }

    w.addSpacer(GAP);

    // 2x2 cards
    const row1 = w.addStack();
    row1.spacing = GAP;
    const c1 = row1.addStack(); c1.layoutVertically(); c1.size = new Size(CARD_W, 0);
    addCard(c1, C.staked, "lock.fill", "Staked",
      fmtNum(state.staked) + " " + CFG.ticker,
      usdSub(state.staked),
      false);
    const c2 = row1.addStack(); c2.layoutVertically(); c2.size = new Size(CARD_W, 0);
    addCard(c2, C.rewards, "gift.fill", "Rewards",
      fmtNum(state.rewards) + " " + CFG.ticker,
      CFG.showValueUsd && rewardsUsd != null ? fmtUsd(rewardsUsd) : null,
      readyToCompound);

    w.addSpacer(GAP);

    const row2 = w.addStack();
    row2.spacing = GAP;
    const c3 = row2.addStack(); c3.layoutVertically(); c3.size = new Size(CARD_W, 0);
    addCard(c3, C.liquid, "wallet.pass.fill", "Available",
      fmtNum(state.liquid) + " " + CFG.ticker,
      usdSub(state.liquid),
      readyToCompound);
    const c4 = row2.addStack(); c4.layoutVertically(); c4.size = new Size(CARD_W, 0);
    addCard(c4, C.unbond, "clock.arrow.circlepath", "Unbonding",
      fmtNum(state.unbonding) + " " + CFG.ticker,
      usdSub(state.unbonding),
      false);

    // Validator breakdown
    if (state.validators.length) {
      w.addSpacer(GAP);
      const secTitle = w.addText("DELEGATIONS");
      secTitle.font = f(9, "semibold");
      secTitle.textColor = C.sub;
      w.addSpacer(4);

      for (const v of state.validators) {
        const row = w.addStack();
        row.centerAlignContent();
        const dot = row.addStack();
        dot.size = new Size(6, 6);
        dot.cornerRadius = 3;
        dot.backgroundColor = new Color(C.staked);
        row.addSpacer(6);
        const n = row.addText(v.name);
        n.font = f(10, "medium");
        n.textColor = new Color("#ffffff", 0.8);
        n.lineLimit = 1;
        n.minimumScaleFactor = 0.6;
        row.addSpacer();
        const a = row.addText(fmtNum(v.amt) + " " + CFG.ticker);
        a.font = f(10, "semibold");
        a.textColor = C.text;
        a.lineLimit = 1;
        w.addSpacer(3);
      }
    }
  } else {
    // ── MEDIUM: hero total left, compact stat rows right ─────────────
    // A 2x2 grid of cards does not fit medium's ~133pt of content height once
    // each card carries a badge, a value and a USD line. This shape does, with
    // margin to spare, instead of relying on iOS to shrink text into place.
    const body = w.addStack();
    body.centerAlignContent();

    const left = body.addStack();
    left.layoutVertically();
    const lbl = left.addText("TOTAL VALUE");
    lbl.font = f(9, "semibold");
    lbl.textColor = C.sub;
    const hero = left.addText(fmtUsd(totalUsd));
    hero.font = Font.boldRoundedSystemFont(
      valueFont(fmtUsd(totalUsd), Math.round(30 * CFG.fontScale)));
    hero.textColor = C.text;
    hero.lineLimit = 1;
    hero.minimumScaleFactor = 0.5;
    const heroSub = left.addText(fmtNum(totalTics) + " " + CFG.ticker);
    heroSub.font = f(9, "medium");
    heroSub.textColor = C.sub;
    heroSub.lineLimit = 1;

    body.addSpacer();

    const rows = body.addStack();
    rows.layoutVertically();
    rows.spacing = 4;
    rows.size = new Size(158, 0);

    // Row form of the compound marker: same tint and threshold as the cards.
    function addStatRow(colorHex, label, value, marked) {
      const row = rows.addStack();
      row.centerAlignContent();
      row.setPadding(2, 6, 2, 6);
      row.cornerRadius = 8;
      if (marked) {
        row.backgroundColor = new Color(colorHex, 0.1);
        row.borderWidth = 1;
        row.borderColor = new Color(colorHex, 0.35);
      }
      const dot = row.addStack();
      dot.size = new Size(7, 7);
      dot.cornerRadius = 3.5;
      dot.backgroundColor = new Color(colorHex);
      row.addSpacer(7);
      const l = row.addText(label);
      l.font = f(11, "medium");
      l.textColor = new Color("#ffffff", 0.75);
      l.lineLimit = 1;
      row.addSpacer();
      // No " TICS" suffix here — the header already says it, and the five
      // characters saved are what let the value run at 13pt.
      const v = row.addText(value);
      v.font = Font.boldRoundedSystemFont(13);
      v.textColor = C.text;
      v.lineLimit = 1;
      v.minimumScaleFactor = 0.6;
    }

    addStatRow(C.staked,  "Staked",    fmtNum(state.staked),  false);
    addStatRow(C.rewards, "Rewards",   fmtNum(state.rewards), readyToCompound);
    addStatRow(C.liquid,  "Available", fmtNum(state.liquid),  readyToCompound);
  }

  w.addSpacer();
}

// ══ FOOTER ═════════════════════════════════════════════════════════
const now = new Date();
const hh = String(now.getHours()).padStart(2, "0");
const mm = String(now.getMinutes()).padStart(2, "0");
function fmtAge(ms) {
  const m = Math.round(ms / 60000);
  if (m < 1) return "just now";
  if (m < 60) return m + "m old";
  const h = Math.round(m / 60);
  return h < 24 ? h + "h old" : Math.round(h / 24) + "d old";
}

const foot = w.addText(
  state.stale ? "⚠︎ cached · " + fmtAge(state.cacheAge)
              : "Updated " + hh + ":" + mm
);
foot.font = f(SMALL ? 8 : 9, "regular");
foot.textColor = C.foot;
foot.lineLimit = 1;
foot.minimumScaleFactor = 0.6;

// ══ PRESENT ════════════════════════════════════════════════════════
if (config.runsInWidget) {
  Script.setWidget(w);
} else {
  // Running inside the Scriptable app — preview whichever size you edited for.
  await w.presentMedium();
}
Script.complete();
