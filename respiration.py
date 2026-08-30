import os
import time
from collections import deque

import numpy as np
from scipy.signal import find_peaks
from godirect import GoDirect


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

PERIOD_MS = 100          # Go Direct sampling period
SAMPLE_RATE = 1000 / PERIOD_MS   # 10 Hz

WINDOW_SECONDS = 30

force_buffer = deque(
    maxlen=int(WINDOW_SECONDS * SAMPLE_RATE)
)

time_buffer = deque(
    maxlen=int(WINDOW_SECONDS * SAMPLE_RATE)
)


# ---------------------------------------------------------
# Connect to Go Direct
# ---------------------------------------------------------

godirect = GoDirect(
    use_ble=True,
    use_usb=False
)

print("Searching for Go Direct Respiration Belt...")

devices = godirect.list_devices()

if not devices:
    print("No Go Direct devices found.")
    godirect.quit()
    raise SystemExit

device = devices[0]

print(f"Found: {device}")
print("Opening device...")

device.open(auto_start=False)

# Populate sensor metadata
device.list_sensors()

# Sensor 1 = Force
# We calculate respiration rate ourselves from this signal.
device.enable_sensors([1])

enabled = device.get_enabled_sensors()

print("\nEnabled sensors:")

for sensor in enabled:
    print(
        f"  {sensor.sensor_description} "
        f"({sensor.sensor_units})"
    )

print("\nStarting stream...")

device.start(period=PERIOD_MS)


# ---------------------------------------------------------
# Current values
# ---------------------------------------------------------

latest = {
    "Force": None,
    "Respiration Rate": None,
    "Breaths Detected": 0,
}


def fmt(value, decimals=3):
    if value is None:
        return "Waiting..."

    if not np.isfinite(value):
        return "Waiting..."

    return f"{value:.{decimals}f}"


# ---------------------------------------------------------
# Respiration-rate calculation
# ---------------------------------------------------------

def calculate_respiration_rate():

    # Wait until we have at least 10 seconds of data.
    if len(force_buffer) < int(10 * SAMPLE_RATE):
        return None, 0

    force_array = np.array(
        force_buffer,
        dtype=float
    )

    time_array = np.array(
        time_buffer,
        dtype=float
    )

    # Remove the DC/baseline force.
    centered = force_array - np.mean(force_array)

    signal_range = np.ptp(centered)

    if signal_range <= 0:
        return None, 0

    # Adaptive threshold so the detector scales with
    # how strongly the belt is expanding/contracting.
    prominence = max(
        0.05,
        signal_range * 0.25
    )

    # At most one inhalation peak every 1.5 seconds.
    # This corresponds to a maximum plausible rate of
    # approximately 40 breaths/min.
    minimum_peak_distance = int(
        SAMPLE_RATE * 1.5
    )

    peaks, _ = find_peaks(
        centered,
        distance=minimum_peak_distance,
        prominence=prominence
    )

    if len(peaks) < 2:
        return None, len(peaks)

    peak_times = time_array[peaks]

    intervals = np.diff(peak_times)

    # Keep physiologically reasonable breathing intervals.
    # 1.5 s -> 40 breaths/min
    # 10 s  -> 6 breaths/min
    valid_intervals = intervals[
        (intervals >= 1.5) &
        (intervals <= 10.0)
    ]

    if len(valid_intervals) == 0:
        return None, len(peaks)

    # Median is less sensitive than the mean to one
    # incorrectly detected breath.
    median_interval = np.median(
        valid_intervals
    )

    respiration_rate = (
        60.0 / median_interval
    )

    return respiration_rate, len(peaks)


# ---------------------------------------------------------
# Main streaming loop
# ---------------------------------------------------------

try:

    while True:

        if device.read():

            for sensor in enabled:

                if sensor.sensor_description == "Force":

                    force = sensor.value

                    if (
                        force is not None
                        and np.isfinite(force)
                    ):

                        latest["Force"] = force

                        force_buffer.append(force)
                        time_buffer.append(
                            time.monotonic()
                        )

        # Calculate respiration rate from force waveform.
        rate, breaths = calculate_respiration_rate()

        latest["Respiration Rate"] = rate
        latest["Breaths Detected"] = breaths


        # -------------------------------------------------
        # Dashboard
        # -------------------------------------------------

        os.system("clear")

        print("=" * 58)
        print("GO DIRECT RESPIRATION")
        print("=" * 58)

        print("\nRespiration")
        print("-" * 58)

        print(
            f"{'Force':<24}"
            f"{fmt(latest['Force']):>12} N"
        )

        print(
            f"{'Respiration Rate':<24}"
            f"{fmt(latest['Respiration Rate'], 1):>12} bpm"
        )

        print(
            f"{'Breaths Detected':<24}"
            f"{latest['Breaths Detected']:>12}"
        )


        print("\nSystem")
        print("-" * 58)

        print(
            f"{'Sample Period':<24}"
            f"{PERIOD_MS} ms"
        )

        print(
            f"{'Analysis Window':<24}"
            f"{WINDOW_SECONDS} s"
        )

        print(
            f"{'Status':<24}"
            f"Streaming"
        )

        print("=" * 58)

        time.sleep(0.05)


except KeyboardInterrupt:

    print("\nStopping respiration stream...")


finally:

    try:
        device.stop()
    except Exception:
        pass

    try:
        device.close()

    except EOFError:
        # Known BLE cleanup issue on this setup.
        pass

    except Exception:
        pass

    godirect.quit()
