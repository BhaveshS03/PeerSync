import time
import threading
import random
import string

from ZeroconfManager import ZeroconfManager, ZeroconfDiscovery


def random_peer_id():
    return "".join(random.choices("abcdef0123456789", k=8))


def fake_info(peer_id):
    return {
        "id": peer_id,
        "address": f"192.168.1.{random.randint(2, 254)}",
        "port": random.randint(1000, 9999),
    }


class DummyBroadcaster:
    def start(self): pass
    def stop(self): pass


def test_stress_discovery_manager():
    PEER_COUNT = 20000
    UPDATE_ROUNDS = 200

    added = set()
    removed = set()
    updated = 0

    lock = threading.Lock()

    def on_add(peer):
        with lock:
            added.add(peer.id)

    def on_update(peer):
        nonlocal updated
        with lock:
            updated += 1

    def on_remove(peer):
        with lock:
            removed.add(peer.id)

    discovery = ZeroconfDiscovery(
        service_type="_http._tcp.local.",
        own_id="self",
        ttl=0.3,
        cleanup_interval=0.05,
    )

    manager = ZeroconfManager(
        broadcaster=DummyBroadcaster(),
        discovery=discovery,
        on_add=on_add,
        on_update=on_update,
        on_remove=on_remove,
    )

    manager.start()

    peer_ids = [random_peer_id() for _ in range(PEER_COUNT)]

    for _ in range(UPDATE_ROUNDS):
        for pid in peer_ids:
            discovery.on_add(
                name=f"Peer-{pid}",
                info=fake_info(pid),
            )
        time.sleep(0.01)

    # Allow TTL expiry
    time.sleep(1)

    manager.stop()

    assert len(added) == PEER_COUNT, (
        f"Expected {PEER_COUNT} peers added, got {len(added)}"
    )

    assert added == removed, (
        "Mismatch between added and removed peers"
    )

    assert updated > 0, "Expected updates but got none"

    print("✅ Discovery stress test PASSED")
    print(f"Peers added:   {len(added)}")
    print(f"Peers removed: {len(removed)}")
    print(f"Updates seen:  {updated}")

if __name__ == '__main__':
    test_stress_discovery_manager()