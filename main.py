import threading
import queue
import requests
import uvicorn
import os
import sys

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib, Gio

from fastapi import FastAPI

from ZeroconfManager import (
    ZeroconfManager,
    ZeroconfBroadcaster,
    ZeroconfDiscovery,
)
from ShareManager import ShareSender, ShareReceiver

class ProgressBarWrapper:
    def __init__(self, gtk_progress_bar):
        self.bar = gtk_progress_bar
    def set(self, val):
        GLib.idle_add(self.bar.set_fraction, val)

class LabelWrapper:
    def __init__(self, gtk_label):
        self.label = gtk_label
    def configure(self, text=""):
        GLib.idle_add(self.label.set_label, text)

class ZenSyncApp(Gtk.Application):
    SERVICE_NAME = "MyService"
    HTTP_PORT = 8000
    REQUEST_TIMEOUT = 2

    def __init__(self):
        super().__init__(application_id='com.zensync.manager',
                         flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.api = FastAPI(title="ZenSyncServer")
        self.receiver = ShareReceiver(self.api)

        self.peers = {}
        self.selected_peer_name = ""

        self.net_queue = queue.Queue()
        self.net_running = True

        threading.Thread(
            target=self._network_worker,
            daemon=True,
        ).start()

    def do_activate(self):
        window = getattr(self.props, 'active_window', None)
        if not window:
            window = Gtk.ApplicationWindow(application=self)
            window.set_title("ZenSync Manager")
            window.set_default_size(680, 650)
            
            # Setup close handler
            window.connect("close-request", self.on_close)

            # Main container (VBox)
            vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            vbox.set_margin_start(10)
            vbox.set_margin_end(10)
            vbox.set_margin_top(10)
            vbox.set_margin_bottom(10)
            window.set_child(vbox)

            # Log box
            scrolled_log = Gtk.ScrolledWindow()
            scrolled_log.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
            scrolled_log.set_size_request(620, 150)
            
            self.log_buffer = Gtk.TextBuffer()
            log_view = Gtk.TextView(buffer=self.log_buffer)
            log_view.set_editable(False)
            log_view.set_cursor_visible(False)
            scrolled_log.set_child(log_view)
            vbox.append(scrolled_log)

            # Peer frame (ListBox)
            scrolled_peers = Gtk.ScrolledWindow()
            scrolled_peers.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
            scrolled_peers.set_size_request(620, 140)
            self.peer_list = Gtk.ListBox()
            self.peer_list.connect("row-selected", self.on_peer_change)
            scrolled_peers.set_child(self.peer_list)
            vbox.append(scrolled_peers)

            # Progress frame
            progress_frame = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            progress_frame.set_margin_start(30)
            progress_frame.set_margin_end(30)
            
            self.progress_label = Gtk.Label(label="File Transfer Progress:")
            progress_frame.append(self.progress_label)
            
            self.progress_bar = Gtk.ProgressBar()
            self.progress_bar.set_size_request(500, -1)
            progress_frame.append(self.progress_bar)
            
            self.progress_status = Gtk.Label(label="")
            progress_frame.append(self.progress_status)
            vbox.append(progress_frame)

            # Message entry
            self.msg_entry = Gtk.Entry()
            self.msg_entry.set_placeholder_text("Type message to send...")
            vbox.append(self.msg_entry)

            # Settings frame
            settings_grid = Gtk.Grid()
            settings_grid.set_column_spacing(10)
            settings_grid.set_row_spacing(10)
            settings_grid.set_margin_start(30)
            settings_grid.set_margin_end(30)
            settings_grid.set_margin_top(10)
            settings_grid.set_margin_bottom(10)
            vbox.append(settings_grid)

            self.name_label = Gtk.Label(label="Your Name:")
            settings_grid.attach(self.name_label, 0, 0, 1, 1)

            default_name = os.getlogin() if hasattr(os, "getlogin") else "User"
            self.name_entry = Gtk.Entry()
            self.name_entry.set_text(default_name)
            self.name_entry.set_width_chars(20)
            settings_grid.attach(self.name_entry, 1, 0, 1, 1)
            custom_name = self.name_entry.get_text().strip()

            self.toggle_btn = Gtk.Button(label="Start Server")
            self.toggle_btn.connect("clicked", self.toggle_manager)
            self.toggle_btn.add_css_class("suggested-action")
            settings_grid.attach(self.toggle_btn, 2, 0, 1, 1)

            # Button frame
            btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            btn_box.set_halign(Gtk.Align.CENTER)
            vbox.append(btn_box)

            self.connect_btn = Gtk.Button(label="Connect to Peer")
            self.connect_btn.connect("clicked", self.connect_selected)
            self.connect_btn.set_sensitive(False)
            btn_box.append(self.connect_btn)

            self.send_btn = Gtk.Button(label="Send Message")
            self.send_btn.connect("clicked", self.send_selected)
            self.send_btn.set_sensitive(False)
            btn_box.append(self.send_btn)

            self.file_btn = Gtk.Button(label="Send File")
            self.file_btn.connect("clicked", self.send_file_selected)
            self.file_btn.set_sensitive(False)
            btn_box.append(self.file_btn)

            self.broadcaster = ZeroconfBroadcaster(
                base_name=custom_name,
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
                ui_progress_bar=ProgressBarWrapper(self.progress_bar),
                ui_progress_status=LabelWrapper(self.progress_status),
            )

            threading.Thread(target=self._start_http_server, daemon=True).start()
            
        window.present()

    def _start_http_server(self):
        uvicorn.run(self.api, host="0.0.0.0", port=self.HTTP_PORT, log_level="critical")

    def ui_log(self, text):
        GLib.idle_add(self._ui_log_idle, text)

    def _ui_log_idle(self, text):
        end_iter = self.log_buffer.get_end_iter()
        self.log_buffer.insert(end_iter, text + "\n")

    def ui_clear(self):
        GLib.idle_add(self._ui_clear_idle)

    def _ui_clear_idle(self):
        self.log_buffer.set_text("")
        
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
        if not self.selected_peer_name:
            return None
        return self.peers.get(self.selected_peer_name)

    def on_add(self, peer):
        GLib.idle_add(self._on_add_main, peer)

    def _on_add_main(self, peer):
        self.peers[peer.name] = peer
        row = Gtk.ListBoxRow()
        label = Gtk.Label(label=f"{peer.name} @ {peer.address}:{peer.port}", xalign=0)
        label.set_margin_start(10)
        label.set_margin_end(10)
        label.set_margin_top(5)
        label.set_margin_bottom(5)
        row.set_child(label)
        row.peer_name = peer.name
        self.peer_list.append(row)
        self.ui_log(f"➕ {peer.name} joined")

    def on_update(self, peer):
        GLib.idle_add(self.ui_log, f"🔄 {peer.name} updated")

    def on_remove(self, peer):
        GLib.idle_add(self._on_remove_main, peer)

    def _on_remove_main(self, peer):
        self.peers.pop(peer.name, None)
        
        # Determine if we need to clear selection
        if self.selected_peer_name == peer.name:
            self.selected_peer_name = ""
            self.on_peer_change(self.peer_list, None)
            
        # Find the row to remove
        row_to_remove = None
        for i in range(1000): # max search safeguard
            row = self.peer_list.get_row_at_index(i)
            if not row: break
            if getattr(row, 'peer_name', None) == peer.name:
                row_to_remove = row
                break
                
        if row_to_remove:
            self.peer_list.remove(row_to_remove)
            
        self.ui_log(f"➖ {peer.name} left")

    def connect_selected(self, btn):
        peer = self.get_selected_peer()
        if peer: self.dispatch(getattr(self.sender, "connect_peer", lambda x: print('connect_peer not implemented in ShareSender')), peer)

    def send_selected(self, btn):
        peer = self.get_selected_peer()
        text = self.msg_entry.get_text().strip()
        if peer and text:
            self.msg_entry.set_text("")
            self.dispatch(getattr(self.sender, "send_message", lambda x, y: print('send_message not implemented in ShareSender')), peer, text)

    def send_file_selected(self, btn):
        peer = self.get_selected_peer()
        if not peer: return
        
        dialog = Gtk.FileDialog()
        dialog.set_title("Select a file to send")
        
        window = getattr(self.props, 'active_window', None)
        if not window: return
        
        dialog.open(window, None, self._on_file_selected_cb, peer)

    def _on_file_selected_cb(self, dialog, result, peer):
        try:
            file = dialog.open_finish(result)
            if file:
                file_path = file.get_path()
                self.dispatch(self.sender.send_file, peer, file_path)
        except GLib.Error:
            pass # user cancelled

    def on_peer_change(self, listbox, row):
        if row:
            self.selected_peer_name = getattr(row, 'peer_name', "")
        else:
            self.selected_peer_name = ""
            
        can_interact = bool(self.selected_peer_name)
        self.connect_btn.set_sensitive(can_interact)
        self.send_btn.set_sensitive(can_interact)
        self.file_btn.set_sensitive(can_interact)

    def toggle_manager(self, btn):
        if self.manager._running:
            self.manager.stop()
            self.ui_log("🛑 Zeroconf stopped")
            self.toggle_btn.set_label("Start Server")
            self.toggle_btn.remove_css_class("destructive-action")
            self.toggle_btn.add_css_class("suggested-action")
            self.name_entry.set_sensitive(True)
        else:
            custom_name = self.name_entry.get_text().strip()
            if not custom_name:
                self._show_error("Please enter a valid name before starting.")
                return

            self.ui_clear()
            self.broadcaster.base_name = custom_name
            self.name_entry.set_sensitive(False)

            self.manager.start()
            self.ui_log(f"▶ Zeroconf started as '{custom_name}'")
            self.toggle_btn.set_label("Stop Server")
            self.toggle_btn.remove_css_class("suggested-action")
            self.toggle_btn.add_css_class("destructive-action")

    def _show_error(self, message):
        window = getattr(self.props, 'active_window', None)
        dialog = Gtk.AlertDialog(message=message)
        dialog.show(window)

    def on_close(self, window):
        self.net_running = False
        if hasattr(self, 'manager'):
            self.manager.stop()
        return False # propagate

if __name__ == "__main__":
    app = ZenSyncApp()
    exit_status = app.run(sys.argv)
    sys.exit(exit_status)

