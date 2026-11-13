"""Read-only soak monitor; run alongside ACTIVE Control, never opens USB."""
import ctypes as c
import json
from pathlib import Path
import re
import sys
import time
from runtime_check import State


def main():
    duration=float(sys.argv[1]) if len(sys.argv)>1 else 300
    api=c.WinDLL('xinput1_4')
    path=Path(__file__).with_name('input-diagnostic.log')
    started=time.monotonic(); next_print=0.; ready=False; last_state=None
    result=dict(seconds=duration,samples=0,changes=0,buttons_seen=0,
                missing_xinput=0,multiple_xinput=0,usb_errors=0,stale_usb=0,
                packet_resets=0,packets=0)
    previous_packets=None
    with path.open(encoding='utf-8') as log:
        log.seek(0,2)
        while time.monotonic()-started<duration:
            for line in log.readlines():
                match=re.search(r'USB=(True|False) packets=(\d+) age=([\d.]+)',line)
                if match:
                    present=match[1]=='True'; packets=int(match[2]); age=float(match[3])
                    if present and packets>0 and age<.25: ready=True
                    if ready:
                        result['stale_usb']+=int(not present or age>.75)
                        if previous_packets is not None and packets<previous_packets: result['packet_resets']+=1
                        previous_packets=packets; result['packets']=packets
                if ready and ('USB read failed' in line or 'No USB input' in line): result['usb_errors']+=1
            slots=[]
            for slot in range(4):
                state=State()
                if api.XInputGetState(slot,c.byref(state))==0: slots.append((slot,state))
            if ready:
                result['samples']+=1
                result['missing_xinput']+=int(not slots)
                result['multiple_xinput']+=int(len(slots)>1)
                if slots:
                    g=slots[0][1].gamepad
                    values=(g.buttons,g.lt,g.rt,g.lx,g.ly,g.rx,g.ry)
                    result['buttons_seen']|=g.buttons
                    result['changes']+=int(last_state is not None and values!=last_state)
                    last_state=values
            elapsed=time.monotonic()-started
            if elapsed>=next_print:
                print(json.dumps(dict(elapsed=round(elapsed),ready=ready,**result)),flush=True)
                next_print=elapsed+15
            time.sleep(.02)
    result['ready']=ready
    Path(__file__).with_name('stability-result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result),flush=True)
    assert ready and result['samples']>100
    assert not any(result[k] for k in ('missing_xinput','multiple_xinput','usb_errors','stale_usb','packet_resets')),result


if __name__=='__main__': main()
