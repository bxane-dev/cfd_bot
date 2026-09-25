const { app, BrowserWindow, dialog } = require('electron');
const { spawn } = require('child_process');
const crypto = require('crypto');
const fs = require('fs');
const http = require('http');
const path = require('path');

let backend = null;
let mainWindow = null;

function copyDefault(src, dst) {
  if (!fs.existsSync(dst)) {
    fs.mkdirSync(path.dirname(dst), { recursive: true });
    fs.copyFileSync(src, dst);
  }
}

function waitForServer(url, timeoutMs = 30000) {
  const started = Date.now();
  return new Promise((resolve, reject) => {
    const check = () => {
      const req = http.get(url, res => {
        res.resume();
        if (res.statusCode && res.statusCode < 500) return resolve();
        retry();
      });
      req.on('error', retry);
      req.setTimeout(1000, () => { req.destroy(); retry(); });
    };
    const retry = () => {
      if (Date.now() - started > timeoutMs) return reject(new Error('Trading backend did not start in time.'));
      setTimeout(check, 350);
    };
    check();
  });
}

async function chooseMode() {
  const first = await dialog.showMessageBox({
    type: 'question',
    title: 'CFD Bot',
    message: 'Choose desktop mode',
    detail: 'Demo uses the four-market trading simulator. Live opens the same desk in read-only monitoring mode.',
    buttons: ['Demo', 'Live monitor', 'Cancel'],
    defaultId: 0,
    cancelId: 2,
    noLink: true
  });
  if (first.response === 2) return null;
  return first.response === 0 ? 'demo' : 'live';
}

function backendCommand(resourcesRoot, mode, token, runtimeDir) {
  const env = {
    ...process.env,
    MODE: mode,
    CFD_DESKTOP: '1',
    CFD_LIVE_READ_ONLY: '1',
    CFD_WEB_TOKEN: token,
    CFD_ROOT: runtimeDir,
    CFD_WEB_ROOT: path.join(resourcesRoot, 'web'),
    PYTHONUNBUFFERED: '1'
  };

  if (app.isPackaged) {
    return {
      command: path.join(resourcesRoot, 'backend', 'cfd_backend.exe'),
      args: ['--mode', mode, '--skip-tune'],
      options: { env, cwd: runtimeDir, windowsHide: true }
    };
  }

  const root = path.resolve(__dirname, '..');
  const venv = process.platform === 'win32'
    ? path.join(root, '.venv', 'Scripts', 'python.exe')
    : path.join(root, '.venv', 'bin', 'python');
  const python = fs.existsSync(venv) ? venv : (process.platform === 'win32' ? 'python' : 'python3');

  return {
    command: python,
    args: ['-m', 'app.auto', '--mode', mode, '--skip-tune'],
    options: {
      env: { ...env, CFD_WEB_ROOT: path.join(root, 'web') },
      cwd: root,
      windowsHide: true
    }
  };
}

async function startApp() {
  const mode = await chooseMode();
  if (!mode) return app.quit();

  const resourcesRoot = app.isPackaged ? process.resourcesPath : path.resolve(__dirname, '..');
  const runtimeDir = path.join(app.getPath('userData'), 'runtime');
  fs.mkdirSync(runtimeDir, { recursive: true });

  const defaultConfig = path.join(resourcesRoot, app.isPackaged ? 'defaults' : '', 'config.yaml');
  const defaultEnv = path.join(resourcesRoot, app.isPackaged ? 'defaults' : '', '.env.example');

  copyDefault(defaultConfig, path.join(runtimeDir, 'config.yaml'));
  if (fs.existsSync(defaultEnv)) copyDefault(defaultEnv, path.join(runtimeDir, '.env'));

  const token = crypto.randomBytes(24).toString('base64url');
  const cmd = backendCommand(resourcesRoot, mode, token, runtimeDir);
  backend = spawn(cmd.command, cmd.args, cmd.options);

  const logPath = path.join(runtimeDir, 'desktop-backend.log');
  const log = fs.createWriteStream(logPath, { flags: 'a' });
  backend.stdout.on('data', d => log.write(d));
  backend.stderr.on('data', d => log.write(d));
  backend.on('exit', code => log.write('\nbackend exit ' + code + '\n'));

  try {
    await waitForServer('http://127.0.0.1:8484/api/status');
  } catch (err) {
    await dialog.showMessageBox({
      type: 'error',
      title: 'CFD Bot could not start',
      message: err.message,
      detail: 'Check credentials in ' + path.join(runtimeDir, '.env') + '\n\nBackend log: ' + logPath
    });
    return app.quit();
  }

  mainWindow = new BrowserWindow({
    width: 1460,
    height: 940,
    minWidth: 1000,
    minHeight: 700,
    backgroundColor: '#080b10',
    autoHideMenuBar: true,
    icon: path.join(resourcesRoot, 'build', 'icon.png'),
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
    }
  });

  await mainWindow.loadURL('http://127.0.0.1:8484/?token=' + encodeURIComponent(token));
}

app.whenReady().then(startApp);
app.on('window-all-closed', () => app.quit());
app.on('before-quit', () => {
  if (backend && !backend.killed) backend.kill();
});
