import asyncio
import threading
from zeroconf import Zeroconf, ServiceBrowser


class ZeroconfDiscovery:
    def __init__(self, service_type="_http._tcp.local.", own_id=None, on_update=None):
        self.service_type = service_type
        self.own_id = own_id          # 🔑 UUID of THIS device
        self.on_update = on_update

        self.thread = None
        self.loop = None
        self.zc = None
        self.browser = None
        self.running = False

    def _on_service(self, **kwargs):
        zc = kwargs.get("zeroconf")
        service_type = kwargs.get("service_type")
        name = kwargs.get("name")

        if not zc:
            return

        info = zc.get_service_info(service_type, name)
        if not info:
            return

        props = info.properties or {}
        remote_id = props.get(b"id", b"").decode()

        # 🚫 hide our own service
        if remote_id == self.own_id:
            return

        if self.on_update:
            self.on_update(name, info)

    def _run(self):
        asyncio.set_event_loop(asyncio.new_event_loop())
        self.loop = asyncio.get_event_loop()

        self.zc = Zeroconf()
        self.browser = ServiceBrowser(
            self.zc,
            self.service_type,
            handlers=[self._on_service],
        )

        print("🔍 Discovery started")

        try:
            self.loop.run_forever()
        finally:
            self.browser.cancel()
            self.zc.close()
            self.loop.close()
            self.loop = None
            self.running = False
            print("🛑 Discovery stopped")

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        if not self.running or not self.loop:
            return
        self.loop.call_soon_threadsafe(self.loop.stop)

    def toggle(self):
        self.stop() if self.running else self.start()
