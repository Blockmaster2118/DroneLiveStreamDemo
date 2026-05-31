# DJI Dock Simulation Environment

This project simulates a simplified **DJI Dock-style drone platform** using MQTT, a REST API interface, a realistic flight model, and livestreaming services.

The simulator demonstrates how a backend system can:

- Control a remote drone dock
- Launch and stop livestreams
- Execute flight commands
- Monitor telemetry in real time
- Track mission state changes
- Simulate battery consumption and charging

The architecture loosely mirrors systems controlled through the DJI Cloud API.

---

# Architecture

```text
Client / API Request
        ↓
Node.js API Server
        ↓
MQTT Commands
        ↓
Dock Simulator (Python)
        ├── Flight Controller Simulation
        ├── Telemetry Publisher
        ├── Battery & Wind Simulation
        ├── FFmpeg Video Stream
        └── FFmpeg Audio Stream
        ↓
MediaMTX
        ↓
HLS / RTSP Stream
        ↓
Client Viewer
(VLC, Browser, Apple Vision Pro, etc.)
```

---

# Features

### Livestream Simulation

- Video streaming via FFmpeg
- Audio streaming via FFmpeg
- RTSP distribution through MediaMTX
- HLS playback support
- Stream status published via MQTT

### Flight Simulation

- Takeoff
- Fly-to waypoint
- Hold position
- Manual movement
- Return-to-home (RTH)
- Landing

### Telemetry Simulation

- GPS position
- Altitude
- Heading
- Horizontal speed
- Vertical speed
- Pitch
- Roll
- Wind speed
- Wind direction
- Battery percentage
- Estimated remaining flight time
- Flight phase
- Mission elapsed time

### Event Notifications

Flight events are published automatically:

- Takeoff complete
- Waypoint reached
- Landing complete
- Flight phase changes

---

# Project Components

| File | Description |
|--------|-------------|
| `api_sim.js` | Simulated API server |
| `dock_sim.py` | Drone dock and flight simulator |
| `telemetry_viewer.py` | Real-time telemetry dashboard |
| `drone_test.mp4` | Sample drone video |
| `radio_test.mp3` | Sample radio/audio feed |
| `mediamtx` | Media streaming server |
| `ffmpeg` | Video/audio streaming engine |

---

# MQTT Topics

## Telemetry

Published continuously:

```text
dock/dock1/drone/telemetry
```

Example:

```json
{
  "lat": -33.560000,
  "lon": 148.955000,
  "altitude": 40.0,
  "heading": 180.0,
  "speed_mps": 8.0,
  "battery": 82.4,
  "phase": "flying_to"
}
```

Update rate:

```text
~20 Hz
```

---

## Flight Commands

Commands are sent to:

```text
dock/dock1/flight
```

### Takeoff

```json
{
  "action": "takeoff",
  "altitude": 40
}
```

### Fly To Coordinate

```json
{
  "action": "fly_to",
  "lat": -33.561,
  "lon": 148.956,
  "speed": 8
}
```

### Hold Position

```json
{
  "action": "hold"
}
```

### Manual Move

```json
{
  "action": "manual_move",
  "forward_m": 10,
  "right_m": 0,
  "up_m": 0,
  "yaw_deg": 0
}
```

### Return To Home

```json
{
  "action": "rth"
}
```

### Land

```json
{
  "action": "land"
}
```

### Cancel Active Navigation

```json
{
  "action": "cancel_fly_to"
}
```

---

## Flight Status Events

Published on:

```text
dock/dock1/flight_status
```

### Phase Change

```json
{
  "event": "phase_changed",
  "phase": "flying_to"
}
```

### Takeoff Complete

```json
{
  "event": "takeoff_done"
}
```

### Waypoint Reached

```json
{
  "event": "node_arrived"
}
```

### Landing Complete

```json
{
  "event": "landed"
}
```

---

## Stream Control Commands

Published to:

```text
dock/dock1/commands
```

### Start Video Stream

```json
{
  "action": "start_stream"
}
```

### Stop Video Stream

```json
{
  "action": "stop_stream"
}
```

### Start Audio Stream

```json
{
  "action": "start_audio"
}
```

### Stop Audio Stream

```json
{
  "action": "stop_audio"
}
```

---

## Stream Status

Published on:

```text
dock/dock1/stream_status
```

Example:

```json
{
  "status": "streaming",
  "stream_url": "http://192.168.1.100:8888/dock1_stream/index.m3u8"
}
```

---

# Viewing the Stream

## HLS Stream

Recommended for browser-based clients and Apple Vision Pro:

```text
http://<host-ip>:8888/dock1_stream/index.m3u8
```

## RTSP Video

```text
rtsp://localhost:8554/dock1_stream
```

## RTSP Audio

```text
rtsp://localhost:8554/dock1_audio
```

---

# Simulated Flight Model

The simulator includes:

- Smooth acceleration and deceleration
- Heading/yaw transitions
- Climb and descent rates
- Return-to-home behaviour
- Battery discharge while flying
- Battery charging while docked
- Dynamic wind conditions
- Mission timer tracking

Flight phases:

```text
idle
taking_off
holding
yawing_to
flying_to
manual_move
rth_turning
rth_flying
rth_facing_home
landing
```

---

# Notes

- This is a simulation environment and does not interact with real DJI hardware.
- Flight behaviour is intentionally simplified but follows realistic operational concepts.
- Stream URLs are published automatically through MQTT when streaming starts.
- The simulator can be used as a backend test environment for cloud-controlled drone applications.
- HLS streaming is recommended for remote clients and browser-based viewing.