"""Offline frozen-build smoke test; never opens a controller or serial port."""
import ctypes
import importlib.util
import json
import multiprocessing as mp
from pathlib import Path

def child_check(channel):
    try:
        import serial
        from serial.tools import list_ports
        from protocol import Config
        from serial_protocol import Decoder,frame
        assert Decoder().feed(frame(4,Config().packet(1,1)))
        # Load the native client without creating a virtual Xbox or driver bus.
        package=Path(importlib.util.find_spec('vgamepad').origin).parent
        dll=package/'win'/'vigem'/'client'/'x64'/'ViGEmClient.dll'
        ctypes.CDLL(str(dll))
        channel.put({'worker':True,'serial':serial.VERSION,'vigem_client':True})
    except Exception as exc:
        channel.put({'error':str(exc)})

def run_checks(report_path):
    from PySide6.QtWidgets import QApplication,QWidget
    from PySide6.QtNetwork import QLocalServer
    from app_paths import resource_path,data_dir
    app=QApplication([]); app.setStyle('windowsvista')
    widget=QWidget(); widget.resize(160,80); widget.show(); app.processEvents()
    result={'qt':not widget.grab().isNull(),'icon':resource_path('assets/app.ico').is_file(),
            'data_dir':str(data_dir())}
    widget.close()
    ctx=mp.get_context('spawn'); channel=ctx.Queue()
    process=ctx.Process(target=child_check,args=(channel,)); process.start()
    process.join(30)
    if process.is_alive(): process.terminate(); process.join(); result['error']='Worker timeout'
    else:
        try: result.update(channel.get(timeout=3))
        except Exception: result['error']='Worker exited without result'
    result['ok']=all(result.get(key) for key in ('qt','icon','worker','vigem_client')) and 'error' not in result
    Path(report_path).write_text(json.dumps(result,indent=2),encoding='utf-8')
    return 0 if result['ok'] else 1
