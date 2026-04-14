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
client.connect("localhost", 1883)
client.subscribe("dock/dock1/commands")
client.loop_start()

START_LAT = -32.895083
START_LON = 146.080528

prev_lat = None
prev_lon = None
t = 0
start_wall_time = time.time()

FLIGHT_RADIUS_DEG = 0.0008
BATTERY_DRAIN_MINUTES = 18.0

while True:
    altitude = 40.0 + 10.0 * math.sin(t / 14)
    vertical_speed = round(10.0 * math.cos(t / 14) * (1.0 / 14.0), 2)

    speed_target = 7.5 + 2.5 * math.sin(t / 10)

    # slightly more accurate roll, didn't use in pres due to larger variations in alt etc.
    # omega = (1.0 / 20.0)
    # roll  = round(math.degrees(math.atan((speed_target * omega) / 9.81)), 2)

    # gentle drift stays near centre
    roll = round(1.0 * math.sin(t / 6.0) + 0.5 * math.sin(t / 2.1), 2)

    # slightly more accurate pitch, didn't use in pres due to larger variations in alt etc.
    # cruise_pitch = -math.degrees(math.atan(speed_target / 9.81)) * 0.20
    # climb_pitch  = math.atan2(vertical_speed, speed_target) * (180.0 / math.pi)
    # pitch = round(cruise_pitch + climb_pitch, 2)

    # gentle drift stays near centre
    pitch = round(1.0 * math.sin(t / 6.0) + 0.5 * math.sin(t / 2.1), 2)

    lat = START_LAT + FLIGHT_RADIUS_DEG * math.sin(t / 20)
    lon = START_LON + FLIGHT_RADIUS_DEG * math.cos(t / 20)

    elapsed_seconds = int(time.time() - start_wall_time)
    elapsed_str = "{:02d}:{:02d}:{:02d}".format(
        elapsed_seconds // 3600,
        (elapsed_seconds % 3600) // 60,
        elapsed_seconds % 60
    )

    elapsed_minutes = elapsed_seconds / 60.0
    battery = max(0.0, 100.0 - elapsed_minutes * (100.0 / BATTERY_DRAIN_MINUTES))
    battery_min = max(0.0, battery / (100.0 / BATTERY_DRAIN_MINUTES))

    wind_speed = 3.5 + 1.5 * math.sin(t / 40) + 0.3 * math.sin(t / 7)
    wind_speed = max(0.0, wind_speed)
    wind_direction = (170 + 15 * math.sin(t / 50) + 5 * math.sin(t / 12)) % 360

    if prev_lat is not None and prev_lon is not None:
        dLon = math.radians(lon - prev_lon)
        lat1 = math.radians(prev_lat)
        lat2 = math.radians(lat)

        x = math.sin(dLon) * math.cos(lat2)
        y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dLon)
        heading = (math.degrees(math.atan2(x, y)) + 360) % 360

        R = 6371000
        dLat = math.radians(lat - prev_lat)
        a = math.sin(dLat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dLon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        raw_speed = (R * c) / 0.1

        speed = speed_target
    else:
        heading = 0
        speed = 0

    telemetry = {
        "lat": round(lat, 6),
        "lon": round(lon, 6),
        "altitude": round(altitude, 2),
        "vertical_speed": vertical_speed,
        "battery": round(battery, 2),
        "heading": round(heading, 2),
        "pitch": pitch,
        "roll":  roll,
        "speed_mps": round(speed, 2),
        "wind_speed_mps": round(wind_speed, 2),
        "wind_direction_deg": round(wind_direction, 2),
        "battery_min": round(battery_min, 2),
        "time_elapsed": elapsed_str
    }

    client.publish(
        "dock/dock1/drone/telemetry",
        json.dumps(telemetry)
    )

    prev_lat = lat
    prev_lon = lon

    t += 0.1
    time.sleep(0.1)
