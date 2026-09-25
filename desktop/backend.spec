# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['app/desktop_entry.py'],
    pathex=['.', 'app'],
    binaries=[],
    datas=[],
    hiddenimports=[
        'main', 'auto', 'desk', 'web_app', 'risk', 'instruments',
        'memory', 'news', 'predict', 'streamers',
        'broker.capital',
        'strategy.base', 'strategy.registry', 'strategy.router',
        'strategy.orb', 'strategy.ema_pullback', 'strategy.macd_trend',
        'strategy.rsi_reversion', 'strategy.ema_atr', 'strategy.donchian',
        'strategy.extra', 'strategy.indicators', 'strategy.levels', 'strategy.tune',
        'research.walk'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='cfd_backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
