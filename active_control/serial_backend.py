"""Firmware v5: one CDC owner, no HID feature transfers or HID polling."""
import logging
import multiprocessing as mp
import queue
import time
import serial
from serial.tools import list_ports
from PySide6.QtCore import QThread,Signal
from protocol import parse_config,parse_status
from serial_protocol import Decoder,frame
from xinput_bridge import decode_usb_report,XboxOutput
from ipc_utils import latest,NEUTRAL
from app_paths import data_dir


def serial_service(stop,updates,commands,events,enabled):
    logging.basicConfig(filename=str(data_dir()/'input-diagnostic.log'),
                        level=logging.INFO,format='%(asctime)s CDC %(message)s')
    port=None; xbox=None; pending=None; output=None; status={}; config=None
    decoder=Decoder(); sequence=0; packets=0; last_packet=0.; last_status=0.
    last_scan=0.; last_emit=0.; last_log=0.; last_xbox_attempt=0.; xbox_error=''
    def emit(kind,*args): latest(events,(kind,*args))
    try:
        while not stop.is_set():
            now=time.monotonic()
            try:
                while True:
                    command=commands.get_nowait()
                    if command[0]=='xinput': enabled=bool(command[1])
                    elif command[0]=='scan': last_scan=0
                    elif command[0]=='apply':
                        _,proposed,operation,token=command
                        if not port:
                            emit('error','USB Serial не подключён.'); continue
                        sequence=sequence%255+1
                        try:
                            port.write(frame(4,proposed.packet(sequence,operation)))
                            pending=(sequence,proposed,operation,token,now)
                        except (OSError,serial.SerialException) as exc:
                            emit('error',str(exc))
            except queue.Empty: pass
            if not enabled and xbox: xbox.close(); xbox=None
            if port is None and now-last_scan>=1:
                last_scan=now
                for device in list_ports.comports():
                    if device.vid!=0x303A or device.pid!=0x1004: continue
                    try:
                        port=serial.Serial(device.device,115200,timeout=0,write_timeout=.1)
                        port.dtr=True; decoder=Decoder(); output=None; status={}
                        last_packet=now
                        logging.info('Opened %s',device.device)
                        break
                    except (OSError,serial.SerialException) as exc:
                        logging.warning('Open failed: %s',exc); port=None
            if port:
                try:
                    data=port.read(min(port.in_waiting,8192))
                    for kind,payload in decoder.feed(data):
                        if kind==1:
                            decoded=decode_usb_report(payload)
                            if decoded is not None:
                                output=decoded; packets+=1; last_packet=time.monotonic()
                        elif kind==2:
                            status=parse_status(payload); last_status=time.monotonic()
                        elif kind==3:
                            current,ack,error=parse_config(payload)
                            if config!=current:
                                config=current; emit('config',current)
                            if pending and ack==pending[0]:
                                _,proposed,operation,token,_=pending; pending=None
                                if error: emit('error','ESP32 отклонила настройки: '+str(error))
                                elif operation!=3 and current!=proposed: emit('error','Ответ ESP32 не совпадает с профилем.')
                                else: emit('completed','Сохранено в ESP32' if operation in (2,3) else 'Применено до перезапуска',current)
                            if not pending: sequence=ack
                    if time.monotonic()-last_packet>5:
                        raise OSError('No USB input for 5 s')
                except (OSError,serial.SerialException,ValueError) as exc:
                    logging.warning('USB read failed: %s',exc)
                    port.close(); port=None; output=None; status={}; config=None
                    if pending: emit('error','USB отключён, настройка не подтверждена.'); pending=None
            fresh=port is not None and time.monotonic()-last_packet<.75 and output is not None
            if enabled and fresh and xbox is None and now-last_xbox_attempt>5:
                last_xbox_attempt=now
                try: xbox=XboxOutput(); xbox_error=''
                except Exception as exc: xbox_error=str(exc)
            if xbox:
                try: xbox.send(output if fresh else NEUTRAL)
                except Exception as exc:
                    xbox_error=str(exc); xbox.close(); xbox=None
            if pending and now-pending[4]>3:
                emit('error','Нет подтверждения настроек ESP32.'); pending=None
            if now-last_emit>=.04:
                last_emit=now; control=now-last_status<1.5
                sample=dict(status) if control else {}
                sample.update(heartbeat=now,usb=fresh,control=control,output=output if fresh else None,
                              packets=packets,telemetry_stale=not control,
                              xinput='active' if xbox else ('off' if not enabled else ('driver_error' if xbox_error else 'waiting')),
                              xinput_error=xbox_error)
                latest(updates,sample)
            if now-last_log>=2:
                last_log=now
                logging.info('USB=%s packets=%s age=%.3f Xbox=%s buttons=%s',fresh,packets,
                             time.monotonic()-last_packet,xbox is not None,
                             output.get('buttons') if fresh else None)
            stop.wait(.004)
    finally:
        if xbox: xbox.close()
        if port: port.close()


class Worker(QThread):
    state=Signal(dict); configuration=Signal(object); completed=Signal(str,object); error=Signal(str)
    def __init__(self,xinput_enabled=True):
        super().__init__(); self.enabled=xinput_enabled; self.commands=queue.Queue()
        self.last_scan=time.monotonic(); self.counter=0
    def submit(self,config,operation):
        config.validate(); self.commands.put(('apply',config,operation))
    def set_xinput_enabled(self,enabled):
        self.enabled=bool(enabled); self.commands.put(('xinput',self.enabled))
    def run(self):
        ctx=mp.get_context('spawn')
        stop=ctx.Event(); updates=ctx.Queue(2); commands=ctx.Queue(16); events=ctx.Queue(32)
        process=ctx.Process(target=serial_service,args=(stop,updates,commands,events,self.enabled),daemon=True)
        process.start(); heartbeat=time.monotonic()+5
        try:
            while not self.isInterruptionRequested():
                try:
                    while True:
                        command=self.commands.get_nowait()
                        if command[0]=='apply': self.counter+=1; command=(*command,self.counter)
                        latest(commands,command)
                except queue.Empty: pass
                if self.last_scan==0:
                    latest(commands,('scan',)); self.last_scan=time.monotonic()
                try:
                    while True:
                        sample=updates.get_nowait(); heartbeat=time.monotonic(); self.state.emit(sample)
                except queue.Empty: pass
                try:
                    while True:
                        event=events.get_nowait()
                        if event[0]=='config': self.configuration.emit(event[1])
                        elif event[0]=='completed': self.completed.emit(event[1],event[2])
                        elif event[0]=='error': self.error.emit(event[1])
                except queue.Empty: pass
                if not process.is_alive() or time.monotonic()-heartbeat>8:
                    stop.set(); process.join(.3)
                    if process.is_alive(): process.terminate(); process.join(.3)
                    # Recreate IPC too: a terminated native call may leave
                    # multiprocessing queues unusable.
                    for channel in (updates,commands,events): channel.cancel_join_thread(); channel.close()
                    stop=ctx.Event(); updates=ctx.Queue(2); commands=ctx.Queue(16); events=ctx.Queue(32)
                    process=ctx.Process(target=serial_service,args=(stop,updates,commands,events,self.enabled),daemon=True)
                    process.start(); heartbeat=time.monotonic()+5
                    self.error.emit('USB Serial-процесс восстановлен; неподтверждённые настройки нужно повторить.')
                self.msleep(10)
        finally:
            stop.set(); process.join(.4)
            if process.is_alive(): process.terminate(); process.join(.4)
            for channel in (updates,commands,events): channel.cancel_join_thread(); channel.close()
