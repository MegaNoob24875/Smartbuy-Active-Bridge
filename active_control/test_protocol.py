import struct
import unittest
from protocol import Config, parse_status, parse_config


class WireTests(unittest.TestCase):
    def test_config_layout_matches_firmware(self):
        config = Config(12, 19, 9, True, 30, [255, 4] + list(range(2, 32)))
        packet = config.packet(127, 2)
        self.assertEqual(len(packet), 64)
        self.assertEqual(packet[:13], b'\x21SBCF\x7f\x02\x01\x0c\x13\x09\x01\x1e')
        self.assertEqual(packet[13:15], b'\xff\x04')
        decoded, sequence, error = parse_config(packet)
        self.assertEqual((decoded, sequence, error), (config, 127, 0))

    def test_status_signed_axes_and_flags(self):
        payload = bytearray(63)
        payload[:8] = b'SBGP\x01\x02\x01\x01'
        struct.pack_into('<IIIhhhhHH', payload, 8, 1243, 8900, 1 << 31,
                         -512, 512, -256, 0, 1023, 0)
        payload[32], payload[40] = 5, 1
        status = parse_status(b'\x20' + payload)
        self.assertEqual(status['axes'], [-1, 1, -.5, 0])
        self.assertEqual(status['triggers'], [1, 0])
        self.assertEqual(status['buttons'], 0x80000000)
        self.assertTrue(status['bluetooth'] and status['received'] and status['storage'])

    def test_reject_unsafe_or_incompatible_data(self):
        for config in (Config(left_deadzone=41), Config(mapping=[32]*32),
                       Config(mapping=[]), Config(threshold=-1)):
            with self.assertRaises(ValueError): config.packet(1, 2)
        with self.assertRaises(ValueError): parse_status(b'\x20' + bytes(63))
        with self.assertRaises(ValueError): Config.from_bytes(bytes(40))


if __name__ == '__main__': unittest.main()
