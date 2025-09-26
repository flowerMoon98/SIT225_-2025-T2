import pandas as pd, numpy as np
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA = PROJECT_ROOT / "data"
OUTIMG = PROJECT_ROOT / "docs/img"
OUTIMG.mkdir(parents=True, exist_ok=True)

COMFORT_LOW, COMFORT_HIGH = 24.0, 27.0

def load_pair(kind, name):
    df = pd.read_csv(DATA / kind / f"{name}.csv", parse_dates=["iso_ts"])
    ev = pd.read_csv(DATA / kind / f"{name}_events.csv", parse_dates=["iso_ts"])
    return df, ev

def metrics(df, ev):
    # restrict to occupied
    dfo = df[df["occupied"]==1].copy()
    # estimate dt (sec)
    if "ms" in df.columns and df["ms"].notna().sum()>1:
        sec = df["ms"].to_numpy() / 1000.0
        dt = float(np.median(np.diff(sec)))
    else:
        dt = 0.25
    # comfort minutes in occupied time
    comfort_mask = (dfo["heat_index_c"].between(COMFORT_LOW, COMFORT_HIGH, inclusive="both"))
    comfort_min = float(comfort_mask.sum() * dt / 60.0)
    # simple focus flag (low fidget threshold = median of occupied window)
    thr = dfo["fidget"].median() + 0.002
    focus_mask = (dfo["fidget"] < thr)
    focus_min = float((focus_mask).sum() * dt / 60.0)
    # distraction rate: unlocks with an app per occupied hour
    ev_app = ev[ev["app"].fillna("")!=""].copy()
    # compute occupied duration (hours)
    occ_hours = (dfo.shape[0] * dt) / 3600.0
    rate_app_per_hour = (len(ev_app) / occ_hours) if occ_hours>0 else 0.0
    return dict(comfort_min=comfort_min, focus_min=focus_min, rate_app=rate_app_per_hour,
                focus_thr=thr)

def bar_plot(res_baseline, res_intervention, outpath):
    labels = ["Comfort (min)", "Focus (min)", "App unlocks/hr"]
    b = [np.mean([r["comfort_min"] for r in res_baseline]),
         np.mean([r["focus_min"] for r in res_baseline]),
         np.mean([r["rate_app"] for r in res_baseline])]
    i = [np.mean([r["comfort_min"] for r in res_intervention]),
         np.mean([r["focus_min"] for r in res_intervention]),
         np.mean([r["rate_app"] for r in res_intervention])]

    x = np.arange(len(labels))
    w = 0.38
    plt.figure(figsize=(8,4.5))
    plt.bar(x-w/2, b, width=w, label="Baseline")
    plt.bar(x+w/2, i, width=w, label="Intervention")
    plt.xticks(x, labels)
    plt.ylabel("Value")
    plt.title("Baseline vs Intervention (synthetic)")
    plt.legend(frameon=False)
    plt.tight_layout()
    plt.savefig(outpath)
    plt.close()

def timeline(df, ev, title, outpath):
    fig, (ax1, ax2, ax3) = plt.subplots(3,1, sharex=True, figsize=(10,6))
    t = df["iso_ts"]
    # HI
    ax1.plot(t, df["heat_index_c"], lw=1.4)
    ax1.axhspan(24,27, color="lightgreen", alpha=0.15)
    ax1.set_ylabel("HI (°C)"); ax1.grid(True, alpha=0.25)
    # Fidget with occupied shading
    ax2.plot(t, df["fidget"], lw=1.2)
    occ = df["occupied"].to_numpy()
    # shade occupied
    start=None
    for i in range(len(df)):
        if occ[i]==1 and start is None: start=i
        if (occ[i]==0 and start is not None) or (i==len(df)-1 and start is not None):
            end = i if occ[i]==0 else i
            ax2.axvspan(t.iloc[start], t.iloc[end], color="lightblue", alpha=0.08)
            start=None
    ax2.set_ylabel("Fidget"); ax2.grid(True, alpha=0.25)
    # Phone events strip (per-app markers)
    if not ev.empty:
        ev = ev.sort_values("iso_ts")
        apps = ev["app"].fillna("").str.lower()
        marker_map = {"": "o", "instagram": "^", "tiktok": "s", "reddit": "v"}
        for app_name in apps.unique():
            e = ev[apps==app_name]
            ax3.scatter(e["iso_ts"], [0]*len(e),
                        s=(26 if app_name else 16),
                        marker=marker_map.get(app_name, "x"),
                        alpha=0.9 if app_name else 0.7,
                        label=(app_name if app_name else "unlock"))
    ax3.set_yticks([]); ax3.set_ylabel("Phone")
    ax3.grid(True, axis="x", alpha=0.25)
    ax3.legend(loc="upper right", frameon=False)
    ax3.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    fig.suptitle(title)
    fig.autofmt_xdate()
    plt.tight_layout()
    plt.savefig(outpath)
    plt.close()

def main():
    # load sessions
    pairs = [
        ("baseline","2025-09-26_A"),
        ("baseline","2025-09-26_B"),
        ("intervention","2025-09-27_A"),
        ("intervention","2025-09-27_B"),
    ]
    res_b, res_i = [], []
    # compute metrics & save timelines for one example of each
    for kind, name in pairs:
        df, ev = load_pair(kind, name)
        m = metrics(df, ev)
        if kind=="baseline": res_b.append(m)
        else: res_i.append(m)

    # bars
    bar_plot(res_b, res_i, OUTIMG / "validation_bars_synth.png")

    # timelines for one baseline & one intervention
    df_b, ev_b = load_pair("baseline", "2025-09-26_A")
    df_i, ev_i = load_pair("intervention", "2025-09-27_A")
    timeline(df_b, ev_b, "Baseline (synthetic)", OUTIMG / "validation_timeline_baseline_synth.png")
    timeline(df_i, ev_i, "Intervention (synthetic)", OUTIMG / "validation_timeline_intervention_synth.png")

    # print headline numbers
    def summarize(tag, res):
        print(f"\n{tag}:")
        print("  Comfort min (avg):   ", np.mean([r['comfort_min'] for r in res]).round(1))
        print("  Focus min (avg):     ", np.mean([r['focus_min']   for r in res]).round(1))
        print("  App unlocks/hr (avg):", np.mean([r['rate_app']    for r in res]).round(2))

    summarize("Baseline", res_b)
    summarize("Intervention", res_i)
    print("\nWrote figures to:", OUTIMG)

if __name__ == "__main__":
    main()
