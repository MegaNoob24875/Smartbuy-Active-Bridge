"""Firmware v5 hardware validation; close ACTIVE Control before running."""
from dataclasses import replace
import time
import serial
from serial.tools import list_ports
from protocol import parse_config,parse_status
from serial_protocol import Decoder,frame

def main():
    ports=[p.device for p in list_ports.comports() if p.vid==0x303A and p.pid==0x1004]
    assert len(ports)==1,ports
    decoder=Decoder(); current=None; ack=0; status=None; packets=0
    with serial.Serial(ports[0],115200,timeout=.05,write_timeout=.3) as port:
        def receive_until(predicate,seconds=3):
            nonlocal current,ack,status,packets
            deadline=time.monotonic()+seconds
            while time.monotonic()<deadline:
                for kind,payload in decoder.feed(port.read(1024)):
                    if kind==1: packets+=1
                    elif kind==2: status=parse_status(payload)
                    elif kind==3:
                        current,ack,error=parse_config(payload)
                        assert error==0,error
                if predicate(): return
            raise RuntimeError('CDC response timeout')
        receive_until(lambda: current is not None and status is not None and packets>20)
        original=current; sequence=ack%255+1
        test=replace(original,left_deadzone=8 if original.left_deadzone!=8 else 7)
        try:
            port.write(frame(4,test.packet(sequence,1)))
            receive_until(lambda: ack==sequence and current==test)
            print('PASS: CDC configuration applied and acknowledged',flush=True)
        finally:
            sequence=sequence%255+1
            port.write(frame(4,original.packet(sequence,2)))
            receive_until(lambda: ack==sequence and current==original)
            print('PASS: original profile restored and saved to NVS',flush=True)
        print('PASS: firmware',status['firmware'],'game packets',packets,'Bluetooth',status['bluetooth'],flush=True)

if __name__=='__main__': main()
