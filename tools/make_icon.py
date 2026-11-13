"""Create an original gamepad icon using Qt's vector painter; no external assets."""
import struct
from pathlib import Path
from PySide6.QtCore import Qt,QBuffer,QIODevice,QRectF
from PySide6.QtGui import QImage,QPainter,QColor,QPen

root=Path(__file__).resolve().parent.parent
images=[]
for size in (256,64,48,32,16):
    image=QImage(size,size,QImage.Format.Format_ARGB32); image.fill(Qt.GlobalColor.transparent)
    p=QPainter(image); p.setRenderHint(QPainter.RenderHint.Antialiasing); p.scale(size/256,size/256)
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor('#0078d4')); p.drawRoundedRect(QRectF(0,0,256,256),52,52)
    p.setBrush(QColor('#ffffff')); p.drawRoundedRect(QRectF(38,79,180,108),35,35)
    p.setPen(QPen(QColor('#0078d4'),13,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap))
    p.drawLine(70,130,106,130); p.drawLine(88,112,88,148)
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor('#0078d4'))
    for x,y in ((170,113),(187,130),(153,130),(170,147)): p.drawEllipse(QRectF(x-7,y-7,14,14))
    p.end(); buf=QBuffer(); buf.open(QIODevice.OpenModeFlag.WriteOnly); image.save(buf,'PNG')
    images.append((size,bytes(buf.data())))
offset=6+16*len(images); entries=[]; payload=[]
for size,data in images:
    entries.append(struct.pack('<BBBBHHII',size%256,size%256,0,0,1,32,len(data),offset))
    payload.append(data); offset+=len(data)
(root/'assets/app.ico').write_bytes(struct.pack('<HHH',0,1,len(images))+b''.join(entries)+b''.join(payload))
