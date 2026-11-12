#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <DNSServer.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <LittleFS.h>
#include <Preferences.h>
#include <time.h>
#include <esp_system.h>

// Compatible wiring/features inspired by NG3D-Druck/Gas-Connect-DIY.
// This standalone firmware adds an acknowledged, durable minute outbox.
constexpr uint32_t CAPACITY = 43200; // 30 days, one record per minute
constexpr int REED = 4, BOOT_PIN = 9;
struct Record { uint32_t seq, minute, total; uint16_t pulses, flags; uint32_t crc; };
static_assert(sizeof(Record)==20, "Unexpected record size");
Preferences prefs;
WebServer web(80);
DNSServer dns;
WiFiClient net;
PubSubClient mqtt(net);
String ssid, password, broker, mqttPassword, stream;
uint32_t nextSeq=1, acked=0, dropped=0, pending=0;
volatile uint32_t total=0;
volatile uint16_t minutePulses=0;
portMUX_TYPE counterMux=portMUX_INITIALIZER_UNLOCKED;
uint32_t bucketStart=0, trackedMinute=0, lastAttempt=0, lastSend=0, lastStatus=0;
volatile uint32_t lastPulse=0, prevPulse=0;
uint32_t rawSince=0, setupStarted=0, bootHeld=0;
int rawState=HIGH, stableState=HIGH;
volatile int debounceMs=100;
bool setupMode=false, storageHealthy=false;
File queueFile;

uint32_t crc32(const uint8_t* p, size_t n) {
  uint32_t c=~0U;
  while(n--) { c^=*p++; for(int b=0;b<8;b++) c=(c>>1)^(0xedb88320U&-(c&1)); }
  return ~c;
}
bool readRecord(uint32_t seq, Record &r) {
  if(!queueFile || !seq) return false;
  queueFile.seek(((seq-1)%CAPACITY)*sizeof(Record));
  return queueFile.read((uint8_t*)&r,sizeof(r))==sizeof(r) && r.seq==seq &&
    r.crc==crc32((uint8_t*)&r,sizeof(r)-4);
}
void saveRecord(uint32_t recordedMinute) {
  if(!storageHealthy) return; // Keep live count; report fault instead of formatting storage.
  portENTER_CRITICAL(&counterMux);
  uint32_t snapshot=total; uint16_t delta=minutePulses;
  portEXIT_CRITICAL(&counterMux);
  Record r{nextSeq, recordedMinute, snapshot, delta, (uint16_t)(recordedMinute?0:1), 0};
  r.crc=crc32((uint8_t*)&r,sizeof(r)-4);
  if(!queueFile.seek(((nextSeq-1)%CAPACITY)*sizeof(r)) ||
     queueFile.write((uint8_t*)&r,sizeof(r))!=sizeof(r)) { storageHealthy=false; return; }
  queueFile.flush();
  if(nextSeq>acked+CAPACITY) { acked=nextSeq-CAPACITY; dropped++; prefs.putUInt("ack",acked); prefs.putUInt("drop",dropped); pending=0; }
  nextSeq++;
  portENTER_CRITICAL(&counterMux); minutePulses-=delta; portEXIT_CRITICAL(&counterMux);
}
void IRAM_ATTR pulseISR() {
  uint32_t now=millis();
  if(lastPulse && now-lastPulse<(uint32_t)debounceMs) return;
  portENTER_CRITICAL_ISR(&counterMux);
  total++; minutePulses++; prevPulse=lastPulse; lastPulse=now;
  portEXIT_CRITICAL_ISR(&counterMux);
}
String topic(const char* suffix) { return "gas/"+stream+"/"+suffix; }
void onMessage(char* t, byte* payload, unsigned int length) {
  JsonDocument doc;
  if(deserializeJson(doc,payload,length)) return;
  if(String(t)==topic("ack")) {
    uint32_t seq=doc["seq"] | 0U;
    if(pending && seq==pending && seq==acked+1) {
      acked=seq; pending=0;
      // Batch acknowledgement checkpoints: duplicates after a reboot are safe.
      if(acked%60==0 || acked==nextSeq-1) prefs.putUInt("ack",acked);
    }
  }
  if(String(t)==topic("config")) {
    int value=doc["debounce_ms"] | debounceMs;
    if(value>=10 && value<=1000 && value!=debounceMs) { debounceMs=value; prefs.putInt("debounce",value); }
  }
}
void status() {
  JsonDocument d;
  d["stream"]=stream; d["total_pulses"]=(uint32_t)total; d["queued"]=nextSeq-acked-1;
  d["dropped_minutes"]=dropped; d["storage_ok"]=storageHealthy;
  d["clock_ok"]=time(nullptr)>1700000000; d["rssi"]=WiFi.RSSI();
  d["uptime"]=millis()/1000; d["reed_closed"]=stableState==LOW;
  d["debounce_ms"]=(int)debounceMs;
  d["pulses_per_hour"]=(lastPulse && prevPulse && millis()-lastPulse<600000) ? 3600000.0/(lastPulse-prevPulse):0;
  String s; serializeJson(d,s); mqtt.publish(topic("status").c_str(),s.c_str(),true);
}
void provision() {
  setupMode=true; setupStarted=millis();
  String mac=WiFi.macAddress(); mac.replace(":",""); String suffix=mac.substring(6);
  WiFi.mode(WIFI_AP_STA);
  WiFi.softAP(("Gas-Setup-"+suffix).c_str(),("gas-"+suffix).c_str());
  dns.start(53,"*",WiFi.softAPIP());
  web.on("/",HTTP_GET,[](){ web.send(200,"text/html; charset=utf-8",
    "<!doctype html><meta name=viewport content='width=device-width'><title>Gas Connect Einrichtung</title>"
    "<style>body{font:18px system-ui;background:#101b26;color:white;max-width:440px;margin:40px auto;padding:20px}input,button{box-sizing:border-box;width:100%;padding:14px;margin:8px 0;border-radius:10px;border:0}button{background:#b9f28e}</style>"
    "<h1>Gas Connect</h1><p>WLAN und Server einrichten. Der Messpuffer bleibt erhalten.</p><form method=post action=/save>"
    "<label>WLAN-Name</label><input name=ssid required maxlength=32><label>WLAN-Passwort</label><input name=wifi type=password maxlength=64>"
    "<label>Server-Adresse (IP oder DNS)</label><input name=broker required placeholder=Server-Adresse maxlength=64>"
    "<label>Sensor-Passwort aus dem Dashboard</label><input name=mqtt type=password required maxlength=100>"
    "<button>Speichern und verbinden</button></form>"); });
  web.on("/save",HTTP_POST,[](){
    if(web.arg("ssid").length()>32 || web.arg("broker").length()>64 || web.arg("mqtt").length()>100 || web.arg("mqtt").length()<12) {web.send(400,"text/plain","Eingaben ungueltig");return;}
    prefs.putString("ssid",web.arg("ssid")); prefs.putString("wifi",web.arg("wifi"));
    prefs.putString("broker",web.arg("broker")); prefs.putString("mqtt",web.arg("mqtt"));
    if(minutePulses) saveRecord(time(nullptr)>1700000000 ? time(nullptr)/60 : 0);
    web.send(200,"text/plain","Gespeichert. Neustart..."); delay(500); ESP.restart();
  });
  web.onNotFound([](){web.sendHeader("Location","http://192.168.4.1/");web.send(302);});
  web.begin();
}
void setup() {
  Serial.begin(115200); pinMode(REED,INPUT_PULLUP); pinMode(BOOT_PIN,INPUT_PULLUP);
  prefs.begin("gas-v1",false);
  stream=prefs.getString("stream","");
  if(stream.isEmpty()) { stream="gas-meter-"+String((uint32_t)ESP.getEfuseMac(),HEX)+"-"+String(esp_random(),HEX); prefs.putString("stream",stream); }
  acked=prefs.getUInt("ack",0); dropped=prefs.getUInt("drop",0); debounceMs=prefs.getInt("debounce",100);
  storageHealthy=LittleFS.begin(false);
  if(!storageHealthy && !prefs.getBool("fsinit",false)) { // Only a new installation may initialize its empty filesystem.
    storageHealthy=LittleFS.format() && LittleFS.begin(false);
    if(storageHealthy) prefs.putBool("fsinit",true);
  }
  if(storageHealthy) {
    prefs.putBool("fsinit",true);
    if(prefs.getBool("journal",false) && !LittleFS.exists("/minutes.bin")) storageHealthy=false;
  }
  if(storageHealthy) {
    queueFile=LittleFS.open("/minutes.bin",LittleFS.exists("/minutes.bin")?"r+":"w+");
    storageHealthy=(bool)queueFile;
    if(storageHealthy) prefs.putBool("journal",true);
    uint32_t newest=0; Record r;
    for(uint32_t slot=0;queueFile && slot<CAPACITY;slot++) {
      if(slot%256==0) yield();
      queueFile.seek(slot*sizeof(r));
      if(queueFile.read((uint8_t*)&r,sizeof(r))!=sizeof(r)) break;
      if(r.seq && r.crc==crc32((uint8_t*)&r,sizeof(r)-4) && r.seq>newest) {newest=r.seq;total=r.total;}
    }
    nextSeq=newest+1;
    if(acked>newest) { storageHealthy=false; } // Do not silently restart a damaged journal.
    if(newest>acked+CAPACITY) acked=newest-CAPACITY;
  }
  rawState=stableState=digitalRead(REED); bucketStart=millis();
  attachInterrupt(digitalPinToInterrupt(REED),pulseISR,FALLING);
  ssid=prefs.getString("ssid",""); password=prefs.getString("wifi","");
  broker=prefs.getString("broker",""); mqttPassword=prefs.getString("mqtt","");
  WiFi.mode(WIFI_STA);
  if(ssid.isEmpty()) provision(); else WiFi.begin(ssid.c_str(),password.c_str());
  configTime(0,0,"pool.ntp.org","time.cloudflare.com");
  mqtt.setServer(broker.c_str(),1883); mqtt.setCallback(onMessage); mqtt.setBufferSize(768); mqtt.setSocketTimeout(1);
}
void loop() {
  uint32_t now=millis();
  int r=digitalRead(REED);
  if(r!=rawState) {rawState=r;rawSince=now;}
  if(rawState!=stableState && now-rawSince>=(uint32_t)debounceMs) {
    stableState=rawState;
  }
  time_t epoch=time(nullptr);
  if(epoch>1700000000) {
    uint32_t currentMinute=epoch/60;
    if(!trackedMinute) { if(minutePulses) saveRecord(0); trackedMinute=currentMinute;bucketStart=now; }
    if(currentMinute!=trackedMinute) { saveRecord(trackedMinute);trackedMinute=currentMinute;bucketStart=now; }
  } else if(now-bucketStart>=60000) { saveRecord(0); bucketStart+=60000; }
  if(digitalRead(BOOT_PIN)==LOW) {
    if(!bootHeld) bootHeld=now;
    if(now-bootHeld>5000 && !setupMode) provision();
  } else bootHeld=0;
  if(setupMode) {
    dns.processNextRequest(); web.handleClient();
    if(now-setupStarted>900000) { web.stop();dns.stop();WiFi.softAPdisconnect(true);setupMode=false;WiFi.mode(WIFI_STA); }
  }
  if(WiFi.status()==WL_CONNECTED && !broker.isEmpty()) {
    if(!mqtt.connected() && now-lastAttempt>10000) {
      lastAttempt=now;
      if(mqtt.connect(stream.c_str(),"sensor",mqttPassword.c_str())) {mqtt.subscribe(topic("ack").c_str(),1);mqtt.subscribe(topic("config").c_str(),1);status();}
    }
    mqtt.loop();
    if(mqtt.connected()) {
      if(now-lastStatus>5000) {status();lastStatus=now;}
      if(storageHealthy && acked<nextSeq-1 && now-lastSend>(pending?3000U:50U)) {
        Record item;
        if(readRecord(acked+1,item)) {
          JsonDocument d; d["seq"]=item.seq; d["minute"]=item.minute;d["pulses"]=item.pulses;d["total"]=item.total;d["flags"]=item.flags;
          String s;serializeJson(d,s);
          if(mqtt.publish(topic("event").c_str(),s.c_str())) pending=item.seq;
        } else {storageHealthy=false;}
        lastSend=now;
      }
    }
  }
  delay(1);
}
