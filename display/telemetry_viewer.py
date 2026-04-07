import paho.mqtt.client as mqtt
import json
import sys

LINES = 9

def on_message(client, userdata, msg):
    data = json.loads(msg.payload)

    sys.stdout.write(f"\033[{LINES}F")

    output = (
        f"Lat: {data['lat']}\n"
        f"Lon: {data['lon']}\n"
        f"Alt: {data['altitude']} m\n"
        f"Battery: {data['battery']}%\n"
        f"Heading: {data['heading']}\n"
        f"Speed: {data['speed_mps']} m/s\n"
        f"Battery Min Remaining: {data['battery_min']} min\n"
        f"Wind Speed: {data['wind_speed_mps']} m/s\n"
        f"Wind Direction: {data['wind_direction_deg']}\n"
    )

    sys.stdout.write(output)
    sys.stdout.flush()

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.on_message = on_message

client.connect("localhost", 1883)
client.subscribe("dock/dock1/drone/telemetry")


print("\n" * LINES)

client.loop_forever()