#pragma once
#include <Arduino.h>
#include <USBCDC.h>

// Native USB CDC, not the separate USB-UART connector. Single owner on PC.
// Frame: SB5! | kind | length | payload | CRC16-CCITT (little endian).
class BridgeSerialLink {
  USBCDC stream;
  uint8_t rx[80]{};
  uint8_t used=0;
  uint8_t tx[72]{};
  uint8_t txSize=0,txOffset=0;
 public:
  static uint16_t crc(const uint8_t* data,size_t size) {
    uint16_t value=0xffff;
    while(size--) { value ^= uint16_t(*data++)<<8;
      for(uint8_t i=0;i<8;++i) value=value&0x8000 ? (value<<1)^0x1021 : value<<1;
    }
    return value;
  }
  void begin() {
    stream.setRxBufferSize(512); stream.setTxTimeoutMs(5);
    stream.enableReboot(false); stream.begin(115200);
  }
  bool send(uint8_t kind,const uint8_t* payload,uint8_t length) {
    pump();
    if(!stream || length>64 || txSize) return false;
    memcpy(tx,"SB5!",4);
    tx[4]=kind; tx[5]=length; memcpy(tx+6,payload,length);
    uint16_t check=crc(tx+4,length+2);
    tx[length+6]=uint8_t(check); tx[length+7]=uint8_t(check>>8);
    txSize=length+8; txOffset=0; pump(); return true;
  }
  void pump() {
    if(!stream) { txSize=txOffset=0; return; }
    if(!txSize) return;
    int room=stream.availableForWrite();
    if(room<=0) return;
    size_t chunk=min(size_t(room),size_t(txSize-txOffset));
    txOffset+=stream.write(tx+txOffset,chunk);
    if(txOffset==txSize) txOffset=txSize=0;
  }
  bool command(uint8_t* payload) {
    pump();
    while(stream.available()) {
      int value=stream.read(); if(value<0) break;
      rx[used++]=uint8_t(value);
      while(used>=4 && memcmp(rx,"SB5!",4)) { memmove(rx,rx+1,--used); }
      if(used<6) continue;
      if(rx[5]>64) { memmove(rx,rx+1,--used); continue; }
      const uint8_t total=rx[5]+8;
      if(used<total) continue;
      const bool valid=crc(rx+4,rx[5]+2)==(uint16_t(rx[total-2])|(uint16_t(rx[total-1])<<8));
      const bool isCommand=valid && rx[4]==4 && rx[5]==64;
      if(isCommand) memcpy(payload,rx+6,64);
      used=0;
      if(isCommand) return true;
    }
    return false;
  }
};
extern BridgeSerialLink activeLink;
