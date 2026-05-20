from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from Agent import query, start
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from llama_index.core.memory import Memory
from pydantic import BaseModel

STATIC_DIR = Path(__file__).resolve().parent / "static"

#Passer a docker
class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    response: str
    session_id: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.agent = start()
    app.state.sessions = {}

    yield

    # Ajouter potentiellement un save de sessions au shutdown.


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def get_session_memory(app: FastAPI, session_id: str):
    if session_id not in app.state.sessions:
        app.state.sessions[session_id] = Memory.from_defaults(
            session_id=session_id,
            token_limit=100000,
        )
    return app.state.sessions[session_id]


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/generate", response_model=ChatResponse)
async def generate(request: ChatRequest):
    session_id = request.session_id or str(uuid4())
    memory = get_session_memory(app, session_id)
    response = await query(app.state.agent, memory, request.message)

    return ChatResponse(response=str(response), session_id=session_id)
