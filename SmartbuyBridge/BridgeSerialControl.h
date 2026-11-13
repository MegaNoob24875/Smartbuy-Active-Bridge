#pragma once
#include <Arduino.h>
#include "BridgeSerialLink.h"
#include <Preferences.h>


// Status/config payloads retain v1 layout, carried by checksummed CDC frames.
// Commands and NVS writes run in Arduino loop; there are no HID callbacks.
struct BridgeConfig {
  uint8_t version, leftDeadzone, rightDeadzone, invert, swapSticks, threshold;
  uint8_t mapping[32];
  uint8_t reserved[2];
};
static_assert(sizeof(BridgeConfig) == 40, "Configuration wire size");

static BridgeConfig defaultBridgeConfig() {
  BridgeConfig c{};
  c.version = 1;
  c.leftDeadzone = c.rightDeadzone = 5;
  c.threshold = 13;
  for (uint8_t i = 0; i < 32; ++i) c.mapping[i] = i;
  return c;
}

static bool validBridgeConfig(const BridgeConfig& c) {
  if (c.version != 1 || c.leftDeadzone > 40 || c.rightDeadzone > 40 ||
      c.invert > 15 || c.swapSticks > 1 || c.threshold > 100) return false;
  for (uint8_t v : c.mapping) if (v > 31 && v != 255) return false;
  return c.reserved[0] == 0 && c.reserved[1] == 0;
}

class BridgeControl {

  Preferences preferences;

  uint8_t status[63]{};
  uint8_t pending[63]{};
  bool queued = false;
  bool storageAvailable = false;
  BridgeConfig applied = defaultBridgeConfig();
  uint8_t acknowledged = 0, result = 0, lastOperation = 0;

 public:
  BridgeConfig config = defaultBridgeConfig(); // accessed by Arduino loop only
  uint32_t revision = 0;
  void begin() {
    storageAvailable = preferences.begin("smartbuy", false);
    BridgeConfig stored{};
    if (storageAvailable && preferences.getBytesLength("config") == sizeof(stored)) {
      preferences.getBytes("config", &stored, sizeof(stored));
      if (validBridgeConfig(stored)) config = stored;
    }
    applied = config;

  }
  uint16_t _onGetFeature(uint8_t id, uint8_t* dst, uint16_t len) {
    if (len < 63) return 0;
    if (id == 0x20) memcpy(dst, status, 63);
    else if (id == 0x21) {
      memset(dst, 0, 63);
      memcpy(dst, "SBCF", 4);
      dst[4] = acknowledged;
      dst[5] = lastOperation;
      memcpy(dst + 6, &applied, sizeof(applied));
      dst[46] = result;
    } else return 0;
    return 63;
  }
  void _onSetFeature(uint8_t id, const uint8_t* src, uint16_t len) {
    if (id != 0x21 || len != 63 || memcmp(src, "SBCF", 4)) return;
    memcpy(pending, src, 63);
    queued = true;
  }
  void service() {
    uint8_t incoming[64];
    while(activeLink.command(incoming)) {
      if(incoming[0]==0x21) _onSetFeature(0x21,incoming+1,63);
    }
    uint8_t request[63];
    {
      if (!queued) return;
      memcpy(request, pending, 63);
      queued = false;
    }
    BridgeConfig candidate;
    memcpy(&candidate, request + 6, sizeof(candidate));
    const uint8_t op = request[5];
    uint8_t error = 0;
    if (op == 3) candidate = defaultBridgeConfig();
    if (op < 1 || op > 3 || !validBridgeConfig(candidate)) error = 1;
    else {
      // Save must succeed before applying, so a failed persistence request
      // cannot silently change the current game mapping.
      if ((op == 2 || op == 3) &&
          (!storageAvailable || preferences.putBytes("config", &candidate, sizeof(candidate)) != sizeof(candidate)))
        error = 2;
      if (!error) { config = candidate; ++revision; }
    }
    applied = config;
    acknowledged = request[4];
    lastOperation = op;
    result = error;
  }
  void publish(bool connected, bool received, uint32_t reports,
               uint32_t lastInput, uint32_t buttons, int16_t lx, int16_t ly,
               int16_t rx, int16_t ry, uint16_t brake, uint16_t throttle,
               uint8_t dpad, uint8_t battery) {
    uint8_t packet[63]{};
    memcpy(packet, "SBGP", 4);
    packet[4] = 1;
    packet[5] = 5;
    packet[6] = connected; packet[7] = received;
    memcpy(packet + 8, &reports, 4);
    memcpy(packet + 12, &lastInput, 4);
    memcpy(packet + 16, &buttons, 4);
    const int16_t sticks[] = {lx, ly, rx, ry};
    memcpy(packet + 20, sticks, 8);
    memcpy(packet + 28, &brake, 2); memcpy(packet + 30, &throttle, 2);
    packet[32] = dpad; packet[33] = battery;
    memcpy(packet + 36, &revision, 4);
    packet[40] = storageAvailable;
    packet[34] = acknowledged; packet[35] = result;
    memcpy(status, packet, 63);
    static uint32_t lastStatus=0,lastConfig=0;
    const uint32_t now=millis();
    if(now-lastStatus>=100) {
      lastStatus=now;
      uint8_t report[64]; report[0]=0x20; memcpy(report+1,status,63);
      activeLink.send(2,report,64);
    }
    if(now-lastConfig>=250) {
      lastConfig=now;
      uint8_t report[64]; report[0]=0x21;
      _onGetFeature(0x21,report+1,63); activeLink.send(3,report,64);
    }
  }
};
