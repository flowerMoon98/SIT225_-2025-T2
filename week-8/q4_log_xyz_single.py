# === Activity 8.2 · Q4: single CSV with timestamp, x, y, z ===
from datetime import datetime
import csv, pathlib
from arduino_iot_cloud import ArduinoCloudClient
from secrets import DEVICE_ID, SECRET_KEY

DATA_DIR = pathlib.Path("data"); DATA_DIR.mkdir(exist_ok=True)
ONE = DATA_DIR/"accelerometer_xyz.csv"
latest = {"ax": None, "ay": None, "az": None}

def write_if_ready():
    if all(v is not None for v in latest.values()):
        stamp = datetime.now().isoformat(timespec="seconds")
        new = not ONE.exists()
        with ONE.open("a", newline="") as f:
            w = csv.writer(f)
            if new: w.writerow(["timestamp", "ax", "ay", "az"])
            w.writerow([stamp, latest["ax"], latest["ay"], latest["az"]])
        print(f"[row] {stamp}, {latest['ax']}, {latest['ay']}, {latest['az']}")

def on_ax(client, value): latest["ax"] = value; write_if_ready()
def on_ay(client, value): latest["ay"] = value; write_if_ready()
def on_az(client, value): latest["az"] = value; write_if_ready()

client = ArduinoCloudClient(device_id=DEVICE_ID, username=DEVICE_ID, password=SECRET_KEY)
client.register("ax", value=None, on_write=on_ax)
client.register("ay", value=None, on_write=on_ay)
client.register("az", value=None, on_write=on_az)

print("Connecting to Arduino IoT Cloud…")
client.start()