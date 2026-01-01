import customtkinter
from ZeroconfManager import (
    ZeroconfManager,
    ZeroconfBroadcaster,
    ZeroconfDiscovery,
)

customtkinter.set_appearance_mode("System")
customtkinter.set_default_color_theme("blue")

app = customtkinter.CTk()
app.geometry("600x480")
app.title("Zeroconf Manager Demo")

services_box = customtkinter.CTkTextbox(app, width=520, height=260)
services_box.pack(pady=20)

# ----------------------------
# UI-safe helpers
# ----------------------------
def ui_log(text):
    app.after(0, lambda: services_box.insert("end", text + "\n"))

def ui_clear():
    app.after(0, lambda: services_box.delete("1.0", "end"))

# ----------------------------
# Zeroconf callbacks
# ----------------------------
def on_add(peer):
    ui_log(f"➕ {peer.name} @ {peer.address}:{peer.port}")

def on_update(peer):
    ui_log(f"🔄 {peer.name}")

def on_remove(peer):
    ui_log(f"➖ {peer.name}")

# ----------------------------
# Zeroconf setup
# ----------------------------
broadcaster = ZeroconfBroadcaster(base_name="MyService")
discovery = ZeroconfDiscovery(own_id=broadcaster.instance_id)

manager = ZeroconfManager(
    broadcaster=broadcaster,
    discovery=discovery,
    on_add=on_add,
    on_update=on_update,
    on_remove=on_remove,
)

# ----------------------------
# Button actions
# ----------------------------
def toggle_manager():
    if manager._running:
        manager.stop()
        ui_log("🛑 Manager stopped")
        toggle_btn.configure(text="Start Zeroconf")
    else:
        ui_clear()
        manager.start()
        ui_log("▶ Zeroconf started")
        toggle_btn.configure(text="Stop Zeroconf")


# ----------------------------
# UI controls
# ----------------------------
toggle_btn = customtkinter.CTkButton(
    app,
    text="Start Zeroconf",
    command=toggle_manager,
)
toggle_btn.pack(pady=10)


# ----------------------------
# Clean shutdown
# ----------------------------
def on_close():
    manager.stop()
    app.destroy()

app.protocol("WM_DELETE_WINDOW", on_close)
app.mainloop()
