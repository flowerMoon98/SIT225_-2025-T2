# week-9/apps/live_plot.py
# Live Matplotlib viewer for FocusAir CSV logs
# Panels: Heat Index (°C), Temp & Humidity, Fidget (+ occupied shading), PIR, Phone Events
# Phone Events panel: distinct markers per app, circles for plain unlock (no app).

import sys
from pathlib import Path
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import matplotlib.dates as mdates

# If you don't see a window, uncomment one:
# matplotlib.use("MacOSX")  # macOS native
# matplotlib.use("TkAgg")   # cross-platform

# ---------- paths ----------
PROJECT_ROOT = Path(__file__).resolve().parents[1]   # .../week-9
DATA_DIR = PROJECT_ROOT / "data"
CSV_GLOB = "*.csv"
EVENTS_RAW = DATA_DIR / "events.csv"          # stream raw first
EVENTS_CLEAN = DATA_DIR / "events_clean.csv"  # fallback
print("[LivePlot] DATA_DIR =", DATA_DIR, "exists:", DATA_DIR.exists())

# ---------- config ----------
TAIL_ROWS  = 1200      # ~5 minutes at ~4 Hz
REFRESH_MS = 1000      # redraw every 1s

# App marker preferences (you can change these)
APP_MARKERS_PREF = {
    "instagram": "^",   # triangle_up
    "tiktok":    "s",   # square
    "reddit":    "v",   # triangle_down
}
# Fallback marker cycle for any new/unknown apps discovered at runtime
FALLBACK_MARKERS = ["D", "P", "X", "*", ">", "<", "h", "H", "+", "x"]

PLAIN_UNLOCK_MARKER = "o"   # no app field => plain unlock

# Optional CLI override: python apps/live_plot.py data/2025-09-25.csv
CSV_OVERRIDE = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else None

def latest_csv():
    if CSV_OVERRIDE and CSV_OVERRIDE.exists():
        return CSV_OVERRIDE
    files = [p for p in DATA_DIR.glob(CSV_GLOB) if p.suffix==".csv" and p.name[:2].isdigit()]
    files = sorted(files)
    return files[-1] if files else None

def load_df():
    p = latest_csv()
    if not p or not p.exists():
        return pd.DataFrame(), None
    df = pd.read_csv(p, on_bad_lines="skip", engine="python")

    # coerce types
    for c in ["occupied","focused","pir_raw","motion"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)
    for c in ["heat_index_c","fidget","temp_c","hum_pct","ms"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    if "heat_index_c" in df.columns:
        df.loc[df["heat_index_c"] <= -100, "heat_index_c"] = np.nan

    # time axis
    if "iso_ts" in df.columns:
        df["t"] = pd.to_datetime(df["iso_ts"], errors="coerce")
    elif "ms" in df.columns:
        df["t"] = pd.to_datetime(df["ms"]/1000.0, unit="s")
    else:
        df["t"] = pd.to_datetime(np.arange(len(df))*0.25, unit="s")

    if len(df) > TAIL_ROWS:
        df = df.tail(TAIL_ROWS).copy()

    return df, p.name

def load_events_live():
    """
    Read events directly (no preprocessing). Minimal normalization in-memory.
    Returns columns: t, app  (type is always 'unlock' by your design; app optional)
    """
    path = EVENTS_RAW if EVENTS_RAW.exists() else EVENTS_CLEAN
    if not path.exists():
        return pd.DataFrame(columns=["t","app"])
    try:
        ev = pd.read_csv(path, on_bad_lines="skip", engine="python")
    except Exception:
        return pd.DataFrame(columns=["t","app"])

    if "iso_ts" not in ev.columns:
        return pd.DataFrame(columns=["t","app"])

    ev["t"] = pd.to_datetime(ev["iso_ts"], errors="coerce")
    ev = ev.dropna(subset=["t"]).sort_values("t")

    # normalize app field
    if "app" in ev.columns:
        ev["app"] = ev["app"].fillna("").astype(str).str.strip().str.lower()
    else:
        ev["app"] = ""

    # soft de-dup within 10s for same app/empty-app
    if len(ev) >= 2:
        ev = ev.reset_index(drop=True)
        keep = [True]
        for i in range(1, len(ev)):
            same = (ev.loc[i,"app"] == ev.loc[i-1,"app"])
            gap  = (ev.loc[i,"t"] - ev.loc[i-1,"t"]).total_seconds()
            keep.append(not (same and gap < 10))
        ev = ev[pd.Series(keep).values]

    # limit to last 1000
    if len(ev) > 1000:
        ev = ev.tail(1000)
    return ev[["t","app"]]

# ---------- plotting setup ----------
plt.rcParams["figure.figsize"] = (12, 12)
fig, axs = plt.subplots(5, 1, sharex=True)
ax_hi, ax_th, ax_fid, ax_pir, ax_evt = axs

# Heat Index
hi_line, = ax_hi.plot([], [], lw=1.6)
ax_hi.axhspan(24, 27, color="lightgreen", alpha=0.15)  # comfort band
ax_hi.set_ylabel("Heat Index (°C)")
ax_hi.grid(True, alpha=0.25)

# Temp & Humidity (twin y-axes)
temp_line, = ax_th.plot([], [], lw=1.3, label="temp_c")
ax_th.set_ylabel("Temp (°C)")
ax_th.grid(True, alpha=0.25)
ax_th2 = ax_th.twinx()
hum_line, = ax_th2.plot([], [], lw=1.0, label="hum_pct")
ax_th2.set_ylabel("Humidity (%)")

# Fidget
fid_line, = ax_fid.plot([], [], lw=1.3)
ax_fid.set_ylabel("Fidget")
ax_fid.grid(True, alpha=0.25)

# PIR panel: raw vs latched occupied (step lines)
pir_raw_line,   = ax_pir.plot([], [], lw=1.2, drawstyle="steps-post", label="pir_raw")
occupied_line,  = ax_pir.plot([], [], lw=1.2, drawstyle="steps-post", label="occupied")
ax_pir.set_ylabel("PIR")
ax_pir.set_yticks([0, 1])
ax_pir.set_ylim(-0.2, 1.2)
ax_pir.grid(True, alpha=0.25)
ax_pir.legend(loc="upper right", frameon=False)

# Phone Events panel (distinct markers per app; circles for plain unlock)
ax_evt.set_ylabel("Phone")
ax_evt.set_yticks([])
ax_evt.set_ylim(-1, 1)  # we just use y=0 line for dots
ax_evt.grid(True, axis="x", alpha=0.25)

# Dynamic collections per app
APP_ARTISTS = {}      # app -> PathCollection
UNKNOWN_MARKER_POOL = iter(FALLBACK_MARKERS)

def get_marker_for_app(app: str) -> str:
    if not app:
        return PLAIN_UNLOCK_MARKER
    if app in APP_MARKERS_PREF:
        return APP_MARKERS_PREF[app]
    # assign next fallback marker for previously unseen app
    try:
        m = next(UNKNOWN_MARKER_POOL)
    except StopIteration:
        # recycle (very rare)
        m = "x"
    APP_MARKERS_PREF[app] = m
    return m

def ensure_artist(app: str):
    """Create (or fetch) a scatter artist for the given app key."""
    if app in APP_ARTISTS:
        return APP_ARTISTS[app]
    marker = get_marker_for_app(app)
    label = "unlock" if app == "" else app
    # create an empty scatter; we'll set offsets later
    art = ax_evt.scatter([], [], s=(26 if app else 18), marker=marker, alpha=0.9 if app else 0.7, label=label)
    APP_ARTISTS[app] = art
    # refresh legend to include the new artist
    ax_evt.legend(loc="upper right", frameon=False)
    return art

# Title + file label
title_txt = fig.suptitle("FocusAir — Live", fontsize=14)
file_lbl  = ax_hi.text(0.01, 0.95, "", transform=ax_hi.transAxes, va="top", fontsize=9)

# x-axis formatting
xfmt = mdates.DateFormatter("%H:%M:%S")
ax_evt.xaxis.set_major_formatter(xfmt)
fig.autofmt_xdate()

# occupied shading on the fidget axis
_occ_patches = []
def clear_occ_patches():
    global _occ_patches
    for p in _occ_patches:
        try: p.remove()
        except Exception: pass
    _occ_patches = []

def add_occ_shading(ax, t, occ):
    """Shade intervals where occupied==1."""
    if t is None or occ is None or len(t) < 2:
        return
    start = None
    for i in range(len(occ)):
        if occ[i] == 1 and start is None:
            start = i
        if (occ[i] == 0 and start is not None) or (i == len(occ) - 1 and start is not None):
            end = i if occ[i] == 0 else i
            _occ_patches.append(ax.axvspan(t[start], t[end], color="lightblue", alpha=0.08))
            start = None

def update(_):
    df, fname = load_df()
    now = datetime.now()
    now_str = now.strftime("%H:%M:%S")

    if df.empty:
        title_txt.set_text(f"FocusAir — Live   •   Last update {now_str}")
        file_lbl.set_text("No data found in data/*.csv")
        # clear lines
        for ln in [hi_line, temp_line, hum_line, fid_line, pir_raw_line, occupied_line]:
            ln.set_data([], [])
        # clear all event artists
        for art in APP_ARTISTS.values():
            art.set_offsets(np.empty((0,2)))
        fig.canvas.draw_idle()
        return tuple([hi_line, temp_line, hum_line, fid_line, pir_raw_line, occupied_line] + list(APP_ARTISTS.values()))

    # x/y data for sensors
    t_dt = df["t"]
    t = mdates.date2num(t_dt)
    hi = df.get("heat_index_c", pd.Series([np.nan]*len(df))).to_numpy()
    tc = df.get("temp_c",      pd.Series([np.nan]*len(df))).to_numpy()
    rh = df.get("hum_pct",     pd.Series([np.nan]*len(df))).to_numpy()
    fid = df.get("fidget",     pd.Series([np.nan]*len(df))).to_numpy()
    pir_raw  = df.get("pir_raw",  pd.Series([0]*len(df))).to_numpy()
    occupied = df.get("occupied", pd.Series([0]*len(df))).to_numpy()

    # lines
    hi_line.set_data(t, hi)
    temp_line.set_data(t, tc)
    hum_line.set_data(t, rh)
    fid_line.set_data(t, fid)
    pir_raw_line.set_data(t, pir_raw)
    occupied_line.set_data(t, occupied)

    # y-lims
    if np.isfinite(hi).any():
        ymin = np.nanmin(hi); ymax = np.nanmax(hi)
        if np.isfinite(ymin) and np.isfinite(ymax):
            pad = max(0.5, (ymax - ymin) * 0.2) if ymax > ymin else 1.0
            ax_hi.set_ylim(ymin - pad*0.2, ymax + pad*0.2)
    ax_hi.relim(); ax_hi.autoscale_view(scalex=True, scaley=False)

    if np.isfinite(tc).any():
        tmin = np.nanmin(tc); tmax = np.nanmax(tc)
        if np.isfinite(tmin) and np.isfinite(tmax):
            pad = (tmax - tmin) * 0.2 if tmax > tmin else 1.0
            ax_th.set_ylim(tmin - pad*0.1, tmax + pad*0.1)
    if np.isfinite(rh).any():
        rmin = max(0.0, np.nanmin(rh)); rmax = min(100.0, np.nanmax(rh))
        ax_th2.set_ylim(max(0.0, rmin - 5), min(100.0, rmax + 5))

    if np.isfinite(fid).any():
        fmin = np.nanmin(fid); fmax = np.nanmax(fid)
        if np.isfinite(fmin) and np.isfinite(fmax):
            pad = (fmax - fmin) * 0.2 if fmax > fmin else 0.1
            ax_fid.set_ylim(fmin - pad, fmax + pad)
    ax_fid.relim(); ax_fid.autoscale_view(scalex=True, scaley=False)

    # x-lims
    if len(t) >= 2:
        x0, x1 = t[0], t[-1]
        for ax in (ax_hi, ax_th, ax_fid, ax_pir, ax_evt):
            ax.set_xlim(x0, x1)

    # occupied shading
    clear_occ_patches()
    add_occ_shading(ax_fid, t_dt.to_numpy(), occupied)

    # ---- realtime phone events panel with per-app markers ----
    ev = load_events_live()
    # compute KPIs regardless (last 60s & 5min by wall-clock)
    last60 = last300 = 0
    last_app = ""
    last_text = "–"
    if not ev.empty:
        # update KPIs
        last60_start  = now - timedelta(seconds=60)
        last300_start = now - timedelta(seconds=300)
        last60  = (ev["t"] >= last60_start).sum()
        last300 = (ev["t"] >= last300_start).sum()
        if len(ev) > 0:
            last_dt = ev["t"].iloc[-1]
            last_app = ev["app"].iloc[-1]
            last_text = last_dt.strftime("%H:%M:%S")

        # only show events inside current sensor window
        t0, t1 = t_dt.iloc[0], t_dt.iloc[-1]
        evw = ev[(ev["t"] >= t0) & (ev["t"] <= t1)].copy()

        # group by 'app' ("" for plain unlock)
        for app_name, df_app in evw.groupby("app", dropna=False):
            artist = ensure_artist(app_name)
            if df_app.empty:
                artist.set_offsets(np.empty((0,2)))
                continue
            xs = mdates.date2num(df_app["t"])
            ys = np.zeros_like(xs)  # y=0 line
            artist.set_offsets(np.column_stack([xs, ys]))

        # also ensure we render artists with no events in window as empty
        for app_name, artist in list(APP_ARTISTS.items()):
            if app_name not in evw["app"].unique():
                artist.set_offsets(np.empty((0,2)))
    else:
        # no events at all yet
        for artist in APP_ARTISTS.values():
            artist.set_offsets(np.empty((0,2)))

    # labels / KPIs
    kpi = f"Last 60s: {last60}   •   Last 5min: {last300}   •   Last event: {last_text}"
    if last_app:
        kpi += f" ({last_app})"
    title_txt.set_text(f"FocusAir — Live   •   {kpi}   •   Updated {now_str}")
    file_lbl.set_text(f"Reading: {fname}   |   rows: {len(df)}")

    # console heartbeat
    if "ms" in df.columns and df["ms"].notna().sum() > 1:
        sec = df["ms"].to_numpy() / 1000.0
        dt = float(np.median(np.diff(sec)))
    else:
        dt = 0.25
    occ_minutes = (occupied.sum() * dt) / 60.0
    print(f"[LivePlot] {fname} rows={len(df)}  occupied≈{occ_minutes:.2f} min  events60={last60}  events5m={last300}")

    # return all artists so FuncAnimation can manage redraws
    return tuple([hi_line, temp_line, hum_line, fid_line, pir_raw_line, occupied_line] + list(APP_ARTISTS.values()))

ani = FuncAnimation(fig, update, interval=REFRESH_MS, blit=False, cache_frame_data=False)
plt.tight_layout()
plt.show()
