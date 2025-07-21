# === Extended Python Queue Manager with Full Queues and Doctor Request Handling ===
import json
from collections import deque
import paho.mqtt.client as mqtt

# MQTT broker settings
broker = 'localhost'  # Change to IP if needed
sub_topic_arrival = 'esp32/to_pi'
sub_topic_doctor_request = 'clinic/doctor/request'
pub_topic_to_esp32 = 'pi/to_esp32'
pub_topic_to_doctor = 'clinic/doctor/response'

# In-memory queues
sharedQueue = deque()
queueA = deque()
queueB = deque()

# MQTT connect callback
def on_connect(client, userdata, flags, rc):
    print("✅ Connected to MQTT Broker")
    client.subscribe(sub_topic_arrival)
    client.subscribe(sub_topic_doctor_request)
    client.subscribe("queue/debug")

    print(f"🔁 Subscribed to topics: {sub_topic_arrival}, {sub_topic_doctor_request}")

# MQTT message callback
def on_message(client, userdata, msg):
    print(f"📩 Message received on topic {msg.topic}: {msg.payload.decode()}")

    try:
        data = json.loads(msg.payload.decode())
        uid = data.get("uid")

        if msg.topic == sub_topic_arrival:
            if not uid:
                print("⚠️ No UID found in message")
                return

            if uid in queueA:
                print(f"🔁 {uid} already served. Moving to queueB")
                queueA.remove(uid)
                queueB.append(uid)
            elif uid in queueB or uid in sharedQueue:
                print(f"⏭ {uid} already in queue. Ignoring.")
                client.publish(pub_topic_to_esp32, "REJECT")
                print("✅ REJECT sent to ESP32")
            else:
                sharedQueue.append(uid)
                print(f"✅ {uid} added to sharedQueue")
                client.publish(pub_topic_to_esp32, "AUTHORIZED")
                print("✅ AUTHORIZED sent to ESP32")

        elif msg.topic == sub_topic_doctor_request:
            if len(queueB) + len(sharedQueue) > 0:
                combined = list(queueB) + list(sharedQueue)
                patient = combined[0]

                if patient in sharedQueue:
                    sharedQueue.popleft()
                    sharedQueue.insert(9, patient)  # push back
                elif patient in queueB:
                    queueB.popleft()
                    queueB.insert(9, patient)

                response = {
                    "uid": patient,
                    "timestamp": data.get("timestamp"),
                    "node": data.get("node")
                }
                client.publish(pub_topic_to_doctor, json.dumps(response))
                print(f"✅ Sent patient {patient} to doctor")
            else:
                client.publish(pub_topic_to_doctor, json.dumps({"uid": "NO_PATIENT"}))
                print("⚠️ No patients in queue")
        elif topic == "queue/debug":
            print("\n📋 Current Queue States:")
            print("🟡 sharedQueue:", list(sharedQueue))
            print("🟢 queueA (completed):", list(queueA))
            print("🔵 queueB (repeat scans):", list(queueB))
            client.publish("queue/response", json.dumps({
                "sharedQueue": list(sharedQueue),
                "queueA": list(queueA),
                "queueB": list(queueB)
        }))

    except json.JSONDecodeError:
        print("❌ Invalid JSON received")
        # View all queues (admin/debug command)
   
# Setup client and loop
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

client.connect(broker, 1883, 60)

print("🚀 Queue Manager Running. Waiting for messages...")
client.loop_forever()
