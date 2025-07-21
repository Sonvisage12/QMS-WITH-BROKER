# this is a modify version of mqtt_queue_manager4.py with SharedQueueC based on ratio 8:6
# clear all queue
import json
import itertools
import os
from collections import deque
import paho.mqtt.client as mqtt

# ==== MQTT CONFIGURATION ====
broker = 'localhost'
topic_arrival_wildcard = 'esp32/arrival/+/scan'
topic_doctor_request_wildcard = 'clinic/doctor/+/request'
topic_doctor_remove_wildcard = 'clinic/doctor/+/remove'
topic_debug = 'queue/debug'
queue_file = "queues.json"

# ==== Queues ====
sharedQueue = deque()
queueA = deque()
queueB = deque()

def build_blended_queue(sharedQueue, queueB, ratio_shared=2, ratio_b=4):
    blended = []
    i, j = 0, 0
    while i < len(sharedQueue) or j < len(queueB):
        for _ in range(ratio_shared):
            if i < len(sharedQueue):
                blended.append(sharedQueue[i])
                i += 1
        for _ in range(ratio_b):
            if j < len(queueB):
                blended.append(queueB[j])
                j += 1
    return blended

# ==== Load UID → Number Mapping ====
def load_uid_mappings(filepath="rfid_mappings.txt"):
    mappings = {}
    try:
        with open(filepath, "r") as f:
            for line in f:
                if '=' in line:
                    uid, number = line.strip().split('=')
                    mappings[uid.strip()] = int(number.strip())
    except FileNotFoundError:
        print("⚠️ Mapping file not found.")
    return mappings

uid_mappings = load_uid_mappings()

# ==== Load Saved Queues ====
def load_queues():
    if not os.path.exists(queue_file):
        return
    try:
        with open(queue_file, "r") as f:
            data = json.load(f)
            sharedQueue.extend(data.get("sharedQueue", []))
            queueA.extend(data.get("queueA", []))
            queueB.extend(data.get("queueB", []))
            print("✅ Queues loaded from file")
    except Exception as e:
        print(f"❌ Error loading queues: {e}")

# ==== Save Queues ====
def save_queues():
    try:
        data = {
            "sharedQueue": list(sharedQueue),
            "queueA": list(queueA),
            "queueB": list(queueB)
        }
        with open(queue_file, "w") as f:
            json.dump(data, f)
    except Exception as e:
        print(f"❌ Error saving queues: {e}")

# ==== MQTT Callbacks ====
def on_connect(client, userdata, flags, rc):
    print("✅ Connected to MQTT Broker")
    client.subscribe(topic_arrival_wildcard)
    client.subscribe(topic_doctor_request_wildcard)
    client.subscribe(topic_doctor_remove_wildcard)
    client.subscribe("clinic/doctor/+/clear")
    client.subscribe(topic_debug)

    print("🔁 Subscribed to:")
    print(f"   - {topic_arrival_wildcard}")
    print(f"   - {topic_doctor_request_wildcard}")
    print(f"   - {topic_doctor_remove_wildcard}")
    print(f"   - clinic/doctor/+/clear")
    print(f"   - {topic_debug}")

def on_message(client, userdata, msg):
    print(f"\n📩 Topic: {msg.topic}\n📦 Payload: {msg.payload.decode()}")

    topic_parts = msg.topic.split("/")
    try:
        data = json.loads(msg.payload.decode())
        uid = data.get("uid")

        # ==== ARRIVAL ====
        if topic_parts[0] == "esp32" and topic_parts[1] == "arrival":
            arrival_node = topic_parts[2]

            if not uid:
                print("⚠️ No UID found in arrival message")
                return

            if uid in queueA:
                print(f"🔁 {uid} already served. Moving to queueB")
                queueA.remove(uid)
                queueB.append(uid)
                save_queues()
                response_topic = f"esp32/arrival/{arrival_node}/response"
                client.publish(response_topic, "AUTHORIZED")
                print(f"✅ AUTHORIZED sent to {response_topic}")

            elif uid in queueB or uid in sharedQueue:
                print(f"⏭ {uid} already in queue. Ignoring.")
                response_topic = f"esp32/arrival/{arrival_node}/response"
                client.publish(response_topic, "REJECT")
                print(f"❌ REJECT sent to {response_topic}")

            else:
                sharedQueue.append(uid)
                save_queues()
                print(f"✅ {uid} added to sharedQueue")
                response_topic = f"esp32/arrival/{arrival_node}/response"
                client.publish(response_topic, "AUTHORIZED")
                print(f"✅ AUTHORIZED sent to {response_topic}")

        # ==== DOCTOR REQUEST ====
        elif topic_parts[0] == "clinic" and topic_parts[1] == "doctor" and topic_parts[3] == "request":
            doctor_node = topic_parts[2]
            response_topic = f"clinic/doctor/{doctor_node}/response"

            blendedQueue = build_blended_queue(list(sharedQueue), list(queueB))
            if blendedQueue:
                patient = blendedQueue[0]

                if patient in sharedQueue:
                    sharedQueue.remove(patient)
                    sharedQueue.insert(min(9, len(sharedQueue)), patient)
                    patient_queue = "sharedQueue"
                elif patient in queueB:
                    queueB.remove(patient)
                    queueB.insert(min(9, len(queueB)), patient)
                    patient_queue = "queueB"
                else:
                    patient_queue = "unknown"

                save_queues()

                mapped_number = uid_mappings.get(patient, -1)
                response = {
                    "uid": patient,
                    "number": mapped_number,
                    "queue": patient_queue,
                    "timestamp": data.get("timestamp", ""),
                    "node": doctor_node
                }

                client.publish(response_topic, json.dumps(response))
                print(f"✅ Sent patient {patient} (#{mapped_number}) from {patient_queue} to doctor {doctor_node}")
            else:
                client.publish(response_topic, json.dumps({"uid": "NO_PATIENT"}))
                print(f"⚠️ No patients to send to doctor {doctor_node}")


        # ==== DOCTOR REMOVES PATIENT ====
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
                print(f"🗑 {uid} removed from queueB")
            save_queues()
        # ==== Clear all queue ====
        elif topic_parts[0] == "clinic" and topic_parts[1] == "doctor" and topic_parts[3] == "clear":
            sharedQueue.clear()
            queueA.clear()
            queueB.clear()
            save_queues()
            print(f"🧹 Doctor node {topic_parts[2]} requested queue clear. All queues cleared.")
            client.publish(f"clinic/doctor/{topic_parts[2]}/response", json.dumps({"status": "queues_cleared"}))

        # ==== DEBUG QUEUE STATUS ====
        elif msg.topic == "queue/debug":
            print("\n📋 Queue Status:")
            print("🟡 sharedQueue:", list(sharedQueue))
            print("🟢 queueA (completed):", list(queueA))
            print("🔵 queueB (re-scans):", list(queueB))

            client.publish("queue/response", json.dumps({
                "sharedQueue": list(sharedQueue),
                "queueA": list(queueA),
                "queueB": list(queueB),
                "sizes": {
                    "sharedQueue": len(sharedQueue),
                    "queueA": len(queueA),
                    "queueB": len(queueB)
                }
            }))

    except json.JSONDecodeError:
        print("❌ JSON decode failed")

# ==== MQTT Client Setup ====
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.connect(broker, 1883, 60)

# ==== Start ====
load_queues()
print("🚀 Queue Manager Running...")
client.loop_forever()
