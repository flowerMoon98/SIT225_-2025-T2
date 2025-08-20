import pandas as pd
import matplotlib.pyplot as plt

CSV = "gyro_samples_clean.csv"

def main():
    df = pd.read_csv(CSV)
    if df.empty:
        print("No data.")
        return

    # Separate plots
    for axis in ["gx","gy","gz"]:
        plt.figure()
        plt.plot(df[axis])
        plt.title(f"{axis} (deg/s)")
        plt.xlabel("sample")
        plt.ylabel("deg/s")
        plt.tight_layout()

    # Combined plot
    plt.figure()
    plt.plot(df["gx"], label="gx")
    plt.plot(df["gy"], label="gy")
    plt.plot(df["gz"], label="gz")
    plt.title("Gyroscope (deg/s)")
    plt.xlabel("sample")
    plt.ylabel("deg/s")
    plt.legend()
    plt.tight_layout()

    plt.show()

if __name__ == "__main__":
    main()