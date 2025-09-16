# week-8/app.py
from datetime import datetime
import threading, time, pathlib, csv
from collections import deque

import pandas as pd
from arduino_iot_cloud import ArduinoCloudClient
from credentials import DEVICE_ID, SECRET_KEY

# Dash/Plotly
from dash import Dash, dcc, html, Output, Input, no_update
import plotly.graph_objects as go
import plotly.io as pio

# ========= Settings you can tune =========
N_CHUNK = 100        # how many samples to accumulate before refreshing/saving
MAX_POINTS = 5000     # keep plot memory bounded (rolling window)
SAVE_DIR = pathlib.Path("snapshots")
SAVE_DIR.mkdir(exist_ok=True)
# ========================================

# ---- thread-safe buffers ----
buf_lock = threading.Lock()
in_x, in_y, in_z = deque(), deque(), deque()   # incoming streams (time-aligned by arrival)
out_x, out_y, out_z = deque(), deque(), deque()  # last "chunk" displayed on the graph

def now_ts():  # ISO timestamp
    return datetime.now().isoformat(timespec="seconds")

# ---- Arduino IoT Cloud client (on_write fires when cloud variable updates) ----
def start_cloud_client():
    def on_ax(client, value):
        with buf_lock:
            in_x.append((datetime.now(), float(value)))
    def on_ay(client, value):
        with buf_lock:
            in_y.append((datetime.now(), float(value)))
    def on_az(client, value):
        with buf_lock:
            in_z.append((datetime.now(), float(value)))

    client = ArduinoCloudClient(device_id=DEVICE_ID, username=DEVICE_ID, password=SECRET_KEY)
    client.register("ax", value=None, on_write=on_ax)
    client.register("ay", value=None, on_write=on_ay)
    client.register("az", value=None, on_write=on_az)
    print("[Cloud] Connecting…")
    client.start()  # blocking loop; run in a thread

# ---- helper: move N_CHUNK samples from input buffers to output, save CSV/PNG ----
def take_chunk_and_save():
    """
    Returns (fig, saved_csv_path, saved_png_path) if a new chunk was cut, else (None, None, None).
    """
    with buf_lock:
        if len(in_x) < N_CHUNK or len(in_y) < N_CHUNK or len(in_z) < N_CHUNK:
            return None, None, None

        # Take exactly N_CHUNK from each axis, keeping their arrival order
        chunk_x = [in_x.popleft() for _ in range(N_CHUNK)]
        chunk_y = [in_y.popleft() for _ in range(N_CHUNK)]
        chunk_z = [in_z.popleft() for _ in range(N_CHUNK)]

        # Update the "display" window (rolling)
        for t, v in chunk_x:
            out_x.append((t, v))
        for t, v in chunk_y:
            out_y.append((t, v))
        for t, v in chunk_z:
            out_z.append((t, v))

        # Trim rolling window to MAX_POINTS
        for dq in (out_x, out_y, out_z):
            while len(dq) > MAX_POINTS:
                dq.popleft()

    # Build a DataFrame for the chunk (use timestamps from X for index; they’re all very close in arrival)
    df = pd.DataFrame({
        "time": [t for t, _ in chunk_x],
        "x":    [v for _, v in chunk_x],
        "y":    [v for _, v in chunk_y],
        "z":    [v for _, v in chunk_z],
    })

    # Save CSV + PNG with a timestamped filename
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = SAVE_DIR / f"accel_chunk_{stamp}.csv"
    png_path = SAVE_DIR / f"accel_chunk_{stamp}.png"
    df.to_csv(csv_path, index=False)

    # Create figure for both live display & saving
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["time"], y=df["x"], mode="lines", name="X"))
    fig.add_trace(go.Scatter(x=df["time"], y=df["y"], mode="lines", name="Y"))
    fig.add_trace(go.Scatter(x=df["time"], y=df["z"], mode="lines", name="Z"))
    fig.update_layout(title=f"Accelerometer (chunk @ {stamp})",
                      xaxis_title="Time", yaxis_title="m/s²", legend_title="Axis")

    # Save PNG
    pio.write_image(fig, png_path, width=1200, height=500, scale=2)

    return fig, str(csv_path), str(png_path)

# ---- Build the live figure from the rolling window ----
def build_live_fig():
    # Try to use the already-cut rolling window first
    with buf_lock:
        xs = list(out_x); ys = list(out_y); zs = list(out_z)

    if xs and ys and zs:
        t = [t for t, _ in xs]
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=t, y=[v for _, v in xs], mode="lines", name="X"))
        fig.add_trace(go.Scatter(x=t, y=[v for _, v in ys], mode="lines", name="Y"))
        fig.add_trace(go.Scatter(x=t, y=[v for _, v in zs], mode="lines", name="Z"))
        fig.update_layout(title="Accelerometer — live (rolling window)",
                          xaxis_title="Time", yaxis_title="m/s²", legend_title="Axis")
        return fig

    # If no chunk cut yet, draw directly from the incoming buffers
    with buf_lock:
        inxs = list(in_x); inys = list(in_y); inzs = list(in_z)
    m = min(len(inxs), len(inys), len(inzs))
    if m == 0:
        return go.Figure(layout=dict(title="Waiting for data… (move phone with app open)",
                                     xaxis_title="Time", yaxis_title="m/s²"))
    inxs, inys, inzs = inxs[-m:], inys[-m:], inzs[-m:]
    t = [t for t, _ in inxs]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=t, y=[v for _, v in inxs], mode="lines", name="X (live)"))
    fig.add_trace(go.Scatter(x=t, y=[v for _, v in inys], mode="lines", name="Y (live)"))
    fig.add_trace(go.Scatter(x=t, y=[v for _, v in inzs], mode="lines", name="Z (live)"))
    fig.update_layout(title="Accelerometer — live (pre-chunk)",
                      xaxis_title="Time", yaxis_title="m/s²", legend_title="Axis")
    return fig

# ---- Dash app ----
app = Dash(__name__)
app.layout = html.Div([
    html.H2("Week 8 — Live Accelerometer Dashboard (Arduino Cloud → Python → Dash)"),
    html.Div(id="status", style={"marginBottom":"8px", "fontFamily":"monospace"}),
    dcc.Graph(id="live-graph"),
    dcc.Interval(id="tick", interval=1000, n_intervals=0)  # check once per second
])

@app.callback(
    Output("live-graph", "figure"),
    Output("status", "children"),
    Input("tick", "n_intervals"),
    prevent_initial_call=False
)
def on_tick(_):
    # First: if we have >= N_CHUNK new samples, cut a chunk, update rolling, and save files
    fig_chunk, csv_saved, png_saved = take_chunk_and_save()
    if fig_chunk:
        return (
            build_live_fig(),
            f"[{now_ts()}] Updated graph • Saved CSV: {csv_saved} • PNG: {png_saved}"
        )
    # Otherwise just show the current rolling window
    return build_live_fig(), f"[{now_ts()}] Live • waiting for {N_CHUNK} new samples for next save"

def main():
    # Start Cloud client in a background thread
    t = threading.Thread(target=start_cloud_client, daemon=True)
    t.start()
    # Give it a moment to connect
    time.sleep(1.0)
    print("[Dash] Starting server at http://127.0.0.1:8050")
    app.run(debug=True, use_reloader=False)

if __name__ == "__main__":
    main()