// Minimal Scriptable API mock so the widget can be executed under Node.
import fs from "fs";

const SRC = process.env.WIDGET_SRC || new URL("./tics-dashboard.js", import.meta.url).pathname;
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

// ── vertical budget ─────────────────────────────────────────────────
// Widgets have a fixed height; overflowing it makes iOS clip the top and
// bottom rather than error. Rendering alone therefore proves nothing, so we
// estimate stacked height and fail when a family blows its budget.
// Rough by design — line height ~1.2x point size — but it catches the
// difference between "fits with margin" and "needs 1.4x the space it has".
const BUDGET = {            // widget height minus vertical padding
  small:  { h: 155, pad: 20 },
  medium: { h: 158, pad: 25 },
  large:  { h: 354, pad: 25 },
  app:    { h: 158, pad: 25 },
};

// Vertical stack = sum of children + spacing; horizontal = tallest child.
function nodeHeight(n) {
  if (n.type !== "stack") return n.h;
  if (n.fixedH != null) return n.fixedH + n.padT + n.padB;
  const kids = n.children.map(nodeHeight);
  const inner = n.vertical
    ? kids.reduce((a, b) => a + b, 0) + n.spacing * Math.max(0, kids.length - 1)
    : (kids.length ? Math.max(...kids) : 0);
  return inner + n.padT + n.padB;
}

class WidgetText {
  constructor(t, sink) {
    this.text = t; log(`text "${t}"`); this.idx = tree.length - 1;
    this.node = { type: "text", h: 0 };
    sink.push(this.node);
  }
  set font(v) {
    if (!v || !isFinite(v.size)) throw new Error(`bad font on "${this.text}"`);
    tree[this.idx] += `  [${v.size}pt]`;
    this.node.h = Math.round(v.size * 1.2);
  }
  set textColor(v) { if (!(v instanceof Color)) throw new Error(`bad textColor on "${this.text}"`); }
  set lineLimit(v) {} set minimumScaleFactor(v) {}
  centerAlignText() {} rightAlignText() {} leftAlignText() {}
}
class WidgetImage {
  constructor(i, sink) {
    if (!i) throw new Error("addImage got null image");
    log("image");
    this.node = { type: "image", h: 0 };
    sink.push(this.node);
  }
  set imageSize(v) { this.node.h = v.height; }
  set tintColor(v) {} set cornerRadius(v) {}
  centerAlignImage() {}
}
class WidgetStack {
  constructor(label = "stack", sink = null) {
    this.label = label; log(label);
    this.node = { type: "stack", vertical: false, children: [], padT: 0, padB: 0, spacing: 0, fixedH: null };
    if (sink) sink.push(this.node);
  }
  addStack() { depth++; const s = new WidgetStack("stack", this.node.children); depth--; return s; }
  addText(t) { depth++; const x = new WidgetText(t, this.node.children); depth--; return x; }
  addImage(i) { depth++; const x = new WidgetImage(i, this.node.children); depth--; return x; }
  // A spacer with no argument is flexible: contributes nothing to minimum height.
  addSpacer(n) { this.node.children.push({ type: "spacer", h: n === undefined ? 0 : n }); }
  layoutHorizontally() { this.node.vertical = false; }
  layoutVertically() { this.node.vertical = true; }
  centerAlignContent() {} topAlignContent() {} bottomAlignContent() {}
  setPadding(t, l, b, r) { this.node.padT = t || 0; this.node.padB = b || 0; }
  set spacing(v) { this.node.spacing = v || 0; }
  set size(v) {
    if (!(v instanceof Size)) throw new Error("size must be Size");
    if (v.height > 0) this.node.fixedH = v.height;
  }
  set cornerRadius(v) {} set borderWidth(v) {} set borderColor(v) {}
  set backgroundColor(v) {
    if (!(v instanceof Color)) throw new Error("backgroundColor must be Color");
    // The compound marker is the only fill at 0.1 alpha (card bodies use 0.95,
    // pills 0.18), so it is identifiable in both card and row form.
    if (v.alpha === 0.1) { glowCount++; tree.push("  ".repeat(depth) + "↑ GLOW HALO"); }
  }
  set url(v) {}
}
let rootWidget = null;
class ListWidget extends WidgetStack {
  constructor() { super("ListWidget"); this.node.vertical = true; this.presented = null; rootWidget = this; }
  // Root padding is excluded here; BUDGET already subtracts it.
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
  // Only large draws the sparkline, so only large may pay for the chart.
  if (FAMILY !== "large" && requestLog.some(u => u.includes("market_chart"))) {
    console.log(`❌ ${FAMILY}/${MODE} fetched market_chart but never renders it`);
    process.exit(1);
  }

  if (process.env.LEAKCHECK === "1") {
    // Any wallet identifier: bech32 body, or the raw hex form.
    for (const u of requestLog) {
      const host = u.split("/")[2];
      const carries = /qubetics1[a-z0-9]{20,}/.test(u) || /0x[0-9a-f]{40}/i.test(u);
      console.log(`   ${carries ? "ADDRESS SENT ->" : "  no address ->"} ${host}`);
    }
  }

  const budget = BUDGET[FAMILY] || BUDGET.medium;
  const avail = budget.h - budget.pad;
  const used = rootWidget ? Math.round(nodeHeight(rootWidget.node)) : 0;
  const ratio = used / avail;
  // <=1.0 fits outright. Up to 1.25 still renders because iOS shrinks text via
  // minimumScaleFactor, but it is living on borrowed space. Beyond that the
  // shrink runs out and the widget clips top and bottom.
  const status = ratio <= 1.0 ? "OK" : ratio <= 1.25 ? "TIGHT" : "OVERFLOW";
  const mark = status === "OK" ? "✅" : status === "TIGHT" ? "⚠️ " : "❌";
  console.log(`${mark} ${FAMILY}/${MODE} rendered — ${tree.length} nodes, ` +
    `${requestLog.length} requests, ${glowCount} glow, height ${used}/${avail}pt ${status}`);
  if (status === "TIGHT") {
    console.log(`   ${Math.round((ratio - 1) * 100)}% over budget — renders, but only because iOS shrinks text.`);
  }
  if (status === "OVERFLOW") {
    console.log(`   ${used - avail}pt over — iOS will clip the top and bottom.`);
    process.exit(1);
  }
  const unknown = [...usedSymbols].filter(s => !KNOWN_SYMBOLS.has(s));
  if (unknown.length) console.log(`⚠️  unknown SF Symbols: ${unknown.join(", ")}`);
  if (process.env.TREE === "1") console.log(tree.join("\n"));
} catch (e) {
  console.log(`❌ ${FAMILY}/${MODE} FAILED: ${e.message}`);
  console.log(e.stack.split("\n").slice(0, 6).join("\n"));
  process.exit(1);
}
