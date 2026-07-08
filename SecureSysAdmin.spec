# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec-файл для SecureSysAdmin.
Сборка: pyinstaller SecureSysAdmin.spec
"""

import sys
from pathlib import Path

block_cipher = None

# Определяем пути
PROJECT_ROOT = Path(__file__).parent

# Собираем все .py файлы из app/ как hidden imports
hidden_imports = [
    "PyQt6",
    "PyQt6.QtCore",
    "PyQt6.QtWidgets",
    "PyQt6.QtGui",
    "psutil",
    "win32api",
    "win32security",
    "win32file",
    "json",
    "hashlib",
    "struct",
    "re",
    "threading",
    "pathlib",
    "shutil",
    "subprocess",
    "datetime",
    "os",
    "ctypes",
    "string",
    "dataclasses",
    "enum",
    "typing",
    "functools",
]

# Данные для включения
datas = [
    # Здесь можно добавить иконки, шрифты, etc.
]

a = Analysis(
    ['main.py'],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='SecureSysAdmin',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,           # БЕЗ консоли для GUI-приложения
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,               # Путь к .ico если нужен
    uac_admin=True,         # True — запрашивать права админа при запуске
)