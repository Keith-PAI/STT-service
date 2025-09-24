from fastapi import FastAPI, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from faster_whisper import WhisperModel
import tempfile, subprocess, os, time

# ---- Config ----
MODEL_NAME = os.getenv("FW_MODEL", "base")
COMPUTE_TYPE = os.getenv("FW_COMPUTE", "int8")  # int8 / int8_float16 / float16 / float32
CORS_ORIGINS = os.getenv("FW_CORS", "*").split(",") if os.getenv("FW_CORS") else ["*"]

# ---- App ----
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Lazy singleton model
_model = None
def get_model():
    global _model
    if _model is None:
        _model = WhisperModel(MODEL_NAME, compute_type=COMPUTE_TYPE)
    return _model

@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL_NAME, "compute": COMPUTE_TYPE}

@app.post("/transcribe")
async def transcribe(
    audio: UploadFile,
    language: str | None = Form(default=None),
    task: str | None = Form(default=None),  # "transcribe" (default) or "translate"
):
    started = time.time()
    suffix = os.path.splitext(audio.filename or "")[1] or ".bin"
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
            raw = await audio.read()
            f.write(raw)
            src = f.name
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read upload: {e}")

    # Convert to 16k mono wav for best results
    wav = src + ".wav"
    try:
        subprocess.run(
            ["ffmpeg", "-nostdin", "-y", "-i", src, "-ar", "16000", "-ac", "1", wav],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as e:
        os.unlink(src)
        raise HTTPException(status_code=415, detail=f"ffmpeg failed: {e.stderr.decode('utf-8', 'ignore')[:400]}")

    try:
        model = get_model()
        segments, info = model.transcribe(
            wav,
            vad_filter=True,
            beam_size=5,
            temperature=0.2,
            language=language,
            task=task or "transcribe",
        )
        text = "".join(s.text for s in segments).strip()
        dur = time.time() - started
        return JSONResponse({"text": text, "language": info.language, "duration_sec": round(dur, 3)})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        try:
            os.unlink(src)
        except Exception:
            pass
        try:
            os.unlink(wav)
        except Exception:
            pass
