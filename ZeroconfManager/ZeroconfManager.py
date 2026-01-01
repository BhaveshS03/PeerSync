import time
from dataclasses import dataclass

@dataclass
class Peer:
    id: str
    name: str
    address: str
    port: int
    last_seen: float


import threading
import time
from typing import Callable, Dict

PEER_TTL = 5.0          # seconds before peer considered gone
CLEANUP_INTERVAL = 1.0 # seconds

class ZeroconfManager:
    def __init__(
        self,
        broadcaster,
        discovery,
        on_add: Callable[[Peer], None] = None,
        on_update: Callable[[Peer], None] = None,
        on_remove: Callable[[Peer], None] = None,
    ):
        self.broadcaster = broadcaster
        self.discovery = discovery

        self.on_add = on_add
        self.on_update = on_update
        self.on_remove = on_remove

        self.peers: Dict[str, Peer] = {}
        self._lock = threading.Lock()

        self._cleanup_thread = None
        self._running = False

        # wire discovery callback
        self.discovery.on_update = self._on_service_update

    # ---------------------------
    # Discovery callback
    # ---------------------------
    def _on_service_update(self, name, info):
        props = info.properties or {}
        peer_id = props.get(b"id", b"").decode()
        if not peer_id:
            return

        address = ".".join(map(str, info.addresses[0]))
        port = info.port
        now = time.time()

        with self._lock:
            if peer_id in self.peers:
                peer = self.peers[peer_id]
                peer.last_seen = now
                peer.address = address
                peer.port = port

                if self.on_update:
                    self.on_update(peer)
            else:
                peer = Peer(
                    id=peer_id,
                    name=name,
                    address=address,
                    port=port,
                    last_seen=now,
                )
                self.peers[peer_id] = peer

                if self.on_add:
                    self.on_add(peer)

    # ---------------------------
    # Cleanup loop
    # ---------------------------
    def _cleanup_loop(self):
        while self._running:
            time.sleep(CLEANUP_INTERVAL)
            now = time.time()

            with self._lock:
                expired = [
                    pid for pid, peer in self.peers.items()
                    if now - peer.last_seen > PEER_TTL
                ]

                for pid in expired:
                    peer = self.peers.pop(pid)
                    if self.on_remove:
                        self.on_remove(peer)

    # ---------------------------
    # Lifecycle
    # ---------------------------
    def start(self):
        if self._running:
            return

        self._running = True

        self.broadcaster.start()
        self.discovery.start()

        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            daemon=True
        )
        self._cleanup_thread.start()

    def stop(self):
        if not self._running:
            return

        self._running = False
        self.discovery.stop()
        self.broadcaster.stop()

        with self._lock:
            for peer in self.peers.values():
                if self.on_remove:
                    self.on_remove(peer)
            self.peers.clear()

    def toggle(self):
        self.stop() if self._running else self.start()
