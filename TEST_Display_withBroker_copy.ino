#include <ESP8266WiFi.h>
#include <Ticker.h>
#include <PxMatrix.h>
#include <PubSubClient.h>
#define WIFI_SSID       "SonvisageAirtel"
#define WIFI_PASSWORD   "@sonvisage2012"
#define MQTT_BROKER      "192.168.0.149"
#define MQTT_PORT        1883

const int nodeID = 2;

int currentNumber = 0;
int Number=0;
int Number1=0;
Ticker display_ticker;
#define P_LAT 16  // D0
#define P_A 5     // D1
#define P_B 4     // D2
#define P_C 15    // D8
#define P_OE 2    // D4
#define P_D 12    // D6
#define P_E 0     // GND (no connection)
WiFiClient espClient;
PxMATRIX display(128, 32, P_LAT, P_OE, P_A, P_B, P_C, P_D);
uint16_t myRED = display.color565(255, 0, 0);
uint16_t myBLUE = display.color565( 0, 0,255);
volatile bool updateDisplay = false;
int latestNumber = 0;
unsigned long lastReconnectAttempt = 0;
//WiFiClient espClient;
PubSubClient mqttClient(espClient);
char topicToSubscribe[64];

void display_updater() {
  display.display(100);
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
unsigned long lastAttemptTime = 0;
int reconnectDelay = 5000;

void reconnectMQTT() {
  if (!mqttClient.connected()) {
    unsigned long now = millis();
    if (now - lastAttemptTime > reconnectDelay) {
      lastAttemptTime = now;

      Serial.print("Connecting to MQTT...");
      String clientId = "display_" + String(ESP.getChipId());
      if (mqttClient.connect(clientId.c_str())) {
        Serial.println(" connected.");

        sprintf(topicToSubscribe, "clinic/display/%d", nodeID);
        mqttClient.subscribe(topicToSubscribe);
        Serial.print("📡 Subscribed to: ");
        Serial.println(topicToSubscribe);
      } else {
        Serial.print("❌ Failed, rc=");
        Serial.print(mqttClient.state());
        Serial.println(" retrying...");
      }
    }
  }
}



void callback(char* topic, byte* message, unsigned int length) {
  String msg = "";
  for (unsigned int i = 0; i < length; i++) {
    msg += (char)message[i];
  }

  int number = msg.toInt();
  latestNumber = number;       // Save number to global
  updateDisplay = true;        // Set flag to update in loop

  Serial.printf("📩 Received %d on %s\n", number, topic);
}


void drawNumber(int num) {
  display.clearDisplay(); // 👈 Add this
 display.setTextSize(2);
  display.setCursor(12, 8);
  display.setTextColor(myRED);
  display.print("NEXT ");

  Serial.printf("Patient No: %d\n", num);

  if(num<10){
  display.setCursor(88, 6 );
  }
    display.setTextSize(3);
  display.print(num);
  display.showBuffer();   // 👈 And this
}

void setup() {
  Serial.begin(115200);
  //WiFi.mode(WIFI_STA);  // Set to station mode (client)
  //WiFi.begin(ssid, password);
connectToWiFi();
  //Serial.print("📡 Connecting to WiFi");

  // while (WiFi.status() != WL_CONNECTED) {
  //   delay(500);
  //   Serial.print(".");
  // }

  // Serial.println("\n✅ Connected!");
  // Serial.print("📶 IP Address: ");
  // Serial.println(WiFi.localIP());
display.begin(16);
  display.setTextColor(myBLUE);
  display.clearDisplay();
  display_ticker.attach(0.002, display_updater);
display.setCursor(5, 1);
  display.setTextSize(2);
  display.print("MEDIBOARDS");
  display.setCursor(5, 17);
  display.print("SONVISAGE");
  display.showBuffer();
  //display.fillScreen(myRED);
display.showBuffer();
delay(3000);
  sprintf(topicToSubscribe, "clinic/display/%d", nodeID);
  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
  mqttClient.setKeepAlive(60);
  mqttClient.setCallback(callback);
  delay(6000);

  display.clearDisplay();

}

void loop() {
 if (!mqttClient.connected()) reconnectMQTT();
  mqttClient.loop();

  if (updateDisplay) {
    drawNumber(latestNumber);
    currentNumber = latestNumber;
    updateDisplay = false;
  }
}

