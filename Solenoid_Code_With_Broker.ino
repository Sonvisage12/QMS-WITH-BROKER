#include <ESP8266WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

const char* ssid = "SonvisageAirtel";
const char* password = "@sonvisage2012";
const char* mqttServer = "192.168.0.149";
const int mqttPort = 1883;

WiFiClient espClient;
PubSubClient client(espClient);

// Map solenoid control to pins
const int solenoidPins[4] = {5, 14, 13, 12};  // D1, D2, D5, D6 for Node 1 to 4

void setup() {
  Serial.begin(115200);
  for (int i = 0; i < 4; i++) {
    pinMode(solenoidPins[i], OUTPUT);
    digitalWrite(solenoidPins[i], LOW); // All OFF initially
  }

  WiFi.begin(ssid, password);
  Serial.print("📶 Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println(" ✅ Connected");
  Serial.println(WiFi.localIP());

  client.setServer(mqttServer, mqttPort);
  client.setCallback(callback);
}

void reconnect() {
  while (!client.connected()) {
    Serial.print("🔌 Connecting to MQTT...");
    if (client.connect("SolenoidNode")) {
      Serial.println(" connected");
      client.subscribe("solenoid/node/+");
    } else {
      Serial.print("❌ failed, rc=");
      Serial.print(client.state());
      Serial.println(" retrying in 5s");
      delay(5000);
    }
  }
}

void callback(char* topic, byte* payload, unsigned int length) {
  String jsonStr;
  for (int i = 0; i < length; i++) {
    jsonStr += (char)payload[i];
  }

  StaticJsonDocument<128> doc;
  DeserializationError err = deserializeJson(doc, jsonStr);
  if (err) {
    Serial.println("❌ JSON Parse Failed");
    return;
  }

  String action = doc["action"];
  int node = String(topic).substring(String(topic).lastIndexOf('/') + 1).toInt();
  if (node >= 1 && node <= 4) {
    int pin = solenoidPins[node - 1];
    digitalWrite(pin, action == "ON" ? HIGH : LOW);
    Serial.printf("⚡ Solenoid %d turned %s\n", node, action.c_str());
  }
}

void loop() {
  if (!client.connected()) reconnect();
  client.loop();
}
