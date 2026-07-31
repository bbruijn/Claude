# TICS Dashboard — Scriptable widget

A Qubetics staking widget for [Scriptable](https://scriptable.app) on iOS.
Single file, no imports, no build step — copy it into Scriptable and it runs.

## Install (from the iPhone)

1. Open **`tics-dashboard.js`** on GitHub → tap **Raw** → long-press → **Select All** → **Copy**.
2. Open **Scriptable** → **+** → paste → name it `TICS Dashboard`.
3. Edit the `MY_ADDRESS` line near the top and put your own address in.
4. Long-press the Home Screen → **+** → **Scriptable** → pick a size → **Add Widget**.
5. Long-press the new widget → **Edit Widget** → set **Script** to `TICS Dashboard`.

Set `MY_ADDRESS` in your own copy only — the committed version ships a
placeholder on purpose, so your address never lands in git.

Both address formats work — `0x…` (EVM) and `qubetics1…` (native). The EVM form is
converted to bech32 on-device.

## Multiple wallets, one script

Leave `MY_ADDRESS` as your main wallet, then for any extra widget set the
**Parameter** field (in *Edit Widget*) to a different address. That widget uses
the parameter; the rest keep using `MY_ADDRESS`. No need to duplicate the script.

## What each size shows

| Size | Contents |
|---|---|
| **Small** | Total value, 24h change, staked / rewards / price |
| **Medium** | Price pill, big total value, and Staked / Rewards / Available as compact rows |
| **Large** | Hero total + 7-day sparkline, 4 cards (adds Unbonding), and a per-validator delegation list with monikers |

Every TICS figure carries its USD equivalent underneath.

## Compound marker

The **Rewards** and **Available** cards light up with a coloured halo once their
combined balance reaches `CFG.compoundThreshold` (default **1000 TICS**) — the
cue that there's enough to claim and re-stake. Below that they stay plain, so
the marker actually means something.

A failed API call contributes 0 rather than an unknown, so the marker can only
ever under-trigger — it will never tell you to compound based on missing data.
Set the threshold to `0` to always show it, or `Infinity` to turn it off.

## Network cost per refresh

| Size | Requests | Extra |
|---|---|---|
| Small | 5 | — |
| Medium | 5 | — |
| Large | 7 | 7-day chart + bonded-validator list |

`refreshMin` is a hint; iOS decides the real rate and will refresh far less
often than you ask.

## Config

All settings live in the `CFG` block at the top:

| Key | Default | Notes |
|---|---|---|
| `restEndpoint` | `https://swagger.qubetics.com` | Any Cosmos REST (LCD) node |
| `coingeckoId` | `qubetics` | CoinGecko coin id |
| `baseDenom` / `decimals` | `attics` / `18` | Non-matching denoms are ignored |
| `refreshMin` | `10` | A hint — iOS decides the real refresh rate |
| `sparklineDays` | `7` | Sparkline window |
| `showSparkline` | `true` | Costs one extra CoinGecko call |
| `maxValidators` | `3` | Rows in the large-widget list |
| `tapUrl` | `null` | Tapping opens Scriptable while null |

## Behaviour worth knowing

**Stale-data fallback.** Last good values are cached on-device. If the chain node
or CoinGecko fails (CoinGecko rate-limits free callers fairly aggressively), the
widget shows the cached numbers and the footer switches to `⚠︎ cached · 20m old`
instead of a wall of `--`. Cached values are dropped after 6 hours.

**Unknown ≠ zero.** If the chain calls fail, totals render as `--`, not `$0.00`.
A `$0.00` total always means the wallet really is empty.

**Privacy.** Only the REST node and CoinGecko are contacted, and your address
never appears in a tap-through URL — `tapUrl` is `null` by default, so tapping
the widget just opens Scriptable.

## Testing without a phone

`widgets/test-harness.mjs` mocks the Scriptable API so the widget can run under
Node against fixture data:

```bash
node widgets/test-harness.mjs <small|medium|large|app> <mode>
# modes: ok offline cached nochart partial badaddr unset empty apierror below atthreshold
TREE=1 node widgets/test-harness.mjs large ok   # dump the rendered text nodes
```

It checks that fonts get finite sizes, colours are `Color` instances, SF Symbol
names resolve, and the sparkline never produces non-finite coordinates.
