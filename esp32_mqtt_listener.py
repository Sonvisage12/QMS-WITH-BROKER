import paho.mqtt.client as mqtt

# MQTT broker settings
broker = 'localhost'  # or use your Pi's IP if ESP32 is connecting to it remotely
topic_sub = 'esp32/to_pi'
topic_pub = 'pi/to_esp32'

# When connected
def on_connect(client, userdata, flags, rc):
    print("✅ Connected to MQTT Broker")
    client.subscribe(topic_sub)
    print(f"🔁 Subscribed to topic: {topic_sub}")

# When a message is received
def on_message(client, userdata, msg):
    print(f"📩 Message received on topic {msg.topic}: {msg.payload.decode()}")

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

client.connect(broker, 1883, 60)

# Start listening in background
client.loop_start()

print("🚀 Listening for ESP32 messages...")

# Send messages manually to ESP32
try:
    while True:
        message = input("💬 Enter message to send to ESP32 (or type 'exit' to quit): ")
        if message.lower() == 'exit':
            break
        client.publish(topic_pub, message)
        print(f"✅ Sent to ESP32: {message}")
except KeyboardInterrupt:
    print("\n👋 Exiting...")

client.loop_stop()
client.disconnect()
