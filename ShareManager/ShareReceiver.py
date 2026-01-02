from fastapi import FastAPI
from pydantic import BaseModel

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
