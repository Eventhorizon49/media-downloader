from pathlib import Path

app = Path("app.py")
s = app.read_text()

s = s.replace(
    'app = FastAPI(title="Draupnir", version="1.5.2")',
    'app = FastAPI(title="Draupnir", version="1.5.3")',
    1,
)

marker = """def direct_file(s):
    return urlparse(s).path.lower().endswith(DIRECT_EXTS)
"""
helper = """def direct_file(s):
    return urlparse(s).path.lower().endswith(DIRECT_EXTS)


def release_download_slot_and_cleanup(path):
    try:
        shutil.rmtree(path, ignore_errors=True)
    finally:
        try:
            DOWNLOAD_SLOT.release()
        except ValueError:
            pass


@app.get("/api/download-state")
def download_state():
    acquired = DOWNLOAD_SLOT.acquire(blocking=False)
    if acquired:
        DOWNLOAD_SLOT.release()
    return {"busy": not acquired}
"""
if '@app.get("/api/download-state")' not in s:
    if marker not in s:
        raise SystemExit("direct_file marker not found")
    s = s.replace(marker, helper, 1)

old_download = """    p = unsign(token)
    d = tempfile.mkdtemp(prefix="media-dl-")
    try:
        with DOWNLOAD_SLOT:
            t = download_one(p, d, mode, height, "media")
        background_tasks.add_task(shutil.rmtree, d, True)
        return FileResponse(t, filename=t.name, media_type="application/octet-stream")
    except Exception as e:
        shutil.rmtree(d, ignore_errors=True)
        c, x = friendly(e)
        raise HTTPException(c, x)
"""
new_download = """    p = unsign(token)
    d = tempfile.mkdtemp(prefix="media-dl-")
    acquired = DOWNLOAD_SLOT.acquire(blocking=False)
    if not acquired:
        shutil.rmtree(d, ignore_errors=True)
        raise HTTPException(
            409,
            "Another download is already running. This download was stopped to protect memory. Try again after the current download finishes.",
        )
    try:
        t = download_one(p, d, mode, height, "media")
        background_tasks.add_task(release_download_slot_and_cleanup, d)
        return FileResponse(t, filename=t.name, media_type="application/octet-stream")
    except Exception as e:
        release_download_slot_and_cleanup(d)
        c, x = friendly(e)
        raise HTTPException(c, x)
"""
if old_download not in s:
    raise SystemExit("download endpoint block not found")
s = s.replace(old_download, new_download, 1)

old_batch = """    d = tempfile.mkdtemp(prefix="media-batch-")
    fs = []
    try:
        with DOWNLOAD_SLOT:
            for n, t in enumerate(r.tokens):
                fs.append(download_one(unsign(t), d, "best", None, f"media-{n+1:02d}"))
        z = Path(d) / "media-downloader.zip"
        with zipfile.ZipFile(z, "w", zipfile.ZIP_STORED, allowZip64=True) as a:
            for f in fs:
                a.write(f, arcname=f.name)
        background_tasks.add_task(shutil.rmtree, d, True)
        return FileResponse(
            z, filename="media-downloader.zip", media_type="application/zip"
        )
    except Exception as e:
        shutil.rmtree(d, ignore_errors=True)
        c, x = friendly(e)
        raise HTTPException(c, x)
"""
new_batch = """    d = tempfile.mkdtemp(prefix="media-batch-")
    fs = []
    acquired = DOWNLOAD_SLOT.acquire(blocking=False)
    if not acquired:
        shutil.rmtree(d, ignore_errors=True)
        raise HTTPException(
            409,
            "Another download is already running. This download was stopped to protect memory. Try again after the current download finishes.",
        )
    try:
        for n, t in enumerate(r.tokens):
            fs.append(download_one(unsign(t), d, "best", None, f"media-{n+1:02d}"))
        z = Path(d) / "media-downloader.zip"
        with zipfile.ZipFile(z, "w", zipfile.ZIP_STORED, allowZip64=True) as a:
            for f in fs:
                a.write(f, arcname=f.name)
        background_tasks.add_task(release_download_slot_and_cleanup, d)
        return FileResponse(
            z, filename="media-downloader.zip", media_type="application/zip"
        )
    except Exception as e:
        release_download_slot_and_cleanup(d)
        c, x = friendly(e)
        raise HTTPException(c, x)
"""
if old_batch not in s:
    raise SystemExit("batch endpoint block not found")
s = s.replace(old_batch, new_batch, 1)

if '"single_download_guard": True,' not in s:
    s = s.replace(
        '"download_concurrency": 1,',
        '"download_concurrency": 1,\n        "single_download_guard": True,',
        1,
    )

app.write_text(s)

index = Path("index.html")
h = index.read_text()

h = h.replace(
    """          <div class="hint">
            Videos · images · carousels · Instagram stories · profile pictures
          </div>
""",
    "",
    1,
)

if ".toast {" not in h:
    h = h.replace(
        "      .error {\n",
        """      .toast {
        display: none;
        position: fixed;
        left: 50%;
        bottom: max(22px, env(safe-area-inset-bottom));
        transform: translateX(-50%);
        width: min(calc(100% - 28px), 560px);
        z-index: 1000;
        padding: 13px 16px;
        border-radius: 14px;
        background: #172033f5;
        border: 1px solid #405077;
        box-shadow: 0 16px 48px #0009;
        color: #eef3ff;
        font-size: 14px;
        text-align: center;
      }
      .toast.show {
        display: block;
        animation: toastIn 0.18s ease-out;
      }
      @keyframes toastIn {
        from { opacity: 0; transform: translate(-50%, 8px); }
        to { opacity: 1; transform: translate(-50%, 0); }
      }
      .error {
""",
        1,
    )

if 'id="toast"' not in h:
    h = h.replace(
        "    <script>\n",
        '    <div id="toast" class="toast" role="status" aria-live="polite"></div>\n    <script>\n',
        1,
    )

if "function showToast(" not in h:
    h = h.replace(
        "      function showErr(s) {\n",
        """      let toastTimer = null;
      function showToast(s) {
        const t = $("toast");
        t.textContent = s;
        t.classList.add("show");
        clearTimeout(toastTimer);
        toastTimer = setTimeout(() => t.classList.remove("show"), 4200);
      }
      async function downloadBusy() {
        try {
          const r = await fetch("/api/download-state", { cache: "no-store" });
          if (!r.ok) return false;
          const d = await r.json();
          return !!d.busy;
        } catch {
          return false;
        }
      }
      function showErr(s) {
""",
        1,
    )

old_current = """      function downloadCurrent() {
        let it = data.items[idx],
          v = $("quality").value,
          mode = "best",
          height = "";
        if (v === "audio") mode = "audio";
        else if (v.startsWith("q:")) {
          mode = "quality";
          height = v.split(":")[1];
        }
        location.href =
          "/api/download?token=" +
          encodeURIComponent(it.token) +
          "&mode=" +
          mode +
          (height ? "&height=" + height : "");
      }
"""
new_current = """      async function downloadCurrent() {
        if (await downloadBusy()) {
          showToast("Another download is already running. This one has been stopped to protect memory. Try again when the current download finishes.");
          return;
        }
        let it = data.items[idx],
          v = $("quality").value,
          mode = "best",
          height = "";
        if (v === "audio") mode = "audio";
        else if (v.startsWith("q:")) {
          mode = "quality";
          height = v.split(":")[1];
        }
        location.href =
          "/api/download?token=" +
          encodeURIComponent(it.token) +
          "&mode=" +
          mode +
          (height ? "&height=" + height : "");
      }
"""
if old_current not in h:
    raise SystemExit("downloadCurrent block not found")
h = h.replace(old_current, new_current, 1)

old_batch_error = """          if (!r.ok) {
            let d = await r.json().catch(() => ({}));
            throw new Error(d.detail || "Could not prepare download.");
          }
"""
new_batch_error = """          if (!r.ok) {
            let d = await r.json().catch(() => ({}));
            if (r.status === 409) {
              showToast(d.detail || "Another download is already running. Try again when it finishes.");
              return;
            }
            throw new Error(d.detail || "Could not prepare download.");
          }
"""
if old_batch_error not in h:
    raise SystemExit("batch error block not found")
h = h.replace(old_batch_error, new_batch_error, 1)

if "A download is already running. New downloads are temporarily blocked" not in h:
    h = h.replace(
        '      if ("serviceWorker" in navigator)\n',
        """      addEventListener("load", async () => {
        if (await downloadBusy()) {
          showToast("A download is already running. New downloads are temporarily blocked to protect memory.");
        }
      });
      if ("serviceWorker" in navigator)
""",
        1,
    )

index.write_text(h)
