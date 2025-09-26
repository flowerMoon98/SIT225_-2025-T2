import pandas as pd, json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
INP = DATA_DIR / "events.csv"
OUT = DATA_DIR / "events_clean.csv"

def maybe_parse_json(s):
    if not isinstance(s, str): return {}
    s = s.strip()
    if not s or s[0] not in "{[\"'": return {}
    try:
        return json.loads(s.replace("'", '"'))
    except Exception:
        return {}

def main():
    df = pd.read_csv(INP)

    # rescue rows where a whole JSON blob ended up in a column
    for col in ["source","type","app","note"]:
        if col in df.columns:
            mask = df[col].astype(str).str.contains("{", na=False)
            if mask.any():
                parsed = df.loc[mask, col].apply(maybe_parse_json)
                for k in ["source","type","app","note"]:
                    df.loc[mask, k] = df.loc[mask, k].fillna(parsed.apply(lambda d: d.get(k, "")))

    # tidy
    for c in ["source","type","app","note"]:
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip().str.lower()

    # drop browser test pings
    df = df[~((df["source"]=="browser") & (df["type"]=="test_ping"))].copy()

    # derive opened_app flag: 1 if app non-empty
    df["opened_app"] = (df["app"].fillna("") != "").astype(int)

    # parse time, sort, dedupe within 10s for same (type, app)
    df["t"] = pd.to_datetime(df["iso_ts"], errors="coerce")
    df = df.sort_values("t").reset_index(drop=True)

    keep = [True]
    for i in range(1, len(df)):
        same = (df.loc[i,"type"] == df.loc[i-1,"type"]) and (df.loc[i,"app"] == df.loc[i-1,"app"])
        gap = (df.loc[i,"t"] - df.loc[i-1,"t"]).total_seconds()
        keep.append(not (same and gap < 10))

    df = df[pd.Series(keep).values].drop(columns=["t"])
    df.to_csv(OUT, index=False)
    print(f"Wrote {OUT} rows: {len(df)}")

if __name__ == "__main__":
    main()
