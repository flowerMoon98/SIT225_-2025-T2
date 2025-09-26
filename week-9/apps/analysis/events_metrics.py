import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"    
EV = DATA_DIR / "events_clean.csv"

def main():
    df = pd.read_csv(EV, parse_dates=["iso_ts"])
    if df.empty:
        print("No events.")
        return

    df = df.sort_values("iso_ts").reset_index(drop=True)
    df["opened_app"] = (df["app"].fillna("") != "").astype(int)
    total_unlocks = len(df)
    app_unlocks = df["opened_app"].sum()

    # rough duration and per-hour rates
    dur_hours = max((df["iso_ts"].iloc[-1] - df["iso_ts"].iloc[0]).total_seconds()/3600.0, 1e-9)
    rate_unlocks = total_unlocks / dur_hours
    rate_app_unlocks = app_unlocks / dur_hours

    per_app = df[df["app"].ne("")]["app"].value_counts().to_dict()

    print(f"Total unlocks: {total_unlocks}")
    print(f"Unlocks leading to app (instagram/tiktok/reddit): {app_unlocks}")
    print(f"Duration (h): {dur_hours:.2f}")
    print(f"Unlocks per hour: {rate_unlocks:.2f}")
    print(f"App-unlocks per hour: {rate_app_unlocks:.2f}")
    print(f"By app: {per_app}")

if __name__ == "__main__":
    main()
