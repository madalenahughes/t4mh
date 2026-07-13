import os
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import welch, iirnotch, filtfilt

class EEGProcessor:

    def __init__(self):
        self.fs = 256
        self.window_count = 0
        self.faa_smoothed = None
        self.faa_smoothing_factor = 0.2

        self.b_notch, self.a_notch = iirnotch(
             w0=60,
             Q=30,
             fs=self.fs
        )
        self.first_plot = True

    def process(self, eeg):
        self.window_count += 1
        print("\nProcessing window")
        results = {}
        for channel in eeg:
            data = eeg[channel]

            data = filtfilt( #remove 60Hz electrical noise
                 self.b_notch,
                 self.a_notch,
                 data
            )

            freqs, psd = welch(
                data,
                fs=self.fs,
                nperseg=self.fs
            )

            if self.first_plot:
                plt.figure(figsize=(8,4))
                plt.plot(freqs, psd)
                plt.xlim(0, 70)
                plt.xlabel("Frequency (Hz)")
                plt.title(f"{channel} Power Spectrum")
                plt.grid(True)
                plt.tight_layout()
                plt.savefig("psd.png")
                print("Saved PSD to psd.png") #^_^
                self.first_plot = False
            alpha = (freqs >= 8) & (freqs <= 13)

            alpha_freqs = freqs[alpha]
            alpha_psd = psd[alpha]
            peak_alpha_freq = alpha_freqs[np.argmax(alpha_psd)]
#           print(f"{channel} peak alpha frequency: {peak_alpha_freq:.1f} Hz")

            alpha_power = np.sum(psd[alpha])
            std = np.std(data)

            results[channel] = {
                 "alpha_power": alpha_power,
                 "peak_alpha": peak_alpha_freq,
                 "std": std,
            }
        if "AF7" in results and "AF8" in results:
            faa = (
                np.log(max(results["AF8"]["alpha_power"], 1e-12)) - np.log(max(results["AF7"]["alpha_power"], 1e-12))
            )
        else:
            faa = None
        if faa is not None:
            if self.faa_smoothed is None:
                self.faa_smoothed = faa
            else:
                self.faa_smoothed = (self.faa_smoothing_factor * faa + (1 - self.faa_smoothing_factor) * self.faa_smoothed
            )
        max_alpha = max(
            result["alpha_power"]
            for result in results.values()
        )

        os.system("clear")

        print("\n" + "=" * 56)
        print("               T4MH Dashboard")
        print("=" * 56)

        print("\nConnections")
        print("-" * 56)
        print(f"{'Muse 2':<20}CONNECTED")
        print(f"{'Polar H10':<20}OFFLINE")
        print(f"{'Controller':<20}RUNNING")
        print(f"{'Audio Engine':<20}READY")

        print("\nEEG")
        print("-" * 56)
        print(f"{'Channel':<8}{'Alpha Activity':<22}{'Power':>10}{'Peak':>10}")

        for channel in ["TP9", "AF7", "AF8", "TP10"]:
           if channel in results:
               std = results[channel]["std"]
               if 10 <= std < 100:
                   quality = "GOOD"
               elif 100 <= std < 200:
                   quality = "FAIR"
               else:
                   quality = "POOR"
               alpha = results[channel]["alpha_power"]
               peak = results[channel]["peak_alpha"]

               bar_length = int((alpha / max_alpha) * 30)
               bar = "█" * bar_length

               print(
                   f"{channel:<6}"
                   f"{quality:<8}"
                   f"{bar:<22}"
                   f"{alpha:>10.1f}"
                   f"{peak:>10} Hz"
               )

        print("\nFAA")
        print("-" * 56)
        if faa is not None:
            print(f"Current: {faa:+3f}")
            print(f"Smoothed: {self.faa_smoothed:+.3f}")
        else:
            print("Waiting for AF7/AF8...")

        print("\nSystem")
        print("-" * 56)
        print(f"{'Sample Rate':<20}{self.fs} Hz")
        print(f"{'Window Size':<20}512 samples")

        print("\nStatus")
        print("-" * 56)
        print("Streaming EEG")
#       print("Processing Windows")

        print("=" * 56)
#           print(f"{channel} : Alpha power = {alpha_power:.2f}")

#           peak_index = np.argmax(psd)
#           peak_freq = freqs[peak_index]
#           print(f"{channel} peak frequency: {peak_freq:.1f} Hz")

#           rms = np.sqrt(np.mean(data**2))
#           print(
#               f"{channel}: "
#               f"Mean = {np.mean(data):7.2f} uV   "
#               f"Std = {np.std(data):7.2f} uV   "
#               f"RMS = {rms:7.2f} uV"
