import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

# === CONFIG ===
FILENAME = "dht22_data.csv"

# === Step 1: Load CSV data ===
df = pd.read_csv(FILENAME, header=None, names=["timestamp", "temperature", "humidity"])

# === Step 2: Convert timestamps to datetime ===
df["datetime"] = pd.to_datetime(df["timestamp"], format="%Y%m%d%H%M%S")

# === Step 3: Create combined plot with two y-axes ===
fig, ax1 = plt.subplots(figsize=(12, 6))

# Primary Y-axis (Left): Temperature
color1 = "tab:red"
ax1.set_xlabel("Time")
ax1.set_ylabel("Temperature (°C)", color=color1)
ax1.plot(df["datetime"], df["temperature"], color=color1, marker='o', label="Temperature")
ax1.tick_params(axis='y', labelcolor=color1)

# Secondary Y-axis (Right): Humidity
ax2 = ax1.twinx()
color2 = "tab:blue"
ax2.set_ylabel("Humidity (%)", color=color2)
ax2.plot(df["datetime"], df["humidity"], color=color2, marker='x', linestyle='--', label="Humidity")
ax2.tick_params(axis='y', labelcolor=color2)

# === Add title and grid ===
plt.title("DHT22 Sensor Readings: Temperature and Humidity Over Time")
fig.tight_layout()
ax1.grid(True)

plt.show()
