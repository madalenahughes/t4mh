import bitstring
import numpy as np


def decode_eeg_packet(packet: bytes):
    """
    Decode one 20-byte Muse EEG BLE packet.

    Returns
    -------
    packet_index : int
    samples : numpy array (12,)
    """

    bits = bitstring.Bits(bytes=packet)

    values = bits.unpack(
        "uint:16,"
        + ",".join(["uint:12"] * 12)
    )

    packet_index = values[0]

    samples = np.array(values[1:])

    # Convert ADC counts to microvolts
    samples = 0.48828125 * (samples - 2048)

    return packet_index, samples
