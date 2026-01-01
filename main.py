import customtkinter
from ZeroconfManager import ZeroconfBroadcaster, ZeroconfDiscovery
customtkinter.set_appearance_mode("System")
customtkinter.set_default_color_theme("blue")

app = customtkinter.CTk()
app.geometry("600x480")

broadcaster = ZeroconfBroadcaster("MyService")
services_box = customtkinter.CTkTextbox(app, width=500, height=200)
services_box.pack(pady=20)


def update_service(name, info):
    app.after(0, lambda: services_box.insert("end", f"{name}\n"))


discovery = ZeroconfDiscovery(on_update=update_service)

def toggle_broadcast():
    if broadcaster.running:
        broadcaster.stop()
        broadcast_btn.configure(text="Start Broadcast")
    else:
        broadcaster.start()
        broadcast_btn.configure(text="Stop Broadcast")



def toggle_discovery():
    if discovery.browser:
        discovery.stop()
        discover_btn.configure(text="Start Discovery")
    else:
        discovery.start()
        discover_btn.configure(text="Stop Discovery")


broadcast_btn = customtkinter.CTkButton(app, text="Start Broadcast", command=toggle_broadcast)
broadcast_btn.pack(pady=10)

discover_btn = customtkinter.CTkButton(app, text="Start Discovery", command=toggle_discovery)
discover_btn.pack(pady=10)

app.mainloop()
