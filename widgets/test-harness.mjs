// Minimal Scriptable API mock so the widget can be executed under Node.
import fs from "fs";

const SRC = new URL("./tics-dashboard.js", import.meta.url).pathname;
const FAMILY = process.argv[2] || "medium";
const MODE = process.argv[3] || "ok";
// A throwaway address, never a real wallet — it only has to survive bech32.
const TEST_ADDRESS = "0x1111111111111111111111111111111111111111";

// ── fixtures ────────────────────────────────────────────────────────
const E18 = "000000000000000000";
const FIX = {
  delegations: {
    delegation_responses: [
      { delegation: { validator_address: "qubeticsvaloper1aaa" }, balance: { denom: "attics", amount: "1250" + E18 } },
      { delegation: { validator_address: "qubeticsvaloper1bbb" }, balance: { denom: "attics", amount: "830" + E18 } },
      { delegation: { validator_address: "qubeticsvaloper1ccc" }, balance: { denom: "attics", amount: "410" + E18 } },
      { delegation: { validator_address: "qubeticsvaloper1ddd" }, balance: { denom: "attics", amount: "95" + E18 } },
    ],
  },
  rewards: { total: [{ denom: "attics", amount: "42731" + E18 + ".500000000000000000" }] },
  balances: { balances: [{ denom: "attics", amount: "317" + E18 }, { denom: "ibc/ABC", amount: "9999" }] },
  unbonding: {
    unbonding_responses: [
      { validator_address: "qubeticsvaloper1aaa", entries: [{ balance: "200" + E18 }, { balance: "50" + E18 }] },
    ],
  },
  price: { qubetics: { usd: 0.1873, usd_24h_change: -3.42 } },
  chart: { prices: Array.from({ length: 168 }, (_, i) => [i, 0.18 + Math.sin(i / 12) * 0.02 + i * 0.00005]) },
  validators: {
    validators: [
      { operator_address: "qubeticsvaloper1aaa", description: { moniker: "TicsForgeNode" } },
      { operator_address: "qubeticsvaloper1bbb", description: { moniker: "Stakecito" } },
      { operator_address: "qubeticsvaloper1ccc", description: { moniker: "Nodes.Guru" } },
    ],
  },
};

let activeMode = MODE === "cached" ? "ok" : MODE;

function route(url) {
  const MODE = activeMode;
  if (MODE === "offline") return null;
  if (MODE === "nochart" && url.includes("market_chart")) return null;
  if (MODE === "empty") {
    // Brand-new wallet: valid address, nothing staked, no rewards.
    if (url.includes("/staking/v1beta1/delegations/")) return { delegation_responses: [] };
    if (url.includes("/rewards")) return { rewards: [], total: [] };
    if (url.includes("/bank/v1beta1/balances/")) return { balances: [] };
    if (url.includes("/unbonding_delegations")) return { unbonding_responses: [] };
  }
  // Threshold cases: rewards + available just under / exactly on 1000 TICS.
  if (MODE === "below" || MODE === "atthreshold") {
    const rew = MODE === "below" ? "600" : "700";
    if (url.includes("/rewards")) return { total: [{ denom: "attics", amount: rew + E18 }] };
    if (url.includes("/bank/v1beta1/balances/")) return { balances: [{ denom: "attics", amount: "300" + E18 }] };
  }
  if (MODE === "apierror" && !url.includes("coingecko")) {
    return { code: 5, message: "rpc error: unknown address", details: [] };
  }
  if (url.includes("/staking/v1beta1/delegations/")) return FIX.delegations;
  if (url.includes("/rewards")) return MODE === "partial" ? null : FIX.rewards;
  if (url.includes("/bank/v1beta1/balances/")) return FIX.balances;
  if (url.includes("/unbonding_delegations")) return FIX.unbonding;
  if (url.includes("simple/price")) return MODE === "partial" ? null : FIX.price;
  if (url.includes("market_chart")) return FIX.chart;
  if (url.includes("/staking/v1beta1/validators")) return FIX.validators;
  return null;
}

// ── drawing primitives ──────────────────────────────────────────────
class Color { constructor(hex, a = 1) { this.hex = hex; this.alpha = a; } }
class Size { constructor(w, h) { this.width = w; this.height = h; } }
class Point { constructor(x, y) { this.x = x; this.y = y; } }
class Path {
  constructor() { this.pts = []; }
  move(p) { this.pts.push(p); }
  addLine(p) { this.pts.push(p); }
  closeSubpath() {}
}
class DrawContext {
  constructor() { this.size = null; this.opaque = true; this.respectScreenScale = false; this.ops = 0; }
  setFillColor() { this.ops++; }
  setStrokeColor() { this.ops++; }
  setLineWidth() { this.ops++; }
  addPath(p) {
    for (const pt of p.pts) {
      if (!isFinite(pt.x) || !isFinite(pt.y)) throw new Error(`sparkline produced non-finite point ${pt.x},${pt.y}`);
    }
    this.ops++;
  }
  fillPath() { this.ops++; }
  strokePath() { this.ops++; }
  getImage() { return { __image: "sparkline" }; }
}

const KNOWN_SYMBOLS = new Set([
  "lock.fill", "gift.fill", "banknote.fill", "chart.line.uptrend.xyaxis",
  "wallet.pass.fill", "clock.arrow.circlepath", "arrow.up.right",
  "arrow.down.right", "minus", "circle.fill",
]);
const usedSymbols = new Set();
const SFSymbol = {
  named(n) {
    usedSymbols.add(n);
    return KNOWN_SYMBOLS.has(n) ? { image: { __image: n } } : null;
  },
};

const mkFont = (kind) => (size) => {
  if (!isFinite(size)) throw new Error(`${kind} got non-finite size: ${size}`);
  return { kind, size };
};
const Font = {};
for (const k of ["system", "ultraLightSystem", "thinSystem", "lightSystem", "regularSystem",
  "mediumSystem", "semiboldSystem", "boldSystem", "heavySystem", "blackSystem",
  "regularRoundedSystem", "mediumRoundedSystem", "semiboldRoundedSystem",
  "boldRoundedSystem", "heavyRoundedSystem"]) {
  Font[k === "system" ? "systemFont" : k + "Font"] = mkFont(k);
}

// ── widget tree ─────────────────────────────────────────────────────
const tree = [];
let glowCount = 0;
let depth = 0;
const log = (s) => tree.push("  ".repeat(depth) + s);

class WidgetText {
  constructor(t) { this.text = t; log(`text "${t}"`); this.idx = tree.length - 1; }
  set font(v) {
    if (!v || !isFinite(v.size)) throw new Error(`bad font on "${this.text}"`);
    tree[this.idx] += `  [${v.size}pt]`;
  }
  set textColor(v) { if (!(v instanceof Color)) throw new Error(`bad textColor on "${this.text}"`); }
  set lineLimit(v) {} set minimumScaleFactor(v) {}
  centerAlignText() {} rightAlignText() {} leftAlignText() {}
}
class WidgetImage {
  constructor(i) { if (!i) throw new Error("addImage got null image"); log("image"); }
  set imageSize(v) {} set tintColor(v) {} set cornerRadius(v) {}
  centerAlignImage() {}
}
class WidgetStack {
  constructor(label = "stack") { this.label = label; log(label); }
  addStack() { depth++; const s = new WidgetStack("stack"); depth--; return s; }
  addText(t) { depth++; const x = new WidgetText(t); depth--; return x; }
  addImage(i) { depth++; const x = new WidgetImage(i); depth--; return x; }
  addSpacer(n) {}
  layoutHorizontally() {} layoutVertically() {}
  centerAlignContent() {} topAlignContent() {} bottomAlignContent() {}
  setPadding() {}
  set spacing(v) {} set size(v) { if (!(v instanceof Size)) throw new Error("size must be Size"); }
  set cornerRadius(v) {} set borderWidth(v) {} set borderColor(v) {}
  set backgroundColor(v) {
    if (!(v instanceof Color)) throw new Error("backgroundColor must be Color");
    // The compound-marker halo is the only stack filled at 0.1 alpha
    // (card bodies use 0.95, pills 0.18), so it is identifiable.
    if (v.alpha === 0.1) { glowCount++; tree.push("  ".repeat(depth) + "↑ GLOW HALO"); }
  }
  set url(v) {}
}
class ListWidget extends WidgetStack {
  constructor() { super("ListWidget"); this.presented = null; }
  setPadding() {} set refreshAfterDate(v) {} set backgroundGradient(v) {} set url(v) {}
  async presentSmall() { this.presented = "small"; }
  async presentMedium() { this.presented = "medium"; }
  async presentLarge() { this.presented = "large"; }
}
class LinearGradient { constructor() { this.colors = []; this.locations = []; } }

// ── platform ────────────────────────────────────────────────────────
const requestLog = [];
class Request {
  constructor(url) { this.url = url; this.headers = {}; this.timeoutInterval = 60; }
  async loadJSON() {
    requestLog.push(this.url);
    const r = route(this.url);
    if (r === null) throw new Error("network error (mocked)");
    return r;
  }
}

let CACHE = null;
const FileManager = {
  local: () => ({
    cacheDirectory: () => "/cache",
    joinPath: (a, b) => a + "/" + b,
    fileExists: () => CACHE !== null,
    readString: () => CACHE,
    writeString: (_p, s) => { CACHE = s; },
  }),
};

const Script = { setWidget() {}, complete() {} };

Object.assign(globalThis, {
  Color, Size, Point, Path, DrawContext, SFSymbol, Font,
  ListWidget, LinearGradient, Request, FileManager, Script,
  config: { widgetFamily: FAMILY === "app" ? null : FAMILY, runsInWidget: FAMILY !== "app" },
  // The committed script ships a placeholder address, so the harness supplies
  // its own via widgetParameter — otherwise every mode would just render the
  // "address not set" screen and silently test nothing.
  args: {
    widgetParameter: MODE === "badaddr" ? "not-an-address"
                   : MODE === "unset"   ? null
                   : TEST_ADDRESS,
  },
  Device: { isUsingDarkAppearance: () => true },
});

// ── run ─────────────────────────────────────────────────────────────
const src = fs.readFileSync(SRC, "utf8");
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;

try {
  if (MODE === "cached") {
    // Priming run populates the cache, then the second run goes fully offline.
    await new AsyncFunction(src)();
    if (CACHE === null) throw new Error("priming run never wrote a cache file");
    tree.length = 0;
    glowCount = 0;
    requestLog.length = 0;
    activeMode = "offline";
  }
  await new AsyncFunction(src)();
  console.log(`✅ ${FAMILY}/${MODE} rendered — ${tree.length} nodes, ${requestLog.length} requests, ${glowCount} glow`);
  const unknown = [...usedSymbols].filter(s => !KNOWN_SYMBOLS.has(s));
  if (unknown.length) console.log(`⚠️  unknown SF Symbols: ${unknown.join(", ")}`);
  if (process.env.TREE === "1") console.log(tree.join("\n"));
} catch (e) {
  console.log(`❌ ${FAMILY}/${MODE} FAILED: ${e.message}`);
  console.log(e.stack.split("\n").slice(0, 6).join("\n"));
  process.exit(1);
}
