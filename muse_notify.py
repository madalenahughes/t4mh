import asyncio
import numpy as np
from bleak import BleakClient
from decoder import decode_eeg_packet
from frame_buffer import MuseFrameBuffer
from rolling_buffer import RollingBuffer
from processor import EEGProcessor

processor = EEGProcessor()

rolling = RollingBuffer()
buffer = MuseFrameBuffer()

frame_counter = 0

ADDRESS = "00:55:DA:B6:2F:72"

CONTROL = "273e0001-4c4d-454d-96be-f03bac821358"

EEG_UUIDS = [
    "273e0003-4c4d-454d-96be-f03bac821358",  # TP9
    "273e0004-4c4d-454d-96be-f03bac821358",  # AF7
    "273e0005-4c4d-454d-96be-f03bac821358",  # AF8
    "273e0006-4c4d-454d-96be-f03bac821358",  # TP10
]


import numpy as np

CHANNEL_NAMES = {
    31: "TP9",
    34: "AF7",
    37: "AF8",
    40: "TP10",
}

def callback(sender, data):
    global frame_counter
    packet, samples = decode_eeg_packet(data)

    frame = buffer.add_packet(
        sender.uuid,
        packet,
        samples
    )

    if frame is not None:

        packet_number, eeg = frame

        rolling.add_frame(eeg)
        if rolling.is_full():
                frame_counter += 1
                if frame_counter % 5 == 0:
                      processor.process(
                           rolling.get_data()
                      )
#                     print (len(rolling.get_data()["TP9"]))

async def main():
    async with BleakClient(ADDRESS) as client:
        print("Connected:", client.is_connected)

        # Subscribe to all EEG channels
        for uuid in EEG_UUIDS:
            await client.start_notify(uuid, callback)

        print("Subscribed to EEG channels.")

        # Start streaming
        cmd = bytearray([2, ord("d"), ord("\n")])

        print("Sending stream command...")
        await client.write_gatt_char(
            CONTROL,
            cmd,
            response=False
        )

        print("Waiting for packets...")
        await asyncio.sleep(15)


asyncio.run(main())
