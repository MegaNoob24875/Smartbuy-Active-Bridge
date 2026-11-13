"""Versioned Smartbuy bridge wire protocol. Independent of Qt and Windows."""
from dataclasses import dataclass, field
import struct

STATUS_REPORT = 0x20
CONFIG_REPORT = 0x21


@dataclass(eq=True)
class Config:
    left_deadzone: int = 5
    right_deadzone: int = 5
    invert: int = 0
    swap_sticks: bool = False
    threshold: int = 13
    mapping: list[int] = field(default_factory=lambda: list(range(32)))

    def validate(self):
        if not 0 <= self.left_deadzone <= 40 or not 0 <= self.right_deadzone <= 40:
            raise ValueError('Мёртвая зона должна быть от 0 до 40%.')
        if not 0 <= self.invert <= 15 or not 0 <= self.threshold <= 100:
            raise ValueError('Некорректные параметры осей.')
        if len(self.mapping) != 32 or any(v not in range(32) and v != 255 for v in self.mapping):
            raise ValueError('Профиль должен содержать 32 назначения кнопок.')

    def to_bytes(self):
        self.validate()
        return bytes([1, self.left_deadzone, self.right_deadzone, self.invert,
                      int(self.swap_sticks), self.threshold, *self.mapping, 0, 0])

    @classmethod
    def from_bytes(cls, data):
        if len(data) != 40 or data[0] != 1 or data[38:40] != b'\0\0':
            raise ValueError('Неизвестный формат настроек.')
        if data[4] not in (0, 1):
            raise ValueError('Некорректный флаг стиков.')
        obj = cls(data[1], data[2], data[3], bool(data[4]), data[5], list(data[6:38]))
        obj.validate()
        return obj

    def packet(self, sequence, operation):
        if operation not in (1, 2, 3):
            raise ValueError('Unknown operation')
        return bytes([CONFIG_REPORT]) + (b'SBCF' + bytes([sequence, operation]) + self.to_bytes()).ljust(63, b'\0')


def feature_payload(data, report, magic):
    packet = bytes(data)
    if len(packet) != 64 or packet[0] != report or packet[1:5] != magic:
        raise ValueError('Ответ ESP32 имеет неизвестный формат.')
    return packet[1:]


def parse_config(data):
    payload = feature_payload(data, CONFIG_REPORT, b'SBCF')
    return Config.from_bytes(payload[6:46]), payload[4], payload[46]


def parse_status(data):
    p = feature_payload(data, STATUS_REPORT, b'SBGP')
    if p[4] != 1:
        raise ValueError('Обновите приложение для этой версии прошивки.')
    reports, last_input, buttons = struct.unpack_from('<III', p, 8)
    axes = struct.unpack_from('<hhhh', p, 20)
    triggers = struct.unpack_from('<HH', p, 28)
    return dict(usb=True, control=True, bluetooth=bool(p[6]), received=bool(p[7]),
                reports=reports, last_input=last_input, buttons=buttons,
                axes=[v / 512 for v in axes], triggers=[v / 1023 for v in triggers],
                dpad=p[32], battery=p[33], firmware=p[5], storage=bool(p[40]),
                revision=struct.unpack_from('<I', p, 36)[0])
