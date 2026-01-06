import os
from fastapi import FastAPI, File, UploadFile
from pydantic import BaseModel
from datetime import datetime


class Message(BaseModel):
    sender: str
    message: str


class Chunk(BaseModel):
    index: int
    total: int
    data: bytes


class ShareReceiver:
    def __init__(self, app: FastAPI):
        self.app = app
        self.download_dir = "received_files"
        os.makedirs(self.download_dir, exist_ok=True)
        self._register_routes()

    def _register_routes(self):
        @self.app.get("/ping")
        async def ping():
            return {"status": "alive"}

        @self.app.post("/message")
        async def receive_message(msg: Message):
            print(f"[{msg.sender}] {msg.message}")
            return {"ok": True}

        @self.app.post("/chunk")
        async def receive_chunk(chunk: Chunk):
            print(f"Chunk {chunk.index + 1}/{chunk.total}")
            return {"ok": True}

        @self.app.post("/upload")
        async def upload_file(file: UploadFile = File(...), sender: str = ""):
            try:
                # Create a unique filename to avoid conflicts
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{timestamp}_{file.filename}"
                file_path = os.path.join(self.download_dir, filename)

                # Save the uploaded file in chunks to handle large files
                with open(file_path, "wb") as f:
                    chunk_size = 8192  # 8KB chunks
                    while True:
                        chunk = await file.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)

                print(f"[{sender}] File received: {file.filename} -> {filename}")
                return {"ok": True, "filename": filename}
            except Exception as e:
                print(f"Error receiving file: {str(e)}")
                return {"ok": False, "error": str(e)}
