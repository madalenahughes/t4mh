#!/usr/bin/env python3
"""
audio_engine.py
Simple audio engine using python-vlc to play a background track and
apply tempo/volume changes via AudioParams-style interface.
"""

import os
import time
import vlc


class AudioEngine:
    def __init__(self, media_path: str | None = None) -> None:
        """
        Initialize VLC player and load an audio file.

        If media_path is None, we try to find an MP3 in ./audio.
        """
        if media_path is None:
            media_path = self._find_default_media()

        print(f"[audio_engine] Using media file: {media_path}")

        self._instance = vlc.Instance()
        self.player = self._instance.media_player_new()
        media = self._instance.media_new(media_path)
        self.player.set_media(media)

    def _find_default_media(self) -> str:
        """
        Try to find a default MP3 file in ./audio.
        Prefer 'Weightless.mp3' or 'weightless.mp3' if present.
        """
        audio_dir = os.path.join(os.path.dirname(__file__), "audio")
        candidates: list[str] = []

        preferred_names = ["Weightless.mp3", "weightless.mp3"]
        for name in preferred_names:
            path = os.path.join(audio_dir, name)
            if os.path.exists(path):
                return path

        # Otherwise, pick any mp3 in audio/
        if os.path.isdir(audio_dir):
            for fname in os.listdir(audio_dir):
                if fname.lower().endswith(".mp3"):
                    candidates.append(os.path.join(audio_dir, fname))

        if candidates:
            return candidates[0]

        raise FileNotFoundError(
            "No MP3 file found in ./audio. "
            "Please place an audio file (e.g., Weightless.mp3) in the audio/ directory."
        )

    def set_params(self, params) -> None:
        """
        Apply AudioParams to the underlying player.

        Expects:
            params.tempo  ~ around 1.0 (e.g., [1.0, 1.10])
            params.pitch  ~ semitones (currently not used for DSP; logged only)
            params.volume ~ [0, 100]
        """
        t = float(params.tempo)
        p = float(params.pitch)
        v = float(params.volume)

        # Keep playback rate at or above 1.0 so it never feels slowed.
        # Bias slightly above 1.0 so it feels a tiny bit energetic by default.
        base_rate = 1.05
        rate = base_rate * t
        rate = max(1.00, min(1.20, rate))

        try:
            self.player.set_rate(rate)
        except Exception as e:
            print(f"[audio_engine] set_rate failed: {e}")

        try:
            volume_int = int(max(0, min(100, v)))
            self.player.audio_set_volume(volume_int)
        except Exception as e:
            print(f"[audio_engine] set_volume failed: {e}")

        print(
            f"[audio_engine] rate={rate:.3f} "
            f"(tempo={t:.2f}, pitch={p:.2f} st, vol={v:.1f})"
        )

    def stop(self) -> None:
        """Stop playback."""
        try:
            self.player.stop()
        except Exception:
            pass


if __name__ == "__main__":
    # Simple self-test: play 10 seconds
    engine = AudioEngine()
    print("Testing audio: playing 10 seconds…")
    engine.player.play()
    time.sleep(10)
    print("Stopping.")
    engine.stop()
