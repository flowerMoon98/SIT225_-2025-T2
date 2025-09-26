import csv, json, os, sys, datetime, glob
import serial  # pip install pyserial
from pathlib import Path



PROJECT_ROOT = Path(__file__).resolve().parents[2]

PORT = os.getenv("SERIAL_PORT", "/dev/tty.usbmodem21101")  # macOS: wildcard ok
BAUD = int(os.getenv("BAUD", "115200"))
OUTDIR = os.getenv("OUTDIR", str(PROJECT_ROOT / "data"))

FIELDS = ["iso_ts","ms","temp_c","hum_pct","heat_index_c","pir_raw","motion","occupied","fidget","focused"]

def pick_port(pattern):
    if "*" not in pattern:
        return pattern
    matches = glob.glob(pattern)
    if not matches:
        print(f"No serial ports match {pattern}")
        sys.exit(1)
    print("Using port:", matches[0])
    return matches[0]

def today_path():
    d = datetime.date.today().isoformat()
    os.makedirs(OUTDIR, exist_ok=True)
    return os.path.join(OUTDIR, f"{d}.csv")

def open_writer(path):
    new = not os.path.exists(path)
    f = open(path, "a", newline="")
    w = csv.DictWriter(f, fieldnames=FIELDS)
    if new: w.writeheader()
    return f, w

def parse_line(line: str):
    line = line.strip()
    if not line: return None
    row = {"iso_ts": datetime.datetime.now().isoformat(timespec="seconds")}
    # CSV from Arduino (preferred)
    if line[0] != "{":
        parts = line.split(",")
        if len(parts) < 9 or not parts[0].isdigit(): return None
        row.update({
            "ms": parts[0], "temp_c": parts[1], "hum_pct": parts[2],
            "heat_index_c": parts[3], "pir_raw": parts[4], "motion": parts[5],
            "occupied": parts[6], "fidget": parts[7], "focused": parts[8],
        })
        return row
    # JSON fallback (if you flip OUTPUT_CSV to 0)
    try:
        obj = json.loads(line)
        row.update({
            "ms": obj.get("ms"), "temp_c": obj.get("temp_c"), "hum_pct": obj.get("hum_pct"),
            "heat_index_c": obj.get("heat_index_c"), "pir_raw": obj.get("pir_raw"),
            "motion": obj.get("motion"), "occupied": obj.get("occupied"),
            "fidget": obj.get("fidget"), "focused": obj.get("focused"),
        })
        return row
    except Exception:
        return None

def main():
    port = pick_port(PORT)
    ser = serial.Serial(port, BAUD, timeout=2)
    current_path = today_path()
    f, w = open_writer(current_path)
    try:
        while True:
            # rotate file daily
            new_path = today_path()
            if new_path != current_path:
                f.close()
                current_path = new_path
                f, w = open_writer(current_path)
            line = ser.readline().decode("utf-8", errors="ignore")
            row = parse_line(line)
            if row:
                w.writerow(row); f.flush()
    except KeyboardInterrupt:
        pass
    finally:
        try: f.close(); ser.close()
        except: pass

if __name__ == "__main__":
    main()
