# === Activity 8.2 · Q3: log each axis to its own CSV (Arduino IoT Cloud Python client) ===
from datetime import datetime
import csv, pathlib
from arduino_iot_cloud import ArduinoCloudClient  # official client
from secrets import DEVICE_ID, SECRET_KEY

# --- file helpers ---
DATA_DIR = pathlib.Path("data"); DATA_DIR.mkdir(exist_ok=True)
def ts(): return datetime.now().isoformat(timespec="seconds")
def append_row(path, values):
    new = not path.exists()
    with path.open("a", newline="") as f:
        w = csv.writer(f)
        if new: w.writerow(["timestamp", "value"])
        w.writerow(values)

# --- callbacks (called whenever the cloud variable updates) ---
def on_ax(client, value):
    append_row(DATA_DIR/"ax.csv", [ts(), value])
    print(f"[ax] {value}")

def on_ay(client, value):
    append_row(DATA_DIR/"ay.csv", [ts(), value])
    print(f"[ay] {value}")

def on_az(client, value):
    append_row(DATA_DIR/"az.csv", [ts(), value])
    print(f"[az] {value}")

# --- connect to Arduino IoT Cloud and register your variables ---
client = ArduinoCloudClient(device_id=DEVICE_ID, username=DEVICE_ID, password=SECRET_KEY)
# These names MUST match the variable names you created in the Thing (ax, ay, az)
# We listen for updates from the Cloud (linked to your phone’s Accelerometer X/Y/Z)
client.register("ax", value=None, on_write=on_ax)
client.register("ay", value=None, on_write=on_ay)
client.register("az", value=None, on_write=on_az)

print("Connecting to Arduino IoT Cloud…")
client.start()  # starts the client loop; on_write triggers whenever values change