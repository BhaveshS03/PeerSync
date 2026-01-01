import socket
import threading
import time
import psutil
from zeroconf import Zeroconf, ServiceInfo


class ZeroconfBroadcaster:
    def __init__(self, name, service_type="_http._tcp.local.", port=9999):
        self.name = name
        self.service_type = service_type
        self.port = port

        self.zc = None
        self.service_info = None
        self.thread = None
        self.stop_event = threading.Event()
        self.running = False

    def _get_local_ip(self):
        for iface, addrs in psutil.net_if_addrs().items():
            for a in addrs:
                if a.family == socket.AF_INET and a.address.startswith("192.168."):
                    return a.address
        return None

    def _run(self):
        ip = self._get_local_ip()
        if not ip:
            print("No LAN IP found")
            self.running = False
            return

        self.zc = Zeroconf()
        self.service_info = ServiceInfo(
            self.service_type,
            f"{self.name}.{self.service_type}",
            addresses=[socket.inet_aton(ip)],
            port=self.port,
            properties={"msg": "hello"},
        )

        self.zc.register_service(self.service_info)
        print("📡 Broadcasting started")

        while not self.stop_event.is_set():
            time.sleep(1)

        self.zc.unregister_service(self.service_info)
        self.zc.close()
        print("🛑 Broadcasting stopped")

    def start(self):
        if self.running:
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        self.running = True

    def stop(self):
        if not self.running:
            return
        self.stop_event.set()
        self.running = False

    def toggle(self):
        self.start() if not self.running else self.stop()
