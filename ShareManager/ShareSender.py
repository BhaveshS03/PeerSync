"""
ShareSender – sends messages and files over an established WebRTC connection.

This is now a thin wrapper around WebRTCConnection, managing the connection
lifecycle per-peer. It uses the SignalingServer to establish WebRTC connections.
"""


class ShareSender:
    def __init__(
        self,
        *,
        signaling_server,
        ui_log=None,
        ui_progress_bar=None,
        ui_progress_status=None,
    ):
        self.signaling = signaling_server
        self.ui_log = ui_log or (lambda *_: None)
        self.ui_progress_bar = ui_progress_bar
        self.ui_progress_status = ui_progress_status

        # peer_id -> WebRTCConnection
        self.connections = {}

    def _log(self, text):
        self.ui_log(text)

    def connect_peer(self, peer):
        """Establish a WebRTC connection to the given peer via signaling."""
        from WebRTCManager import WebRTCConnection

        if peer.id in self.connections:
            self._log(f"🔗 Already connected to {peer.name}")
            return

        try:
            self._log(f"🔗 Connecting to {peer.name} ({peer.address}:{peer.signaling_port})…")
            pc, channel = self.signaling.connect_to_peer(
                peer.address, peer.signaling_port
            )

            conn = WebRTCConnection(
                pc=pc,
                channel=channel,
                on_message=lambda text: self._log(f"💬 {peer.name}: {text}"),
                ui_log=self.ui_log,
                ui_progress_bar=self.ui_progress_bar,
                ui_progress_status=self.ui_progress_status,
            )

            self.connections[peer.id] = conn
            self._log(f"✅ Connected to {peer.name}")

        except Exception as e:
            self._log(f"❌ Failed to connect to {peer.name}: {e}")

    def send_message(self, peer, text: str):
        """Send a text message to a connected peer."""
        conn = self.connections.get(peer.id)
        if not conn:
            self._log(f"⚠ Not connected to {peer.name}. Connect first.")
            return
        try:
            conn.send_message(text)
            self._log(f"📤 Sent to {peer.name}: {text}")
        except Exception as e:
            self._log(f"❌ Send failed: {e}")

    def send_file(self, peer, file_path: str):
        """Send a file to a connected peer."""
        conn = self.connections.get(peer.id)
        if not conn:
            self._log(f"⚠ Not connected to {peer.name}. Connect first.")
            return
        conn.send_file(file_path)

    def disconnect_peer(self, peer_id: str):
        """Close a connection to a peer."""
        conn = self.connections.pop(peer_id, None)
        if conn:
            conn.close()

    def close_all(self):
        """Close all open connections."""
        for conn in self.connections.values():
            conn.close()
        self.connections.clear()