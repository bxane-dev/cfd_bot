# CFD Bot

Built by bxane

A Capital.com CFD trading desk for **Germany 40 (DE40)**, **US Tech 100 (US100)**, **Wall Street 30 (US30)**, and **Gold (GOLD)**.

This hardened local build keeps the original strategy family while adding stricter execution, risk, restart, backtest, predictor, and news safeguards.

> **Important:** CFDs are leveraged and can lose money quickly. No strategy, backtest, or prediction model guarantees profit. Use **demo mode first** and verify behavior before considering live trading.

## Current chat build additions

This packaged build adds **market-specific directional news scoring** and **persistent searchable trading memory**. See `docs/BUILD_NOTES.md` for exact behavior and current limitations. The directional news engine is rules-based and the memory system is SQLite-backed structured retrieval; neither is a guarantee of profitable trading.


## What it does

- Connects to Capital.com demo or live REST API.
- Routes different strategies per market.
- Applies ATR-based stops/targets and equity-based position sizing.
- Enforces spread, position, and index-correlation limits; the daily-loss halt is optional.
- Filters entries with news and an optional statistical predictor.
- Runs walk-forward strategy evaluation and Optuna tuning.
- Logs trades, equity, risk state, and execution state locally.

## Current safeguards

- **Strict demo/live endpoints:** demo and live use separate Capital.com API hosts.
- **Separate Windows launchers:** `START.bat` is demo; `START_LIVE.bat` requires explicit `LIVE` confirmation.
- **Position controls:** configurable total, per-market, index, and estimated broker-margin allocation caps.
- **Optional daily-loss halt:** can be enabled or disabled in `config.yaml`.
- **Per-trade sizing:** position size is derived from equity, stop distance, and configured risk percentage.
- **Spread gate:** entries are skipped when spread exceeds the market limit.
- **Directional news gate:** strong opposite news can veto a technical setup.
- **Local dashboard:** reuses the trading process broker session instead of opening a second dashboard session. It binds to localhost by default and protects control actions with a per-run token.
- **Live desk view:** refreshes account, quotes, news, streamers, and open-position marks on bounded intervals; positions prefer Capital.com's broker-reported unrealized P/L and fall back to a local estimate only when needed.
- **Capital.com headlines:** the news desk merges the public Capital.com feed with Google News RSS and caches each source independently.

## Quick start — Windows

1. Double-click `START.bat`. It installs Python 3.12 with WinGet when needed, creates `.venv`, and installs every package in `requirements.txt`.
2. On first run, fill `.env` with your Capital.com API credentials when prompted.
3. Run `START.bat` again to start the DEMO desk.

`START.bat` is intentionally **DEMO-only**. It will never start live trading. It now starts the trading loop immediately instead of blocking on first-run strategy tuning, and the web dashboard reuses the same authenticated Capital.com session.

Automatic tuning is opt-in. To tune manually before trading, run `python -m app.auto --mode demo --force-tune`, or set `auto.tune_on_start: true` in `config.yaml`. Periodic retuning is disabled by default (`auto.periodic_retune: false`) because tuning is intentionally kept out of the critical startup path.

## Quick start — terminal

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
# source .venv/bin/activate

python -m pip install -r requirements.txt
cp .env.example .env   # Windows CMD: copy .env.example .env
```

Fill `.env`, then:

```bash
python -m app.main --mode demo
```

Run one scan only:

```bash
python -m app.main --mode demo --once
```

Run selected markets only:

```bash
python -m app.main --mode demo --only gold germany40
```

## Dashboard access

By default the web desk binds only to `127.0.0.1`. The launcher opens a URL containing a random one-run control token; the page stores it in session storage and removes it from the visible address bar.

To deliberately expose the dashboard to another device on the same trusted LAN, set:

```text
CFD_WEB_HOST=0.0.0.0
```

The terminal will print a tokenized phone URL. Control endpoints still require that token. Do not expose port 8484 directly to the public internet.

## Live mode

Windows now has a separate live launcher:

```text
START_LIVE.bat
```

It shows the current risk settings and requires you to type `LIVE` before connecting to the Capital.com live endpoint.

You can still start live mode from a terminal:

```bash
python -m app.main --mode live
```

`START.bat` remains demo-only. The startup preflight must still pass, and the credentials in `.env` must work with the Capital.com live environment.

## Configuration

Main settings live in `config.yaml`.

- `risk.risk_per_trade_pct`: target cash risk per trade.
- `risk.max_portfolio_allocation_pct`: estimated open broker-margin cap as a percentage of equity (default: 30%).
- `risk.daily_loss_enabled`: turn the automatic daily-loss halt on/off.
- `risk.max_daily_loss_pct`: daily halt threshold when enabled.
- `risk.max_open_positions`: total position cap (default: 12).
- `risk.max_positions_per_market`: per-market position cap (default: 4).
- `risk.max_index_positions`: index-position cap (default: 8).
- `news.max_headline_age_seconds`: maximum age of a hot headline that can block entries.
- `news.fail_closed`: set `true` to block entries if news is completely unavailable.
- `predict.enabled`: disables predictor computation when `false`.
- `predict.filter`: allows a healthy predictor to veto signals when `true`.
- `auto.min_oos_trades`, `auto.min_oos_pf`: walk-forward guardrails.
- `backtest.slippage_points`, `backtest.fee_per_trade_cash`: conservative research costs.

## Strategy routing

Default mapping:

| Market | Strategy |
|---|---|
| Germany 40 | `orb` |
| US Tech 100 | `ema_pullback` |
| Wall Street 30 | `macd_trend` |
| Gold | `rsi_reversion` |
| US 500 | `ema_atr` |
| US Crude Oil | `donchian` |
| EUR/USD | `sma_cross` |
| GBP/USD | `triple_ema` |
| USD/CHF | `bollinger` |
| Natural Gas | `keltner` |
| Silver | `squeeze` |
| USD/JPY | `stochastic` |
| Copper | `cci` |
| AUD/USD | `williams` |
| UK 100 | `adx_di` |
| Japan 225 | `sar` |
| Hong Kong 50 | `supertrend` |
| France 40 | `vwap` |
| Switzerland 20 | `momentum` |
| EUR/JPY | `engulfing` |
| GBP/JPY | `inside_bar` |

Demo and live use the same four live-enabled markets by default, so demo trade frequency and exposure are representative of live. Set `execution.demo_market_scope` to `all` only when deliberately researching the 17 extra demo markets. Their Capital.com epics are resolved through the authenticated market-search API at startup, so the config does not depend on guessed epic codes.

The bot polls the broker every 5 seconds by default, refreshes the dashboard every 3 seconds, and only evaluates a new candle once. News and streamer feeds refresh every 60 seconds, with Capital.com headlines included in the news desk. Trading sessions are Monday–Friday in this build. Germany 40's ORB strategy forms its opening range from 08:00–08:15 and can enter on a valid breakout until 09:30; after that, the ORB entry window is closed even though the market session remains enabled.

The registry also contains Donchian, Bollinger, Keltner, stochastic, CCI, Williams %R, ADX/DI, SAR, Supertrend, VWAP, momentum, engulfing, inside-bar, and other variants.

## Walk-forward analysis

Example:

```bash
python -m research.walk --mode demo --method rolling --bars 1000 --train 400 --test 100 --embargo 5
```

Apply winners to `config.yaml` only after reviewing the report:

```bash
python -m research.walk --mode demo --method rolling --bars 1000 --train 400 --test 100 --embargo 5 --apply
```

Historical results are estimates, not promises. The simulator now charges configured execution costs and uses the same minimum-lot risk rule as live sizing.

## Repository layout

```text
app/        bot runtime, broker, risk, strategies, dashboard backend
research/   walk-forward analysis and tuning
scripts/    setup and maintenance helpers
docs/       guides and build notes
web/        browser dashboard
```

The root now stays focused on launchers, configuration, dependencies, README/license, and GitHub metadata.

## Files

- `app/main.py` — trading loop.
- `app/broker/capital.py` — Capital.com REST broker adapter.
- `app/risk.py` — account gates and position sizing.
- `app/strategy/` — signal strategies, routing, tuning helpers.
- `app/predict.py` — statistical direction filter with validation health.
- `app/news.py` — market-scoped news gate.
- `research/walk.py` — walk-forward research/tuning.
- `config.yaml` — user configuration.
- `docs/GUIDE.md` — detailed setup and operating guide.

## Validation

The GitHub smoke workflow installs `requirements.txt`, compiles/imports the startup modules, checks dashboard JavaScript syntax, and validates key risk/launcher guards.

Local compile check:

```bash
python -m py_compile app/main.py app/auto.py app/desk.py app/web_app.py research/walk.py
```

## License

This repository uses the **Source-Available Use-Only License v1.0** in `LICENSE.md`. You may run the unmodified software for your own personal/internal use. Modification, redistribution, resale, sublicensing, repackaging, and offering it as a service require prior written permission from the copyright holder.
