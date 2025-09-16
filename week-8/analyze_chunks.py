import pandas as pd, glob, re
from pathlib import Path

paths = sorted(glob.glob("snapshots/*_chunk_*.csv"))
rows = []
for p in paths:
    name = Path(p).name
    m = re.match(r"(.*)_chunk_.*_N(\d+)\.csv$", name)
    label = m.group(1) if m else "unknown"
    df = pd.read_csv(p, parse_dates=["time"])
    stats = df[["x","y","z"]].agg(["mean","std","max","min"])
    rng = (df[["x","y","z"]].max() - df[["x","y","z"]].min()).rename("ptp")  # peak-to-peak
    row = {
        "file": name, "label": label, "N": len(df),
        "mean_x": stats.loc["mean","x"], "std_x": stats.loc["std","x"], "ptp_x": rng["x"],
        "mean_y": stats.loc["mean","y"], "std_y": stats.loc["std","y"], "ptp_y": rng["y"],
        "mean_z": stats.loc["mean","z"], "std_z": stats.loc["std","z"], "ptp_z": rng["z"],
    }
    rows.append(row)

out = pd.DataFrame(rows).sort_values(["label","file"])
print(out.to_string(index=False))

# (optional) quick period estimate on X via autocorr
try:
    import numpy as np
    for p in paths[:2]:
        df = pd.read_csv(p, parse_dates=["time"])
        s = df["x"].astype(float)
        s = (s - s.mean()) / s.std(ddof=0)
        ac = np.correlate(s, s, mode="full")[len(s)-1:]
        lag = ac[1:len(s)//2].argmax() + 1
        sec = (df["time"].iloc[lag] - df["time"].iloc[0]).total_seconds()
        print(f"{Path(p).name} · approx period on X ≈ {sec:.2f}s")
except Exception as e:
    print("period est skipped:", e)