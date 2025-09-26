import numpy as np, pandas as pd, math, random
from pathlib import Path
from datetime import datetime, timedelta

# ----------------- config -----------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUT_BASE = PROJECT_ROOT / "data"
SEED = 225
random.seed(SEED); np.random.seed(SEED)

# durations (minutes) and sampling rate
SESSION_MIN = 30
FS_HZ = 4.0
DT = 1.0 / FS_HZ

# phone apps pool and their relative chances when an app is opened
APPS = ["instagram", "tiktok", "reddit"]
APP_P = [0.4, 0.4, 0.2]

# comfort band
COMFORT_LOW = 24.0
COMFORT_HIGH = 27.0

def heat_index_c(temp_c, rh):
    """Steadily match your firmware’s behavior: below ~26 C, HI ~ temp."""
    if temp_c < 26.0:
        return float(temp_c)
    Tf = temp_c*1.8 + 32.0
    R = rh
    HI = (-42.379 + 2.04901523*Tf + 10.14333127*R
          - 0.22475541*Tf*R - 0.00683783*Tf*Tf - 0.05481717*R*R
          + 0.00122874*Tf*Tf*R + 0.00085282*Tf*R*R - 0.00000199*Tf*Tf*R*R)
    return (HI - 32.0)/1.8

def synth_session(kind="baseline", name="2025-09-26_A"):
    """
    kind: 'baseline' or 'intervention'
    Produces:
      - sensor CSV at week-9/data/<kind>/<name>.csv
      - app events at week-9/data/<kind>/<name>_events.csv
    Model:
      baseline: more time hot, higher phone event rate
      intervention: nudge kicks in to cool & reduce phone rate after hot streaks
    """
    out_dir = OUT_BASE / kind
    out_dir.mkdir(parents=True, exist_ok=True)
    n = int(SESSION_MIN * 60 * FS_HZ)
    t0 = datetime.fromisoformat("2025-09-26T10:00:00")
    ts = np.array([t0 + timedelta(seconds=i*DT) for i in range(n)])
    ms = ((ts - ts[0]).astype("timedelta64[ms]").astype(np.int64))

    # Occupancy: present for most of session with short gaps
    occupied = np.ones(n, dtype=int)
    # sprinkle 2 short away gaps
    for _ in range(2):
        start = np.random.randint(int(5*FS_HZ), int((SESSION_MIN-5)*60*FS_HZ))
        length = int(np.random.uniform(10, 30) * FS_HZ)
        occupied[start:start+length] = 0

    # Temperature/Humidity profiles:
    # start comfortable; baseline drifts warmer; intervention cools faster on hot
    base_temp = 24.5 + np.cumsum(np.random.normal(0, 0.005, size=n))  # gentle drift
    if kind == "baseline":
        temp = base_temp + np.maximum(0, np.sin(np.linspace(0, 6*math.pi, n))) * 3.0  # pushes hot peaks
    else:
        temp = base_temp + np.maximum(0, np.sin(np.linspace(0, 6*math.pi, n))) * 1.5  # reduced peaks

    # humidity around 55–65 % with noise
    rh = 60 + np.random.normal(0, 3.0, size=n)
    rh = np.clip(rh, 30, 90)

    hi = np.array([heat_index_c(t, r) for t, r in zip(temp, rh)])

    # PIR: use occupied transitions; raw motion toggles
    pir_raw = np.zeros(n, dtype=int)
    # add small bursts of motion when occupied
    motion = np.zeros(n, dtype=int)
    burst_idx = np.where(occupied==1)[0]
    for i in burst_idx[::int(2*FS_HZ)]:
        if np.random.rand() < 0.05:
            L = np.random.randint(2, int(1.5*FS_HZ))
            pir_raw[i:i+L] = 1
            motion[i:i+L] = 1

    # Fidget: baseline low; rises with heat or around phone events later
    fidget = np.maximum(0, np.random.normal(0.002, 0.0008, size=n))
    hot = hi >= 28.0
    fidget += hot * np.random.normal(0.01, 0.002, size=n)

    # Phone events (unlock with optional app)
    # baseline: higher base rate; intervention: rate drops and cools when hot
    # Poisson-ish per second; then map to nearest sample
    def gen_events():
        rows = []
        last_event_t = None
        for i in range(n):
            if occupied[i] == 0:
                continue
            # base hazard per sec
            base_lambda = 0.020 if kind=="baseline" else 0.010  # per second
            # add heat penalty; intervention reduces when hot (nudge effect)
            heat_bonus = 0.015 if hot[i] else 0.0
            if kind == "intervention" and hot[i]:
                heat_bonus = 0.005  # smaller
            lam = base_lambda + heat_bonus
            # thin out bursts (avoid crazy clustering)
            if last_event_t is not None:
                delta = (ts[i] - last_event_t).total_seconds()
                if delta < 8:  # refractory 8s
                    lam *= 0.1
            if np.random.rand() < lam * DT:
                # sometimes plain unlock, sometimes straight into an app
                open_app = (np.random.rand() < (0.55 if kind=="baseline" else 0.35))
                app = ""
                if open_app:
                    app = np.random.choice(APPS, p=APP_P)
                rows.append({
                    "iso_ts": ts[i].isoformat(timespec="seconds"),
                    "source": "ios",
                    "type": "unlock",
                    "app": app,
                    "note": ""
                })
                last_event_t = ts[i]
                # bump fidget shortly after event to mimic micro-movement
                j0 = i
                j1 = min(n, i + int(6*FS_HZ))
                fidget[j0:j1] += np.linspace(0.01, 0.003, j1-j0)
        return rows

    events = gen_events()

    # light smoothing on fidget
    for i in range(1, n):
        fidget[i] = 0.95*fidget[i-1] + 0.05*fidget[i]

    # CSV: iso_ts first for plotting code, then ms + signals
    df = pd.DataFrame({
        "iso_ts": [t.isoformat(timespec="seconds") for t in ts],
        "ms": ms,
        "temp_c": np.round(temp, 2),
        "hum_pct": np.round(rh, 1),
        "heat_index_c": np.round(hi, 2),
        "pir_raw": pir_raw.astype(int),
        "motion": motion.astype(int),
        "occupied": occupied.astype(int),
        "fidget": np.round(fidget, 4),
    })

    sensor_path = out_dir / f"{name}.csv"
    events_path = out_dir / f"{name}_events.csv"
    df.to_csv(sensor_path, index=False)
    pd.DataFrame(events)[["iso_ts","source","type","app","note"]].to_csv(events_path, index=False)
    print(f"[sim] wrote {sensor_path} rows={len(df)}; events={len(events)}")

def main():
    # Two baseline + two intervention sessions
    synth_session("baseline",      "2025-09-26_A")
    synth_session("baseline",      "2025-09-26_B")
    synth_session("intervention",  "2025-09-27_A")
    synth_session("intervention",  "2025-09-27_B")

if __name__ == "__main__":
    main()
