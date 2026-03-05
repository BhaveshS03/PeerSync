"""
ShareReceiver – handles incoming WebRTC connections and receives messages/files.

This replaces the old FastAPI-based receiver. It registers itself as the
inbound connection handler on the SignalingServer.
"""

from WebRTCManager import WebRTCConnection


class ShareReceiver:
    def __init__(
        self,
        signaling_server,
        ui_log=None,
        ui_progress_bar=None,
        ui_progress_status=None,
    ):
        self.signaling = signaling_server
        self.ui_log = ui_log or (lambda *_: None)
        self.ui_progress_bar = ui_progress_bar
        self.ui_progress_status = ui_progress_status

        # Register to handle inbound WebRTC connections
        self.signaling.on_connection = self._on_inbound_connection

        # Track inbound connections
        self.connections = []

    def _on_inbound_connection(self, pc, channel):
        """Called by SignalingServer when a remote peer connects to us."""
        conn = WebRTCConnection(
            pc=pc,
            channel=channel,
            on_message=self._on_message,
            on_file_received=self._on_file_received,
            ui_log=self.ui_log,
            ui_progress_bar=self.ui_progress_bar,
            ui_progress_status=self.ui_progress_status,
        )
        self.connections.append(conn)
        self.ui_log("📥 Inbound WebRTC connection established")

    def _on_message(self, text):
        self.ui_log(f"💬 Received: {text}")

    def _on_file_received(self, path):
        self.ui_log(f"📁 File saved: {path}")

    def close_all(self):
        """Close all inbound connections."""
        for conn in self.connections:
            conn.close()
        self.connections.clear()