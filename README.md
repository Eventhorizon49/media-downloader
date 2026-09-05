# Media Downloader

Personal-use downloader for Instagram, X / Twitter and Reddit.

## Stack
FastAPI + yt-dlp + FFmpeg (imageio-ffmpeg), with a same-origin HTML frontend.

## Quality
Best available selects the highest exposed video/audio streams and merges/remuxes them without intentional re-encoding.

## Optional Instagram authentication
Set `YTDLP_COOKIES_B64` to a base64-encoded Netscape cookies.txt when a post requires a logged-in session.

## Run
`pip install -r requirements.txt`
`uvicorn app:app --host 0.0.0.0 --port 8000`
