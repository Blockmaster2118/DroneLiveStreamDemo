const express = require("express")
const mqtt = require("mqtt")

const app = express()

// STREAM_HOST is the address clients use to reach the HLS/RTSP streams.
// Falls back to localhost for local testing without the launcher.
const STREAM_HOST = process.env.STREAM_HOST || "localhost"

const client = mqtt.connect("mqtt://localhost:1883")

client.on("connect", () => {
    console.log("Connected to MQTT broker")
})

// publish start_stream to the dock; return the HLS stream URL
app.post("/livestream/start", (req, res) => {
    client.publish(
        "dock/dock1/commands",
        JSON.stringify({ action: "start_stream" })
    )
    res.json({ stream_url: `http://${STREAM_HOST}:8888/dock1_stream/index.m3u8` })
})

// publish stop_stream to the dock
app.post("/livestream/stop", (req, res) => {
    client.publish(
        "dock/dock1/commands",
        JSON.stringify({ action: "stop_stream" })
    )
    res.json({ status: "stopped" })
})

// publish start_audio to the dock; return the audio stream URL
app.post("/audio/start", (req, res) => {
    client.publish(
        "dock/dock1/commands",
        JSON.stringify({ action: "start_audio" })
    )
    res.json({ stream_url: `rtsp://${STREAM_HOST}:8554/dock1_audio` })
})

// publish stop_audio to the dock
app.post("/audio/stop", (req, res) => {
    client.publish(
        "dock/dock1/commands",
        JSON.stringify({ action: "stop_audio" })
    )
    res.json({ status: "stopped" })
})

app.listen(3000, () => {
    console.log("API simulator running on port 3000")
})