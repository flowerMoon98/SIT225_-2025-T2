"""
pip install --upgrade arduino-iot-cloud websocket-client
"""

from arduino_iot_cloud import ArduinoCloudClient
import traceback
import logging

logging.basicConfig(level=logging.DEBUG)


# ---- Use the Device ID and Secret Key of your MANUAL DEVICE (PythonClient) ----
DEVICE_ID  = "e31902b6-1ba3-4930-8351-6a0d9fc8d203"
SECRET_KEY = "DUJd#LCwA6?kykd6W@Uv1tpAh"

def on_temperature_changed(client, value):
    print(f"New temperature: {value}")

def main():
    print("Starting Arduino IoT Cloud client…")
    client = ArduinoCloudClient(
        device_id=DEVICE_ID,
        username=DEVICE_ID,      # for manual devices, username = device id
        password=SECRET_KEY
    )
    # Register the variable that exists in the PythonClient Thing
    client.register("temperature", value=None, on_write=on_temperature_changed)
    client.start()  # blocks; listens forever

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped by user.")
    except Exception:
        traceback.print_exc()