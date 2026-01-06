import os
from fastapi import FastAPI, Request
from datetime import datetime

class ShareReceiver:
    def __init__(self, app: FastAPI, ui_progress_bar=None, ui_progress_status=None):
        self.app = app
        self.download_dir = "received_files"
        self.ui_progress_bar = ui_progress_bar
        self.ui_progress_status = ui_progress_status
        os.makedirs(self.download_dir, exist_ok=True)
        self._register_routes()

    def _update_ui(self, received, total, filename):
        """Update the receiver's UI elements"""
        if total <= 0: return
        
        progress = received / total
        if self.ui_progress_bar:
            try: self.ui_progress_bar.set(progress)
            except: pass
            
        if self.ui_progress_status:
            try:
                percent = progress * 100
                status = f"Receiving {filename}: {percent:.1f}%"
                self.ui_progress_status.configure(text=status)
            except: pass

    def _register_routes(self):
        @self.app.get("/ping")
        async def ping():
            return {"status": "alive"}

        @self.app.post("/upload")
        async def upload_file(request: Request):
            # 1. Get total size from headers
            try:
                total_size = int(request.headers.get("Content-Length", 0))
            except:
                total_size = 0

            # 2. Parse form headers manually
            form = await request.form()
            file_field = form["file"]
            sender = form.get("sender", "Unknown")
            filename = file_field.filename
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_name = f"{timestamp}_{filename}"
            
            # Define final path and temporary .part path
            final_path = os.path.join(self.download_dir, unique_name)
            part_path = final_path + ".part"

            received_size = 0
            chunk_size = 1024 * 1024  # 1MB
            
            try:
                # Write to the .part file first
                with open(part_path, "wb") as f:
                    while True:
                        chunk = await file_field.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        received_size += len(chunk)
                        
                        # Update progress bar
                        self._update_ui(received_size, total_size, filename)

                # 3. Transfer complete: Rename .part to final filename
                os.rename(part_path, final_path)
                
                print(f"✅ Received {filename} from {sender}")
                self._reset_ui()
                return {"ok": True, "size": received_size}

            except Exception as e:
                self._reset_ui()
                # Cleanup: remove the partial file if it exists
                if os.path.exists(part_path):
                    try:
                        os.remove(part_path)
                    except OSError:
                        pass
                        
                print(f"❌ Error receiving file: {e}")
                return {"ok": False, "error": str(e)}

    def _reset_ui(self):
        if self.ui_progress_bar:
            try: self.ui_progress_bar.set(0)
            except: pass
        if self.ui_progress_status:
            try: self.ui_progress_status.configure(text="")
            except: pass