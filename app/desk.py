from __future__ import annotations

import os
import threading
import time
from datetime import datetime

from dotenv import load_dotenv

from instruments import BERLIN, in_session
from main import (
    fetch_capital_bars,
    gross_open_margin,
    ROOT,
    TRADES_PATH,
    capital_map,
    enabled_markets,
    ensure_logs,
    load_cfg,
    load_state,
    make_broker,
    run_once,
    sync_market_rules,
)
from risk import RiskManager


class Desk:
    def __init__(
        self,
        *,
        cfg: dict | None = None,
        mode: str | None = None,
        markets=None,
        broker=None,
        live_map: dict[str, str] | None = None,
        risk: RiskManager | None = None,
        state: dict | None = None,
        loop_event: threading.Event | None = None,
        lock=None,
    ) -> None:
        load_dotenv(ROOT / ".env")
        self.cfg = cfg if cfg is not None else load_cfg()
        self.mode = mode or os.getenv("MODE") or self.cfg.get("mode") or "demo"
        if self.mode not in ("demo", "live"):
            self.mode = "demo"
        self.markets = markets if markets is not None else enabled_markets(self.cfg, self.mode)
        ensure_logs()
        self.broker = broker if broker is not None else make_broker(self.cfg, self.mode, self.markets)
        self.live_map = live_map if live_map is not None else capital_map(self.markets, self.broker)
        if any(not getattr(m, "broker_rules", False) for m in self.markets):
            sync_market_rules(self.markets, self.broker, self.live_map)
        self.risk = risk if risk is not None else RiskManager(self.cfg)
        self.state = state if state is not None else load_state()
        self.loop_event = loop_event
        self.quotes: dict[str, dict] = {}
        self.running = bool(loop_event.is_set()) if loop_event is not None else False
        self.last_error = ""
        self._lock = lock if lock is not None else threading.RLock()
        self._thread: threading.Thread | None = None
        self._last_account = None
        self._snapshot_cache: dict | None = None
        self._snapshot_cache_at = 0.0
        self._refresh_quotes()

    def _market_for_symbol(self, symbol: str):
        symbol = str(symbol or "")
        for market in self.markets:
            if symbol in {market.key, market.epic, market.name, *market.live_aliases}:
                return market
        return None

    def _position_payload(self, position, currency: str) -> dict:
        symbol = str(getattr(position, "symbol", "") or "")
        side = str(getattr(position, "side", "") or "").lower()
        market = self._market_for_symbol(symbol)
        quote = self.quotes.get(market.key, {}) if market else {}
        mark = quote.get("price")
        spread = quote.get("spread")
        close_price = None
        if mark is not None:
            close_price = float(mark)
            if spread is not None:
                half_spread = float(spread) / 2.0
                close_price += -half_spread if side == "buy" else half_spread

        entry = getattr(position, "entry", None)
        lots = getattr(position, "lots", None)
        broker_upl = getattr(position, "upl", None)
        unrealized = float(broker_upl) if broker_upl is not None else None
        if unrealized is None:
            try:
                contract_size = float(
                    getattr(position, "contract_size", 0)
                    or getattr(market, "contract_size", 1.0)
                    or 1.0
                )
                point_value = float(getattr(market, "point_value", 1.0) or 1.0)
                direction = 1.0 if side == "buy" else -1.0
                if close_price is not None and entry is not None and lots is not None:
                    unrealized = (
                        (close_price - float(entry))
                        * direction
                        * float(lots)
                        * point_value
                        * contract_size
                    )
            except (TypeError, ValueError):
                unrealized = None

        return {
            "ticket": getattr(position, "ticket", None),
            "symbol": symbol,
            "market": market.name if market else symbol,
            "side": getattr(position, "side", None),
            "lots": lots,
            "entry": entry,
            "mark": mark,
            "close_price": close_price,
            "sl": getattr(position, "sl", None),
            "tp": getattr(position, "tp", None),
            "unrealized_pnl": round(unrealized, 2) if unrealized is not None else None,
            "pnl_currency": getattr(position, "currency", None) or currency,
            "pnl_estimated": broker_upl is None,
        }

    def snapshot(self, force: bool = False) -> dict:
        with self._lock:
            now = time.monotonic()
            cache_ttl = max(0.0, float(self.cfg.get("snapshot_cache_seconds", 2) or 0))
            if not force and self._snapshot_cache is not None and now - self._snapshot_cache_at < cache_ttl:
                return self._snapshot_cache
            account_error = ""
            try:
                acct = self.broker.account()
                self._last_account = acct
            except Exception as exc:
                account_error = f"account refresh failed: {str(exc)[:180]}"
                self.last_error = account_error
                acct = self._last_account

            broker_positions = list(getattr(acct, "positions", []) or [])
            equity = getattr(acct, "equity", None)
            currency = getattr(acct, "currency", None) or (self.cfg.get("account") or {}).get("currency") or "EUR"
            positions = [self._position_payload(p, currency) for p in broker_positions]
            margin_used = gross_open_margin(broker_positions, self.risk)
            allocation_pct = float(self.cfg["risk"].get("max_portfolio_allocation_pct", 100) or 0)
            margin_limit = (float(equity) * allocation_pct / 100.0) if equity is not None else 0.0

            for key, quote in (self.state.get("quotes") or {}).items():
                if isinstance(quote, dict):
                    self.quotes[key] = dict(quote)

            markets = []
            decisions = self.state.get("diagnostics") or {}
            streamer_consensus = self.state.get("streamer_consensus") or {}
            for m in self.markets:
                open_ok, msg = in_session(m)
                q = self.quotes.get(m.key, {})
                markets.append(
                    {
                        "key": m.key,
                        "name": m.name,
                        "group": m.group,
                        "session": m.session,
                        "open": open_ok,
                        "session_msg": msg,
                        "price": q.get("price"),
                        "spread": q.get("spread"),
                        "digits": m.digits,
                        "updated": q.get("updated"),
                        "decision": decisions.get(m.key) or {},
                        "streamers": streamer_consensus.get(m.key) or {},
                        "broker_rules": {
                            "min_lot": m.min_lot,
                            "max_lot": m.max_lot,
                            "lot_step": m.lot_step,
                            "contract_size": getattr(m, "contract_size", 1.0),
                            "margin_factor": getattr(m, "margin_factor", None),
                            "margin_factor_unit": getattr(m, "margin_factor_unit", ""),
                        },
                    }
                )
            is_running = self.loop_event.is_set() if self.loop_event is not None else self.running
            payload = {
                "mode": self.mode,
                "strategy": (self.cfg.get("strategy") or {}).get("name") or "ema_atr",
                "running": is_running,
                "equity": equity,
                "currency": currency,
                "open_positions": len(positions),
                "positions": positions,
                "realized": [],
                "markets": markets,
                "berlin": datetime.now(BERLIN).strftime("%a %H:%M"),
                "error": account_error or self.last_error,
                "risk": {
                    "per_trade": self.cfg["risk"]["risk_per_trade_pct"],
                    "daily_loss": self.cfg["risk"]["max_daily_loss_pct"],
                    "max_open": self.cfg["risk"]["max_open_positions"],
                    "max_index": self.cfg["risk"].get("max_index_positions", 2),
                    **self.risk.snapshot(),
                    "margin_used": margin_used,
                    "margin_limit": margin_limit,
                    "margin_usage_pct": (margin_used / margin_limit * 100.0) if margin_limit > 0 else 0.0,
                },
            }
            self._snapshot_cache = payload
            self._snapshot_cache_at = time.monotonic()
            return payload

    def trades(self, limit: int = 50) -> list[dict]:
        if not TRADES_PATH.exists():
            return []
        rows = TRADES_PATH.read_text(encoding="utf-8").strip().splitlines()
        if len(rows) <= 1:
            return []
        header = rows[0].split(",")
        out = []
        for line in rows[-limit:]:
            if line.startswith("time,"):
                continue
            parts = line.split(",")
            out.append(dict(zip(header, parts)))
        return list(reversed(out))

    def scan_once(self) -> dict:
        with self._lock:
            try:
                run_once(self.cfg, self.mode, self.broker, self.risk, self.state, self.markets, self.live_map)
                self.last_error = ""
            except Exception as exc:
                self.last_error = str(exc)
            self._refresh_quotes_locked()
            return self.snapshot(force=True)

    def start(self) -> dict:
        if self.loop_event is not None:
            self.loop_event.set()
            self.running = True
            return self.snapshot(force=True)
        if self.running:
            return self.snapshot(force=True)
        self.running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return self.snapshot(force=True)

    def stop(self) -> dict:
        if self.loop_event is not None:
            self.loop_event.clear()
        self.running = False
        return self.snapshot(force=True)

    def reset_daily_loss(self) -> dict:
        try:
            eq = self.broker.account().equity
        except Exception:
            eq = None
        snap = self.risk.reset_day(eq, why="web")
        try:
            from memory import remember
            remember("risk", "manual daily loss reset", how="web", extra=snap)
        except Exception:
            pass
        self.last_error = ""
        return {**self.snapshot(force=True), "risk_reset": snap}

    def _loop(self) -> None:
        while self.running:
            self.scan_once()
            for _ in range(int(self.cfg.get("poll_seconds", 5))):
                if not self.running:
                    return
                time.sleep(1)

    def _refresh_quotes(self) -> None:
        with self._lock:
            self._refresh_quotes_locked()

    def _refresh_quotes_locked(self) -> None:
        for m in self.markets:
            epic = self.live_map.get(m.key, m.epic)
            try:
                bid, ask = self.broker.quote(epic)
                mid = (bid + ask) / 2.0 if bid and ask else bid or ask
                self.quotes[m.key] = {
                    "price": mid,
                    "spread": (ask - bid) if bid and ask else None,
                    "updated": datetime.now(BERLIN).strftime("%H:%M:%S"),
                }
            except Exception as exc:
                self.quotes[m.key] = {
                    "price": None,
                    "spread": None,
                    "updated": str(exc)[:80],
                }


    def charts(self, count: int = 180, only: str | None = None) -> dict:
        import math
        import time
        import pandas as pd

        now = time.time()
        cache = getattr(self, "_chart_cache", None)
        cache_key = (int(count), only or "")
        if cache and now - cache[0] < 15 and cache[1] == cache_key:
            return cache[2]
        primary = ["gold", "wallstreet30", "ustech100", "germany40"]
        if only:
            order = [only]
        else:
            order = [key for key in primary if any(m.key == key for m in self.markets)]
        by_key = {m.key: m for m in self.markets}
        pos_by = {}
        try:
            positions = getattr(self._last_account, "positions", None)
            if positions is None:
                positions = self.broker.positions()
            for p in positions:
                pos_by.setdefault(p.symbol, p)
        except Exception:
            pos_by = {}
        out = []
        for key in order:
            m = by_key.get(key)
            if not m:
                continue
            epic = self.live_map.get(m.key, m.epic)
            item = {"key": m.key, "name": m.name, "digits": m.digits, "candles": [], "ema_fast": [], "ema_slow": [], "error": None, "position": None}
            try:
                raw = self.broker.candles(
                    epic,
                    {
                        "1m": "MINUTE",
                        "5m": "MINUTE_5",
                        "15m": "MINUTE_15",
                        "30m": "MINUTE_30",
                        "1h": "HOUR",
                        "4h": "HOUR_4",
                        "1d": "DAY",
                    }.get(self.cfg.get("timeframe", "1m"), "MINUTE"),
                    count,
                )
                rows = []
                for bar in raw:
                    ts = bar.get("snapshotTimeUTC") or bar.get("snapshotTime")
                    def mid(obj):
                        if isinstance(obj, dict):
                            bid_v = obj.get("bid")
                            ask_v = obj.get("ask")
                            if bid_v is not None and ask_v is not None:
                                return (float(bid_v) + float(ask_v)) / 2.0
                            return float(bid_v or ask_v or 0)
                        return float(obj or 0)
                    rows.append({
                        "time": ts,
                        "open": mid(bar.get("openPrice") or {}),
                        "high": mid(bar.get("highPrice") or {}),
                        "low": mid(bar.get("lowPrice") or {}),
                        "close": mid(bar.get("closePrice") or {}),
                    })
                df = pd.DataFrame(rows)
                if df.empty:
                    raise RuntimeError(f"no chart candles for {epic}")
                df["time"] = pd.to_datetime(df["time"], utc=True, errors="coerce")
                df = df.dropna(subset=["time", "close"]).set_index("time").tail(count)
                q = self.quotes.get(m.key, {})
                mid_q = q.get("price")
                spread_q = q.get("spread")
                if mid_q is not None and spread_q is not None:
                    bid = float(mid_q) - float(spread_q) / 2.0
                    ask = float(mid_q) + float(spread_q) / 2.0
                else:
                    bid = ask = None
                fast = df["close"].ewm(span=max(2, m.fast_ema), adjust=False).mean()
                slow = df["close"].ewm(span=max(3, m.slow_ema), adjust=False).mean()
                for ts, row in df.iterrows():
                    item["candles"].append({
                        "t": ts.isoformat(),
                        "o": float(row["open"]),
                        "h": float(row["high"]),
                        "l": float(row["low"]),
                        "c": float(row["close"]),
                    })
                    fv, sv = float(fast.loc[ts]), float(slow.loc[ts])
                    item["ema_fast"].append(None if not math.isfinite(fv) else fv)
                    item["ema_slow"].append(None if not math.isfinite(sv) else sv)
                item["bid"] = bid
                item["ask"] = ask
                for symbol_key in (epic, m.epic, m.key, m.name):
                    p = pos_by.get(symbol_key)
                    if p is not None:
                        item["position"] = {"side": p.side, "entry": p.entry, "sl": p.sl, "tp": p.tp, "lots": p.lots}
                        break
            except Exception as exc:
                item["error"] = str(exc)[:160]
            out.append(item)
        payload = {"berlin": datetime.now(BERLIN).strftime("%a %H:%M:%S"), "markets": out}
        self._chart_cache = (now, cache_key, payload)
        return payload


DESK: Desk | None = None


def install_shared_desk(desk: Desk) -> None:
    """Install the already-authenticated desk used by auto.py.

    This prevents the web dashboard from creating a second Capital.com session.
    """
    global DESK
    DESK = desk


def get_desk() -> Desk:
    global DESK
    if DESK is None:
        DESK = Desk()
    return DESK
