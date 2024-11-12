import threading


class PacketCountThread(threading.Thread):
    def __init__(self, file, is_remap, trg_ip, trg_port, protocol):
        super().__init__()
        self.file: str = file
        self.is_remap = is_remap
        self.trg_ip: str = trg_ip  # Destination IP on packet
        self.trg_port: str = trg_port  # Destination Port on packet
        self.protocol = protocol
        self.total_packets = 0  # Packet count
        self.end_event = threading.Event()
        self.start()

    def run(self):
        """This is the method scans total packets"""

        cap.close()
        self.end_event.set()