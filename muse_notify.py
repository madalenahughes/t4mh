import asyncio
from bleak import BleakClient

ADDRESS = "00:55:DA:B6:2F:72"

CONTROL = "273e0001-4c4d-454d-96be-f03bac821358"

EEG_UUIDS = [
    "273e0003-4c4d-454d-96be-f03bac821358",  # TP9
    "273e0004-4c4d-454d-96be-f03bac821358",  # AF7
    "273e0005-4c4d-454d-96be-f03bac821358",  # AF8
    "273e0006-4c4d-454d-96be-f03bac821358",  # TP10
    "273e0007-4c4d-454d-96be-f03bac821358",  # AUX
]


def callback(sender, data):
    print(f"{sender}: {len(data)} bytes  {data.hex()}")


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
