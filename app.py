import base64, hashlib, hmac, json, os, re, shutil, tempfile, time
from pathlib import Path
from urllib.parse import urlparse

import imageio_ffmpeg
import yt_dlp
from curl_cffi import requests as curl_requests
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

app = FastAPI(title="Media Downloader", version="1.1.0")
SECRET = os.getenv("TOKEN_SECRET", "dev-change-me")
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
SUPPORTED = ("instagram.com", "x.com", "twitter.com", "reddit.com", "redd.it")
UA = "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/131.0 Mobile Safari/537.36"
ROOT = Path(__file__).resolve().parent

class AnalyzeRequest(BaseModel):
    url: str


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def valid_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        return parsed.scheme in ("http", "https") and any(host == d or host.endswith("." + d) for d in SUPPORTED)
    except Exception:
        return False


def platform_name(url: str) -> str:
    host = _host(url)
    if "instagram" in host: return "Instagram"
    if "reddit" in host or "redd.it" in host: return "Reddit"
    return "X / Twitter"


def sign(payload: dict) -> str:
    raw = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    sig = hmac.new(SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()
    return f"{raw}.{sig}"


def unsign(token: str) -> dict:
    try:
        raw, sig = token.rsplit(".", 1)
        expected = hmac.new(SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected): raise ValueError
        payload = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
        if payload.get("exp", 0) < time.time(): raise ValueError
        return payload
    except Exception:
        raise HTTPException(410, "Download session expired. Analyze the link again.")


def cookie_file():
    value = os.getenv("YTDLP_COOKIES_B64")
    if not value: return None
    try:
        p = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
        p.write(base64.b64decode(value)); p.close(); return p.name
    except Exception:
        return None


def base_opts(download=False, outtmpl=None, fmt=None):
    opts = {
        "quiet": True, "no_warnings": True, "noplaylist": True,
        "ffmpeg_location": FFMPEG, "socket_timeout": 30, "retries": 3,
        "fragment_retries": 3, "concurrent_fragment_downloads": 4,
        "http_headers": {"User-Agent": UA},
    }
    c = cookie_file()
    if c: opts["cookiefile"] = c
    if download:
        opts.update({"outtmpl": outtmpl, "format": fmt or "bestvideo*+bestaudio/best", "merge_output_format": "mp4", "restrictfilenames": True})
    else:
        opts["skip_download"] = True
    return opts, c


def extract_ytdlp(url: str):
    opts, c = base_opts()
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info and info.get("entries"):
                entries = [e for e in info["entries"] if e]
                if entries: info = entries[0]
            return info
    finally:
        if c:
            try: os.remove(c)
            except OSError: pass


def reddit_fallback(url: str):
    m = re.search(r"/comments/([^/?#]+)", url)
    if not m: raise RuntimeError("Reddit post ID not found")
    post_id = m.group(1)
    payload = None
    for endpoint in (
        f"https://www.reddit.com/comments/{post_id}.json?raw_json=1",
        f"https://old.reddit.com/comments/{post_id}.json?raw_json=1",
    ):
        try:
            r = curl_requests.get(endpoint, headers={"User-Agent": UA, "Accept": "application/json"}, impersonate="chrome", timeout=30)
            if r.status_code == 200:
                payload = r.json(); break
        except Exception:
            pass
    if not payload:
        raise RuntimeError("Reddit metadata unavailable")
    post = payload[0]["data"]["children"][0]["data"]
    media_post = post
    if not ((post.get("secure_media") or post.get("media") or {}).get("reddit_video")) and post.get("crosspost_parent_list"):
        media_post = post["crosspost_parent_list"][0]
    media = media_post.get("secure_media") or media_post.get("media") or {}
    rv = media.get("reddit_video") or (media_post.get("preview") or {}).get("reddit_video_preview") or {}
    source = rv.get("dash_url") or rv.get("hls_url") or rv.get("fallback_url")
    if not source:
        direct = media_post.get("url_overridden_by_dest") or media_post.get("url")
        if direct and ("v.redd.it" in direct or direct.lower().endswith((".mp4", ".gif", ".jpg", ".jpeg", ".png", ".webp"))): source = direct
    if not source: raise RuntimeError("No Reddit media URL found")
    try:
        info = extract_ytdlp(source)
    except Exception:
        info = {"formats": [], "ext": "mp4" if "v.redd.it" in source else Path(urlparse(source).path).suffix.lstrip(".") or None}
    info = info or {"formats": []}
    info["title"] = post.get("title") or info.get("title") or "Reddit media"
    thumb = post.get("thumbnail")
    if thumb and thumb.startswith("http"): info["thumbnail"] = thumb
    info["width"] = info.get("width") or rv.get("width")
    info["height"] = info.get("height") or rv.get("height")
    info["duration"] = info.get("duration") or rv.get("duration")
    info["bitrate"] = rv.get("bitrate_kbps")
    info["_download_url"] = source
    return info


def extract(url: str):
    if platform_name(url) == "Reddit":
        try: return extract_ytdlp(url)
        except Exception: return reddit_fallback(url)
    return extract_ytdlp(url)


def qualities(info: dict):
    heights = {}
    for f in info.get("formats") or []:
        h = f.get("height")
        if not h or f.get("vcodec") in (None, "none"): continue
        tbr = f.get("tbr") or 0
        if h not in heights or tbr > heights[h].get("tbr", 0): heights[h] = {"label": f"{h}p", "height": h, "tbr": tbr}
    if not heights and info.get("height"):
        h = int(info["height"]); heights[h] = {"label": f"{h}p", "height": h, "tbr": 0}
    return [heights[h] for h in sorted(heights, reverse=True)][:10]


def public_info(url: str, info: dict):
    formats = info.get("formats") or []
    media_type = "video" if any(f.get("vcodec") not in (None, "none") for f in formats) or info.get("duration") else "image"
    source = info.get("_download_url") or url
    token = sign({"url": url, "source": source, "exp": time.time() + 900})
    return {
        "platform": platform_name(url), "title": info.get("title") or info.get("description") or "Media",
        "thumbnail": info.get("thumbnail"), "duration": info.get("duration"), "width": info.get("width"),
        "height": info.get("height"), "fps": info.get("fps"), "bitrate": info.get("tbr") or info.get("bitrate"),
        "filesize": info.get("filesize") or info.get("filesize_approx"), "ext": info.get("ext"),
        "media_type": media_type, "qualities": qualities(info), "token": token,
    }


def friendly_extract_error(exc: Exception):
    msg = str(exc).lower()
    if any(x in msg for x in ("login", "cookie", "sign in", "authentication", "challenge")): return 401, "This post requires login/session."
    if any(x in msg for x in ("private", "not available", "unavailable", "deleted")): return 404, "This post is private, deleted, or unavailable."
    if "unsupported url" in msg: return 400, "Unsupported link."
    return 422, "Could not analyze this post right now."


@app.get("/health")
def health(): return {"ok": True, "yt_dlp": yt_dlp.version.__version__, "ffmpeg": bool(FFMPEG), "pwa": True}

@app.post("/api/analyze")
def analyze(req: AnalyzeRequest):
    url = req.url.strip()
    if not valid_url(url): raise HTTPException(400, "Unsupported link. Use Instagram, X / Twitter, or Reddit.")
    try: info = extract(url)
    except Exception as exc:
        code, detail = friendly_extract_error(exc); raise HTTPException(code, detail)
    if not info: raise HTTPException(404, "No downloadable media found.")
    return public_info(url, info)

@app.get("/api/download")
def download(background_tasks: BackgroundTasks, token: str = Query(...), mode: str = Query("best", pattern="^(best|audio|quality)$"), height: int | None = Query(None, ge=1, le=4320)):
    payload = unsign(token)
    source = payload.get("source") or payload["url"]
    tmp = tempfile.mkdtemp(prefix="media-dl-")
    tmpl = str(Path(tmp) / "%(title).80s.%(ext)s")
    if mode == "audio": fmt = "bestaudio/best"
    elif mode == "quality" and height: fmt = f"bestvideo*[height<={height}]+bestaudio/best[height<={height}]/best"
    else: fmt = "bestvideo*+bestaudio/best"
    opts, c = base_opts(True, tmpl, fmt)
    if mode == "audio": opts["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": "m4a", "preferredquality": "0"}]
    try:
        with yt_dlp.YoutubeDL(opts) as ydl: ydl.download([source])
        files = [p for p in Path(tmp).iterdir() if p.is_file()]
        if not files: raise HTTPException(500, "Download failed.")
        target = max(files, key=lambda p: p.stat().st_size)
        background_tasks.add_task(shutil.rmtree, tmp, True)
        media = "audio/mp4" if target.suffix.lower() in (".m4a", ".aac") else "application/octet-stream"
        return FileResponse(target, filename=target.name, media_type=media)
    except HTTPException: raise
    except Exception as exc:
        shutil.rmtree(tmp, ignore_errors=True)
        code, detail = friendly_extract_error(exc)
        if code == 422: detail = "Platform extraction or download is temporarily unavailable."
        raise HTTPException(code, detail)
    finally:
        if c:
            try: os.remove(c)
            except OSError: pass

@app.get("/manifest.webmanifest")
def manifest(): return FileResponse(ROOT / "manifest.webmanifest", media_type="application/manifest+json")

@app.get("/sw.js")
def service_worker(): return FileResponse(ROOT / "sw.js", media_type="application/javascript", headers={"Cache-Control": "no-cache"})

@app.get("/icon.svg")
def app_icon(): return FileResponse(ROOT / "icon.svg", media_type="image/svg+xml")

@app.get("/", response_class=HTMLResponse)
def home(): return (ROOT / "index.html").read_text(encoding="utf-8")
