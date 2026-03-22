import paho.mqtt.client as mqtt
import json

def on_message(client, userdata, msg):
    data = json.loads(msg.payload)
    
    print("Telemetry:")
    print(f"  Lat: {data['lat']}")
    print(f"  Lon: {data['lon']}")
    print(f"  Altitude: {data['altitude']} m")
    print(f"  Battery: {data['battery']}%")
    print("-" * 30)

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

client.on_message = on_message

client.connect("localhost", 1883)
client.subscribe("dock/dock1/drone/telemetry")

client.loop_forever()