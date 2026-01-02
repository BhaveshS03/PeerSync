import threading
import queue
import requests
import uvicorn
import customtkinter as ctk
from fastapi import FastAPI

from ZeroconfManager import (
    ZeroconfManager,
    ZeroconfBroadcaster,
    ZeroconfDiscovery,
)
from ShareManager import ShareSender, ShareReceiver


class ZenSyncApp:
    SERVICE_NAME = "MyService"
    HTTP_PORT = 8000
    REQUEST_TIMEOUT = 2

    def __init__(self):
        self.api = FastAPI(title="ZenSyncServer")
        self.receiver = ShareReceiver(self.api)

        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.app = ctk.CTk()
        self.app.geometry("680x600")
        self.app.title("ZenSync Manager")

        self.log_box = ctk.CTkTextbox(self.app, width=620, height=170)
        self.log_box.pack(pady=10)

        self.peer_frame = ctk.CTkScrollableFrame(self.app, width=620, height=160)
        self.peer_frame.pack(pady=5)

        self.msg_entry = ctk.CTkEntry(
            self.app,
            width=620,
            placeholder_text="Type message to send...",
        )
        self.msg_entry.pack(pady=10)

        self.peers = {}
        self.peer_radios = {}
        self.selected_peer_name = ctk.StringVar(value="")

        self.net_queue = queue.Queue()
        self.net_running = True

        threading.Thread(
            target=self._network_worker,
            daemon=True,
        ).start()

        self.broadcaster = ZeroconfBroadcaster(
            base_name=self.SERVICE_NAME,
            port=self.HTTP_PORT,
        )

        self.discovery = ZeroconfDiscovery(
            own_id=self.broadcaster.instance_id,
        )

        self.manager = ZeroconfManager(
            broadcaster=self.broadcaster,
            discovery=self.discovery,
            on_add=self.on_add,
            on_update=self.on_update,
            on_remove=self.on_remove,
        )

        self.sender = ShareSender(
            timeout=self.REQUEST_TIMEOUT,
            sender_id=self.broadcaster.instance_id,
            ui_log=self.ui_log,
        )

        self.connect_btn = ctk.CTkButton(
            self.app,
            text="Connect to Peer",
            command=self.connect_selected,
            state="disabled",
        )
        self.connect_btn.pack(pady=5)

        self.send_btn = ctk.CTkButton(
            self.app,
            text="Send Message",
            command=self.send_selected,
            state="disabled",
        )
        self.send_btn.pack(pady=5)

        self.toggle_btn = ctk.CTkButton(
            self.app,
            text="Start Zeroconf",
            command=self.toggle_manager,
        )
        self.toggle_btn.pack(pady=12)

        self.selected_peer_name.trace_add("write", self.on_peer_change)
        self.app.protocol("WM_DELETE_WINDOW", self.on_close)

    def start(self):
        threading.Thread(
            target=self._start_http_server,
            daemon=True,
        ).start()

        self.app.mainloop()

    def _start_http_server(self):
        uvicorn.run(
            self.api,
            host="0.0.0.0",
            port=self.HTTP_PORT,
            log_level="warning",
        )

    def ui_log(self, text):
        self.app.after(0, lambda: self.log_box.insert("end", text + "\n"))

    def ui_clear(self):
        self.app.after(0, lambda: self.log_box.delete("1.0", "end"))

    def _network_worker(self):
        while self.net_running:
            try:
                fn, args = self.net_queue.get(timeout=0.5)
                fn(*args)
            except queue.Empty:
                continue
            except Exception as e:
                self.ui_log(f"⚠ Network error: {e}")

    def dispatch(self, fn, *args):
        self.net_queue.put((fn, args))

    def get_selected_peer(self):
        return self.peers.get(self.selected_peer_name.get())

    def on_add(self, peer):
        self.peers[peer.name] = peer

        radio = ctk.CTkRadioButton(
            self.peer_frame,
            text=f"{peer.name} @ {peer.address}:{peer.port}",
            variable=self.selected_peer_name,
            value=peer.name,
        )
        radio.pack(anchor="w", padx=10, pady=2)

        self.peer_radios[peer.name] = radio
        self.ui_log(f"➕ {peer.name} @ {peer.address}:{peer.port}")

    def on_update(self, peer):
        self.ui_log(f"🔄 {peer.name}")

    def on_remove(self, peer):
        self.peers.pop(peer.name, None)

        radio = self.peer_radios.pop(peer.name, None)
        if radio:
            radio.destroy()

        if self.selected_peer_name.get() == peer.name:
            self.selected_peer_name.set("")

        self.ui_log(f"➖ {peer.name}")

    def connect_selected(self):
        peer = self.get_selected_peer()
        if not peer:
            self.ui_log("⚠ No peer selected")
            return
        self.dispatch(self.sender.connect_peer, peer)

    def send_selected(self):
        peer = self.get_selected_peer()
        if not peer:
            self.ui_log("⚠ No peer selected")
            return

        text = self.msg_entry.get().strip()
        if not text:
            return

        self.msg_entry.delete(0, "end")
        self.dispatch(self.sender.send_message, peer, text)

    def on_peer_change(self, *_):
        state = "normal" if self.selected_peer_name.get() else "disabled"
        self.connect_btn.configure(state=state)
        self.send_btn.configure(state=state)

    def toggle_manager(self):
        if self.manager._running:
            self.manager.stop()
            self.ui_log("🛑 Zeroconf stopped")
            self.toggle_btn.configure(text="Start Zeroconf")
        else:
            self.ui_clear()
            self.manager.start()
            self.ui_log("▶ Zeroconf started")
            self.toggle_btn.configure(text="Stop Zeroconf")

    def on_close(self):
        self.net_running = False
        self.manager.stop()
        self.app.destroy()

if __name__ == "__main__":
    ZenSyncApp().start()
