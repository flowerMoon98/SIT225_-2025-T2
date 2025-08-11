import csv
import time
import sys
import threading
from datetime import datetime, timezone, timedelta
from arduino_iot_cloud import ArduinoCloudClient
import traceback

# ==== YOUR MANUAL DEVICE CREDENTIALS ====
DEVICE_ID  = "e31902b6-1ba3-4930-8351-6a0d9fc8d203"   # PythonClient device id
SECRET_KEY = "ttvoJ?uTemvI1@AQqtL2jSWnw"              # Client secret (regenerate alphanumeric if auth issues)

# Melbourne timezone (AET: AEST/AEDT). Adjust to +11 if you want to force DST.
MELBOURNE_TZ = timezone(timedelta(hours=10))

CSV_FILE     = "dht22_cloud_log.csv"
RUN_DURATION = 10 * 60  # seconds

latest_temperature = None
latest_humidity    = None
csv_header_written = False
csv_lock           = threading.Lock()

def now_melbourne():
    return datetime.now(MELBOURNE_TZ).strftime("%Y-%m-%d %H:%M:%S")

def write_csv_row(ts, temp, hum):
    global csv_header_written
    with csv_lock:
        new_file = not csv_header_written
        # Append on every write (simple & robust)
        with open(CSV_FILE, mode="a", newline="") as f:
            w = csv.writer(f)
            if not csv_header_written:
                w.writerow(["timestamp", "temperature", "humidity"])
                csv_header_written = True
            w.writerow([ts, temp, hum])

def maybe_log():
    if latest_temperature is not None and latest_humidity is not None:
        ts = now_melbourne()
        write_csv_row(ts, latest_temperature, latest_humidity)
        print(f"[{ts}] Temp: {latest_temperature} °C, Humidity: {latest_humidity} %")

def on_temperature_changed(client, value):
    global latest_temperature
    latest_temperature = value
    maybe_log()

def on_humidity_changed(client, value):
    global latest_humidity
    latest_humidity = value
    maybe_log()

def run_client(client):
    # Blocks until stopped or process exits
    client.start()

def main():
    print("Starting Arduino IoT Cloud client… (logging for 10 minutes)")
    # Pre-create file header (optional; also handled on first write)
    write_csv_row("timestamp", "temperature", "humidity")
    # Mark header written to avoid duplicating
    global csv_header_written
    csv_header_written = True

    client = ArduinoCloudClient(
        device_id=DEVICE_ID,
        username=DEVICE_ID,
        password=SECRET_KEY
    )
    # Register variables exactly as named in your PythonClient Thing
    client.register("temperature", value=None, on_write=on_temperature_changed)
    client.register("humidity",    value=None, on_write=on_humidity_changed)

    # Run the blocking client in a background thread
    t = threading.Thread(target=run_client, args=(client,), daemon=True)
    t.start()

    # Let it run for the duration
    time.sleep(RUN_DURATION)
    print("✅ 10 minutes reached — stopping client and exiting…")

    # Try to stop gracefully if supported by your lib version
    try:
        client.stop()
    except Exception:
        pass

    # Give the thread a moment to unwind, then exit
    t.join(timeout=2)
    sys.exit(0)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped by user.")
        sys.exit(0)
    except Exception:
        traceback.print_exc()
        sys.exit(1)