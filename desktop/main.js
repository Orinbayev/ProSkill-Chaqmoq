/**
 * ChaqmoqApp Desktop — to'liq saytni native oynada ochadi.
 * URL: CHAQMOQ_URL env yoki default production.
 */
const { app, BrowserWindow, shell, Menu, session, dialog, nativeTheme } = require('electron');
const path = require('path');

const DEFAULT_URL = process.env.CHAQMOQ_URL || 'https://chaqmoq.uz';
const APP_URL = (process.env.CHAQMOQ_URL || DEFAULT_URL).replace(/\/$/, '');

let mainWindow = null;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 920,
    minWidth: 1024,
    minHeight: 680,
    title: 'ChaqmoqApp',
    backgroundColor: nativeTheme.shouldUseDarkColors ? '#070a12' : '#f0f3f9',
    show: false,
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      spellcheck: false,
    },
    icon: path.join(__dirname, 'assets', 'icon.png'),
  });

  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
    if (process.platform === 'darwin') {
      app.dock?.show();
    }
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    // Tashqi havolalar tizim brauzerida
    try {
      const u = new URL(url);
      const appHost = new URL(APP_URL).host;
      if (u.host !== appHost) {
        shell.openExternal(url);
        return { action: 'deny' };
      }
    } catch (_) {
      shell.openExternal(url);
      return { action: 'deny' };
    }
    return { action: 'allow' };
  });

  mainWindow.webContents.on('will-navigate', (event, url) => {
    try {
      const u = new URL(url);
      const appHost = new URL(APP_URL).host;
      // same site ok
      if (u.protocol !== 'https:' && u.protocol !== 'http:') {
        event.preventDefault();
      }
    } catch (_) {
      event.preventDefault();
    }
  });

  // Offline / load error
  mainWindow.webContents.on('did-fail-load', (_e, code, desc, url, isMain) => {
    if (!isMain || code === -3) return; // -3 = aborted
    const html = `<!doctype html><html lang="uz"><head><meta charset="utf-8">
      <title>ChaqmoqApp</title>
      <style>
        body{margin:0;min-height:100vh;display:grid;place-items:center;
          font-family:system-ui,sans-serif;background:#070a12;color:#e2e8f0}
        .box{max-width:420px;padding:28px;border-radius:18px;background:#0f172a;
          border:1px solid rgba(255,255,255,.08);text-align:center}
        h1{font-size:1.25rem;margin:0 0 8px}
        p{color:#94a3b8;font-size:.95rem;line-height:1.5}
        button{margin-top:16px;padding:10px 18px;border:0;border-radius:10px;
          background:linear-gradient(135deg,#f0d78c,#c9a24a);color:#0b1220;
          font-weight:800;cursor:pointer}
        small{display:block;margin-top:12px;color:#64748b;font-size:.75rem;word-break:break-all}
      </style></head><body><div class="box">
        <h1>Internet yoki server bilan bog'lanib bo'lmadi</h1>
        <p>ChaqmoqApp saytiga ulanib bo'lmadi. Internetni tekshiring va qayta urinib ko'ring.</p>
        <button onclick="location.href='${APP_URL}'">Qayta urinish</button>
        <small>${desc || ''} (${code}) · ${url || APP_URL}</small>
      </div></body></html>`;
    mainWindow.loadURL('data:text/html;charset=utf-8,' + encodeURIComponent(html));
  });

  mainWindow.loadURL(APP_URL + '/');

  buildMenu();
}

function buildMenu() {
  const isMac = process.platform === 'darwin';
  const template = [
    ...(isMac
      ? [{
          label: app.name,
          submenu: [
            { role: 'about' },
            { type: 'separator' },
            { role: 'services' },
            { type: 'separator' },
            { role: 'hide' },
            { role: 'hideOthers' },
            { role: 'unhide' },
            { type: 'separator' },
            { role: 'quit' },
          ],
        }]
      : []),
    {
      label: 'Fayl',
      submenu: [
        {
          label: 'Bosh sahifa',
          accelerator: 'CmdOrCtrl+Home',
          click: () => mainWindow?.loadURL(APP_URL + '/'),
        },
        {
          label: 'Yangilash',
          accelerator: 'CmdOrCtrl+R',
          click: () => mainWindow?.webContents.reload(),
        },
        { type: 'separator' },
        isMac ? { role: 'close' } : { role: 'quit' },
      ],
    },
    {
      label: 'Ko\'rinish',
      submenu: [
        { role: 'reload' },
        { role: 'forceReload' },
        { type: 'separator' },
        { role: 'resetZoom' },
        { role: 'zoomIn' },
        { role: 'zoomOut' },
        { type: 'separator' },
        { role: 'togglefullscreen' },
      ],
    },
    {
      label: 'Yordam',
      submenu: [
        {
          label: 'Brauzerda ochish',
          click: () => shell.openExternal(APP_URL),
        },
        {
          label: 'Haqida',
          click: () => {
            dialog.showMessageBox(mainWindow, {
              type: 'info',
              title: 'ChaqmoqApp',
              message: 'ChaqmoqApp Desktop',
              detail: `Versiya ${app.getVersion()}\nSayt: ${APP_URL}\n\nTo'liq o'quv markazi boshqaruv tizimi.`,
            });
          },
        },
      ],
    },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

// Bitta instance
const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });

  app.whenReady().then(() => {
    // Xavfsiz session
    session.defaultSession.setPermissionRequestHandler((_wc, _perm, cb) => cb(false));
    createWindow();
    app.on('activate', () => {
      if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
  });
}

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
