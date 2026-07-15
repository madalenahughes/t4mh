import os
import time
import threading
from collections import deque

import numpy as np
import sounddevice as sd
import soundfile as sf

try:
    import pyrubberband as pyrb
except ImportError as e:
    raise ImportError(
        "pyrubberband is required for true time stretching.\n"
        "Install with:\n"
        "  sudo apt install rubberband-cli\n"
        "  pip install pyrubberband"
    ) from e


class AudioEngine:
    """
    True time-stretching audio engine.

    Features:
    - tempo control without changing pitch
    - separate volume control
    - optional looping playback
    - background render worker to reduce output underflows

    Notes:
    - tempo > 1.0  => faster
    - tempo < 1.0  => slower
    - Rubber Band works best on chunked audio, so this engine processes
      ~1 second segments in a worker thread and queues them for playback.
    """

    def __init__(
        self,
        media_path=None,
        blocksize=4096,
        chunk_seconds=1.0,
        queue_seconds=6.0,
        device=None,
        loop=False,
    ):
        if media_path is None:
            media_path = self.find_default_media()

        if not os.path.isfile(media_path):
            raise FileNotFoundError(f"Audio file not found: {media_path}")

        audio, sr = sf.read(media_path, always_2d=True, dtype="float32")

        if audio.ndim != 2:
            raise ValueError("Expected audio with shape (samples, channels).")

        self.audio = audio
        self.sr = sr
        self.channels = audio.shape[1]
        self.total_frames = audio.shape[0]

        self.blocksize = int(blocksize)
        self.chunk_seconds = float(chunk_seconds)
        self.chunk_frames = max(2048, int(self.sr * self.chunk_seconds))
        self.queue_seconds = float(queue_seconds)
        self.max_buffer_frames = max(
            self.blocksize * 8, int(self.queue_seconds * self.sr)
        )
        self.device = device
        self.loop = bool(loop)

        # Playback state
        self.position = 0
        self.finished = False
        self.running = False
        self.source_exhausted = False

        # Controls
        self._tempo = 1.0
        self._volume = 60.0  # 0..100
        self._lock = threading.Lock()

        # Diagnostics
        self._underflow_count = 0
        self._callback_count = 0
        self._last_status_print = 0.0

        # Output buffer: deque of numpy arrays, each shape (n, channels)
        self._buffer = deque()
        self._buffer_frames = 0
        self._buffer_lock = threading.Lock()

        # Worker thread
        self._worker_thread = None
        self._stop_event = threading.Event()

        self.stream = sd.OutputStream(
            samplerate=self.sr,
            channels=self.channels,
            blocksize=self.blocksize,
            dtype="float32",
            callback=self._callback,
            device=self.device,
        )

    # ---------------------------
    # Public control methods
    # ---------------------------

    def start(self):
        if self.running:
            return

        self.running = True
        self.finished = False
        self.source_exhausted = False
        self._stop_event.clear()

        self._worker_thread = threading.Thread(
            target=self._render_worker,
            daemon=True,
            name="AudioEngineRenderWorker",
        )
        self._worker_thread.start()
        self.stream.start()

    def stop(self):
        self.running = False
        self._stop_event.set()

        try:
            if self.stream.active:
                self.stream.stop()
        finally:
            self.stream.close()

        if self._worker_thread is not None and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)

    def set_tempo(self, tempo):
        """
        Set playback tempo without changing pitch.

        tempo = 1.0  => original
        tempo = 1.1  => 10% faster
        tempo = 0.9  => 10% slower
        """
        tempo = float(np.clip(tempo, 0.50, 1.50))
        with self._lock:
            self._tempo = tempo
            volume = self._volume
        print(f"[audio_engine] tempo={tempo:.3f}x  volume={volume:.1f}")

    def set_volume(self, volume):
        """
        Set output volume in 0..100.
        """
        volume = float(np.clip(volume, 0.0, 100.0))
        with self._lock:
            self._volume = volume
            tempo = self._tempo
        print(f"[audio_engine] tempo={tempo:.3f}x  volume={volume:.1f}")

    def get_tempo(self):
        with self._lock:
            return self._tempo

    def get_volume(self):
        with self._lock:
            return self._volume

    def reset(self):
        """
        Reset source position and clear rendered buffer.
        """
        with self._buffer_lock:
            self._buffer.clear()
            self._buffer_frames = 0

        self.position = 0
        self.finished = False
        self.running = False
        self.source_exhausted = False
        self._stop_event.clear()

    # ---------------------------
    # Audio callback
    # ---------------------------

    def _callback(self, outdata, frames, time_info, status):
        del time_info
        self._callback_count += 1

        if status:
            print(f"[audio_engine] stream status: {status}")

        chunk = self._pop_buffered_audio(frames)

        if chunk.shape[0] < frames:
            missing = frames - chunk.shape[0]
            pad = np.zeros((missing, self.channels), dtype=np.float32)
            chunk = np.vstack([chunk, pad])

            # Only count as an underflow if playback is still meant to be active.
            if not self.finished:
                self._underflow_count += 1

        with self._lock:
            gain = self._volume / 100.0

        outdata[:] = np.clip(chunk * gain, -1.0, 1.0)

        now = time.time()
        if now - self._last_status_print > 5.0:
            with self._buffer_lock:
                buffered_sec = self._buffer_frames / self.sr
            print(
                f"[audio_engine] buffered={buffered_sec:.2f}s "
                f"underflows={self._underflow_count}"
            )
            self._last_status_print = now

    # ---------------------------
    # Background render worker
    # ---------------------------

    def _render_worker(self):
        """
        Keeps the output buffer filled with time-stretched chunks.
        """
        while not self._stop_event.is_set():
            if not self.running:
                time.sleep(0.01)
                continue

            with self._buffer_lock:
                buffered_frames = self._buffer_frames

            if self.source_exhausted and buffered_frames == 0:
                print("[audio_engine] playback finished")
                self.finished = True
                self.running = False
                self._stop_event.set()
                break

            if buffered_frames >= self.max_buffer_frames:
                time.sleep(0.01)
                continue

            with self._lock:
                tempo = self._tempo

            source_chunk = self._get_next_source_chunk(self.chunk_frames)

            if source_chunk.shape[0] == 0:
                time.sleep(0.01)
                continue

            try:
                stretched = self._time_stretch_chunk(source_chunk, tempo)
            except Exception as e:
                print(f"[audio_engine] time-stretch error: {e}")
                stretched = source_chunk.copy()

            if stretched.size == 0:
                time.sleep(0.01)
                continue

            stretched = stretched.astype(np.float32, copy=False)

            with self._buffer_lock:
                self._buffer.append(stretched)
                self._buffer_frames += stretched.shape[0]

    # ---------------------------
    # Source chunking
    # ---------------------------

    def _get_next_source_chunk(self, frames_needed):
        """
        Returns up to `frames_needed` frames from the source file and advances
        source position.

        If loop=False, returns a shorter chunk at the end and then marks the
        source as exhausted.
        If loop=True, wraps around seamlessly.
        """
        frames_needed = int(frames_needed)

        if self.total_frames == 0:
            self.source_exhausted = True
            return np.zeros((0, self.channels), dtype=np.float32)

        if self.source_exhausted:
            return np.zeros((0, self.channels), dtype=np.float32)

        if self.loop:
            chunks = []
            remaining = frames_needed

            while remaining > 0:
                end = min(self.position + remaining, self.total_frames)
                piece = self.audio[self.position:end]

                if piece.shape[0] > 0:
                    chunks.append(piece)
                    consumed = piece.shape[0]
                    self.position += consumed
                    remaining -= consumed

                if self.position >= self.total_frames:
                    self.position = 0

            return np.vstack(chunks).astype(np.float32, copy=False)

        end = min(self.position + frames_needed, self.total_frames)
        piece = self.audio[self.position:end]

        if piece.shape[0] > 0:
            self.position = end

        if self.position >= self.total_frames:
            self.source_exhausted = True

        return piece.astype(np.float32, copy=False)

    # ---------------------------
    # Time-stretching
    # ---------------------------

    def _time_stretch_chunk(self, chunk, tempo):
        """
        Rubber Band time stretching.

        chunk shape: (samples, channels)
        """
        tempo = float(np.clip(tempo, 0.50, 1.50))

        if abs(tempo - 1.0) < 1e-3:
            return chunk

        if self.channels == 1:
            mono = chunk[:, 0]
            stretched = pyrb.time_stretch(mono, self.sr, tempo)
            stretched = np.asarray(stretched, dtype=np.float32).reshape(-1, 1)
            return stretched

        stretched_channels = []
        for ch in range(self.channels):
            y = chunk[:, ch]
            y_stretched = pyrb.time_stretch(y, self.sr, tempo)
            stretched_channels.append(np.asarray(y_stretched, dtype=np.float32))

        min_len = min(len(ch) for ch in stretched_channels)
        if min_len <= 0:
            return np.zeros((0, self.channels), dtype=np.float32)

        stretched = np.stack([ch[:min_len] for ch in stretched_channels], axis=1)
        return stretched.astype(np.float32, copy=False)

    # ---------------------------
    # Output buffer helpers
    # ---------------------------

    def _pop_buffered_audio(self, frames):
        """
        Pop exactly up to `frames` samples from the rendered buffer.
        Returns shape (n, channels), where n <= frames.
        """
        frames = int(frames)
        if frames <= 0:
            return np.zeros((0, self.channels), dtype=np.float32)

        with self._buffer_lock:
            if self._buffer_frames == 0:
                return np.zeros((0, self.channels), dtype=np.float32)

            out_parts = []
            remaining = frames

            while remaining > 0 and self._buffer:
                head = self._buffer[0]
                head_frames = head.shape[0]

                if head_frames <= remaining:
                    out_parts.append(head)
                    self._buffer.popleft()
                    self._buffer_frames -= head_frames
                    remaining -= head_frames
                else:
                    out_parts.append(head[:remaining])
                    self._buffer[0] = head[remaining:]
                    self._buffer_frames -= remaining
                    remaining = 0

        if not out_parts:
            return np.zeros((0, self.channels), dtype=np.float32)

        return np.vstack(out_parts).astype(np.float32, copy=False)

    # ---------------------------
    # Utilities
    # ---------------------------

    @staticmethod
    def find_default_media():
        candidates = [
            "music.wav",
            "music.flac",
            "music.mp3",
            "audio.wav",
            "audio.flac",
            "audio.mp3",
            "test.wav",
            "test.flac",
            "test.mp3",
            "Weightless.wav",
        ]

        for path in candidates:
            if os.path.isfile(path):
                return path

        raise FileNotFoundError(
            "No default media file found. Pass media_path explicitly."
        )


if __name__ == "__main__":
    engine = AudioEngine(
        media_path="Weightless.wav",
        blocksize=4096,
        chunk_seconds=1.0,
        loop=False,
    )
    engine.set_volume(60)
    engine.set_tempo(1.0)
    engine.start()

    try:
        print("Playing... Ctrl+C to stop")
        time.sleep(5)
        engine.set_tempo(0.90)
        print("Tempo -> 0.90x")
        time.sleep(5)
        engine.set_tempo(1.10)
        print("Tempo -> 1.10x")
        time.sleep(5)
        engine.set_tempo(1.00)
        print("Tempo -> 1.00x")

        while not engine.finished:
            time.sleep(0.2)

        print("Finished playback.")

    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        engine.stop()
