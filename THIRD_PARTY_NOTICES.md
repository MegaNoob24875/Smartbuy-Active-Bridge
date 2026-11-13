# Third-party components

The project's own source code is MIT-licensed. Dependencies retain their
respective licenses. No system driver is installed automatically by the EXE.

| Component | Version used | License / source |
|---|---|---|
| Python | 3.13 | [PSF license](https://docs.python.org/3/license.html) |
| Qt / PySide6 / Shiboken6 | 6.12.0 | LGPL-3.0-only or GPL; this build uses the LGPL option. [Qt source](https://download.qt.io/archive/qt/6.12/), [PySide source](https://code.qt.io/cgit/pyside/pyside-setup.git/), [LGPL v3](https://www.gnu.org/licenses/lgpl-3.0.html) |
| pyserial | 3.5 | BSD-3-Clause; [source](https://github.com/pyserial/pyserial) |
| vgamepad / ViGEmClient | 0.2.0 | MIT; [source](https://github.com/yannbouteiller/vgamepad) |
| ViGEmBus | 1.22.0 | Separate third-party driver; [official release and license](https://github.com/nefarius/ViGEmBus/releases/tag/v1.22.0) |
| PyInstaller bootloader | 6.22.3 | GPL with bootloader exception; [license](https://pyinstaller.org/en/stable/license.html) |
| Bluepad32 | 4.1.0 Arduino package | Apache-2.0 project; [source and dependency licensing](https://github.com/ricardoquesada/bluepad32) |
| Arduino-ESP32 | Core supplied by Bluepad32 package | [Source and licenses](https://github.com/espressif/arduino-esp32) |

Qt is loaded from dynamic libraries. This repository supplies the application
source and the complete Windows build spec. Users can replace the compatible
Qt/PySide6 dependencies and rebuild the executable; see [docs/BUILD.md](docs/BUILD.md).
Reverse engineering necessary to debug modifications to LGPL libraries is
permitted under their license. Qt source and notices are available at the links
above; the release archive also contains the LGPL/GPL license texts and the
vgamepad license. The app does not use Qt WebEngine, Qt PDF or QML.

The firmware also uses Bluepad32's bundled BTstack and Espressif SDK components.
Their upstream licenses apply independently; consult the Bluepad32 distribution
before using the firmware commercially. This project does not replace or
relicense those upstream components.
