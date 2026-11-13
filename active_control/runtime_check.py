"""Firmware v5 hardware check; run with ACTIVE Control closed."""
import ctypes as c
from ctypes import wintypes as w
import multiprocessing as mp
import time
from PySide6.QtCore import QCoreApplication,QTimer
from serial_backend import Worker


class Gamepad(c.Structure):
    _fields_=[('buttons',w.WORD),('lt',w.BYTE),('rt',w.BYTE),
              ('lx',c.c_short),('ly',c.c_short),('rx',c.c_short),('ry',c.c_short)]


class State(c.Structure):
    _fields_=[('packet',w.DWORD),('gamepad',Gamepad)]


def read_xinput():
    api=c.WinDLL('xinput1_4')
    for slot in range(4):
        state=State()
        if api.XInputGetState(slot,c.byref(state))==0:
            return slot,state
    return None,None


def main():
    app=QCoreApplication([]); worker=Worker(True)
    result=dict(states=0,ui_ticks=0,max_ui_gap=0,xinput_states=0,packets=0,
                control_states=0)
    last_tick=time.monotonic()
    def tick():
        nonlocal last_tick
        now=time.monotonic(); result['max_ui_gap']=max(result['max_ui_gap'],now-last_tick)
        last_tick=now; result['ui_ticks']+=1
        if read_xinput()[0] is not None: result['xinput_states']+=1
    def sample(state):
        result['states']+=1; result['packets']=state.get('packets',0)
        if state.get('control') and state.get('firmware')==5:
            result['control_states']+=1
    worker.state.connect(sample); worker.error.connect(lambda message:print('EVENT:',message,flush=True))
    timer=QTimer(); timer.timeout.connect(tick); timer.start(16)
    worker.start(); QTimer.singleShot(12000,app.quit)
    app.exec(); worker.requestInterruption(); worker.wait(3000)
    print(result,flush=True)
    assert result['ui_ticks']>300 and result['max_ui_gap']<.3,result
    assert result['xinput_states']>100 and result['packets']>100,result
    assert result['control_states']>100,result


if __name__=='__main__':
    mp.freeze_support(); main()
