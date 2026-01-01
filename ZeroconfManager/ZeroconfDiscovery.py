import asyncio
import threading
from zeroconf import Zeroconf, ServiceBrowser


class ZeroconfDiscovery:
    def __init__(self, service_type="_http._tcp.local.", on_update=None):
        self.service_type = service_type
        self.on_update = on_update  # callback(name, info)

        self.thread = None
        self.loop = None
        self.zc = None
        self.browser = None

        self.running = False

    # ---- Zeroconf callback (NEW API compatible) ----
    def _on_service(self, **kwargs):
        zc = kwargs.get("zeroconf")
        service_type = kwargs.get("service_type")
        name = kwargs.get("name")

        if not zc:
            return

        info = zc.get_service_info(service_type, name)
        if self.on_update:
            self.on_update(name, info)

    # ---- Async loop thread ----
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
            if self.browser:
                self.browser.cancel()
            if self.zc:
                self.zc.close()

            self.browser = None
            self.zc = None
            self.loop.close()
            self.loop = None

            print("🛑 Discovery stopped")

    # ---- Public API ----
    def start(self):
        if self.running:
            return

        self.running = True
        self.thread = threading.Thread(
            target=self._run,
            daemon=True
        )
        self.thread.start()

    def stop(self):
        if not self.running or not self.loop:
            return

        self.loop.call_soon_threadsafe(self.loop.stop)
        self.running = False

    def toggle(self):
        if self.running:
            self.stop()
        else:
            self.start()
