import threading
import socket
import time
import psutil
import uuid
from zeroconf import Zeroconf, ServiceInfo


class ZeroconfBroadcaster:
    def __init__(self, base_name="ZenSync", service_type="_http._tcp.local.", port=9999):
        self.base_name = base_name
        self.service_type = service_type
        self.port = port

        self.instance_id = uuid.uuid4().hex[:8]
        self.full_name = f"{self.base_name}-{self.instance_id}"

        self.thread = None
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
        ip = self._get_ip()
        if not ip:
            print("❌ No valid IP found")
            return

        self.zc = Zeroconf()
        self.service_info = ServiceInfo(
            self.service_type,
            f"{self.full_name}.{self.service_type}",
            addresses=[socket.inet_aton(ip)],
            port=self.port,
            properties={
                "id": self.instance_id,
                "app": "zensync",
            },
        )

        self.zc.register_service(self.service_info)
        print(f"📡 Broadcasting as {self.full_name}")

        # 🔁 Keep thread alive while broadcasting
        while True:
            with self._lock:
                if not self.running:
                    break
            time.sleep(1)

        try:
            self.zc.unregister_service(self.service_info)
        except Exception:
            pass

        self.zc.close()
        self.zc = None
        self.service_info = None

        print("🛑 Broadcasting stopped")

    def start(self):
        with self._lock:
            if self.running:
                return
            self.running = True

        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        with self._lock:
            if not self.running:
                return
            self.running = False

    def toggle(self):
        self.stop() if self.running else self.start()
