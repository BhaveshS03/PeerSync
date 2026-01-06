import threading
import queue
import requests
import uvicorn
import customtkinter as ctk
import os
from tkinter import filedialog, messagebox
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
        self.app.geometry("680x650")
        self.app.title("ZenSync Manager")

        self.log_box = ctk.CTkTextbox(self.app, width=620, height=150)
        self.log_box.pack(pady=10)

        self.peer_frame = ctk.CTkScrollableFrame(self.app, width=620, height=140)
        self.peer_frame.pack(pady=5)

        self.progress_frame = ctk.CTkFrame(self.app, width=620, height=50)
        self.progress_frame.pack(pady=5, fill="x", padx=30)

        self.progress_label = ctk.CTkLabel(self.progress_frame, text="File Transfer Progress:")
        self.progress_label.pack(pady=(5, 0))

        self.progress_bar = ctk.CTkProgressBar(self.progress_frame, width=500)
        self.progress_bar.pack(pady=5)
        self.progress_bar.set(0)

        self.progress_status = ctk.CTkLabel(self.progress_frame, text="")
        self.progress_status.pack(pady=(0, 5))

        self.msg_entry = ctk.CTkEntry(
            self.app,
            width=620,
            placeholder_text="Type message to send...",
        )
        self.msg_entry.pack(pady=5)

        self.settings_frame = ctk.CTkFrame(self.app, width=620)
        self.settings_frame.pack(pady=10, padx=30, fill="x")

        self.name_label = ctk.CTkLabel(self.settings_frame, text="Your Name:")
        self.name_label.grid(row=0, column=0, padx=10, pady=10)

        default_name = os.getlogin() if hasattr(os, "getlogin") else "User"
        self.name_entry = ctk.CTkEntry(self.settings_frame, width=200)
        self.name_entry.insert(0, default_name)
        self.name_entry.grid(row=0, column=1, padx=10, pady=10)

        self.toggle_btn = ctk.CTkButton(
            self.settings_frame,
            text="Start Server",
            command=self.toggle_manager,
            fg_color="green", hover_color="darkgreen"
        )
        self.toggle_btn.grid(row=0, column=2, padx=10, pady=10)

        self.btn_frame = ctk.CTkFrame(self.app, fg_color="transparent")
        self.btn_frame.pack(pady=5)

        self.connect_btn = ctk.CTkButton(
            self.btn_frame,
            text="Connect to Peer",
            command=self.connect_selected,
            state="disabled",
        )
        self.connect_btn.pack(side="left", padx=5)

        self.send_btn = ctk.CTkButton(
            self.btn_frame,
            text="Send Message",
            command=self.send_selected,
            state="disabled",
        )
        self.send_btn.pack(side="left", padx=5)

        self.file_btn = ctk.CTkButton(
            self.btn_frame,
            text="Send File",
            command=self.send_file_selected,
            state="disabled",
        )
        self.file_btn.pack(side="left", padx=5)

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
            ui_progress_bar=self.progress_bar,
            ui_progress_status=self.progress_status,
        )

        self.selected_peer_name.trace_add("write", self.on_peer_change)
        self.app.protocol("WM_DELETE_WINDOW", self.on_close)

    def start(self):
        threading.Thread(target=self._start_http_server, daemon=True).start()
        self.app.mainloop()

    def _start_http_server(self):
        uvicorn.run(self.api, host="0.0.0.0", port=self.HTTP_PORT, log_level="critical")

    def ui_log(self, text):
        self.app.after(0, lambda: self.log_box.insert("end", text + "\n"))

    def ui_clear(self):
        self.app.after(0, lambda: self.log_box.delete("1.0", "end"))
        
    def _network_worker(self):
        while self.net_running:
            try:
                fn, args = self.net_queue.get(timeout=0.5)
                fn(*args)
            except queue.Empty: continue
            except Exception as e: self.ui_log(f"⚠ Network error: {e}")

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
        self.ui_log(f"➕ {peer.name} joined")

    def on_update(self, peer):
        self.ui_log(f"🔄 {peer.name} updated")

    def on_remove(self, peer):
        self.peers.pop(peer.name, None)
        radio = self.peer_radios.pop(peer.name, None)
        if radio: radio.destroy()
        if self.selected_peer_name.get() == peer.name:
            self.selected_peer_name.set("")
        self.ui_log(f"➖ {peer.name} left")

    def connect_selected(self):
        peer = self.get_selected_peer()
        if peer: self.dispatch(self.sender.connect_peer, peer)

    def send_selected(self):
        peer = self.get_selected_peer()
        text = self.msg_entry.get().strip()
        if peer and text:
            self.msg_entry.delete(0, "end")
            self.dispatch(self.sender.send_message, peer, text)

    def send_file_selected(self):
        peer = self.get_selected_peer()
        if not peer: return
        file_path = filedialog.askopenfilename()
        if file_path:
            self.dispatch(self.sender.send_file, peer, file_path)
            
    def on_peer_change(self, *_):
        state = "normal" if self.selected_peer_name.get() else "disabled"
        self.connect_btn.configure(state=state)
        self.send_btn.configure(state=state)
        self.file_btn.configure(state=state)

    def toggle_manager(self):
        if self.manager._running:
            self.manager.stop()
            self.ui_log("🛑 Zeroconf stopped")
            self.toggle_btn.configure(
                text="Start Zeroconf", 
                fg_color="green", 
                hover_color="darkgreen"
            )
            self.name_entry.configure(state="normal")
        else:
            custom_name = self.name_entry.get().strip()
            if not custom_name:
                messagebox.showerror("Error", "Please enter a valid name before starting.")
                return

            self.ui_clear()
            self.broadcaster.instance_id = custom_name
            self.sender.sender_id = custom_name
            self.discovery.own_id = custom_name
            self.name_entry.configure(state="disabled")

            self.manager.start()
            self.ui_log(f"▶ Zeroconf started as '{custom_name}'")
            self.toggle_btn.configure(
                text="Stop Zeroconf", 
                fg_color="red", 
                hover_color="darkred"
            )

    def on_close(self):
        self.net_running = False
        self.manager.stop()
        self.app.destroy()

if __name__ == "__main__":
    ZenSyncApp().start()
