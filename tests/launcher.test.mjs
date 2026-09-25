import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';

const root = path.resolve(import.meta.dirname, '..');
const start = fs.readFileSync(path.join(root, 'START.bat'), 'utf8');
const live = fs.readFileSync(path.join(root, 'START_LIVE.bat'), 'utf8');
const requirements = fs.readFileSync(path.join(root, 'requirements.txt'), 'utf8');

test('demo launcher bootstraps Python and every declared dependency', () => {
  assert.match(start, /winget install -e --id Python\.Python\.3\.12/);
  assert.match(start, /https:\/\/www\.python\.org\/ftp\/python\/3\.12\.10\/python-3\.12\.10-amd64\.exe/);
  assert.match(start, /-m venv \.venv/);
  assert.match(start, /-m pip install -r requirements\.txt/);
  assert.match(start, /import pandas,yaml,dotenv,optuna/);
  assert.match(start, /-m app\.auto --mode demo --skip-tune/);
  for (const packageName of ['pandas', 'numpy', 'pyyaml', 'python-dotenv', 'optuna']) {
    assert.match(requirements.toLowerCase(), new RegExp(`^${packageName}`, 'm'));
  }
});

test('live launcher keeps the explicit live-trading confirmation', () => {
  assert.match(live, /Type LIVE and press Enter to continue/);
  assert.match(live, /-m app\.auto --mode live --skip-tune/);
  assert.doesNotMatch(live, /START\.bat/);
});

test('both launchers show a large by bone banner', () => {
  for (const launcher of [start, live]) {
    assert.match(launcher, /echo\s+\^\|\s+BY @BONE\s+\^\|/i);
    assert.match(launcher, /echo\s+============================================================/);
  }
});
