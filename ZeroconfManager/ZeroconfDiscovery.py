from zeroconf import Zeroconf, ServiceBrowser
import threading


class ZeroconfDiscovery:
    def __init__(self, service_type="_http._tcp.local.", on_update=None):
        self.service_type = service_type
        self.on_update = on_update  # callback(service_name, info)

        self.zc = Zeroconf()
        self.browser = None
        self.services = {}
        self.lock = threading.Lock()

    def start(self):
        if self.browser:
            return
        self.browser = ServiceBrowser(
            self.zc,
            self.service_type,
            handlers=[self._on_service]
        )
        print("🔍 Discovery started")

    def stop(self):
        if not self.browser:
            return
        self.browser.cancel()
        self.zc.close()
        self.browser = None
        print("🛑 Discovery stopped")

    def _on_service(self, zc, service_type, name, state_change):
        info = zc.get_service_info(service_type, name)
        with self.lock:
            if info:
                self.services[name] = info
            else:
                self.services.pop(name, None)

        if self.on_update:
            self.on_update(name, info)
