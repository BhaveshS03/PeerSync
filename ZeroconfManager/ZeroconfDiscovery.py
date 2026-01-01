import threading
import time
import socket
from zeroconf import Zeroconf, ServiceBrowser, ServiceStateChange


class ZeroconfDiscovery:
    def __init__(
        self,
        service_type="_http._tcp.local.",
        own_id=None,
        on_add=None,
        on_remove=None,
        ttl=6,
        cleanup_interval=2,
    ):
        self.service_type = service_type
        self.own_id = own_id
        self.on_add = on_add
        self.on_remove = on_remove

        self.ttl = ttl
        self.cleanup_interval = cleanup_interval

        self.zc = None
        self.browser = None
        self.running = False
        self._lock = threading.Lock()

        # name -> {info, last_seen}
        self.peers = {}

        self._cleanup_thread = None

    def _on_service(
        self,
        zeroconf,
        service_type,
        name,
        state_change,
    ):
        if state_change not in (ServiceStateChange.Added, ServiceStateChange.Updated):
            return

        info = zeroconf.get_service_info(service_type, name)
        if not info or not info.properties:
            return

        props = {k.decode(): v.decode() for k, v in info.properties.items()}
        peer_id = props.get("id")

        if peer_id == self.own_id:
            return

        addr = socket.inet_ntoa(info.addresses[0]) if info.addresses else None

        with self._lock:
            first_seen = name not in self.peers
            self.peers[name] = {
                "id": peer_id,
                "address": addr,
                "port": info.port,
                "last_seen": time.time(),
            }

        if first_seen and self.on_add:
            self.on_add(name, self.peers[name])

    def _cleanup_loop(self):
        while True:
            with self._lock:
                if not self.running:
                    break

                now = time.time()
                expired = [
                    name for name, peer in self.peers.items()
                    if now - peer["last_seen"] > self.ttl
                ]

                for name in expired:
                    peer = self.peers.pop(name)
                    if self.on_remove:
                        self.on_remove(name, peer)

            time.sleep(self.cleanup_interval)

    def start(self):
        with self._lock:
            if self.running:
                return
            self.running = True

        self.zc = Zeroconf()
        self.browser = ServiceBrowser(
            self.zc,
            self.service_type,
            handlers=[self._on_service],
        )

        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            daemon=True,
        )
        self._cleanup_thread.start()

    def stop(self):
        with self._lock:
            if not self.running:
                return
            self.running = False

        if self.browser:
            self.browser.cancel()
            self.browser = None

        if self.zc:
            self.zc.close()
            self.zc = None

        with self._lock:
            self.peers.clear()

    def toggle(self):
        self.stop() if self.running else self.start()
