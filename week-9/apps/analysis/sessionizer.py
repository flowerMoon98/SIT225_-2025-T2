import os, sys, pandas as pd

START_HOLD_S = 10   # require 10s of occupied to start a session
END_GAP_S    = 120  # end after 120s unoccupied

def load_csv(path):
    df = pd.read_csv(path)
    # ensure types
    for c in ["occupied","focused"]:
        if c in df.columns: df[c] = df[c].astype(int)
    df["ms"] = pd.to_numeric(df["ms"], errors="coerce")
    df["sec"] = df["ms"] / 1000.0
    return df

def add_sessions(df):
    session_id = 0
    in_session = False
    start_t = None
    hold = 0.0
    gap = 0.0
    sess_ids = []

    prev_sec = df["sec"].iloc[0] if len(df) else 0.0
    for _, row in df.iterrows():
        dt = max(0.0, row["sec"] - prev_sec)
        prev_sec = row["sec"]

        if not in_session:
            if row["occupied"] == 1:
                hold += dt
                if hold >= START_HOLD_S:
                    in_session = True
                    session_id += 1
                    start_t = row["sec"]
            else:
                hold = 0.0
            sess_ids.append(session_id if in_session else 0)
        else:
            if row["occupied"] == 0:
                gap += dt
                if gap >= END_GAP_S:
                    in_session = False
                    hold = 0.0
                    gap = 0.0
            else:
                gap = 0.0
            sess_ids.append(session_id if in_session else 0)

    df["session_id"] = sess_ids
    return df

def save_with_sessions(path, df):
    out = path.replace(".csv", ".sessions.csv")
    df.to_csv(out, index=False)
    print("Wrote:", out)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python sessionizer.py week-9/data/2025-09-25.csv")
        sys.exit(1)
    p = sys.argv[1]
    df = load_csv(p)
    df = add_sessions(df)
    save_with_sessions(p, df)
