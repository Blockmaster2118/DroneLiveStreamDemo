import paho.mqtt.client as mqtt
import subprocess
import json
import time
import os

# get project root (assuming this file is /dock/dock_sim.py)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

ffmpeg_path = os.path.join(PROJECT_ROOT, "bin", "ffmpeg.exe")
video_path  = os.path.join(PROJECT_ROOT, "media", "drone_test.mp4")

stream_process = None

def on_message(client, userdata, msg):
    global stream_process

    command = json.loads(msg.payload)

    if command["action"] == "start_stream":
        
        stream_process = subprocess.Popen([
            ffmpeg_path,
            "-re",
            "-stream_loop", "-1",
            "-i", video_path,
            "-c:v", "copy",
            "-an",
            "-f", "rtsp",
            "-rtsp_transport", "tcp",
            "rtsp://localhost:8554/dock1_stream"
        ])

    if command["action"] == "stop_stream":
        if stream_process:
            stream_process.kill()

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

client.on_message = on_message

client.connect("localhost",1883)

client.subscribe("dock/dock1/commands")

client.loop_start()

while True:

    telemetry = {
        "lat": -33.86,
        "lon": 151.20,
        "altitude": 60,
        "battery": 85
    }

    client.publish(
        "dock/dock1/drone/telemetry",
        json.dumps(telemetry)
    )

    time.sleep(1)