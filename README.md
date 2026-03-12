# DJI Dock Simulation Environment

This project simulates a simplified version of a **DJI Dock style drone system** using MQTT telemetry, an API interface, and RTSP video streaming.

The simulator demonstrates how a backend system can control a remote drone dock, start a livestream, and receive telemetry data.

The architecture loosely mirrors the behaviour of systems controlled through the DJI Cloud API.

---

# Architecture

```
Client/API Request
        ↓
Node.js API Server
        ↓
MQTT Command
        ↓
Dock Simulator (Python)
        ↓
FFmpeg Video Stream
        ↓
MediaMTX RTSP Server
        ↓
RTSP Viewer (VLC etc.)
```

The dock simulator publishes telemetry data and listens for commands to start or stop the video stream.

---


# Project Components

| File | Description |
|-----|-------------|
| `api_sim.js` | Simulated API server that sends commands to the dock |
| `dock_sim.py` | Simulated dock that publishes telemetry and launches FFmpeg |
| `drone_test.mp4` | Sample drone video used for the livestream |
| `mediamtx.exe` | RTSP server used to distribute the stream |
| `ffmpeg.exe` | Used to push the simulated video stream |

---

## Folder Structure

- `/api/` → Node.js API simulator
- `/dock/` → Python dock simulator
- `/media/` → Sample video files
- `/bin/` → FFmpeg and MediaMTX binaries

# Dependencies

The following software must be installed:

## 1. Node.js

Required to run the API server.

https://nodejs.org/

Verify installation:

```
node -v
npm -v
```

Install required packages:

```
npm install express mqtt
```

---

## 2. Python 3

Required for the dock simulator.

https://www.python.org/

Install required Python package:

```
pip install paho-mqtt
```

---

## 3. MQTT Broker

This project uses **Mosquitto**.

https://mosquitto.org/download/

Start the broker:

```
mosquitto
```

---

## 4. FFmpeg

Used to stream the simulated drone video.

https://ffmpeg.org/download.html

Place `ffmpeg.exe` in the project directory or add it to your system PATH.

---

## 5. MediaMTX (RTSP Server)

Used to distribute the livestream.

https://github.com/bluenviron/mediamtx

Start the server:

```
mediamtx
```

---

# Starting the Simulation

Start each component in separate terminals.

---

## 1. Start MQTT Broker

```
mosquitto
```

---

## 2. Start MediaMTX

```
mediamtx
```

---

## 3. Start Dock Simulator

```
python dock_sim.py
```

The dock simulator will begin publishing telemetry data.

---

## 4. Start API Server

```
node api_sim.js
```

---

# Starting the Livestream

Send a request to the API:

```
POST http://localhost:3000/livestream/start
```

Example using curl:

```
curl -X POST http://localhost:3000/livestream/start
```

The API will trigger the dock simulator to start streaming.

---

# Viewing the Stream

Open the stream in VLC or another RTSP client:

```
rtsp://localhost:8554/dock1_stream
```

---

# Telemetry Topic

Telemetry is published via MQTT on:

```
dock/dock1/drone/telemetry
```

Example telemetry message:

```json
{
  "lat": -33.86,
  "lon": 151.20,
  "altitude": 60,
  "battery": 85
}
```

---

# Commands Topic

Commands are received on:

```
dock/dock1/commands
```

Example command:

```json
{
  "action": "start_stream"
}
```

---

# Notes

- This is a **simulation environment** and does not interact with real drone hardware.
- The implementation demonstrates the core architecture used in dock-controlled drone systems.
- Demo latency will depend on local network conditions and RTSP client buffering.

---# DroneLiveStreamDemo