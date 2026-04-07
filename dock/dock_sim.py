import paho.mqtt.client as mqtt
import subprocess
import json
import time
import os
import math
import random

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

prev_lat = None
prev_lon = None
t = 0

while True:
    lat = -33.86 + 0.001 * math.sin(t)
    lon = 151.20 + 0.001 * math.cos(t)
    altitude = 60 + 5 * math.sin(t / 2)
    
    battery = 100 - ((t * 0.2) % 100)
    battery_min = battery * 5

    # --- WIND SIMULATION ---
    wind_direction = (60 + (4 + 3 * math.sin(t / 3) + 2 * math.sin(t * 2))) % 360

    wind_speed = 4 + 3 * math.sin(t / 3) + 0.5 * math.sin(t * 2)

    wind_speed = max(0, wind_speed)

    if prev_lat is not None and prev_lon is not None:
        # --- HEADING ---
        dLon = math.radians(lon - prev_lon)
        lat1 = math.radians(prev_lat)
        lat2 = math.radians(lat)

        x = math.sin(dLon) * math.cos(lat2)
        y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dLon)

        heading = (math.degrees(math.atan2(x, y)) + 360) % 360

        # --- SPEED ---
        R = 6371000  

        dLat = math.radians(lat - prev_lat)
        dLon = math.radians(lon - prev_lon)

        a = math.sin(dLat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dLon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

        distance = R * c 
        speed = distance / 0.1  

    else:
        heading = 0
        speed = 0

    telemetry = {
        "lat": round(lat, 6),
        "lon": round(lon, 6),
        "altitude": round(altitude, 2),
        "battery": round(battery, 2),
        "heading": round(heading, 2),
        "speed_mps": round(speed, 2),
        "wind_speed_mps": round(wind_speed, 2),
        "wind_direction_deg": round(wind_direction, 2),
        "battery_min": round(battery, 2)
    }

    client.publish(
        "dock/dock1/drone/telemetry",
        json.dumps(telemetry)
    )

    prev_lat = lat
    prev_lon = lon

    t += 0.1
    time.sleep(0.1)