import requests

class ShareSender:
    def __init__(self, *, timeout=2, sender_id=None, ui_log=None):
        self.timeout = timeout
        self.sender_id = sender_id
        self.ui_log = ui_log or (lambda *_: None)

    def _log(self, text):
        self.ui_log(text)

    def connect_peer(self, peer) -> bool:
        # Better in Future
        try:
            requests.get(
                f"http://{peer.address}:{peer.port}/ping",
                timeout=self.timeout,
            )
            self._log(f"✅ Connected to {peer.name}")
            return True
        except Exception as e:
            self._log(f"❌ Connect failed {peer.name}: {e}")
            return False

    def send_message(self, peer, message: str) -> bool:
        # better now
        try:
            requests.post(
                f"http://{peer.address}:{peer.port}/message",
                json={
                    "sender": self.sender_id,
                    "message": message,
                },
                timeout=self.timeout,
            )
            self._log(f"📤 Sent to {peer.name}")
            return True
        except Exception as e:
            self._log(f"❌ Send failed {peer.name}: {e}")
            return False
