#include <ESP8266WiFi.h>
#include <PubSubClient.h>
#include <Ticker.h>
#include <PxMatrix.h>
#include <ArduinoJson.h>
// WiFi & MQTT Config
const char* ssid = "SonvisageAirtel";
const char* password = "@sonvisage2012";
const char* mqtt_server = "192.168.0.149";  // Your broker IP

#define P_LAT 16  // D0
#define P_A 5     // D1
#define P_B 4     // D2
#define P_C 15    // D8
#define P_OE 2    // D4
#define P_D 12    // D6
#define P_E 0     // Not used

PxMATRIX display(512, 32, P_LAT, P_OE, P_A, P_B, P_C, P_D);
Ticker display_ticker;

uint16_t myRED = display.color565(255, 0, 0);
uint16_t myBLUE = display.color565(0, 0, 255);

WiFiClient espClient;
PubSubClient client(espClient);

// Store patient numbers for each doctor (index 0 to 3)
int docNumbers[4] = {0, 0, 0, 0};
volatile bool newDataAvailable = false;

void display_updater() {
  display.display(70);
}

void drawAllNumbers() {
  display.clearDisplay();
  for (int i = 0; i < 4; i++) {
    int baseX = 10 + i * 128;
    int number = docNumbers[i];
    display.setTextSize(2);
    display.setTextColor(myRED);
    display.setCursor(baseX, 2);
    display.print("NEXT");

    int centerX = (number < 10) ? (baseX + 76) : (number < 100) ? (baseX + 69) : (baseX + 66);
    display.setCursor(centerX, 2);
    display.setTextSize(2);
    display.print(number);
  }
  display.showBuffer();
}

// MQTT callback
void callback(char* topic, byte* payload, unsigned int length) {
  StaticJsonDocument<128> doc;
  DeserializationError error = deserializeJson(doc, payload, length);

  if (error) {
    Serial.print("❌ JSON parse error: ");
    Serial.println(error.c_str());
    return;
  }

  int number = doc["number"];
  int doctor = doc["doctor"];

  if (doctor >= 1 && doctor <= 4) {
    docNumbers[doctor - 1] = number;
    newDataAvailable = true;
    Serial.printf("📥 Doctor %d: %d\n", doctor, number);
  }
}

void reconnect() {
  while (!client.connected()) {
    Serial.print("🔌 Connecting to MQTT...");
    if (client.connect("DisplayAllDoctors")) {
      Serial.println(" connected!");
      client.subscribe("clinic/display/all");
      Serial.println("📡 Subscribed to clinic/display/all");
    } else {
      Serial.print("❌ Failed. rc=");
      Serial.print(client.state());
      Serial.println(" retrying in 3 seconds...");
      delay(3000);
    }
  }
}

void setup() {
  Serial.begin(115200);

  display.begin(16);
  display.setFastUpdate(true);
  display.clearDisplay();
  display_ticker.attach(0.008, display_updater);

  display.setCursor(1, 1);
  display.setTextSize(2);
  display.setTextColor(myBLUE);
  display.print("MEDIBOARDS");
  display.setCursor(130, 1);
  display.print("SONVISAGE");
  display.showBuffer();
  delay(6000);
  display.clearDisplay();

  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  Serial.print("📶 Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println(" ✅ Connected!");
  Serial.print("IP: "); Serial.println(WiFi.localIP());

  client.setServer(mqtt_server, 1883);
  client.setCallback(callback);
}

void loop() {
  if (!client.connected()) {
    reconnect();
  }
  client.loop();

  if (newDataAvailable) {
    drawAllNumbers();
    newDataAvailable = false;
  }
}
