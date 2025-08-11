import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import MaxNLocator

CSV_FILE = "dht22_cloud_log.csv"

# --- Load & clean ---
df = pd.read_csv(CSV_FILE)

# Remove any accidental header rows that got appended later
df = df[df["timestamp"] != "timestamp"]

# Parse timestamp with your exact format: "YYYY-mm-dd HH:MM:SS"
df["timestamp"] = pd.to_datetime(df["timestamp"],
                                 format="%Y-%m-%d %H:%M:%S",
                                 errors="coerce")

# Force numeric, drop non-numeric/bad rows
df["temperature"] = pd.to_numeric(df["temperature"], errors="coerce")
df["humidity"]    = pd.to_numeric(df["humidity"], errors="coerce")

df = df.dropna(subset=["timestamp", "temperature", "humidity"])
df = df.sort_values("timestamp").drop_duplicates(subset=["timestamp"])

# --- Plot (clean axes, dual y) ---
fig, ax1 = plt.subplots(figsize=(11, 5))
ax2 = ax1.twinx()

t_line, = ax1.plot(df["timestamp"], df["temperature"], label="Temperature (°C)", marker="o", linewidth=1)
h_line, = ax2.plot(df["timestamp"], df["humidity"],    label="Humidity (%)",    marker="o", linewidth=1, linestyle="--")

# Nice datetime ticks
locator = mdates.AutoDateLocator(minticks=4, maxticks=8)
ax1.xaxis.set_major_locator(locator)
ax1.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))

# Y ranges with padding
tmin, tmax = df["temperature"].min(), df["temperature"].max()
hmin, hmax = df["humidity"].min(), df["humidity"].max()
ax1.set_ylim(tmin - 0.5, tmax + 0.5)
ax2.set_ylim(max(0, hmin - 2), min(100, hmax + 2))

ax1.set_xlabel("Time (Melbourne)")
ax1.set_ylabel("Temperature (°C)")
ax2.set_ylabel("Humidity (%)")
ax1.grid(True, linestyle=":", alpha=0.6)

ax1.yaxis.set_major_locator(MaxNLocator(nbins=6))
ax2.yaxis.set_major_locator(MaxNLocator(nbins=6))

lines = [t_line, h_line]
ax1.legend(lines, [l.get_label() for l in lines], loc="upper left")

plt.tight_layout()
plt.show()