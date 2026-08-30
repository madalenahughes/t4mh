import json
import os
import socket
import time

HOST = "127.0.0.1"
PORT = 15000

latest = {}
last_seen = {}

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((HOST, PORT))
sock.settimeout(0.1)


def status(sensor, timeout=3.0):
    if sensor not in last_seen:
        return "WAITING"

    if time.monotonic() - last_seen[sensor] <= timeout:
        return "LIVE"

    return "STALE"


def get(sensor, key, default="Waiting..."):
    return latest.get(sensor, {}).get(key, default)

def fmt(sensor, key, decimals=3, default="Waiting..."):
    value = latest.get(sensor, {}).get(key)

    if value is None:
        return default

    if isinstance(value, (int, float)):
        return f"{value:.{decimals}f}"

    return str(value)

def draw():
    os.system("clear")

    print("=" * 60)
    print("T4MH MULTISENSOR STATE")
    print("=" * 60)

    print("\nCardiovascular / HRV")
    print("-" * 60)
    print(f"{'RMSSD':<24}{fmt('polar', 'rmssd_ms', 1)} ms")
    print(f"{'RMSSD z-score':<24}{fmt('polar', 'rmssd_z', 3)}")

    print("\nEEG / FAA")
    print("-" * 60)
    print(f"{'FAA Current':<24}{fmt('muse', 'faa', 3)}")
    print(f"{'FAA Smoothed':<24}{fmt('muse', 'faa_smoothed', 3)}")

    print("\nRespiration")
    print("-" * 60)
    print(f"{'Force':<24}{fmt('respiration', 'force', 3)}")
    print(f"{'Respiration Rate':<24}{fmt('respiration', 'rate', 1)}")

    print("\nEDA / Temperature")
    print("-" * 60)
    print(f"{'EDA':<24}{fmt('emotibit', 'eda', 6)}")
    print(f"{'T1':<24}{fmt('emotibit', 't1', 3)}")
    print(f"{'TH':<24}{fmt('emotibit', 'th', 3)}")

    print("\nIMU")
    print("-" * 60)

    print(
        f"{'Acceleration':<16}"
        f"X {fmt('emotibit', 'ax', 3)}   "
        f"Y {fmt('emotibit', 'ay', 3)}   "
        f"Z {fmt('emotibit', 'az', 3)}"
    )

    print(
        f"{'Gyroscope':<16}"
        f"X {fmt('emotibit', 'gx', 3)}   "
        f"Y {fmt('emotibit', 'gy', 3)}   "
        f"Z {fmt('emotibit', 'gz', 3)}"
    )

    print(
        f"{'Magnetometer':<16}"
        f"X {fmt('emotibit', 'mx', 1)}   "
        f"Y {fmt('emotibit', 'my', 1)}   "
        f"Z {fmt('emotibit', 'mz', 1)}"
    )

    print("\nConnections")
    print("-" * 60)
    print(f"{'Polar H10':<24}{status('polar')}")
    print(f"{'Muse 2':<24}{status('muse')}")
    print(f"{'Go Direct':<24}{status('respiration')}")
    print(f"{'EmotiBit':<24}{status('emotibit')}")

    print("=" * 60)

last_draw = 0

try:
    while True:
        try:
            data, addr = sock.recvfrom(65535)
            message = json.loads(data.decode("utf-8"))

            sensor = message.get("sensor")

            if sensor:
                latest[sensor] = message
                last_seen[sensor] = time.monotonic()

        except socket.timeout:
            pass
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass

        now = time.monotonic()

        if now - last_draw >= 0.5:
            draw()
            last_draw = now

except KeyboardInterrupt:
    print("\nIntegration monitor stopped.")

finally:
    sock.close()
