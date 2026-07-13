import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import welch, iirnotch, filtfilt

class EEGProcessor:

    def __init__(self):
        self.fs = 256

        self.b_notch, self.a_notch = iirnotch(
             w0=60,
             Q=30,
             fs=self.fs
        )
        self.first_plot = True

    def process(self, eeg):

        print("\nProcessing window")

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
            print(f"{channel} peak alpha frequency: {peak_alpha_freq:.1f} Hz")

            alpha_power = np.sum(psd[alpha])
            print(f"{channel}: Alpha power = {alpha_power:.2f}")

#           peak_index = np.argmax(psd)
#           peak_freq = freqs[peak_index]
#           print(f"{channel} peak frequency: {peak_freq:.1f} Hz")

            rms = np.sqrt(np.mean(data**2))
            print(
                f"{channel}: "
                f"Mean = {np.mean(data):7.2f} uV   "
                f"Std = {np.std(data):7.2f} uV   "
                f"RMS = {rms:7.2f} uV"
            )
