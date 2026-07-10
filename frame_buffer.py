class MuseFrameBuffer:

    CHANNEL_NAMES = {
        "273e0003-4c4d-454d-96be-f03bac821358": "TP9",
        "273e0004-4c4d-454d-96be-f03bac821358": "AF7",
        "273e0005-4c4d-454d-96be-f03bac821358": "AF8",
        "273e0006-4c4d-454d-96be-f03bac821358": "TP10",
    }

    def __init__(self):
        self.frames = {}

    def add_packet(self, uuid, packet_number, samples):

        channel = self.CHANNEL_NAMES[uuid]

        if packet_number not in self.frames:
            self.frames[packet_number] = {}

        self.frames[packet_number][channel] = samples

        # Finished?
       #print(packet_number, self.frames[packet_number].keys())
        if len(self.frames[packet_number]) == 4:

            frame = self.frames.pop(packet_number)

            return packet_number, frame

        return None
