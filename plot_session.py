import sys
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt


BASELINE_END = 60
MUSIC_END = 120


def plot_session(csv_file):

    df = pd.read_csv(csv_file)

    t = df["t_rel_s"]
    rmssd = df["smoothed_rmssd_ms"]

    baseline = rmssd[t < BASELINE_END].mean()

    fig, ax1 = plt.subplots(figsize=(14, 7))

    # --------------------------------------------------
    # Background regions
    # --------------------------------------------------

    ax1.axvspan(
        0,
        BASELINE_END,
        color="lightgray",
        alpha=0.25,
        label="Baseline"
    )

    ax1.axvspan(
        BASELINE_END,
        MUSIC_END,
        color="lightskyblue",
        alpha=0.25,
        label="Music only"
    )

    ax1.axvspan(
        MUSIC_END,
        t.max(),
        color="lightgreen",
        alpha=0.20,
        label="Adaptive"
    )

    # vertical separators

    ax1.axvline(BASELINE_END, ls=":", color="gray")
    ax1.axvline(MUSIC_END, ls=":", color="gray")

    # --------------------------------------------------
    # RMSSD
    # --------------------------------------------------

    ax1.plot(
        t,
        rmssd,
        color="tab:blue",
        lw=3,
        label="RMSSD (ms)"
    )

    ax1.axhline(
        baseline,
        ls="--",
        color="tab:blue",
        alpha=.6,
        label="Baseline RMSSD"
    )

    ax1.set_xlabel("Time (s)")
    ax1.set_ylabel("RMSSD (ms)", color="tab:blue")

    # --------------------------------------------------
    # Adaptive variable
    # --------------------------------------------------

    ax2 = ax1.twinx()

    if "tempo" in df.columns:

        ax2.plot(
            t,
            df["tempo"],
            color="tab:orange",
            lw=2.5,
            label="Tempo multiplier"
        )

        ax2.set_ylabel(
            "Tempo multiplier",
            color="tab:orange"
        )

    elif "pitch" in df.columns:

        ax2.plot(
            t,
            df["pitch"],
            color="tab:red",
            lw=2.5,
            label="Pitch shift"
        )

        ax2.set_ylabel(
            "Pitch shift (semitones)",
            color="tab:red"
        )

    # --------------------------------------------------

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()

    ax1.legend(
        lines1 + lines2,
        labels1 + labels2,
        loc="upper left"
    )

    plt.title(f"Session: {Path(csv_file).stem}")

    plt.tight_layout()

    out = Path(csv_file).with_suffix("")

    plt.savefig(
        f"{out}_plot.png",
        dpi=300
    )

    print(f"Saved {out}_plot.png")

    plt.show()


if __name__ == "__main__":

    if len(sys.argv) != 2:

        print("Usage:")
        print("python plot_session.py session.csv")
        sys.exit()

    plot_session(sys.argv[1])
