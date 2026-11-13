"""Classic Windows workspace: menus, toolbars, dock panes and tabbed views."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QTabWidget,
    QDockWidget, QTreeWidget, QTreeWidgetItem, QPlainTextEdit, QToolBar,
    QStyle, QSizePolicy, QMessageBox, QCheckBox,
)

STYLE = '''
QWidget { font-family: "Segoe UI"; font-size: 12px; color: #202020; }
QMainWindow, #root { background: #f0f0f0; }
QFrame#card { background: #ffffff; border: 1px solid #b8b8b8; }
QLabel#title, QLabel#section { font-size: 13px; font-weight: 600; }
QLabel#subtitle { color: #555555; }
QLabel#eyebrow { color: #333333; font-weight: 600; }
QLabel#metric { font-size: 12px; }
QLabel#notice { background: #fffce8; border: 1px solid #d0cba4; padding: 5px; }
QPushButton { padding: 3px 10px; min-height: 20px; }
QComboBox { min-height: 22px; }
QLineEdit { min-height: 22px; }
QTableWidget, QTreeWidget, QListWidget, QPlainTextEdit { background: white; alternate-background-color: #f3f5f7; }
QHeaderView::section { padding: 4px; }
QTableWidget::item { padding: 2px; }
QToolBar { spacing: 5px; padding: 3px; border-bottom: 1px solid #b5b5b5; }
QDockWidget::title { background: #e4e4e4; border: 1px solid #b8b8b8; padding: 4px; }
QTabWidget::pane { border: 1px solid #a0a0a0; background: #f0f0f0; }
QTabBar::tab { padding: 5px 14px; }
QLabel[pressed="true"] { background: #0078d4; color: white; border: 1px solid #005a9e; }
QLabel[pressed="false"] { background: #f4f4f4; color: #333333; border: 1px solid #b0b0b0; }
QToolTip { color: #202020; background: #ffffe1; border: 1px solid #777; }
'''


class Pages(QTabWidget):
    names = ('Состояние устройства', 'Кнопки / назначения', 'Оси и курки', 'Профили')
    def addWidget(self, widget):
        self.addTab(widget, self.names[self.count()])


def install(window):
    w = window
    w.resize(1320, 900); w.setMinimumSize(1130, 820)
    w.setDockOptions(w.DockOption.AllowNestedDocks | w.DockOption.AllowTabbedDocks)
    w.nav = []
    root = QWidget(); root.setObjectName('root'); w.setCentralWidget(root)
    main = QVBoxLayout(root); main.setContentsMargins(4,4,4,4); main.setSpacing(4)
    w.notice = QLabel('Подключите ESP32 к разъёму USB. Поиск выполняется автоматически.')
    w.notice.setObjectName('notice'); w.notice.setWordWrap(True); main.addWidget(w.notice)
    w.pages = Pages(); main.addWidget(w.pages,1)
    w.build_overview(); w.build_buttons(); w.build_sticks(); w.build_profiles()

    device_dock = QDockWidget('Устройства и представления', w); device_dock.setObjectName('deviceDock')
    tree = QTreeWidget(); tree.setHeaderHidden(True)
    device = QTreeWidgetItem(tree, ['Smartbuy ACTIVE'])
    device.setIcon(0, w.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))
    device.setExpanded(True)
    for index, text in enumerate(Pages.names):
        node = QTreeWidgetItem(device, [text]); node.setData(0, Qt.ItemDataRole.UserRole, index)
        node.setIcon(0, w.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
    info = QTreeWidgetItem(tree, ['ESP32-S3 N16R8']); info.setExpanded(True)
    QTreeWidgetItem(info, ['USB → Xbox 360 / XInput']); QTreeWidgetItem(info, ['SBG-300BT-KR'])
    tree.itemClicked.connect(lambda item, col: w.navigate(item.data(0,Qt.ItemDataRole.UserRole)) if item.data(0,Qt.ItemDataRole.UserRole) is not None else None)
    device_dock.setWidget(tree); w.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea,device_dock)

    properties_dock = QDockWidget('Свойства устройства', w); properties_dock.setObjectName('propertiesDock')
    props = QTreeWidget(); props.setHeaderLabels(['Параметр','Значение']); props.setRootIsDecorated(False)
    props.setAlternatingRowColors(True); props.setColumnWidth(0,110)
    w.metrics=[]
    for title, text in (('USB','Поиск'),('Bluetooth','Нет данных'),('Ввод','Ожидание')):
        item=QTreeWidgetItem(props,[title,'']); value=QLabel(text); value.setObjectName('metric'); props.setItemWidget(item,1,value); w.metrics.append(value)
    w.properties={}
    for name in ('Прошивка','Отчёты','Кнопки','LX / LY','RX / RY','L2 / R2','Крестовина','Память'):
        item=QTreeWidgetItem(props,[name,'—']); w.properties[name]=item
    properties_dock.setWidget(props); w.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea,properties_dock)

    log_dock = QDockWidget('Журнал событий',w); log_dock.setObjectName('logDock')
    w.event_log=QPlainTextEdit(); w.event_log.setReadOnly(True); w.event_log.setMaximumBlockCount(500)
    w.event_log.setFont(QFont('Consolas',9)); w.event_log.setMinimumHeight(60)
    w.event_log.appendPlainText('ACTIVE Control готов. Ожидание USB-адаптера…')
    log_dock.setWidget(w.event_log); w.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea,log_dock)
    w.resizeDocks([device_dock,properties_dock],[220,250],Qt.Orientation.Horizontal)
    w.resizeDocks([log_dock],[105],Qt.Orientation.Vertical)

    toolbar=QToolBar('Основная панель',w); toolbar.setObjectName('mainToolbar'); w.addToolBar(toolbar)
    refresh=QAction(w.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload),'Повторить поиск',w)
    refresh.triggered.connect(lambda: setattr(w.worker,'last_scan',0)); toolbar.addAction(refresh)
    toolbar.addSeparator()
    w.xinput_checkbox=QCheckBox('Xbox 360 (XInput)')
    w.xinput_checkbox.setChecked(w.xinput_enabled)
    w.xinput_checkbox.toggled.connect(w.toggle_xinput)
    toolbar.addWidget(w.xinput_checkbox)
    toolbar.addSeparator()
    w.apply_btn=QPushButton('Применить'); w.apply_btn.clicked.connect(lambda: w.send_config(1)); toolbar.addWidget(w.apply_btn)
    w.save_btn=QPushButton('Сохранить в ESP32'); w.save_btn.clicked.connect(lambda: w.send_config(2)); toolbar.addWidget(w.save_btn)
    toolbar.addSeparator()
    import_action=QAction(w.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton),'Импорт профиля…',w)
    import_action.triggered.connect(w.import_profile); toolbar.addAction(import_action)
    export_action=QAction(w.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton),'Экспорт профиля…',w)
    export_action.triggered.connect(w.export_profile); toolbar.addAction(export_action)
    toolbar.addSeparator(); toolbar.addWidget(QLabel('Устройство: Smartbuy ACTIVE / ESP32-S3'))

    file_menu=w.menuBar().addMenu('&Файл'); file_menu.addAction(import_action); file_menu.addAction(export_action)
    file_menu.addSeparator(); close= file_menu.addAction('Завершить работу и отключить Xbox'); close.triggered.connect(w.request_exit)
    device_menu=w.menuBar().addMenu('&Устройство'); device_menu.addAction(refresh)
    device_menu.addAction('Применить настройки', lambda: w.send_config(1))
    save_action=device_menu.addAction('Сохранить настройки в ESP32',lambda: w.send_config(2)); save_action.setShortcut('Ctrl+S')
    view_menu=w.menuBar().addMenu('&Вид')
    for dock in (device_dock,properties_dock,log_dock): view_menu.addAction(dock.toggleViewAction())
    view_menu.addAction(toolbar.toggleViewAction())
    help_menu=w.menuBar().addMenu('&Справка')
    help_menu.addAction('О программе',lambda: QMessageBox.information(w,'ACTIVE Control','Smartbuy ACTIVE / ESP32-S3\nВиртуальный Xbox 360 / XInput через ViGEmBus.\nДля игры оставляйте приложение запущенным, можно в трее.\nUSB Serial: ввод и настройки обслуживает отдельный процесс.'))
    w.dirty_label=QLabel('Настройки ещё не считаны'); w.statusBar().addWidget(w.dirty_label,1)
    w.side_status=QLabel('Поиск ESP32…'); w.statusBar().addPermanentWidget(w.side_status)
    xitem=QTreeWidgetItem(props,['XInput',''])
    w.xinput_status=QLabel('Ожидание'); props.setItemWidget(xitem,1,w.xinput_status)
    w.title=QLabel('Smartbuy ACTIVE')
