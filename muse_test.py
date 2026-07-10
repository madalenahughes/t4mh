import asyncio

from bleak import BleakClient

ADDRESS = "00:55:DA:B6:2F:72"

async def main():

    async with BleakClient(ADDRESS) as client:

        print(f"Connected: {client.is_connected}")

        print("\nServices:")

        for service in client.services:

            print(f"\n{service.uuid}")

            for char in service.characteristics:

                props = ", ".join(char.properties)

                print(f"  {char.uuid} [{props}]")

asyncio.run(main())
