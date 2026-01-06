# PeerSync 🚀

**PeerSync** is a high-speed, local network peer-to-peer file sharing application. It combines a modern UI with a **FastAPI** backend to provide seamless transfers without the need for manual IP configuration.

<img width="420" height="400" alt="{1BBE1325-5403-4EC0-ADA0-E96D0D533EE9}" src="https://github.com/user-attachments/assets/c9cce8ac-6dae-4174-b1cf-3415fec4d31e" />


## ✨ Features
- **Auto-Discovery:** Automatically find peers on your local network.
- **Modern UI:** Clean, dark-themed interface built.
- **Real-time Monitoring:** Track transfer progress via threading and queues.

## 🛠 Tech Stack
- **Frontend:** [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter)
- **Backend API:** [FastAPI](https://fastapi.tiangolo.com/)
- **Peer Discovery:** [Zeroconf](https://github.com/python-zeroconf/python-zeroconf)
- **HTTP Client:** [Requests-toolbelt](https://github.com/requests/toolbelt)


## 🚧 Status: Work In Progress
Currently implementing:
- [x] Service broadcasting (Zeroconf)
- [x] UI Layout and design
- [x] Transfer progress bar integration
- [ ] Android Application
- [ ] Multi-peer selection logic
- [ ] Clipboard Sync


## ⚙️ Installation
1. Clone the repository:
   ```bash
   git clone [https://github.com/BhaveshS03/PeerSync.git](https://github.com/BhaveshS03/PeerSync.git)
   cd PeerSync
2. Install dependencies:
   ```bash
    pip install -r requirements.txt
3. Run the application:
   ```bash
    python main.py
