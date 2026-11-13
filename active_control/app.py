"""Smartbuy ACTIVE Control — USB tester and on-device profile editor."""
import argparse
import base64
from dataclasses import asdict
import json
from pathlib import Path
import sys
import time
import multiprocessing as mp

from PySide6.QtCore import Qt, QTimer, QRectF, QPointF
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QAction, QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QLabel, QPushButton,
    QHBoxLayout, QVBoxLayout, QGridLayout, QStackedWidget, QComboBox,
    QTableWidget, QHeaderView, QAbstractItemView, QSlider, QCheckBox,
    QFileDialog, QLineEdit, QListWidget, QMessageBox, QScrollArea,
    QSystemTrayIcon, QMenu, QStyle,
)
from serial_backend import Worker
from protocol import Config

from app_paths import data_dir,resource_path
ROOT = data_dir()
BUTTON_NAMES = {
    0:'A', 1:'B', 2:'X', 3:'Y', 4:'L1', 5:'R1', 6:'L2 · цифровой',
    7:'R2 · цифровой', 8:'L3', 9:'R3', 16:'HOME', 17:'SELECT', 18:'START',
    19:'CAPTURE', 24:'L2 · порог курка', 25:'R2 · порог курка',
}
ACCENT = '#0078d4'
MUTED = '#555555'
from classic_layout import STYLE, install as install_classic_shell



def label(text, name=None):
    obj = QLabel(text)
    if name:
        obj.setObjectName(name)
    return obj


def card():
    box = QFrame()
    box.setObjectName('card')
    layout = QVBoxLayout(box)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.setSpacing(6)
    return box, layout


class ControllerView(QWidget):
    def __init__(self):
        super().__init__()
        self.sample = {}
        self.setMinimumSize(500, 260)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        scale = min(self.width() / 680, self.height() / 350)
        p.translate((self.width() - 680 * scale) / 2, (self.height() - 350 * scale) / 2)
        p.scale(scale, scale)
        body = QPainterPath()
        body.addRoundedRect(QRectF(127, 62, 426, 217), 78, 78)
        for rect in (QRectF(94, 112, 160, 212), QRectF(426, 112, 160, 212)):
            section = QPainterPath(); section.addEllipse(rect); body = body.united(section)
        p.setPen(QPen(QColor('#707070'), 2))
        p.setBrush(QColor('#dedede'))
        p.drawPath(body)
        p.setPen(QColor('#505050')); p.setFont(QFont('Segoe UI', 10, QFont.Weight.DemiBold))
        p.drawText(QRectF(260, 80, 160, 20), Qt.AlignmentFlag.AlignCenter, 'SMARTBUY  ACTIVE')
        values = self.sample.get('triggers', [0, 0])
        for x, name, amount in ((140, 'L2', values[0]), (436, 'R2', values[1])):
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor('#eeeeee'))
            p.drawRoundedRect(QRectF(x, 32, 104, 16), 7, 7)
            p.setBrush(QColor(ACCENT)); p.drawRoundedRect(QRectF(x, 32, 104 * max(0, min(1, amount)), 16), 7, 7)
            p.setPen(QColor(MUTED)); p.drawText(QRectF(x, 10, 104, 20), Qt.AlignmentFlag.AlignCenter, name)
        buttons = self.sample.get('buttons', 0)
        for x, name, bit in ((140, 'L1', 4), (436, 'R1', 5)):
            pressed = bool(buttons & (1 << bit))
            p.setPen(QPen(QColor('#777777'), 1))
            p.setBrush(QColor(ACCENT if pressed else '#f4f4f4'))
            p.drawRoundedRect(QRectF(x, 55, 104, 22), 2, 2)
            p.setPen(QColor('#ffffff' if pressed else '#202020'))
            p.drawText(QRectF(x,55,104,22),Qt.AlignmentFlag.AlignCenter,name)

        def circle(x, y, text, active=False, radius=17):
            p.setPen(QPen(QColor(ACCENT if active else '#888888'), 1.5))
            p.setBrush(QColor(ACCENT if active else '#f7f7f7'))
            p.drawEllipse(QPointF(x, y), radius, radius)
            p.setPen(QColor('#ffffff' if active else '#202020'))
            p.setFont(QFont('Segoe UI', 10, QFont.Weight.Bold))
            p.drawText(QRectF(x - radius, y - radius, radius * 2, radius * 2), Qt.AlignmentFlag.AlignCenter, text)

        for x, y, name, bit in ((500, 166, 'A', 0), (535, 132, 'B', 1),
                                 (465, 132, 'X', 2), (500, 98, 'Y', 3)):
            circle(x, y, name, bool(buttons & (1 << bit)))
        dpad = self.sample.get('dpad', 0)
        for x, y, text, bit in ((179, 102, '↑', 1), (179, 170, '↓', 2),
                                 (213, 136, '→', 4), (145, 136, '←', 8)):
            circle(x, y, text, bool(dpad & bit), 16)
        circle(309, 145, '−', bool(buttons & (1 << 17)), 13)
        circle(370, 145, '+', bool(buttons & (1 << 18)), 13)
        circle(340, 115, 'H', bool(buttons & (1 << 16)), 13)
        axes = self.sample.get('axes', [0] * 4)
        for cx, cy, offset, bit in ((275, 234, 0, 8), (405, 234, 2, 9)):
            p.setBrush(QColor('#f9f9f9')); p.setPen(QPen(QColor('#999999'), 2))
            p.drawEllipse(QPointF(cx, cy), 44, 44)
            p.setPen(QPen(QColor('#c0c0c0'), 1))
            p.drawLine(QPointF(cx - 40, cy), QPointF(cx + 40, cy))
            p.drawLine(QPointF(cx, cy - 40), QPointF(cx, cy + 40))
            x, y = axes[offset:offset + 2]
            p.setBrush(QColor(ACCENT if buttons & (1 << bit) else '#8b99a8'))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(cx + max(-1, min(1, x)) * 21, cy + max(-1, min(1, y)) * 21), 22, 22)
        p.end()


class StickView(QWidget):
    def __init__(self, name):
        super().__init__(); self.name = name; self.values = [0, 0]; self.deadzone = 5
        self.setMinimumSize(180, 160)

    def paintEvent(self, event):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy = self.width() / 2, self.height() / 2 - 12
        r = min(self.width(), self.height() - 45) * .43
        p.setBrush(QColor('#ffffff')); p.setPen(QPen(QColor('#a0a0a0'), 1.5))
        p.drawEllipse(QPointF(cx, cy), r, r)
        p.setBrush(QColor('#dceaf5')); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(cx, cy), r * self.deadzone / 100, r * self.deadzone / 100)
        p.setPen(QPen(QColor('#c0c0c0'), 1))
        p.drawLine(QPointF(cx-r, cy), QPointF(cx+r, cy)); p.drawLine(QPointF(cx, cy-r), QPointF(cx, cy+r))
        p.setBrush(QColor(ACCENT)); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(cx + self.values[0] * r, cy + self.values[1] * r), 6, 6)
        p.setPen(QColor('#404040')); p.setFont(QFont('Consolas', 11))
        p.drawText(QRectF(0, self.height()-31, self.width(), 25), Qt.AlignmentFlag.AlignCenter,
                   f'X {self.values[0]:+.3f}   Y {self.values[1]:+.3f}')


class Window(QMainWindow):
    def __init__(self,start_worker=True):
        super().__init__()
        self.setWindowTitle('ACTIVE Control — Smartbuy × ESP32')
        self.resize(1220, 860); self.setMinimumSize(1080, 760)
        self.loading = True; self.control = False; self.busy = False
        self.exit_requested=False; self.exit_confirmed=False; self.closing=False
        try: self.xinput_enabled=bool(json.loads((ROOT/'app-settings.json').read_text(encoding='utf-8')).get('xinput',True))
        except (OSError,ValueError,AttributeError): self.xinput_enabled=True
        self.applied = Config(); self.sample = {}; self.events = 0
        self.last_input_signature = None; self.last_activity = 0
        self.profile_path = ROOT / 'profiles.json'
        self.profiles = self.read_profiles()
        install_classic_shell(self)
        self.loading = False; self.load_config(Config()); self.navigate(0)
        self.worker = Worker(self.xinput_enabled)
        self.worker.state.connect(self.on_state)
        self.worker.configuration.connect(self.on_device_config)
        self.worker.completed.connect(self.on_completed)
        self.worker.error.connect(self.on_error)
        if start_worker: self.worker.start()
        self.source.setCurrentIndex(1)
        self.tray=QSystemTrayIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon),self)
        tray_menu=QMenu()
        tray_menu.addAction('Открыть ACTIVE Control',self.show_from_tray)
        tray_menu.addSeparator(); tray_menu.addAction('Завершить работу и отключить Xbox',self.request_exit)
        self.tray.setContextMenu(tray_menu)
        self.tray.activated.connect(lambda reason:self.show_from_tray() if reason in (QSystemTrayIcon.ActivationReason.DoubleClick,QSystemTrayIcon.ActivationReason.Trigger) else None)
        self.tray.setToolTip('ACTIVE Control — Xbox 360')
        if QSystemTrayIcon.isSystemTrayAvailable(): self.tray.show()
        try:
            saved=json.loads((ROOT/'window-state.json').read_text(encoding='utf-8'))
            self.restoreGeometry(base64.b64decode(saved['geometry'],validate=True))
            self.restoreState(base64.b64decode(saved['layout'],validate=True))
        except (OSError,ValueError,KeyError,TypeError): pass

    def navigate(self, index):
        self.pages.setCurrentIndex(index)
        for i, btn in enumerate(self.nav): btn.setChecked(i == index)

    def show_from_tray(self):
        self.showNormal(); self.raise_(); self.activateWindow()

    def toggle_xinput(self,enabled):
        self.xinput_enabled=bool(enabled)
        if hasattr(self,'worker'): self.worker.set_xinput_enabled(enabled)
        try: (ROOT/'app-settings.json').write_text(json.dumps({'xinput':bool(enabled)}),encoding='utf-8')
        except OSError as exc: self.log_event('Не удалось сохранить режим Xbox: '+str(exc))

    def request_exit(self):
        self.exit_requested=True; self.close()

    def build_overview(self):
        page = QWidget(); pl = QVBoxLayout(page); pl.setContentsMargins(0,0,0,0); pl.setSpacing(12)
        box, bl = card(); top = QHBoxLayout(); top.addWidget(label('Геймпад в реальном времени', 'section'), 1)
        self.source = QComboBox(); self.source.addItems(['Вход геймпада', 'Выход USB в Windows']); self.source.currentIndexChanged.connect(self.refresh_views); top.addWidget(self.source)
        bl.addLayout(top); self.controller = ControllerView(); bl.addWidget(self.controller,1)
        grid = QGridLayout(); grid.setSpacing(4)
        self.live_indicators = []
        for i in range(32):
            short = {6:'L2',7:'R2',24:'L2+',25:'R2+'}.get(i, BUTTON_NAMES.get(i, ''))
            indicator = label(f'{i+1:02d}' + (f'  {short}' if short else ''))
            indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
            indicator.setMinimumHeight(22); indicator.setProperty('pressed',False)
            indicator.setToolTip(f'Кнопка {i+1}: {BUTTON_NAMES.get(i,"дополнительная")}')
            grid.addWidget(indicator,i//8,i%8); self.live_indicators.append(indicator)
        bl.addLayout(grid)
        self.live_text = label('Нажми любую кнопку или подвигай стик', 'subtitle'); bl.addWidget(self.live_text)
        pl.addWidget(box, 1)
        tip = label('Для Xbox 360 оставляйте ACTIVE Control запущенным. Крестик сворачивает в трей; меню «Файл → Завершить работу» отключает Xbox.', 'subtitle'); tip.setWordWrap(True); pl.addWidget(tip)
        self.pages.addWidget(page)

    def build_buttons(self):
        box, bl = card(); bl.addWidget(label('Назначения кнопок USB', 'section'))
        desc = label('Слева — вход геймпада, справа — кнопка USB. Для Xbox: 1–4 = A/B/X/Y, 5–6 = LB/RB, 7–8 = LT/RT, 9–10 = L3/R3, 17–19 = Guide/Back/Start.\nОстальные номера доступны в HID-режиме. Несколько входов можно назначить на один выход.', 'subtitle'); desc.setWordWrap(True); bl.addWidget(desc)
        self.table = QTableWidget(32, 3); self.table.setHorizontalHeaderLabels(['Вход геймпада', 'Сейчас', 'Выход USB'])
        self.table.verticalHeader().hide(); self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.mapping = []; self.button_indicators = []
        for i in range(32):
            self.table.setRowHeight(i, 30)
            name = label(f'  {i+1:02d}   {BUTTON_NAMES.get(i, "Дополнительная кнопка")}')
            self.table.setCellWidget(i, 0, name)
            indicator = label('  —  '); self.table.setCellWidget(i, 1, indicator); self.button_indicators.append(indicator)
            combo = QComboBox(); combo.addItem('Отключена', 255)
            for n in range(32): combo.addItem(f'Кнопка {n+1}', n)
            combo.setCurrentIndex(i+1); combo.currentIndexChanged.connect(self.edited)
            self.table.setCellWidget(i, 2, combo); self.mapping.append(combo)
        bl.addWidget(self.table, 1)
        reset = QPushButton('Вернуть назначения 1 → 1'); reset.clicked.connect(self.reset_mapping); bl.addWidget(reset)
        self.pages.addWidget(box)

    def slider_row(self, layout, title, maximum, default):
        row = QHBoxLayout(); row.addWidget(label(title),1); value = label(f'{default}%'); row.addWidget(value); layout.addLayout(row)
        slider = QSlider(Qt.Orientation.Horizontal); slider.setRange(0, maximum); slider.setValue(default)
        slider.valueChanged.connect(lambda v: value.setText(f'{v}%')); slider.valueChanged.connect(self.edited)
        layout.addWidget(slider); return slider

    def build_sticks(self):
        page = QWidget(); pl = QVBoxLayout(page); pl.setContentsMargins(0,0,0,0)
        row = QHBoxLayout(); self.stick_views = []; self.dz = []; self.inversions = []
        for title in ('Левый стик', 'Правый стик'):
            box, bl = card(); bl.setSpacing(8); bl.setContentsMargins(18,16,18,16); bl.addWidget(label(title, 'section'))
            view = StickView(title); self.stick_views.append(view); bl.addWidget(view,1)
            self.dz.append(self.slider_row(bl, 'Мёртвая зона', 40, 5))
            inv_row = QHBoxLayout()
            for axis in ('X', 'Y'):
                cb = QCheckBox('Инверсия ' + axis); cb.toggled.connect(self.edited); inv_row.addWidget(cb); self.inversions.append(cb)
            bl.addLayout(inv_row)
            row.addWidget(box)
        pl.addLayout(row,1)
        box, bl = card(); self.swap = QCheckBox('Поменять левый и правый стики местами'); self.swap.toggled.connect(self.edited); bl.addWidget(self.swap)
        self.threshold = self.slider_row(bl, 'Порог цифрового нажатия L2 / R2', 100, 13)
        note = label('Мёртвая зона задаётся отдельно по каждой оси. Аналоговые курки передаются независимо от порога кнопок.', 'subtitle'); note.setWordWrap(True); bl.addWidget(note)
        pl.addWidget(box); self.pages.addWidget(page)

    def build_profiles(self):
        box, bl = card(); bl.addWidget(label('Твои профили', 'section'))
        text = label('Сохрани разные раскладки для игр. Загрузка профиля заполняет редактор;\nкнопка «Сохранить в ESP32» записывает его в плату.', 'subtitle'); text.setWordWrap(True); bl.addWidget(text)
        self.profile_list = QListWidget(); bl.addWidget(self.profile_list,1)
        self.profile_name = QLineEdit(); self.profile_name.setPlaceholderText('Название профиля, например «Гонки»'); bl.addWidget(self.profile_name)
        row = QHBoxLayout()
        for title, callback in (('Сохранить профиль', self.save_profile), ('Загрузить', self.load_profile), ('Импорт JSON', self.import_profile), ('Экспорт JSON', self.export_profile)):
            btn = QPushButton(title); btn.clicked.connect(callback); row.addWidget(btn)
        bl.addLayout(row)
        reset = QPushButton('Заводские настройки в редакторе'); reset.clicked.connect(lambda: self.load_config(Config())); bl.addWidget(reset)
        self.pages.addWidget(box); self.refresh_profiles()

    def current_config(self):
        return Config(self.dz[0].value(), self.dz[1].value(),
                      sum((1 << i) for i,c in enumerate(self.inversions) if c.isChecked()),
                      self.swap.isChecked(), self.threshold.value(), [c.currentData() for c in self.mapping])

    def load_config(self, config):
        self.loading = True
        self.dz[0].setValue(config.left_deadzone); self.dz[1].setValue(config.right_deadzone)
        for i, cb in enumerate(self.inversions): cb.setChecked(bool(config.invert & (1 << i)))
        self.swap.setChecked(config.swap_sticks); self.threshold.setValue(config.threshold)
        for combo, value in zip(self.mapping, config.mapping): combo.setCurrentIndex(combo.findData(value))
        self.loading = False; self.edited()

    def edited(self, *args):
        if self.loading: return
        for view, slider in zip(self.stick_views, self.dz): view.deadzone = slider.value(); view.update()
        dirty = self.current_config() != self.applied
        self.dirty_label.setText('Есть неприменённые изменения' if dirty else 'Редактор совпадает с настройками ESP32' if self.control else 'Профиль в редакторе · ESP32 ещё не настроена')
        self.apply_btn.setEnabled(self.control and not self.busy)
        self.save_btn.setEnabled(self.control and not self.busy)

    def on_device_config(self, config):
        had_edits = self.current_config() != self.applied
        self.applied = config
        if not had_edits: self.load_config(config)
        self.edited()

    def send_config(self, operation):
        if not self.control or self.busy: return
        self.busy = True; self.edited(); self.notice.setText('Отправляю настройки в ESP32…')
        self.worker.submit(self.current_config(), operation)

    def on_completed(self, message, config):
        self.busy = False; self.applied = config; self.load_config(config)
        self.notice.setText(message + '. ' + ('Они действуют и после отключения питания.' if 'Сохранено' in message else 'Для постоянного хранения нажми «Сохранить в ESP32».'))
        self.log_event(message)

    def on_error(self, message):
        self.busy = False; self.edited(); self.notice.setText(message)
        self.log_event(message)

    def log_event(self, message):
        self.event_log.appendPlainText(time.strftime('%H:%M:%S') + '  ' + message)

    def on_state(self, sample):
        previous_usb = self.sample.get('usb'); previous_control = self.control
        previous_bt = self.sample.get('bluetooth')
        self.sample = sample; self.control = sample.get('control', False)
        usb = sample.get('usb', False)
        if usb != previous_usb:
            self.log_event('USB-адаптер подключён' if usb else 'USB-адаптер не найден')
        if self.control and sample.get('bluetooth') != previous_bt:
            self.log_event('Bluetooth: геймпад подключён' if sample.get('bluetooth') else 'Bluetooth: ожидание геймпада')
        self.metrics[0].setText('Подключён' if usb else 'Не найден')
        self.metrics[0].setStyleSheet('color: #00723c' if usb else 'color: #555555')
        if self.control:
            bt = sample.get('bluetooth', False)
            self.metrics[1].setText('Подключён' if bt else 'Поиск геймпада')
            self.metrics[1].setStyleSheet('color: #00723c' if bt else 'color: #986000')
            self.metrics[2].setText(f'{sample.get("reports",0):,}'.replace(',', ' ') + ' отчётов')
            self.side_status.setText('Прошивка v' + str(sample.get('firmware', '?')) + ' · USB готов')
            if previous_control != self.control:
                self.notice.setText('USB и Bluetooth подключены. Ввод и настройки доступны.' if sample.get('received') else 'Настройки доступны. Нажми любую кнопку на геймпаде для первого отчёта.')
            if not bt: self.live_text.setText('Включи геймпад. Bluetooth на телефоне должен быть отключён.')
            elif not sample.get('received'): self.live_text.setText('Bluetooth подключён. Нажми кнопку на геймпаде для первого отчёта.')
        else:
            self.metrics[1].setText('Нет телеметрии'); self.metrics[1].setStyleSheet('color: #555555')
            self.side_status.setText('USB готов · нет телеметрии' if usb else 'Ожидание USB')
            if usb != previous_usb or previous_control:
                self.notice.setText('Игровой USB-ввод доступен. Канал настроек восстанавливается в фоне.' if usb else 'ESP32 не найдена. Подключи кабель к разъёму USB на плате.')
        xinput=sample.get('xinput','waiting')
        previous_xinput=getattr(self,'last_xinput',None)
        self.last_xinput=xinput
        xbox_text={'active':'Xbox 360 подключён','off':'Выключен','waiting':'Ожидание USB','driver_error':'Нет драйвера / ошибка'}.get(xinput,'Ожидание')
        self.xinput_status.setText(xbox_text)
        self.tray.setToolTip('ACTIVE Control — '+xbox_text)
        if xinput!=previous_xinput:
            self.log_event('XInput: '+xbox_text)
            if xinput=='driver_error':
                self.notice.setText('Xbox 360 недоступен: нужен установленный ViGEmBus. Игровой HID-ввод продолжает работать.')
        source = sample if self.control else sample.get('output') or {}
        if hasattr(self,'properties'):
            axes = source.get('axes',[0]*4); triggers = source.get('triggers',[0,0])
            values = {'Прошивка':str(sample.get('firmware','—')),
                      'Отчёты':str(sample.get('reports','—')),
                      'Кнопки':f'0x{source.get("buttons",0):08X}',
                      'LX / LY':f'{axes[0]:+.3f} / {axes[1]:+.3f}',
                      'RX / RY':f'{axes[2]:+.3f} / {axes[3]:+.3f}',
                      'L2 / R2':f'{triggers[0]:.2f} / {triggers[1]:.2f}',
                      'Крестовина':str(source.get('dpad',0)),
                      'Память':'Доступна' if sample.get('storage') else '—'}
            for key,value in values.items(): self.properties[key].setText(1,value)
        signature = (tuple(source.get('axes',[])), tuple(source.get('triggers',[])), source.get('buttons',0), source.get('dpad',0))
        if self.last_input_signature is not None and signature != self.last_input_signature:
            self.events += 1; self.last_activity = time.monotonic()
        self.last_input_signature = signature
        if not self.control: self.metrics[2].setText('Есть ввод' if time.monotonic()-self.last_activity < 3 else 'Ожидание ввода')
        if self.control and sample.get('received'):
            self.live_text.setText(f'Bluetooth → ESP32 → USB   ·   изменений в приложении: {self.events}')
        for i, indicator in enumerate(self.button_indicators):
            pressed = bool(source.get('buttons', 0) & (1 << i))
            if indicator.property('active')!=pressed:
                indicator.setProperty('active',pressed)
                indicator.setText('  ●  ' if pressed else '  —  ')
                indicator.setStyleSheet('color: #0078d4; font-weight: bold;' if pressed else 'color: #777777;')
        self.refresh_views()
        if previous_control!=self.control: self.edited()

    def refresh_views(self, *args):
        if not hasattr(self, 'controller'): return
        sample = self.sample
        chosen = (sample.get('output') or {}) if self.source.currentIndex() == 1 or not self.control else sample
        visual={key:chosen.get(key,default) for key,default in (('axes',[0]*4),('triggers',[0,0]),('buttons',0),('dpad',0))}
        if self.controller.sample!=visual:
            self.controller.sample=visual; self.controller.update()
        for i, indicator in enumerate(self.live_indicators):
            pressed = bool(chosen.get('buttons',0) & (1 << i))
            if indicator.property('pressed') != pressed:
                indicator.setProperty('pressed',pressed)
                indicator.style().unpolish(indicator); indicator.style().polish(indicator)
        axes = sample.get('axes', [0]*4) if self.control else (sample.get('output') or {}).get('axes', [0]*4)
        for i, view in enumerate(self.stick_views):
            values=axes[i*2:i*2+2]
            if view.values!=values: view.values=values; view.update()

    def reset_mapping(self):
        for i, combo in enumerate(self.mapping): combo.setCurrentIndex(i+1)

    def read_profiles(self):
        try:
            data = json.loads(self.profile_path.read_text(encoding='utf-8'))
            if not isinstance(data, dict): return {}
            valid = {}
            for name, raw in data.items():
                try:
                    config = Config(**raw); config.validate(); valid[name] = asdict(config)
                except (TypeError, ValueError): pass
            return valid
        except (OSError, ValueError): return {}

    def refresh_profiles(self):
        self.profile_list.clear(); self.profile_list.addItems(sorted(self.profiles))

    def save_profile(self):
        name = self.profile_name.text().strip()
        if not name:
            self.notice.setText('Введи название профиля.'); return
        if name in self.profiles and QMessageBox.question(self, 'Заменить профиль?', f'Перезаписать профиль «{name}»?') != QMessageBox.StandardButton.Yes: return
        proposed = dict(self.profiles); proposed[name] = asdict(self.current_config())
        try:
            tmp = self.profile_path.with_suffix('.tmp')
            tmp.write_text(json.dumps(proposed, ensure_ascii=False, indent=2), encoding='utf-8'); tmp.replace(self.profile_path)
        except OSError as exc:
            self.on_error('Не удалось сохранить профиль: ' + str(exc)); return
        self.profiles = proposed; self.refresh_profiles(); self.notice.setText(f'Профиль «{name}» сохранён на компьютере.')

    def load_profile(self):
        item = self.profile_list.currentItem()
        if not item: self.notice.setText('Выбери профиль из списка.'); return
        self.load_config(Config(**self.profiles[item.text()])); self.profile_name.setText(item.text())
        self.notice.setText('Профиль загружен в редактор. Примени его или сохрани в ESP32.')

    def export_profile(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Экспорт профиля', 'active-profile.json', 'JSON (*.json)')
        if not path: return
        try: Path(path).write_text(json.dumps({'format':'active-control/1', 'config':asdict(self.current_config())}, ensure_ascii=False, indent=2), encoding='utf-8')
        except OSError as exc: self.on_error(str(exc))

    def import_profile(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Импорт профиля', '', 'JSON (*.json)')
        if not path: return
        try:
            if Path(path).stat().st_size > 65536: raise ValueError('Файл профиля слишком большой.')
            raw = json.loads(Path(path).read_text(encoding='utf-8'))
            if raw.get('format') != 'active-control/1': raise ValueError('Неизвестный формат профиля.')
            config = Config(**raw['config']); config.to_bytes(); self.load_config(config)
            self.notice.setText('Профиль импортирован в редактор. Для записи в плату нажми «Сохранить в ESP32».')
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc: self.on_error('Не удалось импортировать профиль: ' + str(exc))

    def closeEvent(self, event):
        if not self.exit_requested and self.tray.isVisible():
            self.hide(); event.ignore(); return
        if not self.exit_confirmed:
            if self.current_config()!=self.applied and QMessageBox.question(self,'Закрыть приложение?','В редакторе есть неприменённые изменения. Завершить работу и отключить Xbox?')!=QMessageBox.StandardButton.Yes:
                self.exit_requested=False; event.ignore(); return
            self.exit_confirmed=True
        if self.worker.isRunning():
            if not self.closing:
                self.closing=True; self.worker.finished.connect(self.close); self.worker.requestInterruption()
                self.notice.setText('Завершаю игровой ввод и отключаю виртуальный Xbox…')
            event.ignore(); return
        try:
            (ROOT/'window-state.json').write_text(json.dumps({
                'geometry':base64.b64encode(bytes(self.saveGeometry())).decode('ascii'),
                'layout':base64.b64encode(bytes(self.saveState())).decode('ascii')
            }),encoding='utf-8')
        except OSError: pass
        self.tray.hide()
        event.accept()


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--screenshot'); parser.add_argument('--page', type=int, default=0)
    parser.add_argument('--self-test',metavar='REPORT_JSON')
    args = parser.parse_args()
    if args.self_test:
        from packaging_checks import run_checks
        sys.exit(run_checks(args.self_test))
    app = QApplication(sys.argv); app.setStyle('windowsvista'); app.setStyleSheet(STYLE)
    app.setWindowIcon(QIcon(str(resource_path('assets/app.ico'))))
    server = None
    if not args.screenshot:
        socket = QLocalSocket()
        socket.connectToServer('SmartbuyActiveControlApp')
        if socket.waitForConnected(250):
            socket.write(b'activate'); socket.flush(); socket.waitForBytesWritten(250)
            return
        server = QLocalServer()
        if not server.listen('SmartbuyActiveControlApp'):
            QMessageBox.information(None, 'ACTIVE Control', 'Приложение уже запущено.')
            return
    window = Window(start_worker=not bool(args.screenshot)); window.show(); window.navigate(args.page)
    if server:
        def activate():
            connection = server.nextPendingConnection()
            if connection:
                connection.close(); connection.deleteLater()
            window.showNormal(); window.raise_(); window.activateWindow()
        server.newConnection.connect(activate)
    if args.screenshot:
        def capture():
            window.grab().save(args.screenshot)
            window.worker.requestInterruption(); window.worker.wait(3000)
            app.quit()
        QTimer.singleShot(2500, capture)
    sys.exit(app.exec())


if __name__ == '__main__':
    mp.freeze_support()
    main()
