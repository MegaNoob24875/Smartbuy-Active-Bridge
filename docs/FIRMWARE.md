# Прошивка ESP32-S3

Готовый BIN рассчитан на **ESP32-S3 N16R8**: 16 МБ Flash и 8 МБ OPI PSRAM.
Для другой платы сначала проверьте её параметры и соберите подходящий скетч.
Обычный ESP32, S2 и C3 не являются заменой для этого BIN.

## Готовый BIN — без Arduino IDE

1. Скачайте `SmartbuyBridge-v5-ESP32S3-N16R8.bin` из
   [последнего релиза](https://github.com/MegaNoob24875/Smartbuy-Active-Bridge/releases/latest).
2. Подключите плату к ПК через разъём **COM**, кабелем с передачей данных.
3. Откройте официальный [ESP Tool в браузере](https://espressif.github.io/esptool-js/)
   в Chrome или Edge. Firefox не поддерживает необходимый Web Serial.
4. Нажмите Connect/Подключить и выберите USB-UART порт платы.
5. Добавьте скачанный файл с **Flash Address `0x0`**. Это единый образ:
   загрузчик, разделы и приложение уже объединены.
6. Оставьте Flash Mode/Frequency/Size в режиме Keep, если он предлагается.
   Для ручного выбора: DIO, 80 MHz, 16 MB. Начните прошивку и дождитесь завершения.
7. Переставьте кабель в **USB**, запустите ACTIVE Control и включите геймпад.

Если подключение к загрузчику не удалось: удерживайте BOOT, нажмите и отпустите
RESET, затем отпустите BOOT и повторите подключение. COM-порт может измениться.
**Единый BIN предназначен для первой установки:** он перезаписывает также
область NVS, поэтому Bluetooth-пары и профиль платы будут сброшены.
Перед переходом с другого проекта сохраните важные данные.

Для обновления уже установленной v5 с той же разметкой скачайте
`SmartbuyBridge-v5-app-only.bin` и прошивайте **только его по адресу `0x10000`**,
без `Erase all`. Этот вариант сохраняет NVS и не заменяет загрузчик/разделы.
Не используйте app-only для пустой платы или другой таблицы разделов.

Для esptool 4.x:

```powershell
python -m esptool --chip esp32s3 --port COM3 --baud 460800 write_flash 0x0 SmartbuyBridge-v5-ESP32S3-N16R8.bin
```

Замените COM3 своим портом. В релизе есть SHA256SUMS.txt для проверки файлов.

## Исходники для Arduino IDE

Скачайте репозиторий целиком и откройте `SmartbuyBridge/SmartbuyBridge.ino`.
Соседние `.h` файлы тоже нужны — не переносите один `.ino` отдельно.
Основной вариант использует **Bluepad32 4.1.0** и встроенный USB CDC;
Joystick_ESP32S2 нужен только для сохранённого альтернативного HID-варианта.

Добавьте оба URL в Additional Boards Manager URLs:

```text
https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
https://raw.githubusercontent.com/ricardoquesada/esp32-arduino-lib-builder/master/bluepad32_files/package_esp32_bluepad32_index.json
```

Установите пакет **ESP32 + Bluepad32 Arduino**, выберите его ESP32S3 Dev Module.

| Параметр | Значение |
|---|---|
| Board | ESP32S3 Dev Module, пакет Bluepad32 |
| USB Mode | USB-OTG (TinyUSB) |
| USB CDC On Boot | Disabled — CDC создаётся явно в скетче |
| Flash Size | 16MB (128Mb) |
| PSRAM | OPI PSRAM |
| Flash Mode | QIO для WROOM-1-N16R8; не OPI Flash |
| Partition Scheme | 16M Flash (3MB APP/9.9MB FATFS) |
| Core Debug Level | None |

Для Arduino CLI используемый FQBN:

```text
esp32-bluepad32:esp32:esp32s3:USBMode=default,CDCOnBoot=default,FlashSize=16M,PSRAM=opi,PartitionScheme=app3M_fat9M_16MB
```

Прошивка — Arduino-скетч; отдельно собирать ESP-IDF проект не нужно.
Плата принимает первый распознанный геймпад, без фильтра по имени Smartbuy.
Если Bluepad32 не понимает HID-модель, одного UUID 1812 недостаточно:
потребуется поддержка её HID Report Map в парсере либо отдельный NimBLE-вариант.

В рабочей v5 включены `ACTIVE_CDC_TRANSPORT=1` и `ACTIVE_EXCLUSIVE_XINPUT=1`.
Она не создаёт физический DirectInput-геймпад. Сохранённые альтернативные
HID-режимы v3/v4 не являются рекомендуемыми стабильными сборками.
