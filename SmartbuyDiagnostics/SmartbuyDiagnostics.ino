/*
  Smartbuy ACTIVE / SBG-300BT-KR -> ESP32-S3 -> USB HID Gamepad.
  Чистый Arduino, без вызовов ESP-IDF.

  Arduino IDE:
  1. В Additional Boards Manager URLs добавить ОБА адреса:
     https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
     https://raw.githubusercontent.com/ricardoquesada/esp32-arduino-lib-builder/master/bluepad32_files/package_esp32_bluepad32_index.json
  2. Установить пакеты esp32 и esp32_bluepad32.
  3. Board: ESP32S3 Dev Module из пакета ESP32 + Bluepad32 Arduino.
  4. USB Mode: USB-OTG (TinyUSB).
     USB CDC On Boot: Disabled. Core Debug Level: None.
     Для вашей N16R8: Flash Size: 16MB (128Mb), PSRAM: OPI PSRAM.
     Если это WROOM-1-N16R8: Flash Mode: QIO (не OPI Flash).
     Partition Scheme: 16M Flash (3MB APP/9.9MB FATFS).
  5. Установить Joystick_ESP32S2 автора schnoog через Library Manager.
  6. Для USB-джойстика нужен родной USB ESP32-S3, НЕ USB-UART
     разъём на CP210x/CH340. На вашей плате: USB = джойстик, COM = прошивка.
     Используйте USB-кабель с передачей данных.

  ESP32-S3 поддерживает только BLE, Bluetooth Classic здесь не работает.
  В пакете Bluepad32 BLE HID host уже включён; отдельного Arduino-вызова
  "подключиться к UUID 0x1812" нет. enableNewBluetoothConnections()
  разрешает поиск/подключение, но не добавляет поддержку неизвестных HID.
  Этот скетч принимает первое HID-устройство, без фильтра по имени;
  игровые отчёты обрабатываются после определения типа устройства.

  Если Smartbuy не распознаётся или кнопки неверные: отдельная прошивка
  на NimBLE-Arduino вместо Bluepad32: найти HID service 0x1812, прочитать
  Report Map 0x2A4B, Report Reference 0x2908, подписаться на INPUT Report
  0x2A4D; при необходимости выполнить pairing/bonding. Формат кнопок и осей
  определяется Report Map, угадывать байты по одному имени нельзя.
  Не запускайте NimBLE и Bluetooth-стек Bluepad32 одновременно.

  На ПК это обычный USB HID gamepad (DirectInput), не Xbox/XInput.
  Для XInput нужен отдельный подход: трансляция на ПК или другая USB-
  прошивка/стек. Смена USB VID/PID сама по себе XInput не добавляет.

  Serial намеренно не используется: автор Joystick_ESP32S2 предупреждает
  о возможных проблемах USB при совместной работе с Serial.
*/

#include <Arduino.h>
#include <USB.h>
#include <Joystick_ESP32S2.h>

// Bluepad32 4.1.0 (BTstack) и TinyUSB объявляют одинаковые HID-типы.
// Сначала загрузить USB, затем локально переименовать символы BTstack.
// Бинарный интерфейс библиотек не меняется; их файлы править не нужно.
#define hid_report_type_t bp32_hid_report_type_t
#define HID_REPORT_TYPE_INPUT BP32_HID_REPORT_TYPE_INPUT
#define HID_REPORT_TYPE_OUTPUT BP32_HID_REPORT_TYPE_OUTPUT
#define HID_REPORT_TYPE_FEATURE BP32_HID_REPORT_TYPE_FEATURE
#include <Bluepad32.h>
#undef hid_report_type_t
#undef HID_REPORT_TYPE_INPUT
#undef HID_REPORT_TYPE_OUTPUT
#undef HID_REPORT_TYPE_FEATURE

// В обычной сборке UART-диагностика отключена. Отдельный скетч
// SmartbuyDiagnostics включает её для поиска проблем Bluetooth через COM.
#ifndef BRIDGE_UART_DIAGNOSTICS
#define BRIDGE_UART_DIAGNOSTICS 1
#endif
uint32_t receivedReports = 0;

#if !defined(CONFIG_IDF_TARGET_ESP32S3)
#error "Select ESP32S3 Dev Module from ESP32 + Bluepad32 Arduino"
#endif

struct GamepadState {
  bool connected = false;
  bool receivedReport = false;
  uint16_t buttons = 0;
  uint8_t misc = 0;
  uint8_t dpad = 0;
  int32_t lx = 0, ly = 0, rx = 0, ry = 0;
  int32_t brake = 0, throttle = 0;
};

GamepadState gamepadState;
ControllerPtr activeController = nullptr;

Joystick_ Joystick(
  JOYSTICK_DEFAULT_REPORT_ID, JOYSTICK_TYPE_GAMEPAD,
  32, 1,                        // 32 кнопки, одна крестовина POV
  true, true, false,            // X, Y; без Z
  true, true, false,            // Rx, Ry; без Rz
  false, true, false, true, false // только Throttle и Brake
);

// BP32 вызывает callbacks подключения/отключения внутри BP32.update().
// В Arduino API нет отдельного зарегистрированного callback на каждый
// input report. Наш обработчик onGamepadData() вызывается из loop()
// после update()/hasData(). Все обращения к gamepadState идут из одного
// Arduino-потока: volatile и межъядерные блокировки здесь не нужны.
void onConnectedController(ControllerPtr ctl) {
#if BRIDGE_UART_DIAGNOSTICS
  const auto props = ctl->getProperties();
  Serial.printf("BT_CONNECTED model=%s gamepad=%d VID=%04x PID=%04x\n",
                ctl->getModelName().c_str(), ctl->isGamepad(),
                props.vendor_id, props.product_id);
#endif
  // У generic BLE HID тип может определиться лишь после первого отчёта.
  // Нельзя отбрасывать устройство по isGamepad() в callback подключения.
  if (activeController == nullptr) {
    activeController = ctl;
    gamepadState = GamepadState{};
    gamepadState.connected = true;
  }
}

void onDisconnectedController(ControllerPtr ctl) {
#if BRIDGE_UART_DIAGNOSTICS
  Serial.println("BT_DISCONNECTED");
#endif
  if (ctl == activeController) {
    activeController = nullptr;
    gamepadState = GamepadState{}; // отпустить кнопки, центрировать стики
  }
}

void onGamepadData(ControllerPtr ctl) {
  ++receivedReports;
  gamepadState.connected = true;
  gamepadState.receivedReport = true;
  gamepadState.buttons = ctl->buttons();
  gamepadState.misc = ctl->miscButtons();
  gamepadState.dpad = ctl->dpad();
  gamepadState.lx = ctl->axisX();
  gamepadState.ly = ctl->axisY();
  gamepadState.rx = ctl->axisRX();
  gamepadState.ry = ctl->axisRY();
  gamepadState.brake = ctl->brake();
  gamepadState.throttle = ctl->throttle();
}

int32_t stickValue(int32_t value) {
  // Bluepad32: примерно -511..512. Симметричный выход с точным центром.
  // Небольшая мёртвая зона; после неё масштаб восстанавливает полный ход.
  const int32_t deadzone = 24;
  value = constrain(value, -512L, 512L);
  if (value > deadzone)
    return (value - deadzone) * 32767L / (512 - deadzone);
  if (value < -deadzone)
    return (value + deadzone) * 32767L / (512 - deadzone);
  return 0;
}

int16_t hatAngle(uint8_t dpad) {
  // Биты Bluepad32: up=1, down=2, right=4, left=8.
  int x = ((dpad & 4) ? 1 : 0) - ((dpad & 8) ? 1 : 0);
  int y = ((dpad & 2) ? 1 : 0) - ((dpad & 1) ? 1 : 0);
  if (y < 0) return x < 0 ? 315 : (x > 0 ? 45 : 0);
  if (y > 0) return x < 0 ? 225 : (x > 0 ? 135 : 180);
  return x < 0 ? 270 : (x > 0 ? 90 : -1);
}

void sendUsbState() {
  GamepadState state = gamepadState;
  if (!state.connected || !state.receivedReport) state = GamepadState{};

  // USB кнопки 1..16 = биты buttons(), 17..24 = биты miscButtons().
  // 25/26 = цифровое представление L2/R2 (параллельно аналоговым осям).
  // В setButton() нумерация начинается с 0; в Windows обычно с 1.
  uint32_t mask = uint32_t(state.buttons) | (uint32_t(state.misc) << 16);
  if (state.brake > 128) mask |= (1UL << 24);
  if (state.throttle > 128) mask |= (1UL << 25);
  for (uint8_t i = 0; i < 32; ++i)
    Joystick.setButton(i, (mask >> i) & 1U);

  Joystick.setXAxis(stickValue(state.lx));
  Joystick.setYAxis(stickValue(state.ly));
  Joystick.setRxAxis(stickValue(state.rx));
  Joystick.setRyAxis(stickValue(state.ry));
  Joystick.setBrake(constrain(state.brake, 0L, 1023L));
  Joystick.setThrottle(constrain(state.throttle, 0L, 1023L));
  Joystick.setHatSwitch(0, hatAngle(state.dpad));
  Joystick.sendState(); // один цельный USB-репорт
}

void setup() {
#if BRIDGE_UART_DIAGNOSTICS
  Serial.begin(115200); // CDC отключён: вывод только через разъём COM
  Serial.println("SMARTBUY_DIAGNOSTICS: UART=COM, baud=115200");
#endif
  Joystick.setXAxisRange(-32767, 32767);
  Joystick.setYAxisRange(-32767, 32767);
  Joystick.setRxAxisRange(-32767, 32767);
  Joystick.setRyAxisRange(-32767, 32767);
  Joystick.setBrakeRange(0, 1023);
  Joystick.setThrottleRange(0, 1023);
  Joystick.begin(false); // отключить автоотправку каждого setButton()
  USB.begin();           // запустить родной USB ESP32-S3

  BP32.setup(&onConnectedController, &onDisconnectedController);
  BP32.enableVirtualDevice(false);
  BP32.enableNewBluetoothConnections(true);
  // При проблемах pairing можно ОДИН РАЗ раскомментировать строку ниже,
  // загрузить, затем снова закомментировать и перезагрузить прошивку.
  // BP32.forgetBluetoothKeys();
}

void loop() {
  const bool updated = BP32.update();
  if (updated && activeController != nullptr &&
      activeController->isConnected() && activeController->hasData() &&
      activeController->isGamepad()) {
    onGamepadData(activeController);
  }

  static uint32_t lastUsbMs = 0;
  const uint32_t now = millis();
  if (now - lastUsbMs >= 5) {
    lastUsbMs = now;
    sendUsbState();
  }
  delay(1); // дать Bluetooth/USB задачам процессорное время
#if BRIDGE_UART_DIAGNOSTICS
  static uint32_t lastDiagnosticMs = 0;
  if (now - lastDiagnosticMs >= 2000) {
    lastDiagnosticMs = now;
    Serial.printf("STATE connected=%d gamepad=%d report=%d count=%lu buttons=%04x "
                  "dpad=%02x LX=%ld LY=%ld RX=%ld RY=%ld\n",
                  gamepadState.connected,
                  activeController ? activeController->isGamepad() : false,
                  gamepadState.receivedReport,
                  (unsigned long)receivedReports, gamepadState.buttons,
                  gamepadState.dpad, (long)gamepadState.lx,
                  (long)gamepadState.ly, (long)gamepadState.rx,
                  (long)gamepadState.ry);
  }
#endif
}
