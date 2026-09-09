import math
import os
import shutil
import struct
import subprocess
import tempfile
import wave
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

router = APIRouter(prefix="/api/vocals", tags=["vocals"])

ALLOWED_EXTS = {".wav", ".mp3", ".m4a", ".flac", ".aac", ".ogg"}
MAX_UPLOAD_BYTES = 120 * 1024 * 1024
MODEL_DIR = Path(os.getenv("AUDIO_SEPARATOR_MODEL_DIR", "/tmp/draupnir-models"))
MODEL_DIR.mkdir(parents=True, exist_ok=True)

# These two models are intentionally chosen for Render Free's 512 MB memory ceiling.
# Stage 1 is a small ONNX vocal/instrumental model. Stage 2 is a VR backing-vocal
# extractor that separates backing vocals from the vocal stem and lets us keep lead.
VOCAL_MODEL = os.getenv("VOCAL_MODEL", "UVR-MDX-NET-Inst_HQ_5.onnx")
LEAD_MODEL = os.getenv("LEAD_VOCAL_MODEL", "UVR-BVE-4B_SN-44100-2.pth")


def _run(cmd: list[str], timeout: int = 1800) -> str:
    env = os.environ.copy()
    env.setdefault("OMP_NUM_THREADS", "1")
    env.setdefault("MKL_NUM_THREADS", "1")
    env.setdefault("OPENBLAS_NUM_THREADS", "1")
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=timeout,
        env=env,
    )
    output = result.stdout or ""
    if result.returncode != 0:
        if result.returncode in (-9, 137):
            raise RuntimeError("separator process was killed, most likely by the memory limit")
        tail = output[-5000:] if output else f"separator exited with code {result.returncode}"
        raise RuntimeError(tail)
    return output


def _audio_files(folder: Path) -> list[Path]:
    return [
        p
        for p in folder.rglob("*")
        if p.is_file() and p.suffix.lower() in ALLOWED_EXTS and p.stat().st_size > 0
    ]


def _find_audio(folder: Path, preferred: tuple[str, ...]) -> Path:
    files = _audio_files(folder)
    if not files:
        raise RuntimeError("separator did not produce an audio file")

    for token in preferred:
        matches = [p for p in files if token.lower() in p.name.lower()]
        if matches:
            return max(matches, key=lambda p: p.stat().st_size)

    return max(files, key=lambda p: p.stat().st_size)


def extract_lead_vocal(source: Path, workdir: Path) -> Path:
    stage1 = workdir / "stage1"
    stage2 = workdir / "stage2"
    stage1.mkdir(parents=True, exist_ok=True)
    stage2.mkdir(parents=True, exist_ok=True)

    # Stage 1: music removal. Small ONNX model + conservative settings for 512 MB RAM.
    _run(
        [
            "audio-separator",
            str(source),
            "--model_filename",
            VOCAL_MODEL,
            "--single_stem",
            "Vocals",
            "--output_dir",
            str(stage1),
            "--model_file_dir",
            str(MODEL_DIR),
            "--output_format",
            "WAV",
            "--mdx_batch_size",
            "1",
            "--mdx_segment_size",
            "128",
        ]
    )
    vocal_stem = _find_audio(stage1, ("vocals", "vocal"))

    # Stage 2: backing-vocal extraction. The BVE model labels the pair as lead/backing
    # internally; keeping the lead-side output preserves the natural main singer.
    _run(
        [
            "audio-separator",
            str(vocal_stem),
            "--model_filename",
            LEAD_MODEL,
            "--output_dir",
            str(stage2),
            "--model_file_dir",
            str(MODEL_DIR),
            "--output_format",
            "WAV",
            "--vr_batch_size",
            "1",
            "--vr_window_size",
            "320",
            "--vr_enable_tta",
        ]
    )

    # Current audio-separator versions emit BVE outputs with lead/backing naming.
    # Prefer lead explicitly; fallback is intentionally deterministic for compatibility.
    lead = _find_audio(stage2, ("lead_only", "lead vocal", "lead", "no backing"))
    final = workdir / "lead-vocals.wav"
    shutil.copy2(lead, final)
    return final


def _make_selftest_wav(path: Path, seconds: float = 2.0, sr: int = 44100) -> None:
    # Synthetic stereo audio for end-to-end pipeline verification. This validates model
    # loading, inference, file handling and WAV export without relying on user media.
    frames = int(seconds * sr)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        for i in range(frames):
            t = i / sr
            # Two tones with a gentle amplitude envelope so the signal is non-trivial.
            env = min(1.0, i / (0.08 * sr), (frames - i) / (0.08 * sr))
            sample = 0.28 * env * (math.sin(2 * math.pi * 220 * t) + 0.55 * math.sin(2 * math.pi * 440 * t))
            v = max(-32767, min(32767, int(sample * 32767)))
            wf.writeframesraw(struct.pack("<hh", v, v))


@router.get("/selftest")
def vocal_selftest():
    workdir = Path(tempfile.mkdtemp(prefix="draupnir-vocal-selftest-"))
    try:
        source = workdir / "selftest.wav"
        _make_selftest_wav(source)
        result = extract_lead_vocal(source, workdir)
        if not result.exists() or result.stat().st_size < 1000:
            raise RuntimeError("pipeline returned an empty output")
        return JSONResponse(
            {
                "ok": True,
                "output_bytes": result.stat().st_size,
                "vocal_model": VOCAL_MODEL,
                "lead_model": LEAD_MODEL,
            }
        )
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)[-4000:]}, status_code=500)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


@router.post("/extract")
async def extract_vocals(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    filename = file.filename or "upload.wav"
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTS:
        raise HTTPException(400, "Upload WAV, MP3, M4A, FLAC, AAC, or OGG audio.")

    workdir = Path(tempfile.mkdtemp(prefix="draupnir-vocals-"))
    source = workdir / f"source{suffix}"
    total = 0

    try:
        with source.open("wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_UPLOAD_BYTES:
                    raise HTTPException(413, "Audio file is too large. Maximum is 120 MB.")
                out.write(chunk)

        if total == 0:
            raise HTTPException(400, "The uploaded audio file is empty.")

        try:
            result = extract_lead_vocal(source, workdir)
        except subprocess.TimeoutExpired:
            raise HTTPException(504, "Vocal extraction took too long on this server.")
        except Exception as exc:
            msg = str(exc)
            low = msg.lower()
            print(f"VOCAL_EXTRACTION_ERROR: {msg[-5000:]}", flush=True)
            if "killed" in low or "memory" in low or "out of memory" in low:
                raise HTTPException(503, "This server does not have enough memory for vocal extraction.")
            raise HTTPException(500, "Could not isolate the lead vocal from this track.")

        background_tasks.add_task(shutil.rmtree, workdir, True)
        stem = Path(filename).stem[:80] or "song"
        return FileResponse(
            result,
            filename=f"{stem}_lead-vocals.wav",
            media_type="audio/wav",
        )
    except HTTPException:
        shutil.rmtree(workdir, ignore_errors=True)
        raise
    except Exception as exc:
        print(f"VOCAL_UPLOAD_ERROR: {exc}", flush=True)
        shutil.rmtree(workdir, ignore_errors=True)
        raise HTTPException(500, "Could not process this audio file.")
