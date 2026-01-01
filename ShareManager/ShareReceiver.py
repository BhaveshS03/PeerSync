from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="ZenSyncServer")

class chunk(BaseModel):
    pass

class ShareReceiver:
    def __init__():
        pass
