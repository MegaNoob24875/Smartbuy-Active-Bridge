# Windows x64, one file. No QtWebEngine/QML/dev environment bundled.
from pathlib import Path
import importlib.util
import os

root=Path(SPECPATH).parent
vgamepad=Path(importlib.util.find_spec('vgamepad').origin).parent
dll=vgamepad/'win/vigem/client/x64/ViGEmClient.dll'
a=Analysis([str(root/'active_control/app.py')],pathex=[str(root/'active_control')],
    binaries=[(str(dll),'vgamepad/win/vigem/client/x64')],
    datas=[(str(root/'assets/app.ico'),'assets')],
    hiddenimports=['packaging_checks','vgamepad.win.virtual_gamepad'],
    excludes=['PySide6.QtQml','PySide6.QtQuick','PySide6.QtWebEngineCore',
              'PySide6.QtWebEngineWidgets','PySide6.QtWebEngineQuick',
              'PySide6.QtMultimedia','PySide6.QtPdf','tkinter','unittest',
              'vgamepad.lin','hid','services','transport'],
    noarchive=False)
# API-set DLLs are supplied by Windows 10/11. An unrelated application on
# PATH can contribute old downlevel CRT shims and break Qt with error 127.
a.binaries=[entry for entry in a.binaries if not Path(entry[0]).name.lower().startswith('api-ms-win-')
            and Path(entry[0]).name.lower() not in ('ucrtbase.dll','icu.dll','icuuc.dll','icuin.dll','icudt.dll')
            and not Path(entry[0]).name.lower().startswith('icudt')
            and Path(entry[0]).name.lower() not in ('libcrypto-3-x64.dll','libssl-3-x64.dll','qopensslbackend.dll')
            and not any(name in entry[0].lower() for name in ('qt6quick','qt6qml','virtualkeyboard'))]
pyz=PYZ(a.pure)
debug_console=os.environ.get('ACTIVE_DEBUG_CONSOLE')=='1'
exe=EXE(pyz,a.scripts,a.binaries,a.datas,[],name='ACTIVE-Control-debug' if debug_console else 'ACTIVE-Control',
    debug=False,bootloader_ignore_signals=False,strip=False,upx=False,
    console=debug_console,icon=str(root/'assets/app.ico'),
    version=str(root/'packaging/version.txt'))
