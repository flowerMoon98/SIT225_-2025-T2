import sys, time
from datetime import datetime
import serial

from firebase_client import get_db

# ---------- SETTINGS ----------
DEVICE_ID = "nano33-gyro-1"
PORT = "/dev/tty.usbmodem21401"   # fixed port for your Nano
BAUD = 115200
ROUND_DP = 3
# --------------------------------

def now_epoch_ms() -> int:
    return int(time.time() * 1000)

def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def is_header(line: str) -> bool:
    s = line.strip().lower()
    return s.startswith("gx") or "gx,gy,gz" in s

def main(device_id: str = DEVICE_ID):
    print(f"Using serial port: {PORT} @ {BAUD}")
    db = get_db()
    base_ref = db.reference(f"/sensors/{device_id}/readings")
    print(f"Firebase path: /sensors/{device_id}/readings")

    try:
        with serial.Serial(PORT, BAUD, timeout=2) as ser:
            print("Streaming… (Ctrl+C to stop)")
            line_no = 0
            while True:
                raw = ser.readline().decode("utf-8", errors="ignore").strip()
                if not raw:
                    continue
                line_no += 1
                if is_header(raw):
                    continue

                parts = [p.strip() for p in raw.split(",")]
                if len(parts) != 3:
                    continue  # malformed line

                try:
                    gx = round(float(parts[0]), ROUND_DP)
                    gy = round(float(parts[1]), ROUND_DP)
                    gz = round(float(parts[2]), ROUND_DP)
                except ValueError:
                    continue  # skip bad numbers

                if any(abs(v) > 4000 for v in (gx, gy, gz)):
                    continue  # discard absurd spikes

                key = str(now_epoch_ms())
                record = {
                    "sensor_name": "LSM6DS3_Gyro",
                    "timestamp": now_str(),   # human-readable
                    "gx": gx, "gy": gy, "gz": gz
                }
                base_ref.child(key).set(record)

                if line_no % 50 == 0:
                    print(f"[ok] sent {line_no} samples; last {gx},{gy},{gz} @ {record['timestamp']}")

    except KeyboardInterrupt:
        print("\nStopped by user.")
    except serial.SerialException as e:
        print(f"Serial error: {e}")
    print("Done.")

if __name__ == "__main__":
    # Optional CLI override for device id
    dev = sys.argv[1] if len(sys.argv) > 1 else DEVICE_ID
    main(dev)