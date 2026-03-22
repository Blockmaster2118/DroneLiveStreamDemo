import paho.mqtt.client as mqtt
import subprocess
import json
import time
import os
import math

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

ffmpeg_path = os.path.join(PROJECT_ROOT, "bin", "ffmpeg.exe")
video_path  = os.path.join(PROJECT_ROOT, "media", "drone_test.mp4")

stream_process = None
audio_process = None

def on_message(client, userdata, msg):
    global stream_process, audio_process

    command = json.loads(msg.payload)

    # VIDEO
    if command["action"] == "start_stream":
        stream_process = subprocess.Popen([
            ffmpeg_path,
            "-re",
            "-stream_loop", "-1",
            "-i", video_path,
            "-c:v", "copy",
            "-an",
            "-f", "rtsp",
            "-rtsp_transport", "udp",
            "rtsp://localhost:8554/dock1_stream"
        ])

    elif command["action"] == "stop_stream":
        if stream_process:
            stream_process.terminate()
            stream_process.wait()
            stream_process = None

    # AUDIO
    elif command["action"] == "start_audio":
        audio_process = subprocess.Popen([
            ffmpeg_path,
            "-re",
            "-stream_loop", "-1",
            "-i", os.path.join(PROJECT_ROOT, "media", "radio_test.mp3"),
            "-c:a", "aac",
            "-b:a", "128k",
            "-f", "rtsp",
            "-rtsp_transport", "udp",
            "rtsp://localhost:8554/dock1_audio"
        ])

    elif command["action"] == "stop_audio":
        if audio_process:
            audio_process.terminate()
            audio_process.wait()
            audio_process = None

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

client.on_message = on_message

client.connect("localhost",1883)

client.subscribe("dock/dock1/commands")

client.loop_start()

t = 0

while True:
    lat = -33.86 + 0.001 * math.sin(t)
    lon = 151.20 + 0.001 * math.cos(t)
    altitude = 60 + 5 * math.sin(t / 2)
    
    battery = 100 - ((t * 0.2) % 100)

    telemetry = {
        "lat": round(lat, 6),
        "lon": round(lon, 6),
        "altitude": round(altitude, 2),
        "battery": round(battery, 2)
    }

    client.publish(
        "dock/dock1/drone/telemetry",
        json.dumps(telemetry)
    )

    t += 0.1
    time.sleep(0.1)