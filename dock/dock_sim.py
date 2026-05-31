import paho.mqtt.client as mqtt
import subprocess
import json
import time
import os
import math
import threading

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

_local_ffmpeg = os.path.join(PROJECT_ROOT, "bin", "ffmpeg")
ffmpeg_path = _local_ffmpeg if os.path.isfile(_local_ffmpeg) else "ffmpeg"
video_path  = os.path.join(PROJECT_ROOT, "media", "drone_test.mp4")

# STREAM_HOST is the address clients use to reach the HLS stream.
# Set to the Mac's LAN IP via the launcher so remote devices (e.g. Vision Pro)
# can resolve it. Falls back to localhost for local testing without the launcher.
STREAM_HOST = os.environ.get("STREAM_HOST", "localhost")

stream_process = None
audio_process  = None

DOCK_LAT = -33.560
DOCK_LON = 148.955

CLIMB_RATE     = 2.0
DESCENT_RATE   = 1.5
CRUISE_SPEED   = 8.0
YAW_RATE       = 45.0
ACCEL_RATE     = 1.5
DECEL_RATE     = 2.5
MANUAL_SPEED   = 3.0
ARRIVAL_THRESH = 1.0
YAW_THRESH     = 0.3
STOP_THRESH    = 0.05
BATTERY_DRAIN  = 100.0 / (40.0 * 60)
BATTERY_CHARGE = 100.0 / (18.0 * 60)

TICK = 0.025
PUBLISH_EVERY = 2

# NOTE: state_lock is acquired in both the main loop (physics_tick) and the MQTT
# callback (on_flight_command). This is safe right now because we use loop(timeout=0)
# which processes MQTT events on the main thread — there is no background MQTT thread.
# If this is ever changed to loop_start(), the two threads would contend on state_lock
# and the current structure would need to be reviewed carefully.
state_lock = threading.Lock()

state = {
    "lat":          DOCK_LAT,
    "lon":          DOCK_LON,
    "altitude":     0.0,
    "heading":      0.0,
    "speed_mps":    0.0,
    "vertical_speed": 0.0,
    "pitch":        0.0,
    "roll":         0.0,
    "battery":      100.0,
    "battery_min":  18.0,
    "wind_speed_mps":    3.5,
    "wind_direction_deg": 170.0,
    "wind_t":       0.0,
    "elapsed_seconds": 0.0,

    "phase":           "idle",
    "active_bearing":  0.0,
    "active_speed":        8.0,
    "active_manual_speed":  3.0,
    "active_rth_speed":     8.0,
    "active_decel":    2.5,
    "target_lat":      DOCK_LAT,
    "target_lon":      DOCK_LON,
    "target_altitude": 0.0,
    "target_heading":  0.0,

    "manual_north_remain": 0.0,
    "manual_east_remain":  0.0,
    "manual_up_remain":    0.0,

    "_pending":   None,
    "_cancelled":            False,
    "_pending_node_arrived": False,
}

# ---------------------------------------------------------------------------
# Geo helpers
# ---------------------------------------------------------------------------

def geo_bearing(from_lat, from_lon, to_lat, to_lon):
    lat1 = math.radians(from_lat)
    lat2 = math.radians(to_lat)
    dlon = math.radians(to_lon - from_lon)
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360

def distance_m(lat1, lon1, lat2, lon2):
    mp_lat = 111_320.0
    mp_lon = 111_320.0 * math.cos(math.radians(lat1))
    dn = (lat2 - lat1) * mp_lat
    de = (lon2 - lon1) * mp_lon
    return math.sqrt(dn * dn + de * de)

def move_by_metres(lat, lon, north_m, east_m):
    new_lat = lat + north_m / 111_320.0
    lon_scale = 111_320.0 * math.cos(math.radians(lat))
    new_lon = lon + (east_m / lon_scale if lon_scale != 0 else 0)
    return new_lat, new_lon

def shortest_delta(current, target):
    d = (target - current + 360) % 360
    return d - 360 if d > 180 else d

def yaw_step(current, target, dt):
    delta = shortest_delta(current, target)
    if abs(delta) <= YAW_THRESH:
        return target
    step = math.copysign(min(abs(delta), YAW_RATE * dt), delta)
    return (current + step) % 360

def step_toward(current, target, max_step):
    delta = target - current
    if abs(delta) <= max_step:
        return target
    return current + math.copysign(max_step, delta)

# ---------------------------------------------------------------------------
# MQTT message routing
# ---------------------------------------------------------------------------

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload)
    except Exception:
        return

    if msg.topic == "dock/dock1/commands":
        handle_stream_command(client, payload)
    elif msg.topic == "dock/dock1/flight":
        handle_flight_command(payload)

def handle_stream_command(client, payload):
    global stream_process, audio_process

    action = payload.get("action", "")

    if action == "start_stream":
        stream_process = subprocess.Popen([
            ffmpeg_path,
            "-re", "-stream_loop", "-1", "-i", video_path,
            "-c:v", "libx264", "-preset", "veryfast",
            "-tune", "zerolatency",
            "-x264-params", "keyint=60:min-keyint=60:scenecut=0",
            "-b:v", "4000k", "-an",
            "-f", "rtsp", "-rtsp_transport", "tcp",
            "rtsp://localhost:8554/dock1_stream"
        ])
        time.sleep(1.5)
        client.publish(
            "dock/dock1/stream_status",
            json.dumps({"status": "streaming",
                        "stream_url": f"http://{STREAM_HOST}:8888/dock1_stream/index.m3u8"}),
            retain=True
        )

    elif action == "stop_stream":
        if stream_process:
            stream_process.terminate(); stream_process.wait()
            stream_process = None
        client.publish("dock/dock1/stream_status",
                       json.dumps({"status": "stopped", "stream_url": None}), retain=True)

    elif action == "start_audio":
        audio_process = subprocess.Popen([
            ffmpeg_path, "-re", "-stream_loop", "-1",
            "-i", os.path.join(PROJECT_ROOT, "media", "radio_test.mp3"),
            "-c:a", "aac", "-b:a", "128k",
            "-f", "rtsp", "-rtsp_transport", "udp",
            "rtsp://localhost:8554/dock1_audio"
        ])

    elif action == "stop_audio":
        if audio_process:
            audio_process.terminate(); audio_process.wait()
            audio_process = None

def handle_flight_command(payload):
    action = payload.get("action", "")
    log_command(action)
    with state_lock:
        _apply_flight_command(action, payload)

# ---------------------------------------------------------------------------
# Flight command application (called with state_lock held)
# ---------------------------------------------------------------------------

def _apply_flight_command(action, payload):
    phase = state["phase"]

    if action == "takeoff":
        if phase == "idle":
            state["target_altitude"] = payload.get("altitude", 40.0)
            state["active_speed"]    = float(payload.get("speed", CRUISE_SPEED))
            state["phase"]           = "taking_off"
            state["_pending"]        = None

    elif action == "hold":
        state["_pending"]     = None
        state["active_decel"] = DECEL_RATE
        state["target_lat"]   = state["lat"]
        state["target_lon"]   = state["lon"]
        state["phase"]        = "holding"

    elif action == "fly_to":
        state["_cancelled"] = False
        tlat  = payload["lat"]
        tlon  = payload["lon"]
        speed = float(payload.get("speed", CRUISE_SPEED))
        speed = max(0.5, min(speed, 20.0))
        brg = geo_bearing(state["lat"], state["lon"], tlat, tlon)
        state["target_lat"]     = tlat
        state["target_lon"]     = tlon
        state["active_bearing"] = brg
        state["active_speed"]   = speed

        if state["speed_mps"] <= STOP_THRESH:
            state["_pending"] = None
            state["phase"]    = "yawing_to"
        else:
            state["_pending"] = {"action": "fly_to", "lat": tlat, "lon": tlon, "speed": speed}
            state["phase"]    = "holding"

    elif action == "cancel_fly_to":
        state["_pending"]              = None
        state["_cancelled"]            = True
        state["_pending_node_arrived"] = False
        state["active_decel"]          = DECEL_RATE
        if phase in ("flying_to", "yawing_to"):
            state["target_lat"] = state["lat"]
            state["target_lon"] = state["lon"]
            state["phase"]      = "holding"

    elif action == "rth":
        state["_pending"]          = None
        state["active_rth_speed"]  = float(payload.get("speed", CRUISE_SPEED))
        state["active_rth_speed"]  = max(0.5, min(state["active_rth_speed"], 20.0))
        if state["speed_mps"] <= STOP_THRESH:
            _begin_rth_turn()
        else:
            state["_pending"] = {"action": "rth", "speed": state["active_rth_speed"]}
            state["phase"]    = "holding"

    elif action == "land":
        state["_pending"]              = None
        state["_cancelled"]            = True
        state["_pending_node_arrived"] = False
        state["active_bearing"]        = 0.0
        state["phase"]                 = "rth_facing_home"

    elif action == "manual_move":
        if phase in ("holding", "manual_move"):
            fwd   = payload.get("forward_m", 0.0)
            right = payload.get("right_m",   0.0)
            up    = payload.get("up_m",      0.0)
            yaw   = payload.get("yaw_deg",   0.0)
            speed = float(payload.get("speed", MANUAL_SPEED))
            speed = max(0.5, min(speed, 20.0))
            h_rad = math.radians(state["heading"])
            north = fwd * math.cos(h_rad) - right * math.sin(h_rad)
            east  = fwd * math.sin(h_rad) + right * math.cos(h_rad)
            state["manual_north_remain"] += north
            state["manual_east_remain"]  += east
            state["manual_up_remain"]    += up
            if yaw != 0.0:
                state["heading"] = (state["heading"] + yaw) % 360
            state["active_manual_speed"] = speed
            has_displacement = abs(north) > 0.001 or abs(east) > 0.001 or abs(up) > 0.001
            if phase != "manual_move" and has_displacement:
                state["phase"] = "manual_move"

def _begin_rth_turn():
    dock_brg = geo_bearing(state["lat"], state["lon"], DOCK_LAT, DOCK_LON)
    state["active_bearing"] = dock_brg
    state["phase"]          = "rth_turning"

# ---------------------------------------------------------------------------
# Physics tick — one function per flight phase
# ---------------------------------------------------------------------------

def _tick_environment(dt):
    """Update wind simulation and battery charge/drain."""
    t = state["wind_t"] + dt
    state["wind_t"] = t
    state["wind_speed_mps"]     = max(0.0, 3.5 + 1.5 * math.sin(t/40) + 0.3 * math.sin(t/7))
    state["wind_direction_deg"] = (170 + 15 * math.sin(t/50) + 5 * math.sin(t/12)) % 360

    is_at_dock = (state["altitude"] <= 0.05 and
                  distance_m(state["lat"], state["lon"], DOCK_LAT, DOCK_LON) < 1.0)
    on_ground  = state["altitude"] <= 0.05

    if is_at_dock:
        state["battery"] = min(100.0, state["battery"] + BATTERY_CHARGE * dt)
    elif not on_ground:
        state["battery"] = max(0.0, state["battery"] - BATTERY_DRAIN * dt)

    drain_per_min = BATTERY_DRAIN * 60
    state["battery_min"] = state["battery"] / drain_per_min if drain_per_min > 0 else 0.0

def _tick_idle(dt):
    state["speed_mps"]      = 0.0
    state["vertical_speed"] = 0.0
    state["pitch"]          = 0.0
    state["roll"]           = 0.0

def _tick_taking_off(dt):
    tgt   = state["target_altitude"]
    climb = min(CLIMB_RATE * dt, max(0.0, tgt - state["altitude"]))
    state["altitude"]       += climb
    state["vertical_speed"]  = CLIMB_RATE
    state["speed_mps"]       = step_toward(state["speed_mps"], 0.0, DECEL_RATE * dt)
    state["pitch"]           = step_toward(state["pitch"], 5.0, 10.0 * dt)
    state["roll"]            = step_toward(state["roll"],  0.0, 5.0  * dt)
    if state["altitude"] >= tgt - 0.01:
        state["altitude"]       = tgt
        state["vertical_speed"] = 0.0
        state["pitch"]          = step_toward(state["pitch"], 0.0, 5.0 * dt)
        state["speed_mps"]      = 0.0
        state["phase"]          = "holding"
        state["_pending"]       = None
        state["_takeoff_done"]  = True

def _tick_holding(dt):
    state["speed_mps"] = step_toward(state["speed_mps"], 0.0, DECEL_RATE * dt)
    if state["speed_mps"] < STOP_THRESH:
        state["speed_mps"] = 0.0
    state["vertical_speed"] = 0.0
    state["pitch"]  = step_toward(state["pitch"], 0.0, 4.0 * dt)
    state["roll"]   = step_toward(state["roll"],  0.0, 4.0 * dt)

    if state["speed_mps"] <= STOP_THRESH:
        if state.get("_pending_node_arrived") and not state.get("_cancelled", False):
            state["_pending_node_arrived"] = False
            state["_node_arrived"]          = True
        elif state.get("_pending_node_arrived"):
            state["_pending_node_arrived"] = False
        pending = state.get("_pending")
        if pending:
            state["_pending"] = None
            _apply_flight_command(pending["action"], pending)

def _tick_yawing_to(dt):
    state["speed_mps"] = step_toward(state["speed_mps"], 0.0, DECEL_RATE * dt)
    if state["speed_mps"] < STOP_THRESH:
        state["speed_mps"] = 0.0
    state["vertical_speed"] = 0.0
    state["pitch"] = step_toward(state["pitch"], 0.0, 4.0 * dt)
    state["roll"]  = step_toward(state["roll"],  0.0, 4.0 * dt)
    if state["speed_mps"] <= STOP_THRESH:
        new_hdg = yaw_step(state["heading"], state["active_bearing"], dt)
        state["heading"] = new_hdg
        if state["heading"] == state["active_bearing"]:
            state["phase"] = "flying_to"

def _tick_flying_to(dt):
    tgt_lat = state["target_lat"]
    tgt_lon = state["target_lon"]
    dist    = distance_m(state["lat"], state["lon"], tgt_lat, tgt_lon)

    if dist <= ARRIVAL_THRESH:
        state["lat"]          = tgt_lat
        state["lon"]          = tgt_lon
        state["phase"]        = "holding"
        state["_pending"]     = None
        if not state.get("_cancelled", False):
            state["_pending_node_arrived"] = True
    else:
        state["heading"]   = state["active_bearing"]
        active_spd = state["active_speed"]
        state["speed_mps"] = step_toward(state["speed_mps"], active_spd, ACCEL_RATE * dt)
        spd   = state["speed_mps"]
        ratio = min(spd * dt / max(dist, 0.001), 1.0)
        state["lat"] += (tgt_lat - state["lat"]) * ratio
        state["lon"] += (tgt_lon - state["lon"]) * ratio
        state["pitch"] = step_toward(state["pitch"],
                                     -min(spd / active_spd * 8.0, 8.0) if active_spd > 0 else 0.0, 3.0 * dt)
        state["roll"]           = step_toward(state["roll"], 0.0, 3.0 * dt)
        state["vertical_speed"] = 0.0

def _tick_rth_turning(dt):
    state["speed_mps"] = step_toward(state["speed_mps"], 0.0, DECEL_RATE * dt)
    if state["speed_mps"] < STOP_THRESH:
        state["speed_mps"] = 0.0
    state["vertical_speed"] = 0.0
    state["pitch"] = step_toward(state["pitch"], 0.0, 4.0 * dt)
    state["roll"]  = step_toward(state["roll"],  0.0, 4.0 * dt)
    if state["speed_mps"] <= STOP_THRESH:
        new_hdg = yaw_step(state["heading"], state["active_bearing"], dt)
        state["heading"] = new_hdg
        if state["heading"] == state["active_bearing"]:
            state["phase"] = "rth_flying"

def _tick_rth_flying(dt):
    dist = distance_m(state["lat"], state["lon"], DOCK_LAT, DOCK_LON)

    if dist <= ARRIVAL_THRESH:
        state["lat"]            = DOCK_LAT
        state["lon"]            = DOCK_LON
        state["active_bearing"] = 0.0
        state["phase"]          = "rth_facing_home"
    else:
        dock_brg = geo_bearing(state["lat"], state["lon"], DOCK_LAT, DOCK_LON)
        state["heading"]   = dock_brg
        rth_spd = state.get("active_rth_speed", CRUISE_SPEED)
        state["speed_mps"] = step_toward(state["speed_mps"], rth_spd, ACCEL_RATE * dt)
        spd   = state["speed_mps"]
        ratio = min(spd * dt / max(dist, 0.001), 1.0)
        state["lat"] += (DOCK_LAT - state["lat"]) * ratio
        state["lon"] += (DOCK_LON - state["lon"]) * ratio
        state["pitch"] = step_toward(state["pitch"],
                                     -min(spd / rth_spd * 8.0, 8.0) if rth_spd > 0 else 0.0, 3.0 * dt)
        state["roll"]           = step_toward(state["roll"], 0.0, 3.0 * dt)
        state["vertical_speed"] = 0.0

def _tick_rth_facing_home(dt):
    state["speed_mps"] = step_toward(state["speed_mps"], 0.0, DECEL_RATE * dt)
    if state["speed_mps"] < STOP_THRESH:
        state["speed_mps"] = 0.0
    state["vertical_speed"] = 0.0
    state["pitch"] = step_toward(state["pitch"], 0.0, 4.0 * dt)
    state["roll"]  = step_toward(state["roll"],  0.0, 4.0 * dt)
    if state["speed_mps"] <= STOP_THRESH:
        new_hdg = yaw_step(state["heading"], 0.0, dt)
        state["heading"] = new_hdg
        if state["heading"] == 0.0:
            state["phase"] = "landing"

def _tick_manual_move(dt):
    north_rem = state["manual_north_remain"]
    east_rem  = state["manual_east_remain"]
    up_rem    = state["manual_up_remain"]
    total_horiz = math.sqrt(north_rem ** 2 + east_rem ** 2)

    if abs(up_rem) > 0.01:
        climb_rate = CLIMB_RATE if up_rem > 0 else DESCENT_RATE
        v_step = min(climb_rate * dt, abs(up_rem))
        state["altitude"] = max(0.0, state["altitude"] + math.copysign(v_step, up_rem))
        state["manual_up_remain"] -= math.copysign(v_step, up_rem)
        state["vertical_speed"]    = math.copysign(climb_rate, up_rem)
    else:
        state["manual_up_remain"] = 0.0
        state["vertical_speed"]   = 0.0

    if total_horiz <= 0.1:
        state["manual_north_remain"] = 0.0
        state["manual_east_remain"]  = 0.0
        if abs(state["manual_up_remain"]) <= 0.01:
            state["phase"] = "holding"
    else:
        spd    = step_toward(state["speed_mps"], state.get("active_manual_speed", MANUAL_SPEED), ACCEL_RATE * dt)
        step_m = min(spd * dt, total_horiz)
        frac   = step_m / total_horiz
        dn     = north_rem * frac
        de     = east_rem  * frac
        state["lat"], state["lon"] = move_by_metres(state["lat"], state["lon"], dn, de)
        state["manual_north_remain"] -= dn
        state["manual_east_remain"]  -= de
        state["speed_mps"] = spd
        ms = state.get("active_manual_speed", MANUAL_SPEED)
        state["pitch"] = step_toward(state["pitch"],
                                     -min(spd / ms * 5.0, 5.0) if ms > 0 else 0.0, 3.0 * dt)
        state["roll"] = step_toward(state["roll"], 0.0, 3.0 * dt)

def _tick_landing(dt):
    drop = min(DESCENT_RATE * dt, state["altitude"])
    state["altitude"]       = max(0.0, state["altitude"] - drop)
    state["vertical_speed"] = step_toward(state["vertical_speed"], -DESCENT_RATE, 2.0 * dt)
    state["speed_mps"]      = step_toward(state["speed_mps"], 0.0, DECEL_RATE * dt)
    state["pitch"]          = step_toward(state["pitch"], 2.0, 3.0 * dt)
    state["roll"]           = step_toward(state["roll"],  0.0, 3.0 * dt)
    if state["altitude"] <= 0.01:
        state["altitude"]       = 0.0
        state["vertical_speed"] = 0.0
        state["speed_mps"]      = 0.0
        state["pitch"]          = 0.0
        state["roll"]           = 0.0
        state["heading"]        = 0.0
        state["phase"]          = "idle"
        state["_landed"]        = True

_PHASE_TICK = {
    "idle":           _tick_idle,
    "taking_off":     _tick_taking_off,
    "holding":        _tick_holding,
    "yawing_to":      _tick_yawing_to,
    "flying_to":      _tick_flying_to,
    "rth_turning":    _tick_rth_turning,
    "rth_flying":     _tick_rth_flying,
    "rth_facing_home": _tick_rth_facing_home,
    "manual_move":    _tick_manual_move,
    "landing":        _tick_landing,
}

def physics_tick(dt):
    with state_lock:
        _tick_environment(dt)

        if state["phase"] != "idle":
            state["elapsed_seconds"] += dt

        tick_fn = _PHASE_TICK.get(state["phase"])
        if tick_fn:
            tick_fn(dt)

# ---------------------------------------------------------------------------
# MQTT setup
# ---------------------------------------------------------------------------

mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
mqtt_client.on_message = on_message
mqtt_client.connect("localhost", 1883)
mqtt_client.loop(timeout=0)
mqtt_client.subscribe("dock/dock1/commands")
mqtt_client.subscribe("dock/dock1/flight")
mqtt_client.loop(timeout=0)

# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------

_last_log_phase    = "idle"
_last_pubbed_phase = "idle"
_cmd_count         = 0
_tick_count        = 0
LOG_INTERVAL    = 80

def log_command(action):
    global _cmd_count
    _cmd_count += 1

def log_status():
    global _last_log_phase
    with state_lock:
        phase = state["phase"]
    if phase != _last_log_phase:
        print(f"[SIM] Phase: {_last_log_phase} -> {phase}")
        _last_log_phase = phase

# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

last_tick = time.time()
_tick_count = 0

while True:
    mqtt_client.loop(timeout=0)

    now = time.time()
    dt  = min(now - last_tick, 0.2)
    last_tick = now
    _tick_count += 1

    physics_tick(dt)
    log_status()

    events = {}
    with state_lock:
        for key in ("_node_arrived", "_takeoff_done", "_landed"):
            if state.get(key):
                events[key] = True
                del state[key]

    event_map = {
        "_node_arrived": "node_arrived",
        "_takeoff_done": "takeoff_done",
        "_landed":       "landed",
    }
    for key in events:
        mqtt_client.publish("dock/dock1/flight_status",
                            json.dumps({"event": event_map[key]}))

    with state_lock:
        cur_phase = state["phase"]
    if cur_phase != _last_pubbed_phase:
        _last_pubbed_phase = cur_phase
        mqtt_client.publish("dock/dock1/flight_status",
                            json.dumps({"event": "phase_changed", "phase": cur_phase}))
        print(f"[SIM] -> phase_changed: {cur_phase}")

    if _tick_count % PUBLISH_EVERY == 0:
        with state_lock:
            elapsed = int(state["elapsed_seconds"])
            elapsed_str = "{:02d}:{:02d}:{:02d}".format(
                elapsed // 3600, (elapsed % 3600) // 60, elapsed % 60
            )
            telemetry = {
                "lat":                round(state["lat"],       6),
                "lon":                round(state["lon"],       6),
                "altitude":           round(state["altitude"],  2),
                "vertical_speed":     round(state["vertical_speed"], 2),
                "heading":            round(state["heading"],   2),
                "pitch":              round(state["pitch"],     2),
                "roll":               round(state["roll"],      2),
                "speed_mps":          round(state["speed_mps"], 2),
                "wind_speed_mps":     round(state["wind_speed_mps"], 2),
                "wind_direction_deg": round(state["wind_direction_deg"], 2),
                "battery":            round(state["battery"],   2),
                "battery_min":        round(state["battery_min"], 2),
                "time_elapsed":       elapsed_str,
                "phase":              state["phase"],
            }
        mqtt_client.publish("dock/dock1/drone/telemetry", json.dumps(telemetry))

    mqtt_client.loop(timeout=0)
    time.sleep(TICK)