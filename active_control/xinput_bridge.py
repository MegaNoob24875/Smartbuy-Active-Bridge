"""Xbox 360 output. This module has no Qt or USB feature/control I/O."""
import struct


def decode_usb_report(packet):
    if len(packet) != 18 or packet[0] != 3:
        return None
    axes = struct.unpack_from('<HHHH', bytes(packet), 6)
    throttle, brake = struct.unpack_from('<HH', bytes(packet), 14)
    return dict(axes=[max(-1., min(1., (v-32767)/32767)) for v in axes],
                triggers=[brake/65535, throttle/65535],
                buttons=struct.unpack_from('<I', bytes(packet), 1)[0],
                dpad={0:1,1:5,2:4,3:6,4:2,5:10,6:8,7:9}.get(packet[5]&15, 0))


def xbox_values(sample):
    mask = sample.get('buttons', 0)
    buttons = 0
    for source, target in ((0,0x1000),(1,0x2000),(2,0x4000),(3,0x8000),
                           (4,0x0100),(5,0x0200),(8,0x0040),(9,0x0080),
                           (16,0x0400),(17,0x0020),(18,0x0010)):
        if mask & (1 << source): buttons |= target
    dpad = sample.get('dpad', 0)
    for source, target in ((1,1),(2,2),(4,8),(8,4)):
        if dpad & source: buttons |= target
    axes = sample.get('axes', [0.]*4)
    sticks = [0 if abs(v)<.0001 else max(-32768,min(32767,round(v*32767))) for v in axes]
    sticks[1] = max(-32768,min(32767,-sticks[1]))
    sticks[3] = max(-32768,min(32767,-sticks[3]))
    triggers = [max(0,min(255,round(v*255))) for v in sample.get('triggers',[0.,0.])]
    if not triggers[0] and mask & ((1<<6)|(1<<24)): triggers[0]=255
    if not triggers[1] and mask & ((1<<7)|(1<<25)): triggers[1]=255
    return buttons, triggers, sticks


class XboxOutput:
    def __init__(self):
        import vgamepad
        self.pad = vgamepad.VX360Gamepad()
        self.last = None
        self.neutral()

    def send(self, sample):
        buttons, triggers, sticks = xbox_values(sample)
        values=(buttons,*triggers,*sticks)
        if values == self.last: return
        report=self.pad.report
        report.wButtons=buttons
        report.bLeftTrigger,report.bRightTrigger=triggers
        report.sThumbLX,report.sThumbLY,report.sThumbRX,report.sThumbRY=sticks
        self.pad.update()
        self.last=values

    def neutral(self):
        self.send(dict(axes=[0.]*4,triggers=[0.,0.],buttons=0,dpad=0))

    def close(self):
        if self.pad is not None:
            self.neutral()
            self.pad=None
