import base64, hashlib, hmac, json, os, tempfile, time
from pathlib import Path
from urllib.parse import urlparse

import imageio_ffmpeg
import yt_dlp
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

app = FastAPI(title='Media Downloader')
SECRET = os.getenv('TOKEN_SECRET', 'dev-change-me')
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
SUPPORTED = ('instagram.com', 'x.com', 'twitter.com', 'reddit.com', 'redd.it')

class AnalyzeRequest(BaseModel):
    url: str


def valid_url(url: str):
    try:
        host = urlparse(url).hostname or ''
        return any(host == d or host.endswith('.'+d) for d in SUPPORTED)
    except Exception:
        return False


def sign(data: dict):
    raw = base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip('=')
    sig = hmac.new(SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()
    return f'{raw}.{sig}'


def unsign(token: str):
    try:
        raw, sig = token.rsplit('.', 1)
        expected = hmac.new(SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected): raise ValueError
        payload = json.loads(base64.urlsafe_b64decode(raw + '=' * (-len(raw) % 4)))
        if payload['exp'] < time.time(): raise ValueError
        return payload
    except Exception:
        raise HTTPException(410, 'Download session expired')


def cookie_file():
    value = os.getenv('YTDLP_COOKIES_B64')
    if not value: return None
    p = tempfile.NamedTemporaryFile(delete=False, suffix='.txt')
    p.write(base64.b64decode(value)); p.close()
    return p.name


def ydl_opts(download=False, outtmpl=None, fmt=None):
    opts = {
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'ffmpeg_location': FFMPEG,
        'socket_timeout': 30,
        'retries': 2,
        'http_headers': {'User-Agent':'Mozilla/5.0'},
    }
    c = cookie_file()
    if c: opts['cookiefile'] = c
    if download:
        opts.update({'outtmpl': outtmpl, 'format': fmt or 'bestvideo*+bestaudio/best', 'merge_output_format':'mp4'})
    else:
        opts['skip_download'] = True
    return opts, c


def extract(url: str):
    opts, c = ydl_opts()
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)
    finally:
        if c:
            try: os.remove(c)
            except OSError: pass


def platform_name(url: str):
    h = (urlparse(url).hostname or '').lower()
    if 'instagram' in h: return 'Instagram'
    if 'reddit' in h or 'redd.it' in h: return 'Reddit'
    return 'X / Twitter'


def quality_rows(info):
    rows, seen = [], set()
    for f in info.get('formats') or []:
        h = f.get('height')
        if not h or f.get('vcodec') in (None, 'none'): continue
        if h in seen: continue
        seen.add(h)
        rows.append({'label': f'{h}p','height':h})
    rows.sort(key=lambda x: x['height'], reverse=True)
    return rows[:8]

@app.get('/health')
def health():
    return {'ok': True, 'ffmpeg': bool(FFMPEG)}

@app.post('/api/analyze')
def analyze(req: AnalyzeRequest):
    if not valid_url(req.url): raise HTTPException(400, 'Unsupported link')
    try:
        info = extract(req.url)
    except Exception as e:
        msg = str(e).lower()
        if 'login' in msg or 'cookie' in msg or 'sign in' in msg:
            raise HTTPException(401, 'This post requires login/session')
        raise HTTPException(422, 'Could not analyze this post')
    if not info: raise HTTPException(404, 'No downloadable media found')
    token = sign({'url': req.url, 'exp': time.time()+900})
    return {
        'platform': platform_name(req.url),
        'title': info.get('title') or info.get('description') or 'Media',
        'thumbnail': info.get('thumbnail'),
        'duration': info.get('duration'),
        'width': info.get('width'), 'height': info.get('height'),
        'fps': info.get('fps'), 'bitrate': info.get('tbr'),
        'filesize': info.get('filesize') or info.get('filesize_approx'),
        'ext': info.get('ext'),
        'qualities': quality_rows(info),
        'token': token,
    }

@app.get('/api/download')
def download(token: str, background_tasks: BackgroundTasks, height: int | None = None):
    payload = unsign(token)
    tmp = tempfile.mkdtemp(prefix='media-dl-')
    tmpl = str(Path(tmp) / '%(title).80s.%(ext)s')
    fmt = 'bestvideo*+bestaudio/best' if not height else f'bestvideo*[height<={height}]+bestaudio/best[height<={height}]/best'
    opts, c = ydl_opts(True, tmpl, fmt)
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([payload['url']])
        files = [p for p in Path(tmp).iterdir() if p.is_file()]
        if not files: raise HTTPException(500, 'Download failed')
        target = max(files, key=lambda p: p.stat().st_size)
        background_tasks.add_task(lambda: __import__('shutil').rmtree(tmp, ignore_errors=True))
        return FileResponse(target, filename=target.name, media_type='application/octet-stream')
    except HTTPException: raise
    except Exception:
        __import__('shutil').rmtree(tmp, ignore_errors=True)
        raise HTTPException(422, 'Platform extraction temporarily unavailable')
    finally:
        if c:
            try: os.remove(c)
            except OSError: pass

@app.get('/', response_class=HTMLResponse)
def home():
    return Path('index.html').read_text(encoding='utf-8')
