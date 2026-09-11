from pathlib import Path

app = Path("app.py")
s = app.read_text(encoding="utf-8")

if "def instagram_profile_picture(" not in s:
    block = '''
def instagram_url_type(u):
    parts = [x for x in urlparse(u).path.split("/") if x]
    if not parts:
        return "unknown"
    if parts[0] == "stories":
        return "story"
    if parts[0] in ("p", "reel", "reels", "tv"):
        return "post"
    return "profile"


def instagram_profile_picture(u):
    parts = [x for x in urlparse(u).path.split("/") if x]
    if not parts or parts[0] in ("p", "reel", "reels", "tv", "stories"):
        raise RuntimeError("Instagram profile URL not found")
    username = parts[0].lstrip("@")
    page = f"https://www.instagram.com/{username}/"
    r = cr.get(
        page,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
        impersonate="chrome",
        timeout=30,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Instagram profile unavailable ({r.status_code})")
    html = r.text
    src = None
    for pat in (
        r'"profile_pic_url_hd":"([^"]+)"',
        r'"profile_pic_url":"([^"]+)"',
        r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"',
    ):
        m = re.search(pat, html, re.I)
        if m:
            src = m.group(1)
            break
    if not src:
        raise RuntimeError("Instagram profile picture unavailable")
    src = src.replace("\\u0026", "&").replace("\\/", "/").replace("&amp;", "&")
    return {
        "title": f"@{username} profile picture",
        "uploader_id": username,
        "url": src,
        "_download_url": src,
        "thumbnail": src,
        "ext": Path(urlparse(src).path).suffix.lstrip(".") or "jpg",
    }


def best_instagram(u):
    kind = instagram_url_type(u)
    if kind == "profile":
        candidates = []
        for fn in (instagram_profile_picture, ytdlp):
            try:
                candidates.append(fn(u))
            except Exception:
                pass
        if not candidates:
            raise RuntimeError("Instagram profile picture unavailable")
        return max(candidates, key=lambda x: len(flat(x)))
    return ytdlp(u)

'''
    s = s.replace("\ndef extract(u):\n", "\n" + block + "def extract(u):\n", 1)

old = '''def extract(u):
    p = platform(u)
    if p == "X / Twitter":
        return best_public_x(u)
    if p == "Reddit":
'''
new = '''def extract(u):
    p = platform(u)
    if p == "Instagram":
        return best_instagram(u)
    if p == "X / Twitter":
        return best_public_x(u)
    if p == "Reddit":
'''
if old in s:
    s = s.replace(old, new, 1)

s = s.replace('app = FastAPI(title="Draupnir", version="1.4.2")', 'app = FastAPI(title="Draupnir", version="1.5.0")')

if '"instagram_profile_picture": True' not in s:
    s = s.replace(
        '"x_fallback": "fxtwitter+syndication",',
        '"x_fallback": "fxtwitter+syndication",\n        "instagram_profile_picture": True,\n        "instagram_story": True,',
        1,
    )

if '"direct": bool(i.get("_download_url") and typ == "image")' not in s:
    s = s.replace(
        '"creator": creator,\n                "exp": time.time() + 900,',
        '"creator": creator,\n                "direct": bool(i.get("_download_url") and typ == "image"),\n                "exp": time.time() + 900,',
        1,
    )

s = s.replace('if direct_file(s):', 'if p.get("direct") or direct_file(s):', 1)
s = s.replace('ext = Path(urlparse(s).path).suffix or ".bin"', 'ext = Path(urlparse(s).path).suffix or (".jpg" if p.get("direct") else ".bin")', 1)

app.write_text(s, encoding="utf-8")

index = Path("index.html")
h = index.read_text(encoding="utf-8")
h = h.replace("Paste a public post link.", "Paste a public post, story, or Instagram profile link.")
h = h.replace(
    "<div class=\"hint\">Videos · images · carousels</div>",
    "<div class=\"hint\">Videos · images · carousels · Instagram stories · profile pictures</div>",
)
index.write_text(h, encoding="utf-8")
