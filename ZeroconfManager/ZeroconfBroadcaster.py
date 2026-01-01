import asyncio
import threading
import socket
import psutil
from zeroconf import Zeroconf, ServiceInfo


class ZeroconfBroadcaster:
    def __init__(self, name, service_type="_http._tcp.local.", port=9999):
        self.name = name
        self.service_type = service_type
        self.port = port

        self.thread = None
        self.loop = None
        self.zc = None
        self.service_info = None

        self.running = False
        self._lock = threading.Lock()

    def _get_ip(self):
        for iface, addrs in psutil.net_if_addrs().items():
            for a in addrs:
                if a.family == socket.AF_INET and a.address.startswith("192.168."):
                    return a.address
        return None

    def _run(self):
        asyncio.set_event_loop(asyncio.new_event_loop())
        self.loop = asyncio.get_event_loop()

        ip = self._get_ip()
        if not ip:
            return

        self.zc = Zeroconf()
        self.service_info = ServiceInfo(
            self.service_type,
            f"{self.name}.{self.service_type}",
            addresses=[socket.inet_aton(ip)],
            port=self.port,
            properties={"msg": "hello"},
        )

        self.zc.register_service(
            self.service_info
        )

        print("📡 Broadcasting started")

        try:
            self.loop.run_forever()
        finally:
            if self.zc and self.service_info:
                self.zc.unregister_service(self.service_info)
                self.zc.close()

            self.loop.close()
            self.loop = None
            self.zc = None
            self.service_info = None

            with self._lock:
                self.running = False

            print("🛑 Broadcasting stopped")

    # ---------- Public API ----------

    def start(self):
        with self._lock:
            if self.running:
                return
            self.running = True

        self.thread = threading.Thread(
            target=self._run,
            daemon=True
        )
        self.thread.start()

    def stop(self):
        with self._lock:
            loop = self.loop
            if not self.running or not loop or loop.is_closed():
                return

        loop.call_soon_threadsafe(loop.stop)

    def toggle(self):
        if self.running:
            self.stop()
        else:
            self.start()
