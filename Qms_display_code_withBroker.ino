#include <WiFi.h>
#include <PubSubClient.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// ==== WiFi & MQTT Config ====
#define WIFI_SSID     "SonvisageAirtel"
#define WIFI_PASSWORD "@sonvisage2012"
#define MQTT_BROKER   "192.168.1.236"
#define MQTT_PORT     1883

const int nodeID = 4;  // Display node for Doctor Node 2
char topicToSubscribe[64];

WiFiClient espClient;
PubSubClient client(espClient);

// LCD
LiquidCrystal_I2C lcd(0x27, 16, 2);
int currentNumber = 0;

void drawNumber(int num) {
  lcd.clear();
  if (num == 0) {
    lcd.setCursor(0, 0); lcd.print("NO PATIENT");
    lcd.setCursor(0, 1); lcd.print("QUEUE IS EMPTY");
  } else {
    lcd.setCursor(0, 0); lcd.print("NEXT PATIENT");
    lcd.setCursor(6, 1); lcd.print(num);
  }
}

void callback(char* topic, byte* message, unsigned int length) {
  String msg = "";
  for (int i = 0; i < length; i++) {
    msg += (char)message[i];
  }
  int num = msg.toInt();
  currentNumber = num;
  Serial.printf("📩 Received %d on %s\n", num, topic);
  drawNumber(currentNumber);
}

void connectToWiFi() {
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500); Serial.print(".");
  }
  Serial.println(" ✅ WiFi Connected");
  Serial.print("IP Address: "); Serial.println(WiFi.localIP());
}

void connectToMQTT() {
  while (!client.connected()) {
    Serial.print("Connecting to MQTT...");
   String clientId = "DisplayNode_" + String(nodeID);
if (client.connect(clientId.c_str())) {
      Serial.println(" connected!");
      client.subscribe(topicToSubscribe);
      Serial.print("📡 Subscribed to: ");
      Serial.println(topicToSubscribe);
      drawNumber(currentNumber);
    } else {
      Serial.print("❌ Failed. State: ");
      Serial.println(client.state());
      delay(3000);
    }
  }
}

void setup() {
  Serial.begin(115200);
  lcd.init(); lcd.backlight();
  lcd.setCursor(0, 0); lcd.print("Display Node");
  lcd.setCursor(0, 1); lcd.print("Starting...");
  delay(2000);

  sprintf(topicToSubscribe, "clinic/display/%d", nodeID);

  WiFi.mode(WIFI_STA);
  connectToWiFi();

  client.setServer(MQTT_BROKER, MQTT_PORT);
  client.setCallback(callback);
}

void loop() {
  if (!client.connected()) connectToMQTT();
  client.loop();
}
