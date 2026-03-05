"""
Manages a single WebRTC peer connection and its data channels.

Provides high-level methods for sending/receiving messages and files
over RTCDataChannel, with chunked binary transfer and progress tracking.
"""

import json
import os
import struct
import threading
from datetime import datetime


# Maximum chunk size for file transfer (16 KB — safe for data channels)
CHUNK_SIZE = 16 * 1024


class WebRTCConnection:
    """
    Wraps an established RTCPeerConnection + data channel for
    sending and receiving messages and files.
    """

    def __init__(
        self,
        pc,
        channel,
        download_dir="received_files",
        on_message=None,
        on_file_received=None,
        ui_log=None,
        ui_progress_bar=None,
        ui_progress_status=None,
    ):
        self.pc = pc
        self.channel = channel
        self.download_dir = download_dir
        self.on_message = on_message
        self.on_file_received = on_file_received
        self.ui_log = ui_log or (lambda *_: None)
        self.ui_progress_bar = ui_progress_bar
        self.ui_progress_status = ui_progress_status

        os.makedirs(self.download_dir, exist_ok=True)

        # Receive state
        self._recv_file_meta = None   # {"filename": ..., "size": ...}
        self._recv_file_handle = None
        self._recv_bytes = 0
        self._recv_part_path = None
        self._recv_final_path = None

        # Register channel event handlers
        self._setup_channel(channel)

    # ── Channel setup ─────────────────────────────────────

    def _setup_channel(self, channel):
        """Attach event handlers to the data channel."""

        @channel.on("message")
        def on_message(data):
            if isinstance(data, str):
                self._handle_text(data)
            else:
                self._handle_binary(data)

        @channel.on("close")
        def on_close():
            self._cleanup_recv()

    # ── Sending ───────────────────────────────────────────

    def send_message(self, text: str):
        """Send a text message."""
        msg = json.dumps({"type": "message", "text": text})
        self.channel.send(msg)

    def send_file(self, file_path: str, max_retries=3):
        """
        Send a file in chunks over the data channel.
        Runs in a background thread so the UI stays responsive.
        """
        def _send():
            if not os.path.exists(file_path):
                self.ui_log(f"❌ File not found: {file_path}")
                return

            file_size = os.path.getsize(file_path)
            filename = os.path.basename(file_path)

            for attempt in range(max_retries):
                try:
                    self.ui_log(
                        f"📁 Attempt {attempt + 1}: Sending {filename} "
                        f"({self._format_bytes(file_size)})"
                    )

                    # 1. Send file metadata header
                    header = json.dumps({
                        "type": "file_start",
                        "filename": filename,
                        "size": file_size,
                    })
                    self.channel.send(header)

                    # 2. Send file chunks
                    sent = 0
                    with open(file_path, "rb") as f:
                        while True:
                            chunk = f.read(CHUNK_SIZE)
                            if not chunk:
                                break
                            self.channel.send(chunk)
                            sent += len(chunk)
                            self._update_progress(sent, file_size, "Sending")

                    # 3. Send end marker
                    end_msg = json.dumps({"type": "file_end", "filename": filename})
                    self.channel.send(end_msg)

                    self.ui_log(f"✅ Successfully sent {filename}")
                    break

                except Exception as e:
                    self.ui_log(f"⚠️ Attempt {attempt + 1} failed: {e}")
                    if attempt == max_retries - 1:
                        self.ui_log(
                            f"❌ Failed to send {filename} after {max_retries} tries."
                        )

            self._reset_progress()

        threading.Thread(target=_send, daemon=True).start()

    # ── Receiving ─────────────────────────────────────────

    def _handle_text(self, data: str):
        """Handle incoming text data (JSON control messages or plain messages)."""
        try:
            msg = json.loads(data)
        except json.JSONDecodeError:
            # Plain text message
            if self.on_message:
                self.on_message(data)
            return

        msg_type = msg.get("type")

        if msg_type == "message":
            if self.on_message:
                self.on_message(msg.get("text", ""))

        elif msg_type == "file_start":
            self._start_recv(msg["filename"], msg["size"])

        elif msg_type == "file_end":
            self._finish_recv(msg["filename"])

    def _handle_binary(self, data: bytes):
        """Handle incoming binary data (file chunks)."""
        if self._recv_file_handle is None:
            return  # No file transfer in progress

        self._recv_file_handle.write(data)
        self._recv_bytes += len(data)

        total = self._recv_file_meta.get("size", 0) if self._recv_file_meta else 0
        filename = self._recv_file_meta.get("filename", "") if self._recv_file_meta else ""
        self._update_progress(self._recv_bytes, total, f"Receiving {filename}")

    def _start_recv(self, filename: str, size: int):
        """Begin receiving a new file."""
        self._recv_file_meta = {"filename": filename, "size": size}
        self._recv_bytes = 0

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_name = f"{timestamp}_{filename}"
        self._recv_final_path = os.path.join(self.download_dir, unique_name)
        self._recv_part_path = self._recv_final_path + ".part"

        self._recv_file_handle = open(self._recv_part_path, "wb")
        self.ui_log(f"📥 Receiving {filename} ({self._format_bytes(size)})")

    def _finish_recv(self, filename: str):
        """Finalize a received file."""
        if self._recv_file_handle:
            self._recv_file_handle.close()
            self._recv_file_handle = None

        if self._recv_part_path and self._recv_final_path:
            try:
                os.rename(self._recv_part_path, self._recv_final_path)
            except OSError as e:
                self.ui_log(f"❌ Error finalizing file: {e}")

        self.ui_log(f"✅ Received {filename}")
        self._reset_progress()

        if self.on_file_received:
            self.on_file_received(self._recv_final_path)

        self._recv_file_meta = None
        self._recv_bytes = 0
        self._recv_part_path = None
        self._recv_final_path = None

    def _cleanup_recv(self):
        """Clean up on channel close."""
        if self._recv_file_handle:
            self._recv_file_handle.close()
            self._recv_file_handle = None

        if self._recv_part_path and os.path.exists(self._recv_part_path):
            try:
                os.remove(self._recv_part_path)
            except OSError:
                pass

    # ── UI helpers ────────────────────────────────────────

    def _update_progress(self, sent, total, label):
        if total <= 0:
            return
        progress = sent / total
        percent = progress * 100

        if self.ui_progress_bar:
            try:
                self.ui_progress_bar.set(progress)
            except Exception:
                pass

        if self.ui_progress_status:
            try:
                status = (
                    f"{label}: {self._format_bytes(sent)}/"
                    f"{self._format_bytes(total)} ({percent:.1f}%)"
                )
                self.ui_progress_status.configure(text=status)
            except Exception:
                pass

    def _reset_progress(self):
        if self.ui_progress_bar:
            try:
                self.ui_progress_bar.set(0)
            except Exception:
                pass
        if self.ui_progress_status:
            try:
                self.ui_progress_status.configure(text="")
            except Exception:
                pass

    @staticmethod
    def _format_bytes(val):
        for unit in ["B", "KB", "MB", "GB"]:
            if val < 1024.0:
                return f"{val:.1f}{unit}"
            val /= 1024.0
        return f"{val:.1f}TB"

    # ── Cleanup ───────────────────────────────────────────

    def close(self):
        """Close the WebRTC connection."""
        self._cleanup_recv()
        try:
            self.channel.close()
        except Exception:
            pass
