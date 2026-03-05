"""
Lightweight TCP-based signaling server for WebRTC SDP exchange.

Each peer runs a SignalingServer that listens for incoming TCP connections.
When another peer wants to connect, it sends a JSON SDP offer, receives
a JSON SDP answer, and both sides exchange ICE candidates — all over this
single TCP connection. Once the WebRTC RTCPeerConnection is established,
the TCP signaling socket is closed.
"""

import asyncio
import json
import struct
import threading
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCConfiguration


def _create_pc():
    """Create an RTCPeerConnection with no STUN/TURN (LAN-only)."""
    config = RTCConfiguration(iceServers=[])
    return RTCPeerConnection(configuration=config)


async def _send_json(writer: asyncio.StreamWriter, obj: dict):
    """Send a length-prefixed JSON message."""
    data = json.dumps(obj).encode("utf-8")
    writer.write(struct.pack("!I", len(data)) + data)
    await writer.drain()


async def _recv_json(reader: asyncio.StreamReader) -> dict:
    """Receive a length-prefixed JSON message."""
    raw_len = await reader.readexactly(4)
    length = struct.unpack("!I", raw_len)[0]
    data = await reader.readexactly(length)
    return json.loads(data.decode("utf-8"))


class SignalingServer:
    """
    Runs an asyncio TCP server in a background thread.
    
    - Listens for incoming WebRTC signaling requests.
    - Provides `connect_to_peer()` for outbound connections.
    - Fires `on_connection(pc, channel)` when a data channel is ready.
    """

    def __init__(self, on_connection=None):
        """
        Args:
            on_connection: callback(pc: RTCPeerConnection, channel: RTCDataChannel)
                           Called when an inbound WebRTC connection is established.
        """
        self.on_connection = on_connection
        self._loop = None
        self._server = None
        self._thread = None
        self.port = None
        self._ready = threading.Event()

    # ── Lifecycle ──────────────────────────────────────────

    def start(self):
        """Start the signaling server in a background thread."""
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._ready.wait(timeout=10)

    def stop(self):
        """Shut down the server and event loop."""
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

    def _run_loop(self):
        """Entry point for the background thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._start_server())
        self._ready.set()
        self._loop.run_forever()

    async def _start_server(self):
        """Bind the TCP server on a random available port."""
        self._server = await asyncio.start_server(
            self._handle_client, "0.0.0.0", 0
        )
        self.port = self._server.sockets[0].getsockname()[1]

    # ── Inbound (answerer side) ───────────────────────────

    async def _handle_client(self, reader, writer):
        """Handle an incoming signaling TCP connection (answerer role)."""
        try:
            msg = await _recv_json(reader)
            offer = RTCSessionDescription(sdp=msg["sdp"], type=msg["type"])

            pc = _create_pc()
            ready_event = asyncio.Event()
            channel_holder = {}

            @pc.on("datachannel")
            def on_datachannel(channel):
                channel_holder["ch"] = channel
                ready_event.set()

            await pc.setRemoteDescription(offer)
            answer = await pc.createAnswer()
            await pc.setLocalDescription(answer)

            # Send answer back
            await _send_json(writer, {
                "sdp": pc.localDescription.sdp,
                "type": pc.localDescription.type,
            })

            # Wait for the data channel to open (with timeout)
            try:
                await asyncio.wait_for(ready_event.wait(), timeout=15)
            except asyncio.TimeoutError:
                await pc.close()
                return

            channel = channel_holder.get("ch")
            if channel and self.on_connection:
                self.on_connection(pc, channel)

        except Exception as e:
            print(f"Signaling error (inbound): {e}")
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    # ── Outbound (offerer side) ───────────────────────────

    async def _connect_async(self, host: str, port: int):
        """Create an outbound WebRTC connection via TCP signaling."""
        reader, writer = await asyncio.open_connection(host, port)

        pc = _create_pc()
        channel = pc.createDataChannel("data", ordered=True)

        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)

        # Send offer
        await _send_json(writer, {
            "sdp": pc.localDescription.sdp,
            "type": pc.localDescription.type,
        })

        # Receive answer
        msg = await _recv_json(reader)
        answer = RTCSessionDescription(sdp=msg["sdp"], type=msg["type"])
        await pc.setRemoteDescription(answer)

        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass

        # Wait for channel to open
        open_event = asyncio.Event()

        @channel.on("open")
        def on_open():
            open_event.set()

        if channel.readyState == "open":
            open_event.set()

        await asyncio.wait_for(open_event.wait(), timeout=15)

        return pc, channel

    def connect_to_peer(self, host: str, port: int):
        """
        Synchronous wrapper: connect to a remote peer's signaling server.
        Returns (pc, channel) or raises on failure.
        Must be called from a non-event-loop thread.
        """
        future = asyncio.run_coroutine_threadsafe(
            self._connect_async(host, port), self._loop
        )
        return future.result(timeout=20)
