#pragma once
#include <Arduino.h>
#if ACTIVE_CDC_TRANSPORT
#include "BridgeSerialLink.h"
#else
#include <USBHID.h>
#endif

// Application-only input collection. The packet format is the same as the
// earlier HID joystick, but its top-level Usage Page is vendor-defined.
// Windows/Steam/games must NOT enumerate it as another game controller.
class BridgeGameInput
#if !ACTIVE_CDC_TRANSPORT
 : public USBHIDDevice
#endif
{
#if !ACTIVE_CDC_TRANSPORT
  USBHID hid;
#endif
  uint32_t buttons = 0;
  int32_t axes[4]{};
  int32_t axisMin[4] = {-32767,-32767,-32767,-32767};
  int32_t axisMax[4] = {32767,32767,32767,32767};
  int32_t pedals[2]{}; // throttle, brake
  int32_t pedalMin[2]{};
  int32_t pedalMax[2] = {1023,1023};
  uint8_t hat = 8;
  uint32_t lastCompletedMs = 0;
  uint32_t mountedSinceMs = 0;

  static uint16_t scaled(int32_t value,int32_t lo,int32_t hi) {
    if (hi <= lo) return 0;
    value=constrain(value,lo,hi);
    return uint16_t((int64_t(value)-lo)*65535/(int64_t(hi)-lo));
  }
  static void put16(uint8_t* data,uint16_t value) {
    data[0]=uint8_t(value); data[1]=uint8_t(value>>8);
  }
 public:
  static constexpr uint8_t descriptor[] = {
    0x06,0x00,0xff, // Vendor Usage Page FF00
    0x09,0x02,      // Usage 2: private game input transport
    0xa1,0x01,      // Application collection
    0x85,0x03,      // report ID 3
    0x15,0x00,0x26,0xff,0x00,
    0x75,0x08,0x95,0x11, // 17 data bytes (+ report ID = 18)
    0x09,0x03,0x81,0x02,0xc0
  };
#if !ACTIVE_CDC_TRANSPORT
  BridgeGameInput() { hid.addDevice(this,sizeof(descriptor)); }
  uint16_t _onGetDescriptor(uint8_t* buffer) override {
    memcpy(buffer,descriptor,sizeof(descriptor)); return sizeof(descriptor);
  }
  void begin(bool = false) { hid.begin(); }
#else
  void begin(bool = false) { activeLink.begin(); }
#endif
  void setButton(uint8_t index,uint8_t value) {
    if (index >= 32) return;
    if (value) buttons |= 1UL<<index; else buttons &= ~(1UL<<index);
  }
  void setXAxisRange(int32_t a,int32_t b) { axisMin[0]=a; axisMax[0]=b; }
  void setYAxisRange(int32_t a,int32_t b) { axisMin[1]=a; axisMax[1]=b; }
  void setRxAxisRange(int32_t a,int32_t b) { axisMin[2]=a; axisMax[2]=b; }
  void setRyAxisRange(int32_t a,int32_t b) { axisMin[3]=a; axisMax[3]=b; }
  void setXAxis(int32_t v) { axes[0]=v; }
  void setYAxis(int32_t v) { axes[1]=v; }
  void setRxAxis(int32_t v) { axes[2]=v; }
  void setRyAxis(int32_t v) { axes[3]=v; }
  void setThrottleRange(int32_t a,int32_t b) { pedalMin[0]=a; pedalMax[0]=b; }
  void setBrakeRange(int32_t a,int32_t b) { pedalMin[1]=a; pedalMax[1]=b; }
  void setThrottle(int32_t v) { pedals[0]=v; }
  void setBrake(int32_t v) { pedals[1]=v; }
  void setHatSwitch(int8_t index,int16_t value) {
    if (index==0) hat=value<0 ? 8 : uint8_t((value%360)/45);
  }
  void sendState() {
#if !ACTIVE_CDC_TRANSPORT
    const uint32_t now = millis();
    if (!USB) { mountedSinceMs = lastCompletedMs = 0; return; }
    if (!mountedSinceMs) mountedSinceMs = now;
    // Recovery fallback for the old core's stuck interrupt endpoint.
    // A normal transfer completes in a few ms. Do not retry indefinitely
    // on a wedged endpoint and force the user to unplug the board.
    if (now - (lastCompletedMs ? lastCompletedMs : mountedSinceMs) > 10000) {
      ESP.restart();
      return;
    }
    if (!hid.ready()) return;
#endif
    uint8_t data[17]{};
    for (uint8_t i=0;i<4;++i) data[i]=uint8_t(buttons>>(8*i));
    data[4]=0x80|hat;
    for (uint8_t i=0;i<4;++i) put16(data+5+2*i,scaled(axes[i],axisMin[i],axisMax[i]));
    for (uint8_t i=0;i<2;++i) put16(data+13+2*i,scaled(pedals[i],pedalMin[i],pedalMax[i]));
    // 2 ms was shorter than host scheduling delays. A timed-out transfer
    // can leave the old TinyUSB endpoint stalled (Espressif issue #11600).
#if ACTIVE_CDC_TRANSPORT
    uint8_t report[18]; report[0]=3; memcpy(report+1,data,17);
    activeLink.send(1,report,18);
#else
    if (hid.SendReport(3,data,sizeof(data),50)) lastCompletedMs = millis();
#endif
  }
};
constexpr uint8_t BridgeGameInput::descriptor[];
