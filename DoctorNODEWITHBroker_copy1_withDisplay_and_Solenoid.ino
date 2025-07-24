#include <SPI.h>
#include <MFRC522.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <ArduinoJson.h>

// === Pins and Config ===
#define RST_PIN         5
#define SS_PIN          4
#define GREEN_LED_PIN   16
#define RED_LED_PIN     15
#define BTN_REQUEST_PIN 32
#define BTN_CLEAR1_PIN  33
#define BTN_CLEAR2_PIN  34
#define BTN_RESET_PIN   35
#define WIFI_SSID       "SonvisageAirtel"
#define WIFI_PASSWORD   "@sonvisage2012"
#define MQTT_BROKER     "192.168.0.149"
#define MQTT_PORT       1883
bool solenoidState = false;  // False = OFF, True = ON
unsigned long lastToggle = 0;

const int nodeID = 1;

MFRC522 mfrc522(SS_PIN, RST_PIN);
WiFiClient espClient;
PubSubClient mqttClient(espClient);
LiquidCrystal_I2C lcd(0x27, 16, 2);

char currentUID[21];
char currentTimestamp[25];
bool patientReady = false;
int patientNum = 0;
char pubRemoveTopic[64];
char pubTopic[64];
char subTopic[64];
char solenoidTopic[64];
// === Helper Functions ===
String getUIDString(byte *buffer, byte bufferSize) {
  String uid = "";
  for (byte i = 0; i < bufferSize; i++) {
    if (buffer[i] < 0x10) uid += "0";
    uid += String(buffer[i], HEX);
  }
  uid.toUpperCase();
  return uid;
}

void blinkLED(int pin) {
  digitalWrite(pin, HIGH);
  delay(500);
  digitalWrite(pin, LOW);
}

// === MQTT Logic ===
void mqttCallback(char* topic, byte* payload, unsigned int length) {
  String message;
  for (unsigned int i = 0; i < length; i++) {
    message += (char)payload[i];
  }

  StaticJsonDocument<256> doc;
  DeserializationError err = deserializeJson(doc, message);
  if (err) {
    Serial.print("❌ JSON Error: ");
    Serial.println(err.f_str());
    return;
  }

  String uid = doc["uid"] | "";
  if (uid == "NO_PATIENT") {
    patientNum = 0;
    lcd.clear();
    lcd.setCursor(2, 0); lcd.print("NO PATIENT");
    lcd.setCursor(1, 1); lcd.print("QUEUE IS EMPTY");
    patientReady = false;

    // Publish zero to display
    char displayTopic[64];
    sprintf(displayTopic, "clinic/display/%d", nodeID);
    mqttClient.publish(displayTopic, "0");
    return;
  }
if (doc.containsKey("status") && doc["status"] == "queues_cleared") {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Queues Cleared");
  delay(2000);
}

  patientNum = doc["number"] | 0;
  String ts = doc["timestamp"] | "";
  uid.toCharArray(currentUID, 21);
  ts.toCharArray(currentTimestamp, 25);
  patientReady = true;

  lcd.clear();
  lcd.setCursor(0, 0); lcd.print("NEXT PATIENT");
  lcd.setCursor(6, 1); lcd.print(patientNum);
   char displayTopic[64];
  sprintf(displayTopic, "clinic/display/%d", nodeID);
  mqttClient.publish(displayTopic, String(patientNum).c_str());
  Serial.printf("📺 Sent to display topic: %s => %d\n", displayTopic, patientNum);

  Serial.printf("✅ Received UID: %s | Number: %d\n", currentUID, patientNum);
}

void sendRequestToQueueManager() {
  StaticJsonDocument<256> doc;
  doc["uid"] = "REQ_NEXT";
  doc["timestamp"] = millis();
  doc["node"] = nodeID;

  char buffer[256];
  serializeJson(doc, buffer);
  mqttClient.publish(pubTopic, buffer);
  Serial.print("📤 MQTT Sent to ");
  Serial.println(pubTopic);
}


void connectToWiFi() {
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500); Serial.print(".");
  }
  Serial.println(" ✅ WiFi Connected!");
  Serial.print("IP: "); Serial.println(WiFi.localIP());
}

void reconnectMQTT() { lcd.clear();
  while (!mqttClient.connected()) {
    Serial.print("Connecting to MQTT...");
    uint64_t chipId = ESP.getEfuseMac(); // 64-bit MAC address
String clientId = "DoctorNode" + String((uint32_t)(chipId & 0xFFFFFFFF));
    if (mqttClient.connect(clientId.c_str())) { // this most be change
      Serial.println(" connected.");
      lcd.clear();
      mqttClient.subscribe(subTopic);
      Serial.print("📡 Subscribed to: ");
      Serial.println(subTopic);
     lcd.setCursor(0, 0); // First column, first row
     lcd.print("Connect 2 Broker");
     lcd.setCursor(0, 1); // First column, first row
     lcd.print("Successfully");
     delay(2000);
    } else {
      Serial.print("❌ Failed, rc=");
      Serial.print(mqttClient.state());
      Serial.println(" retrying in 5 sec");
      lcd.setCursor(0, 0); // First column, first row
      lcd.print("Connecting...");
      delay(5000);
    }
  }
}

// === Setup and Loop ===
void setup() {
  Serial.begin(115200);
  pinMode(GREEN_LED_PIN, OUTPUT);
  pinMode(RED_LED_PIN, OUTPUT);
  pinMode(BTN_REQUEST_PIN, INPUT);
pinMode(BTN_CLEAR1_PIN, INPUT);
pinMode(BTN_CLEAR2_PIN, INPUT);
pinMode(BTN_RESET_PIN, INPUT);
  SPI.begin();
  mfrc522.PCD_Init();
  Wire.begin(21, 22);
  lcd.init(); lcd.backlight();
  lcd.setCursor(2, 0); // First column, first row
  lcd.print("SONVISAGE");
     lcd.setCursor(2, 1); // First column, second row
       lcd.print("MEDIBOARDS");
       delay(7000);
lcd.clear();
  lcd.setCursor(2, 0); lcd.print("NEXT PATIENT");

  sprintf(solenoidTopic, "clinic/solenoid/%d/toggle", nodeID);

  sprintf(pubTopic, "clinic/doctor/%d/request", nodeID);
  sprintf(subTopic, "clinic/doctor/%d/response", nodeID);
  sprintf(pubRemoveTopic, "clinic/doctor/%d/remove", nodeID);
  connectToWiFi();
  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
  mqttClient.setCallback(mqttCallback);
  

}

void loop() {
  if (!mqttClient.connected()) reconnectMQTT();
  mqttClient.loop();

  if (digitalRead(BTN_REQUEST_PIN) == HIGH) {
    Serial.println("🔘 Request Button Pressed");
    sendRequestToQueueManager();
    delay(500);
  }

  if (digitalRead(BTN_RESET_PIN) == HIGH) {
  Serial.println("🔁 Reset Button Pressed");
  delay(200);  // Optional delay
  ESP.restart();
}
// Solenoid toggle logic
static bool lastSolenoidButtonState = LOW;
bool currentSolenoidButtonState = digitalRead(BTN_CLEAR2_PIN);

if (currentSolenoidButtonState == HIGH && lastSolenoidButtonState == LOW) {
  solenoidState = !solenoidState;  // Toggle state
  StaticJsonDocument<128> doc;
  doc["solenoid"] = solenoidState ? "ON" : "OFF";
  doc["node"] = nodeID;

  char buffer[128];
  serializeJson(doc, buffer);
  mqttClient.publish("clinic/solenoid/control", buffer);
  Serial.printf("🔧 Solenoid command sent: %s\n", buffer);
  delay(300);  // debounce
}
lastSolenoidButtonState = currentSolenoidButtonState;


  if (digitalRead(BTN_CLEAR1_PIN) == HIGH && digitalRead(BTN_CLEAR2_PIN) == HIGH) {
  Serial.println("🧹 CLEAR QUEUE Buttons Pressed Together");

String topic = "clinic/doctor/" + String(nodeID) + "/clear";
  mqttClient.publish(topic.c_str(), "{}");
  delay(1000);  // Prevent multiple sends
  
}

  if (!mfrc522.PICC_IsNewCardPresent() || !mfrc522.PICC_ReadCardSerial()) return;

  String scannedUID = getUIDString(mfrc522.uid.uidByte, mfrc522.uid.size);
  scannedUID.toUpperCase();

  if (patientReady && scannedUID == String(currentUID)) {
    Serial.printf("✅ Patient %d attended\n", patientNum);

    StaticJsonDocument<256> doc;
    doc["uid"] = currentUID;
    doc["node"] = nodeID;
    doc["timestamp"] = currentTimestamp;

    char buffer[256];
    serializeJson(doc, buffer);
    mqttClient.publish(pubRemoveTopic, buffer);
    //mqttClient.publish("clinic/doctor/1/remove", buffer);
   
    Serial.println("📤 MQTT Sent: REMOVE");
    patientReady = false;
    sendRequestToQueueManager();
    blinkLED(GREEN_LED_PIN);
  } else {
    Serial.println("❌ Access Denied");
    blinkLED(RED_LED_PIN);
  }

  mfrc522.PICC_HaltA();
  mfrc522.PCD_StopCrypto1();
  delay(1000);
}
