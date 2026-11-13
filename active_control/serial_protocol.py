"""Resynchronizing, checksummed native CDC transport (firmware v5)."""
import binascii

MAGIC=b'SB5!'

def frame(kind,payload):
    payload=bytes(payload)
    if len(payload)>64: raise ValueError('Frame too long')
    body=bytes((kind,len(payload)))+payload
    return MAGIC+body+binascii.crc_hqx(body,0xffff).to_bytes(2,'little')

class Decoder:
    def __init__(self): self.buffer=bytearray()
    def feed(self,data):
        self.buffer.extend(data); result=[]
        while True:
            start=self.buffer.find(MAGIC)
            if start<0:
                self.buffer=self.buffer[-3:]; break
            if start: del self.buffer[:start]
            if len(self.buffer)<6: break
            size=self.buffer[5]
            if size>64: del self.buffer[0]; continue
            if len(self.buffer)<size+8: break
            body=self.buffer[4:6+size]
            check=int.from_bytes(self.buffer[6+size:8+size],'little')
            if binascii.crc_hqx(body,0xffff)!=check:
                del self.buffer[0]; continue
            result.append((body[0],bytes(body[2:])))
            del self.buffer[:size+8]
        return result
