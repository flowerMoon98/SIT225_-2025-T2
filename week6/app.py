# app.py
# Plotly Dash Gyroscope Explorer
# - Reads ./gyro_samples_clean.csv from your Week 6 project root
# - Chart type dropdown: Line, Scatter, Histogram, Box (basic + distribution)
# - Axis selector: choose X, Y, Z (any or all)
# - Sample window: enter N samples, page with Prev/Next
# - Summary table updates whenever the graph updates

import os
import pandas as pd
import numpy as np
from dash import Dash, dcc, html, dash_table, Input, Output, State, ctx
import plotly.graph_objects as go
import plotly.express as px

CSV_PATH = "./gyro_samples_clean.csv"  # keep the CSV in the same folder as app.py

# ---------- Load & prepare data ----------
if not os.path.exists(CSV_PATH):
    raise FileNotFoundError(f"CSV not found at {CSV_PATH}. Put gyro_samples_clean.csv in the same folder as app.py.")

df_raw = pd.read_csv(CSV_PATH)

# Try to detect timestamp column
time_col = None
for cand in ["timestamp", "time", "datetime", "date"]:
    if cand in df_raw.columns:
        time_col = cand
        break

if time_col is not None:
    # parse to datetime if possible; if it fails, we keep as string
    try:
        df_raw[time_col] = pd.to_datetime(df_raw[time_col])
    except Exception:
        pass

# Try to detect gyro axis columns (robust to various names)
axis_candidates = {
    "x": ["x", "gx", "gyro_x", "gyroX", "accel_x"],
    "y": ["y", "gy", "gyro_y", "gyroY", "accel_y"],
    "z": ["z", "gz", "gyro_z", "gyroZ", "accel_z"],
}
axis_map = {}
for axis, names in axis_candidates.items():
    for name in names:
        if name in df_raw.columns:
            axis_map[axis] = name
            break

# If nothing found, fall back to the first three numeric columns
if len(axis_map) == 0:
    numeric_cols = [c for c in df_raw.columns if pd.api.types.is_numeric_dtype(df_raw[c])]
    if len(numeric_cols) >= 3:
        axis_map = {"x": numeric_cols[0], "y": numeric_cols[1], "z": numeric_cols[2]}
    elif len(numeric_cols) > 0:
        # Partial availability is okay; we’ll only show what exists
        for lbl, col in zip(["x", "y", "z"], numeric_cols):
            axis_map[lbl] = col

# Build a working DataFrame with friendly column names
df = df_raw.copy()
for short, real in axis_map.items():
    if short != real and real in df.columns:
        df.rename(columns={real: short}, inplace=True)

# Index column for plotting if no time available
df["sample_idx"] = np.arange(len(df))

# Which axes do we actually have?
available_axes = [a for a in ["x", "y", "z"] if a in df.columns and pd.api.types.is_numeric_dtype(df[a])]
if len(available_axes) == 0:
    raise ValueError("No numeric X/Y/Z gyro columns found. Ensure your CSV has x,y,z (or recognizable) numeric columns.")

# ---------- Build the app ----------
app = Dash(__name__)
app.title = "Gyroscope CSV Explorer"

app.layout = html.Div(
    className="container",
    children=[
        html.H1("Gyroscope CSV Explorer", style={"marginBottom": "0.5rem"}),
        html.Div(
            f"Loaded {len(df)} samples from {os.path.basename(CSV_PATH)}",
            style={"color": "#666", "marginBottom": "1rem"},
        ),

        # Controls row
        html.Div(
            style={"display": "grid", "gridTemplateColumns": "1fr 1fr 1fr 0.5fr 0.5fr", "gap": "12px", "alignItems": "end"},
            children=[
                html.Div([
                    html.Label("Chart type"),
                    dcc.Dropdown(
                        id="chart-type",
                        options=[
                            {"label": "Line", "value": "line"},
                            {"label": "Scatter", "value": "scatter"},
                            {"label": "Histogram", "value": "hist"},
                            {"label": "Box (distribution)", "value": "box"},
                        ],
                        value="line",
                        clearable=False,
                    ),
                ]),
                html.Div([
                    html.Label("Axes (X/Y/Z)"),
                    dcc.Dropdown(
                        id="axes",
                        options=[{"label": ax.upper(), "value": ax} for ax in available_axes],
                        value=available_axes,  # default: show all that exist
                        multi=True,
                    ),
                ]),
                html.Div([
                    html.Label("Samples per page (N)"),
                    dcc.Input(
                        id="n-samples",
                        type="number",
                        min=10, step=10,
                        value=min(500, len(df)),  # sensible default
                        debounce=True,
                        style={"width": "100%"},
                    ),
                ]),
                html.Div([
                    html.Label(" "),
                    html.Button("Prev", id="prev-btn", n_clicks=0, style={"width": "100%"}),
                ]),
                html.Div([
                    html.Label(" "),
                    html.Button("Next", id="next-btn", n_clicks=0, style={"width": "100%"}),
                ]),
            ]
        ),

        # Store for paging offset
        dcc.Store(id="page-offset", data=0),

        # Window info
        html.Div(id="window-info", style={"margin": "12px 0", "color": "#444"}),

        # Graph
        dcc.Graph(id="gyro-graph", style={"height": "520px"}),

        # Summary table
        html.H3("Summary of Current Window"),
        dash_table.DataTable(
            id="summary-table",
            style_table={"maxWidth": "720px"},
            style_cell={"textAlign": "center", "padding": "6px"},
            style_header={"fontWeight": "bold"},
        ),
    ]
)

# ---------- Helpers ----------
def compute_window(df_in, offset, n):
    """Return a slice of df_in from offset to offset+n, clipped to valid range."""
    total = len(df_in)
    if total == 0:
        return df_in.iloc[0:0], 0, 0, 0
    n = max(1, int(n)) if pd.notna(n) else total
    start = max(0, min(int(offset), max(0, total - 1)))
    end = min(total, start + n)
    return df_in.iloc[start:end], start, end, total

def make_summary(df_win, axes, start, end, total):
    """Build a tidy stats table for the selected axes in the current window."""
    rows = []
    for ax in axes:
        if ax in df_win.columns and pd.api.types.is_numeric_dtype(df_win[ax]):
            s = df_win[ax].dropna()
            if len(s) == 0:
                continue
            stats = {
                "Axis": ax.upper(),
                "Count": int(s.count()),
                "Mean": float(s.mean()),
                "Std": float(s.std(ddof=1)) if s.count() > 1 else 0.0,
                "Min": float(s.min()),
                "25%": float(s.quantile(0.25)),
                "Median": float(s.median()),
                "75%": float(s.quantile(0.75)),
                "Max": float(s.max()),
            }
            rows.append(stats)
    meta = f"Showing samples {start}–{end-1} of {total} (window size {end-start})"
    return rows, meta

def build_figure(df_win, axes, chart_type):
    """Return a Plotly Figure according to chart type and selected axes."""
    # X-axis: timestamp if available, else sample_idx
    x_axis = "sample_idx"
    x_title = "Sample #"
    if "timestamp" in df_win.columns or "time" in df_win.columns or "datetime" in df_win.columns or "date" in df_win.columns:
        # choose first available time-like column in the original priority
        for cand in ["timestamp", "time", "datetime", "date"]:
            if cand in df_win.columns:
                x_axis = cand
                x_title = cand.capitalize()
                break

    fig = go.Figure()

    if chart_type in ("line", "scatter"):
        mode = "lines" if chart_type == "line" else "markers"
        for ax in axes:
            if ax in df_win.columns:
                fig.add_trace(go.Scatter(
                    x=df_win[x_axis],
                    y=df_win[ax],
                    mode=mode,
                    name=ax.upper(),
                ))
        fig.update_layout(
            xaxis_title=x_title,
            yaxis_title="Angular rate / units",
            legend_title="Axis",
            margin=dict(l=40, r=20, t=20, b=40),
        )

    elif chart_type == "hist":
        # Overlaid histograms for each axis
        for ax in axes:
            if ax in df_win.columns:
                fig.add_trace(go.Histogram(
                    x=df_win[ax],
                    name=ax.upper(),
                    opacity=0.65,
                ))
        fig.update_layout(
            barmode="overlay",
            xaxis_title="Value",
            yaxis_title="Count",
            legend_title="Axis",
            margin=dict(l=40, r=20, t=20, b=40),
        )

    elif chart_type == "box":
        # Box plots for distribution comparison
        for ax in axes:
            if ax in df_win.columns:
                fig.add_trace(go.Box(
                    y=df_win[ax],
                    name=ax.upper(),
                    boxmean=True
                ))
        fig.update_layout(
            yaxis_title="Value",
            margin=dict(l=40, r=20, t=20, b=40),
        )

    return fig

# ---------- Callbacks ----------
@app.callback(
    Output("page-offset", "data"),
    Input("prev-btn", "n_clicks"),
    Input("next-btn", "n_clicks"),
    Input("n-samples", "value"),
    Input("axes", "value"),
    Input("chart-type", "value"),
    State("page-offset", "data"),
    prevent_initial_call=True
)
def update_offset(prev_clicks, next_clicks, n_samples, axes, chart_type, offset):
    """
    Paging logic.
    - If Prev/Next clicked: move by N samples.
    - If other controls changed (n, axes, chart type): reset to 0 for a fresh view.
    """
    triggered = ctx.triggered_id
    total = len(df)
    n = max(1, int(n_samples)) if pd.notna(n_samples) else total
    max_start = max(0, total - n)

    if triggered == "prev-btn":
        new_offset = max(0, int(offset or 0) - n)
    elif triggered == "next-btn":
        new_offset = min(max_start, int(offset or 0) + n)
    else:
        # Controls changed → reset paging
        new_offset = 0
    return int(new_offset)

@app.callback(
    Output("gyro-graph", "figure"),
    Output("summary-table", "data"),
    Output("summary-table", "columns"),
    Output("window-info", "children"),
    Input("chart-type", "value"),
    Input("axes", "value"),
    Input("n-samples", "value"),
    Input("page-offset", "data"),
)
def update_outputs(chart_type, axes, n_samples, offset):
    # normalize axes input (could be None or single str)
    if axes is None:
        axes = []
    if isinstance(axes, str):
        axes = [axes]
    axes = [a for a in axes if a in available_axes]
    if not axes:
        # Fall back to at least one axis
        axes = available_axes[:1]

    df_win, start, end, total = compute_window(df, offset or 0, n_samples)
    fig = build_figure(df_win, axes, chart_type)
    rows, meta = make_summary(df_win, axes, start, end, total)

    columns = [{"name": k, "id": k} for k in (rows[0].keys() if rows else ["Axis", "Count", "Mean", "Std", "Min", "25%", "Median", "75%", "Max"])]
    return fig, rows, columns, meta

if __name__ == "__main__":
    app.run(debug=True)