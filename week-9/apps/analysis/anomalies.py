import sys, pandas as pd, numpy as np

HI_THRESHOLD = 28.0
S1_WINDOW_S  = 600     # 10 min
F1_WINDOW_S  = 300     # 5 min
F1_MARGIN    = 0.005   # add-on over per-session median (tune)

def load_sessions_csv(path):
    df = pd.read_csv(path)
    if "session_id" not in df.columns:
        raise SystemExit("Please run sessionizer.py first to create session_id.")
    df["ms"] = pd.to_numeric(df["ms"], errors="coerce")
    df["sec"] = df["ms"]/1000.0
    return df

def rolling_by_seconds(df, col, window_s):
    # assume near-constant ~4Hz; convert to N samples
    # find median dt to infer Hz
    dt = np.median(np.diff(df["sec"])) if len(df)>1 else 0.25
    n = max(1, int(window_s / max(dt, 1e-6)))
    return df[col].rolling(window=n, min_periods=n).mean()

def find_anomalies(df):
    events = []
    for sid, block in df.groupby("session_id"):
        if sid == 0: continue  # skip non-session
        block = block.reset_index(drop=True)

        # S1: Too warm while working
        hi_roll = rolling_by_seconds(block, "heat_index_c", S1_WINDOW_S)
        s1_mask = (hi_roll >= HI_THRESHOLD)
        if s1_mask.any():
            t_idx = s1_mask.idxmax()
            ts = block.loc[t_idx, "iso_ts"]
            hi_val = float(hi_roll.iloc[t_idx])
            events.append({
                "type":"S1_too_warm",
                "session_id": int(sid),
                "iso_ts": ts,
                "heat_index_c_10min": round(hi_val,2)
            })

        # F1: Fidget spike vs per-session median
        f_med = float(block["fidget"].median())
        f_roll = rolling_by_seconds(block, "fidget", F1_WINDOW_S)
        f_thresh = f_med + F1_MARGIN
        f1_mask = (f_roll >= f_thresh)
        if f1_mask.any():
            t_idx = f1_mask.idxmax()
            ts = block.loc[t_idx, "iso_ts"]
            events.append({
                "type":"F1_fidget_spike",
                "session_id": int(sid),
                "iso_ts": ts,
                "fidget_5min": round(float(f_roll.iloc[t_idx]),4),
                "threshold": round(f_thresh,4),
                "session_median": round(f_med,4)
            })

    return events

if __name__ == "__main__":
    if len(sys.argv)<2:
        print("Usage: python anomalies.py week-9/data/2025-09-25.sessions.csv")
        sys.exit(1)
    df = load_sessions_csv(sys.argv[1])
    events = find_anomalies(df)
    for e in events:
        print(e)
