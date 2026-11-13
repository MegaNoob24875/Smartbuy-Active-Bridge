# Сборка Windows EXE

Для обычного запуска скачайте EXE из Releases. Дальнейшие шаги нужны разработчикам.

## Требования

- Windows x64 и Python 3.13 x64.
- Зависимости из `active_control/requirements.txt`.
- PyInstaller 6.22.3. Системный драйвер ViGEmBus нужен для игрового XInput,
  но не для сборки и встроенного теста EXE.

```powershell
python -m venv .venv
$env:VGAMEPAD_SKIP_VIGEMBUS_INSTALL = 'true'
.\.venv\Scripts\python.exe -m pip install -r active_control/requirements.txt
.\.venv\Scripts\python.exe -m pip install pyinstaller==6.22.3
.\build-windows.ps1
```

Результат: `dist/ACTIVE-Control.exe`. Python и Qt включены внутрь.
Скрипт создаёт иконку, собирает EXE и выполняет офлайн smoke-тест.
Системный драйвер, исходники, среда `.venv`, личные профили и журналы не включаются.

## Почему EXE меньше папки проекта

Большую часть рабочего проекта занимает полная среда Python с Qt, включая
неиспользуемые WebEngine, QML, Multimedia и инструменты разработки. PyInstaller
собирает только используемые модули. EXE сжат стандартной упаковкой PyInstaller;
UPX и внешние упаковщики не используются. Сам EXE при запуске распаковывает
библиотеки во временную папку; размер на диске во время работы будет больше EXE.

Qt DLL загружаются динамически. Чтобы использовать другую совместимую сборку
Qt/PySide6, замените соответствующие пакеты в `.venv` и выполните открытую сборку
повторно; исходники приложения и spec доступны в этом репозитории.

## Данные и проверка

EXE хранит настройки в `%LOCALAPPDATA%\SmartbuyActiveControl`; исходный Python-
вариант — рядом с `active_control/app.py`, как в режиме разработки.
Обновление EXE не удаляет данные. Профиль в NVS платы сохраняется независимо.

```powershell
.\dist\ACTIVE-Control.exe --self-test smoke-test.json
```

Smoke-тест проверяет Qt, иконку, отдельный процесс, pyserial и загрузку
ViGEmClient.dll. Он не открывает COM-порт и не создаёт второй Xbox.
Для вывода ошибок упаковки можно собрать консольный вариант:

```powershell
$env:ACTIVE_DEBUG_CONSOLE = '1'
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --distpath dist/debug --workpath build/windows packaging/active-control.spec
```

Удалите переменную `ACTIVE_DEBUG_CONSOLE` перед обычной сборкой.
Публикуемый EXE не имеет цифровой подписи издателя.

Для GitHub Actions есть шаблон `packaging/windows-workflow.yml`.
Скопируйте его в `.github/workflows/windows.yml`, если нужна автоматическая
сборка. Для добавления workflow через OAuth-токен GitHub требуется scope `workflow`.
