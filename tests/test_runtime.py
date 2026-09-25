import copy
import unittest
from pathlib import Path
import yaml

import app  # noqa: F401 - keeps legacy top-level imports available

from broker.capital import CapitalBroker
from instruments import MARKETS
from risk import RiskManager
from streamers import classify_text
from research.walk import pick_winner
from main import effective_trade_cfg, enabled_markets


class RuntimeRegressionTests(unittest.TestCase):
    def test_unconfirmed_order_is_not_reported_as_success(self):
        broker = CapitalBroker.__new__(CapitalBroker)

        def fake_request(method, path, payload=None, query=None):
            if method == "POST" and path == "/api/v1/positions":
                return {"dealReference": "o_test"}
            raise RuntimeError("confirmation temporarily unavailable")

        broker._request = fake_request
        fill = broker.market_order("GOLD", "buy", 1.0, 100.0, 110.0, "test")
        self.assertFalse(fill.ok)
        self.assertIn("UNCONFIRMED", fill.message)

    def test_confirmed_order_can_succeed(self):
        broker = CapitalBroker.__new__(CapitalBroker)

        def fake_request(method, path, payload=None, query=None):
            if method == "POST":
                return {"dealReference": "o_test"}
            if path == "/api/v1/confirms/o_test":
                return {
                    "dealStatus": "ACCEPTED",
                    "dealId": "deal-1",
                    "level": 105.0,
                }
            raise AssertionError(path)

        broker._request = fake_request
        fill = broker.market_order("GOLD", "buy", 1.0, 100.0, 110.0, "test")
        self.assertTrue(fill.ok)
        self.assertEqual(fill.price, 105.0)

    def test_contract_size_is_used_in_risk_sizing(self):
        market = copy.deepcopy(MARKETS["gold"])
        market.contract_size = 50.0
        market.min_lot = 0.01
        market.lot_step = 0.01
        market.max_lot = 10.0
        cfg = {
            "account": {"leverage": 20},
            "risk": {
                "risk_per_trade_pct": 0.4,
                "max_portfolio_allocation_pct": 100.0,
                "daily_loss_enabled": False,
                "max_open_positions": 12,
                "max_positions_per_market": 4,
                "max_index_positions": 8,
            },
        }
        rm = RiskManager(cfg)
        sized = rm.size_lots(10_000.0, 1.0, market, price=100.0)
        self.assertTrue(sized.allowed)
        self.assertAlmostEqual(sized.lots, 0.8)

    def test_streamer_negation_is_not_a_directional_vote(self):
        self.assertEqual(classify_text("Gold not bullish - do not buy"), "neutral")
        self.assertEqual(classify_text("Nasdaq bearish short setup"), "sell")
        self.assertEqual(classify_text("Gold bullish buy setup"), "buy")

    def test_demo_frequency_overrides_do_not_change_live(self):
        cfg = {
            "mode": "demo",
            "execution": {
                "demo_market_scope": "all",
                "demo_frequency": {
                    "quality": {"min_reward_risk": 1.0},
                    "news": {"min_confidence": 0.68},
                },
            },
            "quality": {"min_reward_risk": 1.05},
            "news": {"min_confidence": 0.62},
            "markets": {
                "gold": {"enabled": True, "live_enabled": True},
                "us500": {"enabled": True, "live_enabled": False},
            },
        }
        demo = effective_trade_cfg(cfg, "demo")
        live = effective_trade_cfg(cfg, "live")
        self.assertEqual(demo["quality"]["min_reward_risk"], 1.0)
        self.assertEqual(demo["news"]["min_confidence"], 0.68)
        self.assertEqual(live["quality"]["min_reward_risk"], 1.05)
        self.assertEqual(live["news"]["min_confidence"], 0.62)

    def test_desktop_config_exposes_only_four_markets_at_five_percent_risk(self):
        cfg = yaml.safe_load((Path(__file__).resolve().parents[1] / "config.yaml").read_text(encoding="utf-8"))
        demo_keys = {m.key for m in enabled_markets(cfg, "demo")}
        live_keys = {m.key for m in enabled_markets(cfg, "live")}
        expected = {"ustech100", "wallstreet30", "germany40", "gold"}
        self.assertEqual(demo_keys, expected)
        self.assertEqual(live_keys, expected)
        self.assertEqual(float(cfg["risk"]["risk_per_trade_pct"]), 5.0)

    def test_no_profitable_strategy_returns_no_winner(self):
        rows = [
            {
                "name": "a",
                "error": None,
                "trades": 10,
                "pnl": -5.0,
                "expectancy": -0.5,
                "pf": 0.8,
                "score": -1.0,
                "win_rate": 40.0,
            }
        ]
        self.assertIsNone(pick_winner(rows))


if __name__ == "__main__":
    unittest.main()
