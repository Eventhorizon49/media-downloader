from pathlib import Path

p = Path("app.py")
s = p.read_text()

s = s.replace(
    'app = FastAPI(title="Draupnir", version="1.5.0")',
    'app = FastAPI(title="Draupnir", version="1.5.1")',
)

start = s.index("def cookie_file():")
end = s.index("\ndef opts(", start)
replacement = '''def instagram_auth_configured():
    return bool(
        os.getenv("INSTAGRAM_COOKIES_B64")
        or os.getenv("YTDLP_COOKIES_B64")
        or os.getenv("INSTAGRAM_SESSIONID")
    )


def cookie_file():
    for key in ("INSTAGRAM_COOKIES_B64", "YTDLP_COOKIES_B64"):
        v = os.getenv(key)
        if not v:
            continue
        try:
            f = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
            f.write(base64.b64decode(v))
            f.close()
            return f.name
        except Exception:
            pass

    sessionid = os.getenv("INSTAGRAM_SESSIONID")
    if not sessionid:
        return None
    csrf = os.getenv("INSTAGRAM_CSRFTOKEN", "")
    ds_user_id = os.getenv("INSTAGRAM_DS_USER_ID", "")
    try:
        rows = ["# Netscape HTTP Cookie File"]
        rows.append(
            ".instagram.com\\tTRUE\\t/\\tTRUE\\t2147483647\\tsessionid\\t" + sessionid
        )
        if csrf:
            rows.append(
                ".instagram.com\\tTRUE\\t/\\tTRUE\\t2147483647\\tcsrftoken\\t" + csrf
            )
        if ds_user_id:
            rows.append(
                ".instagram.com\\tTRUE\\t/\\tTRUE\\t2147483647\\tds_user_id\\t" + ds_user_id
            )
        f = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
        f.write(("\\n".join(rows) + "\\n").encode())
        f.close()
        return f.name
    except Exception:
        return None

'''
s = s[:start] + replacement + s[end:]

s = s.replace(
    '"http_headers": {"User-Agent": UA},',
    '"http_headers": {"User-Agent": os.getenv("INSTAGRAM_USER_AGENT") or UA},',
    1,
)

old = '''def best_instagram(u):
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
new = '''def best_instagram(u):
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
    if kind == "story" and not instagram_auth_configured():
        raise RuntimeError(
            "Instagram Story requires an authenticated Instagram session cookie"
        )
    return ytdlp(u)
'''
if old not in s:
    raise SystemExit("best_instagram block not found")
s = s.replace(old, new, 1)

s = s.replace(
    '"instagram_story": True,',
    '"instagram_story": True,\n        "instagram_auth_configured": instagram_auth_configured(),',
    1,
)

s = s.replace(
    '"This public post is currently being served behind a platform login/session requirement.",',
    '"Instagram Story access needs an authenticated Instagram session on the server. Reconnect the Instagram session and try again.",',
    1,
)

p.write_text(s)
