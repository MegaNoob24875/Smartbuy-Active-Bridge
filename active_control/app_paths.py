"""Writable user data and read-only resources in source and frozen builds."""
import os
from pathlib import Path
import sys

def data_dir():
    if getattr(sys,'frozen',False):
        path=Path(os.environ.get('LOCALAPPDATA',Path.home()/'AppData'/'Local'))/'SmartbuyActiveControl'
    else:
        path=Path(__file__).resolve().parent
    path.mkdir(parents=True,exist_ok=True)
    return path

def resource_path(name):
    root=Path(sys._MEIPASS) if getattr(sys,'frozen',False) else Path(__file__).resolve().parent.parent
    return root/name
