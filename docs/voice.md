# Voice input (Phase 6)

Voice is **only an input modality**. The browser records audio, Cura transcribes it, and the **transcript is sent through the existing `/api/v1/chat` pipeline** (language detection, intent, QueryPlan, retrieval, safety, LLM, follow-ups). There is no separate health-reasoning path for voice.

Text-to-speech and audio history are **not** implemented.

## Supported spoken languages

English, Hindi, Marathi, Punjabi, Gujarati, Bengali, plus Hinglish/code-mixed speech. The Phase 5 language selector is passed as an STT hint when it is not Auto.

## Environment variables

Set these in `backend/.env` (never in frontend code):

| Variable | Default | Meaning |
|---|---|---|
| `VOICE_ENABLED` | `false` | Master switch. If false, transcribe returns a typed-chat fallback error. |
| `STT_PROVIDER` | `none` | `none`, `local`, or `openai_compatible` |
| `STT_BASE_URL` | `http://127.0.0.1:8001/v1` | OpenAI-compatible base (must expose `POST /audio/transcriptions`) |
| `STT_MODEL` | `whisper-1` | Model name the STT server expects |
| `STT_API_KEY` | empty | Optional bearer token. Not required for many local servers. |
| `STT_TIMEOUT_SECONDS` | `60` | HTTP timeout |
| `STT_MAX_AUDIO_BYTES` | `10000000` | Max upload size (~10 MB) |

No STT API keys are sent to the browser.

## Local setup (optional Whisper server)

Typed Cura works with `VOICE_ENABLED=false`. To enable voice:

1. Run any OpenAI-compatible Whisper server on port 8001 (examples: [speaches](https://github.com/speaches-ai/speaches), whisper.cpp HTTP, Groq Whisper).
2. Set:

```
VOICE_ENABLED=true
STT_PROVIDER=local
STT_BASE_URL=http://127.0.0.1:8001/v1
STT_MODEL=whisper-1
```

3. Restart the Cura backend.
4. Allow microphone access in the browser when prompted.

Remote example:

```
VOICE_ENABLED=true
STT_PROVIDER=openai_compatible
STT_BASE_URL=https://api.openai.com/v1
STT_API_KEY=...
STT_MODEL=whisper-1
```

## Audio

Accepted types include WebM, WAV, MP3, M4A, OGG. Recordings are written to a **temporary file**, transcribed, then **deleted**. Audio is not stored in Cura SQLite and is never sent to SuperShyft.

## Fallback

If STT is off, misconfigured, times out, or returns empty text, Cura shows a clear error. **Typing still works.**

## Microphone

If the browser blocks the mic:

"Microphone access is blocked. You can allow microphone access in your browser settings or continue typing."
