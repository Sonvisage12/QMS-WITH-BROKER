import json
from collections import deque
import paho.mqtt.client as mqtt

# MQTT broker settings
broker = 'localhost'  # Update to your actual broker IP if needed
topic_arrival_wildcard = 'esp32/arrival/+/scan'
topic_doctor_request_wildcard = 'clinic/doctor/+/request'
topic_doctor_remove_wildcard = 'clinic/doctor/+/remove'
topic_debug = 'queue/debug'

# Queues
sharedQueue = deque()
queueA = deque()
queueB = deque()

# Load UID → number mappings from file
def load_uid_mappings(filename="rfid_mappings.txt"):
    mappings = {}
    try:
        with open(filename, "r") as file:
            for line in file:
                if "=" in line:
                    uid, number = line.strip().split("=")
                    mappings[uid.strip()] = number.strip()
    except FileNotFoundError:
        print("❌ Mapping file not found!")
    return mappings

uid_mappings = load_uid_mappings()

def on_connect(client, userdata, flags, rc):
    print("✅ Connected to MQTT Broker")

    client.subscribe(topic_arrival_wildcard)
    client.subscribe(topic_doctor_request_wildcard)
    client.subscribe(topic_doctor_remove_wildcard)
    client.subscribe(topic_debug)

    print("🔁 Subscribed to:")
    print(f"   - {topic_arrival_wildcard}")
    print(f"   - {topic_doctor_request_wildcard}")
    print(f"   - {topic_doctor_remove_wildcard}")
    print(f"   - {topic_debug}")

def on_message(client, userdata, msg):
    print(f"\n📩 Topic: {msg.topic}\n📦 Payload: {msg.payload.decode()}")

    topic_parts = msg.topic.split("/")
    try:
        data = json.loads(msg.payload.decode())
        uid = data.get("uid")

        # Arrival message
        if topic_parts[0] == "esp32" and topic_parts[1] == "arrival":
            arrival_node = topic_parts[2]

            if not uid:
                print("⚠️ No UID found in arrival message")
                return

            if uid in queueA:
                print(f"🔁 {uid} already served. Moving to queueB")
                queueA.remove(uid)
                client.publish(response_topic, "AUTHORIZED")
                print(f"✅ AUTHORIZED sent to {response_topic}")
                queueB.append(uid)
            elif uid in queueB or uid in sharedQueue:
                print(f"⏭ {uid} already in queue. Ignoring.")
                response_topic = f"esp32/arrival/{arrival_node}/response"
                client.publish(response_topic, "REJECT")
                print(f"❌ REJECT sent to {response_topic}")
            else:
                sharedQueue.append(uid)
                print(f"✅ {uid} added to sharedQueue")
                response_topic = f"esp32/arrival/{arrival_node}/response"
                client.publish(response_topic, "AUTHORIZED")
                print(f"✅ AUTHORIZED sent to {response_topic}")

        # Doctor request
        elif topic_parts[0] == "clinic" and topic_parts[1] == "doctor" and topic_parts[3] == "request":
            doctor_node = topic_parts[2]
            response_topic = f"clinic/doctor/{doctor_node}/response"

            if len(queueB) + len(sharedQueue) > 0:
                combined = list(queueB) + list(sharedQueue)
                patient = combined[0]

                # Remove and re-insert at index 9
                if patient in sharedQueue:
                    sharedQueue.remove(patient)
                    sharedQueue.insert(min(9, len(sharedQueue)), patient)
                elif patient in queueB:
                    queueB.remove(patient)
                    queueB.insert(min(9, len(queueB)), patient)

                patient_number = uid_mappings.get(patient, "UNKNOWN")
                response = {
                    "uid": patient,
                    "number": patient_number,
                    "timestamp": data.get("timestamp", ""),
                    "node": doctor_node
                }
                client.publish(response_topic, json.dumps(response))
                print(f"✅ Sent patient {patient} (# {patient_number}) to doctor {doctor_node}")
            else:
                client.publish(response_topic, json.dumps({"uid": "NO_PATIENT"}))
                print(f"⚠️ No patients to send to doctor {doctor_node}")

        # Doctor removes patient
        elif topic_parts[0] == "clinic" and topic_parts[1] == "doctor" and topic_parts[3] == "remove":
            if not uid:
                print("⚠️ No UID in remove message")
                return

            if uid in sharedQueue:
                sharedQueue.remove(uid)
                queueA.append(uid)
                print(f"🗑 {uid} removed from sharedQueue → queueA")
            elif uid in queueB:
                queueB.remove(uid)
                print(f"🗑 {uid} removed from queueB permanently")
            else:
                print(f"⚠️ UID {uid} not found in queues")

        # Debug info
        elif msg.topic == "queue/debug":
            print("\n📋 Queue Status:")
            print("🟡 sharedQueue:", list(sharedQueue))
            print("🟢 queueA (completed):", list(queueA))
            print("🔵 queueB (re-scans):", list(queueB))

            client.publish("queue/response", json.dumps({
                "sharedQueue": list(sharedQueue),
                "queueA": list(queueA),
                "queueB": list(queueB)
            }))

    except json.JSONDecodeError:
        print("❌ JSON decode failed")

# MQTT setup
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.connect(broker, 1883, 60)

print("🚀 Queue Manager Running...")
client.loop_forever()
