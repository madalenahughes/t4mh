import numpy as np


class RollingBuffer:
    def __init__(self, window_size=512):
        self.window_size = window_size

        self.channels = {
            "TP9": np.array([], dtype=float),
            "AF7": np.array([], dtype=float),
            "AF8": np.array([], dtype=float),
            "TP10": np.array([], dtype=float),
       }
        self.ready = False
    def add_frame(self, frame):

        for channel in self.channels:

            self.channels[channel] = np.concatenate([
                self.channels[channel],
                frame[channel]
            ])

            if len(self.channels[channel]) > self.window_size:
                self.channels[channel] = self.channels[channel][-self.window_size:]

    def is_full(self):
        if len(self.channels["TP9"]) == self.window_size:
            if not self.ready:
                 self.ready = True
                 return True
        return False
    def get_data(self):
        return self.channels
