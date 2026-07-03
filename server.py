import io
import os
from pathlib import Path
from typing import Any

import numpy as np
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastrtc import ReplyOnPause, Stream, get_current_context
from fastrtc.pause_detection import get_silero_model
from fastrtc.utils import audio_to_bytes
from groq import Groq
from gtts import gTTS
from openai import OpenAI
from pydub import AudioSegment

load_dotenv()

# --- Clients ---
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
nim_client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=os.getenv("NVIDIA_API_KEY"),
)

# Per-session chat history keyed by webrtc_id
sessions: dict[str, list[dict[str, str]]] = {}

SYSTEM_PROMPT = os.getenv(
    "SYSTEM_PROMPT",
    "You are a helpful, concise voice assistant. Keep responses short and natural for speech.",
)


def gtts_tts(text: str):
    """Google TTS — free, no API key, works server-side."""
    buf = io.BytesIO()
    gTTS(text=text, lang="en").write_to_fp(buf)
    buf.seek(0)
    seg = AudioSegment.from_file(buf, format="mp3").set_channels(1).set_frame_rate(24000)
    audio_array = np.frombuffer(seg.raw_data, dtype=np.int16).reshape(1, -1)
    yield (24000, audio_array)


def get_or_create_session(webrtc_id: str) -> list[dict[str, str]]:
    if webrtc_id not in sessions:
        sessions[webrtc_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
    return sessions[webrtc_id]


def respond(audio: tuple[int, np.ndarray]):
    ctx = get_current_context()
    history = get_or_create_session(ctx.webrtc_id)

    # 1. STT — Groq Whisper
    transcript = groq_client.audio.transcriptions.create(
        file=("audio.mp3", audio_to_bytes(audio)),
        model="whisper-large-v3-turbo",
    ).text.strip()

    if not transcript:
        return

    history.append({"role": "user", "content": transcript})

    # 2. LLM — NVIDIA NIM Llama-3
    reply = (
        nim_client.chat.completions.create(
            model=os.getenv("NIM_MODEL", "meta/llama-3.1-8b-instruct"),
            messages=history,
            max_tokens=int(os.getenv("MAX_TOKENS", "200")),
            temperature=0.7,
        )
        .choices[0]
        .message.content
    )

    history.append({"role": "assistant", "content": reply})

    # 3. TTS — Google TTS (free, no key needed)
    yield from gtts_tts(reply)


# Pre-warm Silero VAD before accepting connections
get_silero_model()

# --- FastAPI app ---
app = FastAPI(title="Realtime Voice API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

stream = Stream(
    handler=ReplyOnPause(respond),
    modality="audio",
    mode="send-receive",
)
stream.mount(app)


@app.get("/")
def index():
    return HTMLResponse((Path(__file__).parent / "test.html").read_text(encoding="utf-8"))


@app.delete("/session/{webrtc_id}")
def clear_session(webrtc_id: str):
    sessions.pop(webrtc_id, None)
    return {"status": "cleared"}


@app.get("/session/{webrtc_id}")
def get_session(webrtc_id: str) -> list[dict[str, Any]]:
    return sessions.get(webrtc_id, [])[1:]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
