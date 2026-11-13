import struct
import unittest
from xinput_bridge import decode_usb_report,xbox_values


class XboxTests(unittest.TestCase):
    def test_face_shoulders_and_menu_buttons(self):
        mask=sum(1<<i for i in (0,1,2,3,4,5,8,9,16,17,18))
        buttons,triggers,sticks=xbox_values(dict(buttons=mask,dpad=0,axes=[0]*4,triggers=[0,0]))
        self.assertEqual(buttons,0xF7F0)
        self.assertEqual(triggers,[0,0]); self.assertEqual(sticks,[0]*4)

    def test_axes_triggers_and_dpad(self):
        buttons,triggers,sticks=xbox_values(dict(buttons=0,dpad=1|4,axes=[-1,-1,1,1],triggers=[.5,1]))
        self.assertEqual(buttons,0x9)
        self.assertEqual(triggers,[128,255])
        self.assertEqual(sticks,[-32767,32767,32767,-32767])

    def test_actual_usb_report_layout(self):
        packet=b'\x03'+struct.pack('<IBHHHHHH',0x30,0x82,0,32767,65535,32767,1023,65535)
        decoded=decode_usb_report(packet)
        self.assertEqual(decoded['buttons'],0x30)
        self.assertEqual(decoded['dpad'],4)
        self.assertEqual(decoded['axes'],[-1,0,1,0])
        self.assertAlmostEqual(decoded['triggers'][0],1)
        self.assertIsNone(decode_usb_report(b'bad'))


if __name__=='__main__': unittest.main()
