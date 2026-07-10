#!/usr/bin/env python3
"""
polar_run.py

Single-script biofeedback run:

- Connects to Polar H10 via rmssd_z_stream()
- Falls back to a simulated HRV stream if no H10 is found
- Uses integral controller to map HRV z-score to tempo/pitch/volume
- Auto-stops when the audio file ends
- Logs per-sample data:
        t_rel_sec, rmssd_z, tempo, pitch, volume
- Computes pre/post windows and writes summary row to stress_summary.csv
"""

import asyncio
import csv
import math
import os
import random
import time
from datetime import datetime
from typing import List, Tuple

from polar_hrv import rmssd_z_stream
from audio_engine import AudioEngine
from controller import AudioParams, update_audio_params


# ===== CONFIG =====
BASELINE_SECONDS = 60         # HRV baseline (music OFF)
PRE_WINDOW_SECONDS = 120      # Full pre window = 60s baseline + 60s static params
POST_WINDOW_SECONDS = 60      # Last 60s of audio
SUMMARY_CSV = "stress_summary.csv"
LOG_DIR = "logs"

SUBJECT_ID = "test_subject"
SESSION_LABEL = "music_biofeedback_1"


# ===== GLOBAL AUDIO STATE =====
audio_engine: AudioEngine | None = None
current_params = AudioParams()


# ======================================================================
# SIMULATED HRV STREAM
# ======================================================================

async def simulated_rmssd_z_stream(update_interval: float = 1.0):
    """
    Async generator that yields a fake RMSSD z-score stream.
    - Slow sinusoidal stress waves + small noise
    """
    print("[polar_run] Using simulated HRV stream (no Polar H10 detected).")
    t0 = time.time()

    while True:
        t = time.time() - t0
        slow = 0.6 * math.sin(2.0 * math.pi * t / 90.0)
        noise = random.uniform(-0.15, 0.15)
        z = slow + noise
        yield z
        await asyncio.sleep(update_interval)


# ======================================================================
# AUDIO HOOK
# ======================================================================

def apply_biofeedback(t_rel: float, z: float, is_baseline: bool, is_post_window: bool):
    """
    Called once per HRV z-score sample.
    Updates tempo/pitch/volume via integral controller.
    """
    global current_params, audio_engine

    hrv_z = z
    faa_z = None  # not used yet

    current_params = update_audio_params(
        current_params,
        hrv_z=hrv_z,
        faa_z=faa_z,
        is_baseline=is_baseline,
        is_post_window=is_post_window,
    )

    if audio_engine is not None:
        audio_engine.set_params(current_params)

    print(
        f"[biofeedback] t={t_rel:6.1f}s z={z:+6.3f} "
        f"{'(baseline)' if is_baseline else ''} | "
        f"tempo={current_params.tempo:.3f} "
        f"pitch={current_params.pitch:.2f} "
        f"vol={current_params.volume:.1f}"
    )


# ======================================================================
# LOGGING HELPERS
# ======================================================================

def write_per_sample_log(
    samples: List[Tuple[float, float, float, float, float]],
    session_id: str,
    directory: str = LOG_DIR,
) -> str:
    """
    Each sample is:
        (t_rel_s, rmssd_z, tempo, pitch, volume)
    """
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, f"session_{session_id}_samples.csv")

    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["t_rel_s", "rmssd_z", "tempo", "pitch", "volume"])

        for t_rel, z, tempo, pitch, volume in samples:
            writer.writerow(
                [
                    round(t_rel, 3),
                    round(z, 6),
                    round(tempo, 4),
                    round(pitch, 4),
                    round(volume, 2),
                ]
            )

    return path


def compute_pre_post(samples):
    """
    Computes pre/post HRV windows from samples.
    samples: list of tuples (t_rel_s, z, tempo, pitch, volume)
    """
    if not samples:
        raise ValueError("No samples to compute pre/post windows.")

    t_last = samples[-1][0]

    # PRE WINDOW = first PRE_WINDOW_SECONDS (usually 120s)
    pre_vals = [z for (t, z, _, _, _) in samples if t <= PRE_WINDOW_SECONDS]

    # POST WINDOW = last POST_WINDOW_SECONDS
    post_start = max(0.0, t_last - POST_WINDOW_SECONDS)
    post_vals = [z for (t, z, _, _, _) in samples if t >= post_start]

    pre_mean = sum(pre_vals) / len(pre_vals)
    post_mean = sum(post_vals) / len(post_vals)
    delta = post_mean - pre_mean

    return pre_mean, post_mean, delta, t_last, len(pre_vals), len(post_vals)


def append_summary_row(
    session_id,
    pre_mean,
    post_mean,
    delta,
    t_last,
    n_pre,
    n_post,
    t_start_iso,
    summary_csv=SUMMARY_CSV,
):
    """
    Appends a summary line to stress_summary.csv
    """
    header = [
        "subject_id",
        "session_label",
        "session_id",
        "t_start_iso",
        "duration_s",
        "baseline_s",
        "pre_window_s",
        "post_window_s",
        "pre_mean_z",
        "post_mean_z",
        "delta_z",
        "pre_n",
        "post_n",
    ]

    row = [
        SUBJECT_ID,
        SESSION_LABEL,
        session_id,
        t_start_iso,
        round(t_last, 3),
        BASELINE_SECONDS,
        PRE_WINDOW_SECONDS,
        POST_WINDOW_SECONDS,
        round(pre_mean, 4),
        round(post_mean, 4),
        round(delta, 4),
        n_pre,
        n_post,
    ]

    file_exists = os.path.isfile(summary_csv)
    with open(summary_csv, "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(header)
        writer.writerow(row)


# ======================================================================
# MAIN SESSION LOOP
# ======================================================================

async def run_session():
    global audio_engine, current_params

    samples = []

    print("\n[polar_run] Starting HRV + adaptive music session...")
    print(f"[polar_run] Baseline: first {BASELINE_SECONDS}s (music OFF)")
    print(f"[polar_run] Pre Window: first {PRE_WINDOW_SECONDS}s")
    print(f"[polar_run] Post Window: last {POST_WINDOW_SECONDS}s of track")
    print("[polar_run] Press Ctrl+C if you need to end manually.\n")

    # Timestamp and session ID
    start_dt = datetime.now()
    session_id = start_dt.strftime("%Y%m%d_%H%M%S")
    t_start_iso = start_dt.isoformat(timespec="seconds")

    t0 = None

    # ----- Initialize audio engine -----
    try:
        audio_engine = AudioEngine()
        current_params = AudioParams()
        audio_engine.finished = False
        audio_engine.player.play()
        audio_engine.set_params(current_params)
    except Exception as e:
        print(f"[polar_run] WARNING: audio engine failed: {e!r}")
        audio_engine = None

    try:
        # ======================================================
        # FIRST TRY REAL POLAR H10 STREAM
        # ======================================================
        print("[polar_run] Trying to connect to Polar H10...")
        try:
            async for z in rmssd_z_stream():

                # Start timing
                if t0 is None:
                    t0 = time.time()

                # Auto-stop when audio finishes
                if audio_engine is not None and audio_engine.finished:
                    print("[polar_run] Audio finished — ending session.")
                    break

                t_rel = time.time() - t0

                # Store full per-sample data
                samples.append(
                    (
                        t_rel,
                        z,
                        current_params.tempo,
                        current_params.pitch,
                        current_params.volume,
                    )
                )

                is_baseline = t_rel <= BASELINE_SECONDS
                is_post_window = False

                apply_biofeedback(t_rel, z, is_baseline, is_post_window)

        except RuntimeError as e:
            if "Polar H10" in str(e):
                print("[polar_run] Could not find Polar H10 — using simulation.")
                t0 = None

                # ======================================================
                # SIMULATED HRV LOOP
                # ======================================================
                async for z in simulated_rmssd_z_stream():

                    if t0 is None:
                        t0 = time.time()

                    if audio_engine is not None and audio_engine.finished:
                        print("[polar_run] Audio finished — ending simulated session.")
                        break

                    t_rel = time.time() - t0

                    samples.append(
                        (
                            t_rel,
                            z,
                            current_params.tempo,
                            current_params.pitch,
                            current_params.volume,
                        )
                    )

                    is_baseline = t_rel <= BASELINE_SECONDS
                    is_post_window = False

                    apply_biofeedback(t_rel, z, is_baseline, is_post_window)

            else:
                raise

    except KeyboardInterrupt:
        print("\n[polar_run] Session ended manually by user.")
    except Exception as e:
        print(f"\n[polar_run] ERROR during streaming: {e!r}")
    finally:
        if audio_engine is not None:
            try:
                audio_engine.stop()
            except:
                pass

    # ==================================================================
    # POST-PROCESSING
    # ==================================================================

    if not samples:
        raise RuntimeError("No HRV data collected (Polar or simulated).")

    pre_mean, post_mean, delta, t_last, n_pre, n_post = compute_pre_post(samples)

    pre_stress = -pre_mean
    post_stress = -post_mean
    delta_stress = post_stress - pre_stress

    print("\n===== SESSION SUMMARY =====")
    print(f"Session ID: {session_id}")
    print(f"Duration: {t_last:.1f} sec")
    print(f"Pre mean z:   {pre_mean:+.3f}")
    print(f"Post mean z:  {post_mean:+.3f}")
    print(f"Δz:           {delta:+.3f}")
    print(f"Pre stress:   {pre_stress:+.3f}")
    print(f"Post stress:  {post_stress:+.3f}")
    print(f"Δstress:      {delta_stress:+.3f}")

    # Write logs
    per_sample_path = write_per_sample_log(samples, session_id)
    print(f"[polar_run] Per-sample log saved to: {per_sample_path}")

    append_summary_row(
        session_id,
        pre_mean,
        post_mean,
        delta,
        t_last,
        n_pre,
        n_post,
        t_start_iso,
    )

    print(f"[polar_run] Summary appended to: {SUMMARY_CSV}\n")


async def main():
    await run_session()


if __name__ == "__main__":
    asyncio.run(main())
