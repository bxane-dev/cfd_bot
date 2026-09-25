import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

const root = new URL("../", import.meta.url);
const config = fs.readFileSync(new URL("config.yaml", root), "utf8");
const news = fs.readFileSync(new URL("app/news.py", root), "utf8");
const streamers = fs.readFileSync(new URL("app/streamers.py", root), "utf8");
const desk = fs.readFileSync(new URL("app/desk.py", root), "utf8");
const main = fs.readFileSync(new URL("app/main.py", root), "utf8");
const page = fs.readFileSync(new URL("web/index.html", root), "utf8");

test("live feeds use short bounded refresh intervals", () => {
  assert.match(config, /poll_seconds:\s*5\b/);
  assert.match(config, /news:\s*[\s\S]*?refresh_seconds:\s*60\b/);
  assert.match(config, /streamers:\s*[\s\S]*?refresh_seconds:\s*60\b/);
  assert.match(page, /setInterval\(refresh,\s*5000\)/);
});

test("demo stays on core live market scope with demo-only frequency overrides", () => {
  assert.match(config, /demo_market_scope:\s*live\b/);
  assert.match(config, /demo_frequency:/);
  assert.match(main, /effective_mode == "live" or \(effective_mode == "demo" and demo_scope == "live"\)/);
  assert.match(main, /use_live_scope[\s\S]*live_enabled/);
});

test("Capital.com headlines are merged into the existing news feed", () => {
  assert.match(news, /CAPITAL_NEWS_URL\s*=\s*["']https:\/\/capital\.com\/en-int\/news/);
  assert.match(news, /def _capital_news\(/);
  assert.match(news, /source["']:\s*["']capital\.com["']/);
  assert.match(news, /fetch_desk_news[\s\S]*?_capital_news/);
});

test("streamer discovery targets CFD market-analysis creators", () => {
  assert.match(streamers, /CFD trading live market analysis/);
});

test("open positions expose live mark and estimated P/L", () => {
  assert.match(desk, /"mark":/);
  assert.match(desk, /"unrealized_pnl":/);
  assert.match(page, /unrealized_pnl/);
});

test("dashboard controls require a per-run token", () => {
  const webApp = fs.readFileSync(new URL("app/web_app.py", root), "utf8");
  assert.match(webApp, /X-CFD-Control-Token/);
  assert.match(webApp, /CFD_WEB_HOST["'],\s*["']127\.0\.0\.1/);
  assert.match(page, /cfdControlToken/);
});
