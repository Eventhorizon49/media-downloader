from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse

from app import app as legacy_app
from vocal_extractor import router as vocal_router

ROOT = Path(__file__).resolve().parent

app = FastAPI(title="Draupnir", version="1.5.0-test")

# Preserve every existing downloader route except the legacy homepage.
for route in legacy_app.router.routes:
    if getattr(route, "path", None) != "/":
        app.router.routes.append(route)

app.include_router(vocal_router)


@app.get("/", response_class=HTMLResponse)
def home():
    return (ROOT / "index-vocals.html").read_text(encoding="utf-8")


@app.get("/draupnir-logo.png")
def draupnir_png():
    return FileResponse(
        ROOT / "draupnir-logo.png",
        media_type="image/png",
        headers={"Cache-Control": "public,max-age=3600"},
    )
