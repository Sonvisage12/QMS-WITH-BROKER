#include <ESP8266WiFi.h>
#include <PubSubClient.h>
#include <EEPROM.h>
#include <ArduinoJson.h>

// === WiFi & MQTT Configuration ===
const char* ssid = "SonvisageAirtel";
const char* password = "@sonvisage2012";
const char* mqttServer = "192.168.0.149";
const int mqttPort = 1883;

// === Solenoid Pin Mapping ===
// Node 1 → D6 (GPIO12), Node 2 → D7 (GPIO13), Node 3 → D5 (GPIO14), Node 4 → D1 (GPIO5)
const int solenoidPins[4] = {12, 13, 14, 5};  

WiFiClient espClient;
PubSubClient client(espClient);

// === EEPROM Config ===
#define EEPROM_SIZE 4  // One byte per solenoid

// === Setup ===
void setup() {
  Serial.begin(115200);
  EEPROM.begin(EEPROM_SIZE);

  // Setup solenoid pins and restore saved state
  for (int i = 0; i < 4; i++) {
    pinMode(solenoidPins[i], OUTPUT);
    bool savedState = EEPROM.read(i);
    digitalWrite(solenoidPins[i], savedState ? HIGH : LOW);
    Serial.printf("🔄 Solenoid %d restored to %s\n", i + 1, savedState ? "ON" : "OFF");
  }

  // Connect to WiFi
  WiFi.begin(ssid, password);
  Serial.print("📶 Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500); Serial.print(".");
  }
  Serial.println("\n✅ WiFi Connected!");
  Serial.print("IP Address: "); Serial.println(WiFi.localIP());

  // Connect to MQTT
  client.setServer(mqttServer, mqttPort);
  client.setCallback(callback);
}

// === Reconnect MQTT if disconnected ===
void reconnect() {
  while (!client.connected()) {
    Serial.print("🔌 Connecting to MQTT...");
    if (client.connect("SolenoidNode")) {
      Serial.println(" connected.");
      client.subscribe("solenoid/node/+");
      Serial.println("📡 Subscribed to: solenoid/node/+");
    } else {
      Serial.print("❌ Failed, rc=");
      Serial.print(client.state());
      Serial.println(" retrying in 5s...");
      delay(5000);
    }
  }
}

// === MQTT Callback ===
void callback(char* topic, byte* payload, unsigned int length) {
  String message;
  for (int i = 0; i < length; i++) {
    message += (char)payload[i];
  }

  Serial.printf("📩 Topic: %s | Message: %s\n", topic, message.c_str());

  StaticJsonDocument<128> doc;
  DeserializationError err = deserializeJson(doc, message);
  if (err) {
    Serial.println("❌ JSON parse failed!");
    return;
  }

  String action = doc["action"];
  int node = String(topic).substring(String(topic).lastIndexOf('/') + 1).toInt();

  if (node >= 1 && node <= 4) {
    int pin = solenoidPins[node - 1];
    bool state = (action == "ON");

    digitalWrite(pin, state ? HIGH : LOW);
    EEPROM.write(node - 1, state);
    EEPROM.commit();

    Serial.printf("⚡ Solenoid %d set to %s and saved\n", node, action.c_str());
  } else {
    Serial.println("⚠️ Invalid node number");
  }
}

// === Main Loop ===
void loop() {
  if (!client.connected()) reconnect();
  client.loop();
}
