from godirect import GoDirect
import time

godirect = GoDirect(use_ble=True, use_usb=False)

print("Searching for Go Direct device...")

devices = godirect.list_devices()

if not devices:
    print("No Go Direct devices found.")
    godirect.quit()
    raise SystemExit

for device in devices:
    print("Found:", device)

device = devices[0]

print("Opening device...")
device.open()

print("CONNECTED — holding connection for 60 seconds")

try:
    time.sleep(60)
finally:
    print("Closing...")
    try:
        device.close()
    except EOFError:
        print("Disconnect cleanup hit EOFError")
    godirect.quit()
