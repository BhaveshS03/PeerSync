import threading
import time
from dataclasses import dataclass
from typing import Callable, Dict


@dataclass
class Peer:
    id: str
    name: str
    address: str
    port: int
    last_seen: float


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
        self._running = False

        # 🔌 Wire discovery callbacks
        self.discovery.on_add = self._on_peer_add
        self.discovery.on_remove = self._on_peer_remove

    # ─────────────────────────────
    # Discovery → Manager callbacks
    # ─────────────────────────────
    def _on_peer_add(self, name, info):
        now = time.time()
        peer_id = info["id"]

        with self._lock:
            if peer_id in self.peers:
                peer = self.peers[peer_id]
                peer.address = info["address"]
                peer.port = info["port"]
                peer.last_seen = now

                if self.on_update:
                    self.on_update(peer)
                return

            peer = Peer(
                id=peer_id,
                name=name,
                address=info["address"],
                port=info["port"],
                last_seen=now,
            )

            self.peers[peer_id] = peer

        if self.on_add:
            self.on_add(peer)

    def _on_peer_remove(self, name, info):
        peer_id = info["id"]

        with self._lock:
            peer = self.peers.pop(peer_id, None)

        if peer and self.on_remove:
            self.on_remove(peer)

    # ─────────────────────────────
    # Lifecycle
    # ─────────────────────────────
    def start(self):
        with self._lock:
            if self._running:
                return
            self._running = True

        self.broadcaster.start()
        self.discovery.start()

    def stop(self):
        with self._lock:
            if not self._running:
                return
            self._running = False

        self.discovery.stop()
        self.broadcaster.stop()

        with self._lock:
            peers = list(self.peers.values())
            self.peers.clear()

        for peer in peers:
            if self.on_remove:
                self.on_remove(peer)

    def toggle(self):
        self.stop() if self._running else self.start()
