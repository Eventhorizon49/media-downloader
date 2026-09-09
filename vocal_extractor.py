import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

router = APIRouter(prefix="/api/vocals", tags=["vocals"])

ALLOWED_EXTS = {".wav", ".mp3", ".m4a", ".flac", ".aac", ".ogg"}
MAX_UPLOAD_BYTES = 120 * 1024 * 1024
MODEL_DIR = Path(os.getenv("AUDIO_SEPARATOR_MODEL_DIR", "/tmp/draupnir-models"))
MODEL_DIR.mkdir(parents=True, exist_ok=True)

# Stage 1 favors natural, full-bodied vocals. Stage 2 removes backing/chorus vocals.
VOCAL_ENSEMBLE = os.getenv("VOCAL_ENSEMBLE", "vocal_balanced")
LEAD_MODEL = os.getenv(
    "LEAD_VOCAL_MODEL",
    "mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt",
)


def _run(cmd: list[str], timeout: int = 1800) -> None:
    env = os.environ.copy()
    env.setdefault("OMP_NUM_THREADS", "2")
    env.setdefault("MKL_NUM_THREADS", "2")
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=timeout,
        env=env,
    )
    if result.returncode != 0:
        tail = result.stdout[-3500:] if result.stdout else "Unknown separator error"
        raise RuntimeError(tail)


def _largest_audio(folder: Path, include: tuple[str, ...] = ()) -> Path:
    files = [
        p
        for p in folder.rglob("*")
        if p.is_file() and p.suffix.lower() in ALLOWED_EXTS
    ]
    if include:
        filtered = [
            p for p in files if any(token.lower() in p.name.lower() for token in include)
        ]
        if filtered:
            files = filtered
    if not files:
        raise RuntimeError("Separator did not produce an audio file.")
    return max(files, key=lambda p: p.stat().st_size)


def extract_lead_vocal(source: Path, workdir: Path) -> Path:
    stage1 = workdir / "stage1"
    stage2 = workdir / "stage2"
    stage1.mkdir()
    stage2.mkdir()

    # Natural vocal extraction. Using an ensemble avoids the brittle/metallic sound
    # produced by overly aggressive single-model filtering.
    _run(
        [
            "audio-separator",
            str(source),
            "--ensemble_preset",
            VOCAL_ENSEMBLE,
            "--output_dir",
            str(stage1),
            "--model_file_dir",
            str(MODEL_DIR),
            "--output_format",
            "WAV",
        ]
    )
    vocal_stem = _largest_audio(stage1, ("vocal",))

    # Karaoke/lead-vocal pass: the instrumental-side result contains backing vocals;
    # the lead-vocal side is retained for the user.
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
        ]
    )

    lead = _largest_audio(stage2, ("lead", "vocal"))
    final = workdir / "lead-vocals.wav"
    shutil.copy2(lead, final)
    return final


@router.post("/extract")
async def extract_vocals(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    filename = file.filename or "upload.wav"
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTS:
        raise HTTPException(
            400,
            "Upload WAV, MP3, M4A, FLAC, AAC, or OGG audio.",
        )

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
            msg = str(exc).lower()
            if "killed" in msg or "memory" in msg or "out of memory" in msg:
                raise HTTPException(
                    503,
                    "This server does not currently have enough memory for this song.",
                )
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
    except Exception:
        shutil.rmtree(workdir, ignore_errors=True)
        raise HTTPException(500, "Could not process this audio file.")
