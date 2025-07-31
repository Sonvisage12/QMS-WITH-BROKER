# this is a modify version of mqtt_queue_manager4.py with SharedQueueC based on ratio 8:6
# clear all queue
# with full solenoid feedback
import json
import itertools
import os
from collections import deque
import paho.mqtt.client as mqtt
import threading
import time
from datetime import datetime 
solenoid_timers = {}  # Track timers per node
solenoid_states = {} 

k =0
n =0
lenB=10
lenA=10
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


def build_blended_queue(sharedQueue, queueB):
    blended = []
    i, j = 0, 0  # indices for sharedQueue and queueB

    while i < len(sharedQueue) or j < len(queueB):
        # Take up to 10 from queueB
        for _ in range(10):
            if j < len(queueB):
                blended.append(queueB[j])
                j += 1

        # Take up to 5 from sharedQueue
        for _ in range(5):
            if i < len(sharedQueue):
                blended.append(sharedQueue[i])
                i += 1

    return blended
def build_blended_queue1(sharedQueue, queueB):
    blended = []
    i, j = 0, 0  # indices for sharedQueue and queueB

    while i < len(sharedQueue) or j < len(queueB):
        # Take up to 5 from sharedQueue
        for _ in range(5):
            if i < len(sharedQueue):
                blended.append(sharedQueue[i])
                i += 1
        # Take up to 10 from queueB
        for _ in range(10):
            if j < len(queueB):
                blended.append(queueB[j])
                j += 1


    return blended
def daily_queue_reset():
    while True:
        now = datetime.now()
        print("🕒 Checking time:", now.strftime("%Y-%m-%d %H:%M:%S"))  # Add this line
        if now.hour == 14 and now.minute == 21:
            print("🧹 It's 4:05 AM — clearing all queues...")
            sharedQueue.clear()
            queueA.clear()
            queueB.clear()
            save_queues()
            print("✅ Queues cleared at 10:05 AM.")
            for doc_id in ["1", "2", "3", "4"]:
                # Display shows 0
                client.publish(f"clinic/display/{doc_id}/number", json.dumps({"number": 0}))
                print(f"📺 Sent 0 to clinic/display/{doc_id}/number")

                # Shared display update
                client.publish("clinic/display/all", json.dumps({
                    "number": 0,
                    "doctor": doc_id
                }))
                print(f"📺 Broadcasted 0 to shared display for doctor {doc_id}")

                # Notify doctor node
                client.publish(f"clinic/doctor/{doc_id}/response", json.dumps({
                    "uid": "NO_PATIENT",
                    "number": 0,
                    "doctor": doc_id
                }))
                print(f"📨 Sent NO_PATIENT to clinic/doctor/{doc_id}/response")

            time.sleep(60)  # Prevent multiple clears
        time.sleep(10)

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
    client.subscribe("clinic/solenoid/control")
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
            display_topic = f"clinic/display/{doctor_node}/number"  # NEW
            global k, n, lenB, lenA
            if n==0:
                if len(queueB)< 10:
                    lenB=len(queueB)
                elif len(sharedQueue) <10:
                    len(sharedQueue)
                
            if uid == "REQ_BREAK":
                  print(f"⏸ Doctor node {doctor_node} requested BREAK — sending 0 to display.")
              
                  client.publish(f"clinic/display/{doctor_node}/number", json.dumps({"number": 0}))
                  print(f"📺 Sent 0 to clinic/display/{doctor_node}/number")
              
                  client.publish("clinic/display/all", json.dumps({
                      "number": 0,
                      "doctor": doctor_node
                  }))
                  print(f"📺 Broadcasted 0 to shared display for doctor {doctor_node}")
              
                  client.publish(f"clinic/doctor/{doctor_node}/response", json.dumps({
                      "uid": "BREAK",
                      "number": 0,
                      "doctor": doctor_node
                  }))
                  print(f"📨 Sent NO_PATIENT to clinic/doctor/{doctor_node}/response")
              
                  return  # Exit early so the rest of the logic doesn't run



            k +=1
            print(k)

            if k>lenB:
                blendedQueue = build_blended_queue(list(sharedQueue), list(queueB))
            else:
                blendedQueue = build_blended_queue1(list(sharedQueue), list(queueB))
                
            if blendedQueue:
                patient = blendedQueue[0]
             
                
                if patient in sharedQueue:
                    sharedQueue.remove(patient)
                    sharedQueue.insert(min(20, len(sharedQueue)), patient)
                    patient_queue = "sharedQueue"
                elif patient in queueB:
                    queueB.remove(patient)
                    queueB.insert(min(16, len(queueB)), patient)
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
                client.publish(display_topic, json.dumps({"number": mapped_number}))
                print(f"📺 Display update sent to {display_topic}: #{mapped_number}")
                
                client.publish("clinic/display/all", json.dumps({
                "number": mapped_number,
                "doctor": doctor_node
                }))
                print(f"📺 Broadcast sent to shared display for doctor {doctor_node}: #{mapped_number}")
                if k>20:
                    k=0;
                    n=0;
            else:
          
                client.publish(response_topic, json.dumps({"uid": "NO_PATIENT"}))
                print(f"⚠️ No patients to send to doctor {doctor_node}")

                # 🔄 Broadcast "0" to all individual doctor display topics
                for doc_id in ["1", "2", "3", "4"]:
                    client.publish(f"clinic/display/{doc_id}/number", json.dumps({"number": 0}))
                    print(f"📺 Sent 0 to clinic/display/{doc_id}/number")

                # 🖥 Send "0" for all doctors to shared summary display
                for doc_id in ["1", "2", "3", "4"]:
                    client.publish("clinic/display/all", json.dumps({
                        "number": 0,
                        "doctor": doc_id
                    }))
                    print(f"📺 Broadcasted 0 to shared display for doctor {doc_id}")

                # 👨‍⚕️ Notify all doctor nodes as well
                for doc_id in ["1", "2", "3", "4"]:
                    client.publish(f"clinic/doctor/{doc_id}/response", json.dumps({
                        "uid": "NO_PATIENT",
                        "number": 0,
                        "doctor": doc_id
                    }))
                    print(f"📨 Sent NO_PATIENT to clinic/doctor/{doc_id}/response")

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
            for doc_id in ["1", "2", "3", "4"]:
                # Display shows 0
                client.publish(f"clinic/display/{doc_id}/number", json.dumps({"number": 0}))
                print(f"📺 Sent 0 to clinic/display/{doc_id}/number")

                # Shared display update
                client.publish("clinic/display/all", json.dumps({
                    "number": 0,
                    "doctor": doc_id
                }))
                print(f"📺 Broadcasted 0 to shared display for doctor {doc_id}")

                # Notify doctor node
                client.publish(f"clinic/doctor/{doc_id}/response", json.dumps({
                    "uid": "NO_PATIENT",
                    "number": 0,
                    "doctor": doc_id
                }))
                print(f"📨 Sent NO_PATIENT to clinic/doctor/{doc_id}/response")

         
        elif msg.topic == "clinic/solenoid/control":
            try:
                data = json.loads(msg.payload.decode())
                node = str(data.get("node"))
                action = data.get("solenoid", "OFF")
                if node and action in ["ON", "OFF"]:
                    target_topic = f"solenoid/node/{node}"
                    client.publish(target_topic, json.dumps({"action": action}))
                    print(f"🔁 Forwarded solenoid control to {target_topic}: {action}")

                    # Save solenoid state
                    solenoid_states[node] = action

                    # Cancel any existing timer
                    if node in solenoid_timers:
                        solenoid_timers[node].cancel()

                    if action == "ON":
                        # Start auto-OFF timer (10 mins)
                        def auto_off():
                            solenoid_states[node] = "OFF"
                            client.publish(target_topic, json.dumps({"action": "OFF"}))
                            print(f"⏱ Solenoid {node} auto-OFF triggered")

                            # Notify doctor node
                            doctor_response_topic = f"clinic/doctor/{node}/response"
                            client.publish(doctor_response_topic, json.dumps({
                                "uid": "SOLENOID",
                                "number": 0
                            }))
                            print(f"📨 Sent solenoid OFF state to doctor {node}")

                        timer = threading.Timer(15, auto_off)  # 600 seconds = 10 minutes
                        solenoid_timers[node] = timer
                        timer.start()
            except json.JSONDecodeError:
                print("❌ JSON parse failed for solenoid control")

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
# Start daily reset thread
threading.Thread(target=daily_queue_reset, daemon=True).start()

print("🚀 Queue Manager Running...")
client.loop_forever()
