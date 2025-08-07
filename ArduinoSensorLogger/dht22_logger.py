import serial
import time
from datetime import datetime

# === CONFIG ===
SERIAL_PORT = '/dev/tty.usbmodem21201'  
FILENAME = "dht22_data.csv"

def get_timestamp():
    """Return current timestamp in YearMonthDayHourMinuteSecond format."""
    return datetime.now().strftime("%Y%m%d%H%M%S")

def main():
    try:
        with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=5) as ser:
            print(f"Listening on {SERIAL_PORT}...")
            with open(FILENAME, "a") as file:
                while True:
                    line = ser.readline().decode().strip()
                    if not line:
                        continue  # ignore empty lines

                    timestamp = get_timestamp()

                    # Basic validation: two values, comma-separated
                    if "," in line:
                        data_items = line.split(",")
                        if len(data_items) == 2:
                            csv_line = f"{timestamp},{data_items[0]},{data_items[1]}\n"
                            file.write(csv_line)
                            file.flush()
                            print(f"Logged: {csv_line.strip()}")
                        else:
                            print(f"⚠️ Malformed data: {line}")
                    else:
                        print(f"⚠️ Ignored line: {line}")
    except KeyboardInterrupt:
        print("\nLogging stopped by user.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
