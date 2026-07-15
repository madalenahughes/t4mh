import sys
import pandas as pd
import matplotlib.pyplot as plt

if len(sys.argv) != 2:
    print("Usage: python plot_session.py logs/session_xxx_samples.csv")
    sys.exit(1)

csv_path = sys.argv[1]
df = pd.read_csv(csv_path)

t = df["t_rel_s"]
rmssd = df["rmssd_ms"]
tempo = df["tempo"]

plt.figure(figsize=(12,6))

# Background phases
plt.axvspan(0, 30, color="lightgray", alpha=0.4, label="Baseline")
plt.axvspan(30, t.max(), color="lightgreen", alpha=0.25, label="Adaptive")

ax1 = plt.gca()

ax1.plot(
    t,
    rmssd,
    linewidth=2.5,
)

ax1.set_xlabel("Time (s)")
ax1.set_ylabel("RMSSD (ms)")
ax1.grid(True)

ax2 = ax1.twinx()

ax2.plot(
    t,
    tempo,
    "--",
    linewidth=2,
    label="Adaptive Tempo",
)

ax2.set_ylabel("Tempo multiplier")

lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()

ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")

plt.title("Adaptive Music Session with 1Beeth.wav")

plt.tight_layout()

outfile = csv_path.replace("_samples.csv", ".png")
plt.savefig(outfile, dpi=300)

print(f"Saved {outfile}")

plt.show()
