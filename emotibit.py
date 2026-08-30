import socket
import time
import os
import threading

HOST = "0.0.0.0"
PORT = 12346

WANTED_TAGS = {
    "EA",
    "T1", "TH",
    "AX", "AY", "AZ",
    "GX", "GY", "GZ",
    "MX", "MY", "MZ",
}

latest = {}
lock = threading.Lock()
running = True


def receiver():
    global running

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # Give ourselves more room for the EmotiBit firehose
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 1024)
    sock.bind((HOST, PORT))
    sock.settimeout(0.5)

    while running:
        try:
            data, addr = sock.recvfrom(65535)
        except socket.timeout:
            continue

        text = data.decode("utf-8", errors="ignore").strip()
        fields = text.split(",")

        try:
            n_samples = int(fields[2])
            tag = fields[3]

            if tag not in WANTED_TAGS:
                continue

            values = [
                float(x)
                for x in fields[6:6 + n_samples]
            ]

            if values:
                with lock:
                    latest[tag] = values[-1]

        except (ValueError, IndexError):
            pass

    sock.close()


def value(tag, decimals=3):
    with lock:
        val = latest.get(tag)

    if val is None:
        return "Waiting..."

    return f"{val:.{decimals}f}"


def draw_dashboard():
    os.system("clear")

    print("=" * 60)
    print("EMOTIBIT")
    print("=" * 60)

    print("\nEDA")
    print("-" * 60)
    print(f"EA                {value('EA', 6):>15}")

    print("\nTemperature")
    print("-" * 60)
    print(f"T1                {value('T1'):>15} °C")
    print(f"TH                {value('TH'):>15} °C")

    print("\nIMU")
    print("-" * 60)

    print(
        f"Accelerometer     "
        f"X {value('AX'):>8}   "
        f"Y {value('AY'):>8}   "
        f"Z {value('AZ'):>8}"
    )

    print(
        f"Gyroscope         "
        f"X {value('GX'):>8}   "
        f"Y {value('GY'):>8}   "
        f"Z {value('GZ'):>8}"
    )

    print(
        f"Magnetometer      "
        f"X {value('MX', 1):>8}   "
        f"Y {value('MY', 1):>8}   "
        f"Z {value('MZ', 1):>8}"
    )

    print("\nSystem")
    print("-" * 60)
    print(f"UDP Port          {PORT}")
    print("Status            Streaming EmotiBit")

    print("=" * 60)


# Start UDP acquisition independently
rx_thread = threading.Thread(target=receiver, daemon=True)
rx_thread.start()

try:
    while True:
        draw_dashboard()
        time.sleep(0.5)

except KeyboardInterrupt:
    running = False
    print("\nEmotiBit stream stopped.")

rx_thread.join(timeout=1)
