#!/usr/bin/env python3
"""
controller.py
Maps physiological signals (HRV z-score, FAA) to audio parameters.

AudioParams:
    tempo  ~ overall playback rate factor (around 1.0)
    pitch  ~ semitone shift (negative = deeper)
    volume ~ 0–100 (percent)

Design:
    - Higher HRV (positive z) → calmer → slower, softer, slightly deeper.
    - Lower HRV (negative z) → more aroused → slightly faster, brighter, louder.

This version uses integral control on HRV:
    - HRV error is integrated into tempo, pitch, and volume.
    - FAA provides a small proportional “coloring” on top.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AudioParams:
    tempo: float = 1.0   # neutral tempo
    pitch: float = -2.0  # base pitch shift (semitones)
    volume: float = 60.0 # neutral volume (0–100)


# ----- HRV control configuration -----

HRV_SETPOINT = 0.0  # target HRV z-score (baseline)

# Clamp ranges to keep things musical
TEMPO_MIN, TEMPO_MAX   = 0.85, 1.15
PITCH_MIN, PITCH_MAX   = -6.0, 0.0
VOLUME_MIN, VOLUME_MAX = 52.0, 68.0

# Integral gains (tune by ear)
HRV_KI_TEMPO  = 0.010    # how fast tempo reacts to HRV error
HRV_KI_PITCH  = -0.030   # negative: calmer (hrv_z > 0) => deeper pitch
HRV_KI_VOLUME = -0.400   # negative: calmer => softer

# Effective time step of the control loop (seconds).
# If update_audio_params is called ~once per second, DT=1.0 is fine.
DT = 1.0


def update_audio_params(
    params: AudioParams,
    hrv_z: Optional[float],
    faa_z: Optional[float] = None,
    is_baseline: bool = False,
    is_post_window: bool = False,
) -> AudioParams:
    """
    Integral HRV controller + small FAA shaping.

    params       : previous AudioParams (integrator state)
    hrv_z        : RMSSD z-score
    faa_z        : frontal alpha asymmetry z (optional)
    is_baseline  : True during baseline window
    is_post_window : currently unused, but available if needed
    """

    # ----- During baseline or missing HRV: drift gently to neutral -----
    if is_baseline or hrv_z is None:
        relax_alpha = 0.02  # 0=no change, 1=jump immediately to neutral

        return AudioParams(
            tempo= params.tempo  + relax_alpha * (1.0  - params.tempo),
            pitch= params.pitch  + relax_alpha * (-2.0 - params.pitch),
            volume=params.volume + relax_alpha * (60.0 - params.volume),
        )

    # ----- HRV integral control -----
    # error > 0  => HRV below setpoint (more aroused)  => tempo/volume creep up
    # error < 0  => HRV above setpoint (calm)         => tempo/volume creep down
    hrv_error = HRV_SETPOINT - hrv_z

    tempo  = params.tempo  + HRV_KI_TEMPO  * hrv_error * DT
    pitch  = params.pitch  + HRV_KI_PITCH  * hrv_error * DT
    volume = params.volume + HRV_KI_VOLUME * hrv_error * DT

    # ----- FAA proportional shaping (optional, small) -----
    if faa_z is not None:
        FAA_KP_PITCH  = 0.15  # left > right => slightly brighter / higher
        FAA_KP_VOLUME = 1.0   # modest loudness change

        pitch  += FAA_KP_PITCH  * faa_z
        volume += FAA_KP_VOLUME * faa_z

    # ----- Clamp to safe musical ranges (anti-windup) -----
    tempo  = max(TEMPO_MIN,   min(TEMPO_MAX,   tempo))
    pitch  = max(PITCH_MIN,   min(PITCH_MAX,   pitch))
    volume = max(VOLUME_MIN,  min(VOLUME_MAX,  volume))

    return AudioParams(
        tempo=tempo,
        pitch=pitch,
        volume=volume,
    )
