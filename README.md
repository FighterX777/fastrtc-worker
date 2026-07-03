# Realtime Voice API

A realtime voice conversation API built on [FastRTC](https://fastrtc.org/). Streams audio over WebRTC and pipes it through:

```
Mic → WebRTC → Silero VAD → Groq Whisper STT → NVIDIA NIM Llama-3 → Google TTS → Speaker
```

---

## Stack

| Layer | Service | Notes |
|---|---|---|
| Transport | WebRTC (FastRTC) | Low-latency, browser-native |
| VAD | Silero ONNX | Local, lightweight pause detection |
| STT | Groq `whisper-large-v3-turbo` | Cloud transcription |
| LLM | NVIDIA NIM `meta/llama-3.1-8b-instruct` | OpenAI-compatible cloud API |
| TTS | Google TTS (gTTS) | Free, no API key, cloud |

---

## Setup (Local)

### 1. Install dependencies

```powershell
pip install -r requirements.txt
pip install "gradio>=5.0,<6.0" "huggingface_hub>=0.24.0" "typer>=0.12,<1.0"
```

> The extra pip install line resolves version conflicts between gradio, huggingface_hub, and typer.

### 2. Configure environment

Fill in your keys in `.env`:

```env
GROQ_API_KEY=your_groq_api_key
NVIDIA_API_KEY=your_nvidia_nim_api_key
```

Get your keys:
- Groq: https://console.groq.com/keys
- NVIDIA NIM: https://integrate.api.nvidia.com

### 3. Run

```powershell
python server.py
```

Server starts at `http://localhost:8000`

On first run, the Silero VAD model (~2MB) downloads from HuggingFace and warms up. Subsequent runs load from cache instantly.

---

## Setup (Docker)

### Build

```bash
docker build -t voice-api .
```

### Run

```bash
docker run -p 8000:8000 --env-file .env voice-api
```

The Silero VAD model is downloaded at **build time**, so the container starts instantly with no cold-start delay.

---

## Deployment (GitHub → Cloud)

All routes are served on a **single port (8000)**. Your hosting provider only needs to expose port 8000.

| URL | What you get |
|---|---|
| `http://your-host:8000/` | Voice test page |
| `http://your-host:8000/webrtc/offer` | WebRTC signaling |
| `http://your-host:8000/session/{id}` | Chat history API |
| `http://your-host:8000/docs` | FastAPI auto docs |

Set these environment variables in your hosting dashboard (never commit `.env`):

```
GROQ_API_KEY
NVIDIA_API_KEY
```

Recommended platforms (all support Docker + env vars):
- **Railway** — https://railway.app
- **Render** — https://render.com
- **Fly.io** — https://fly.io

---

## Test Page

Open **http://localhost:8000** in your browser.

- Click **START** — grants mic access and connects WebRTC
- Speak — status shows `listening` → `processing` → `speaking`
- AI voice plays back through your speakers
- Click **STOP** to disconnect

---

## Configuration

| Variable | Default | Description |
|---|---|---|
| `GROQ_API_KEY` | — | Required. Groq API key |
| `NVIDIA_API_KEY` | — | Required. NVIDIA NIM API key |
| `NIM_MODEL` | `meta/llama-3.1-8b-instruct` | Any NVIDIA NIM chat model |
| `MAX_TOKENS` | `200` | Max tokens in LLM response |
| `SYSTEM_PROMPT` | `You are a helpful...` | Controls the assistant's persona |
| `PORT` | `8000` | Server port |

### Changing the LLM model

Any model on NVIDIA NIM works:

```env
NIM_MODEL=meta/llama-3.3-70b-instruct
NIM_MODEL=mistralai/mistral-large-2-instruct
```

---

## Project Structure

```
api/
├── server.py        # Main FastAPI + FastRTC server
├── test.html        # Browser voice test page
├── fastrtc/         # Local copy of FastRTC package
├── Dockerfile
├── .dockerignore
├── requirements.txt
├── .env             # Not committed — add to .gitignore
└── README.md
```

---

## How the Pipeline Works

1. Browser connects via WebRTC and streams mic audio to the server
2. **Silero VAD** buffers audio chunks and detects when the user stops speaking
3. On pause → **Groq Whisper** transcribes the buffered audio to text
4. Transcript is added to the session's chat history and sent to **NVIDIA NIM Llama-3**
5. LLM reply is passed to **Google TTS**, which returns an MP3
6. MP3 is decoded to PCM and streamed back to the browser over WebRTC

Each session has isolated chat history keyed by `webrtc_id`, persisting for the lifetime of the server process.

---

## Known Dependency Conflicts

This project uses a local copy of FastRTC which has strict version requirements. If you hit import errors on startup, run:

```powershell
pip install "gradio>=5.0,<6.0" "huggingface_hub>=0.24.0" "typer>=0.12,<1.0" "aioice>=0.9.0" "numba>=0.58.0"
```
