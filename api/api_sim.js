const express = require("express")
const mqtt = require("mqtt")

const app = express()

const client = mqtt.connect("mqtt://localhost:1883")

client.on("connect", () => {
    console.log("Connected to MQTT broker")
})

app.post("/livestream/start", (req,res)=>{

 client.publish(
  "dock/dock1/commands",
  JSON.stringify({action:"start_stream"})
 )

 res.json({
  stream_url:"rtsp://localhost:8554/dock1_stream"
 })

})

app.post("/livestream/stop", (req,res)=>{

 client.publish(
  "dock/dock1/commands",
  JSON.stringify({action:"stop_stream"})
 )

 res.json({
  status:"stopped"
 })

})

app.listen(3000, () => {
 console.log("API simulator running on port 3000")
})