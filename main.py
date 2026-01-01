import customtkinter
from zeroconf import Zeroconf, ServiceInfo
import socket, time


customtkinter.set_appearance_mode("System")
customtkinter.set_default_color_theme("blue")
app = customtkinter.CTk()

app.geometry("600x480")

def broadcast(name):
    import psutil

    for iface, addrs in psutil.net_if_addrs().items():
        for a in addrs:
            if a.family == socket.AF_INET and a.address.startswith("192.168."):
                ip = a.address
    info = ServiceInfo(
        "_http._tcp.local.",
        f"{name}._http._tcp.local.",
        addresses=[ip],
        port=9999,
        properties={"msg": "hello"},
    )

    z = Zeroconf()
    z.register_service(info)
    try:
        print("Broadcasting service...")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        z.unregister_service(info)
        z.close()



def button_function():
    print("button pressed")


button = customtkinter.CTkButton(master=app, text="CTkButton", command=button_function)
button.place(relx=0.5, rely=0.5, anchor=customtkinter.CENTER)


app.mainloop()