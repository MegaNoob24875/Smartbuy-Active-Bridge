import unittest
from serial_protocol import Decoder,frame

class SerialTests(unittest.TestCase):
    def test_fragmentation(self):
        message=frame(2,bytes(range(64))); decoder=Decoder(); result=[]
        for value in message: result.extend(decoder.feed(bytes([value])))
        self.assertEqual(result,[(2,bytes(range(64)))])
    def test_corruption_and_noise_resynchronize(self):
        broken=bytearray(frame(1,b'bad')); broken[6]^=1
        decoder=Decoder()
        self.assertEqual(decoder.feed(b'noise'+broken+frame(1,b'good')),[(1,b'good')])
    def test_concatenated_frames_and_partial_magic(self):
        decoder=Decoder(); self.assertEqual(decoder.feed(b'noiseSB'),[])
        self.assertEqual(decoder.feed(frame(1,b'a')[2:]+frame(3,b'b')),[(1,b'a'),(3,b'b')])
    def test_command_payload(self):
        from protocol import Config,parse_config
        payload=Config().packet(7,2)
        self.assertEqual(Decoder().feed(frame(4,payload)),[(4,payload)])

if __name__=='__main__': unittest.main()
