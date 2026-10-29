"""NYZ REAL 3D AI backend: FastAPI + Tripo V3 (multiview-to-model).

The Tripo key is read only from the environment. Nothing here is sent to the browser.
Docs used: https://developers.tripo3d.com/en/docs/introduction
"""
import asyncio, hashlib, hmac, json, logging, os, sqlite3, struct, threading, time, uuid
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

log = logging.getLogger("nyz")
logging.basicConfig(level=logging.INFO)

TRIPO_KEY = os.environ.get("TRIPO_API_KEY", "")
BASE = os.environ.get("TRIPO_BASE_URL", "https://openapi.tripo3d.com/v3")
MODEL = os.environ.get("TRIPO_MODEL", "v3.1-20260211")
TOKENS = [t.strip() for t in os.environ.get("APP_TOKENS", "").split(",") if t.strip()]
SECRET = os.environ.get("LINK_SECRET", "")
ORIGIN = os.environ.get("ALLOWED_ORIGIN", "")
DATA = Path(os.environ.get("DATA_DIR", "./data"))
RETENTION_H = float(os.environ.get("RETENTION_HOURS", "24"))
CONCURRENCY = int(os.environ.get("MAX_CONCURRENT_JOBS", "1"))
JOB_TIMEOUT = int(os.environ.get("JOB_TIMEOUT_SECONDS", "1200"))
MAX_IMG = 20 * 1024 * 1024  # Tripo limit for image upload
MAX_FILES = 12
VIEWS = ("front", "left", "back", "right")  # the only views Tripo multiview accepts
ALIASES = {"rear": "back"}

# Every preset changes real parameters sent to Tripo (names from the multiview-to-model docs).
PRESETS = {
    "draft": dict(texture=True, pbr=False, face_limit=20000, geometry_quality="standard", texture_quality="standard"),
    "mobile": dict(texture=True, pbr=True, face_limit=30000, geometry_quality="standard", texture_quality="standard"),
    "high": dict(texture=True, pbr=True, face_limit=500000, geometry_quality="detailed", texture_quality="detailed"),
    "ultra": dict(texture=True, pbr=True, face_limit=1500000, geometry_quality="detailed", texture_quality="extreme"),
}
CUSTOM_KEYS = {"face_limit", "texture", "pbr", "texture_quality", "geometry_quality", "auto_size"}
PRESET_WARNINGS = {
    "mobile": ["LOD generation is not supported by this backend.", "Texture compression is not applied."],
    "draft": ["Output is intentionally simplified."],
}

# ---------- storage ----------
DATA.mkdir(parents=True, exist_ok=True)
(DATA / "jobs").mkdir(exist_ok=True)
_lock = threading.Lock()
_con = sqlite3.connect(DATA / "jobs.db", check_same_thread=False)
_con.execute("CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, owner TEXT, created REAL, doc TEXT)")
_con.commit()


def save(job):
    job["updated"] = time.time()
    with _lock:
        _con.execute("INSERT OR REPLACE INTO jobs VALUES(?,?,?,?)", (job["id"], job["owner"], job["created"], json.dumps(job)))
        _con.commit()


def load(jid):
    with _lock:
        r = _con.execute("SELECT doc FROM jobs WHERE id=?", (jid,)).fetchone()
    return json.loads(r[0]) if r else None


def all_docs(owner=None):
    with _lock:
        rows = _con.execute("SELECT doc FROM jobs" + (" WHERE owner=?" if owner else "") + " ORDER BY created DESC",
                            (owner,) if owner else ()).fetchall()
    return [json.loads(r[0]) for r in rows]


def delete(jid):
    with _lock:
        _con.execute("DELETE FROM jobs WHERE id=?", (jid,))
        _con.commit()
    d = DATA / "jobs" / jid
    if d.exists():
        for f in d.iterdir():
            f.unlink(missing_ok=True)
        d.rmdir()


# ---------- security helpers ----------
def auth(tok):
    if tok:
        for t in TOKENS:
            if hmac.compare_digest(tok, t):
                return hashlib.sha256(tok.encode()).hexdigest()[:12]
    raise HTTPException(401, "Invalid or missing X-API-Token")


_hits = {}


def rate(key, limit, window):
    now = time.time()
    h = [t for t in _hits.get(key, []) if now - t < window]
    if len(h) >= limit:
        raise HTTPException(429, "Too many requests, try again later")
    h.append(now)
    _hits[key] = h


def sign(jid, exp):
    return hmac.new(SECRET.encode(), f"{jid}.{exp}".encode(), hashlib.sha256).hexdigest()


def sniff(data):
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg", "jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png", "png"
    return None, None


# ---------- GLB structural validation (not a visual quality check) ----------
def validate_glb(path):
    errors, stats = [], {}
    raw = Path(path).read_bytes()
    stats["file_size"] = len(raw)
    if len(raw) < 20 or raw[:4] != b"glTF":
        return {"ok": False, "errors": ["Not a GLB file (bad magic)"], "stats": stats}
    ver, length = struct.unpack("<II", raw[4:12])
    if ver != 2:
        errors.append(f"Unexpected glTF version {ver}")
    if length != len(raw):
        errors.append("Header length does not match file size (truncated?)")
    clen, ctype = struct.unpack("<II", raw[12:20])
    if ctype != 0x4E4F534A:
        return {"ok": False, "errors": errors + ["First chunk is not JSON"], "stats": stats}
    try:
        g = json.loads(raw[20:20 + clen])
    except ValueError:
        return {"ok": False, "errors": errors + ["JSON chunk is invalid"], "stats": stats}
    meshes, mats = g.get("meshes", []), g.get("materials", [])
    stats.update(meshes=len(meshes), materials=len(mats), textures=len(g.get("textures", [])),
                 images=len(g.get("images", [])), skins=len(g.get("skins", [])), animations=len(g.get("animations", [])))
    if not meshes:
        errors.append("No meshes")
    for mi, m in enumerate(meshes):
        if not m.get("primitives"):
            errors.append(f"Mesh {mi} is empty")
        for p in m.get("primitives", []):
            if "material" in p and p["material"] >= len(mats):
                errors.append(f"Mesh {mi} references missing material {p['material']}")
            if p.get("attributes", {}).get("POSITION") is None:
                errors.append(f"Mesh {mi} has no POSITION")
    for t in g.get("textures", []):
        if t.get("source", 0) >= len(g.get("images", [])):
            errors.append("Texture references missing image")
    return {"ok": not errors, "errors": errors, "stats": stats}


# ---------- Tripo client ----------
class TripoError(Exception):
    pass


async def tripo(c, method, path, **kw):
    last = None
    for attempt in range(3):
        try:
            r = await c.request(method, BASE + path, headers={"Authorization": f"Bearer {TRIPO_KEY}"}, **kw)
            if r.status_code in (429,) or r.status_code >= 500:
                raise httpx.HTTPError(f"HTTP {r.status_code}")
            body = r.json()
            if body.get("code") != 0:
                raise TripoError(f"{body.get('message') or body.get('code')} {body.get('suggestion') or ''}".strip())
            return body["data"]
        except TripoError:
            raise
        except (httpx.HTTPError, ValueError) as e:
            last = e
            await asyncio.sleep(2 ** attempt)
    raise RuntimeError(f"Network error after 3 attempts: {last}")


sem = asyncio.Semaphore(CONCURRENCY)
runners = {}


def setst(job, status, **kw):
    job["status"] = status
    job.update(kw)
    save(job)


async def run_job(jid):
    job = load(jid)
    try:
        async with sem:
            job = load(jid)
            if job["status"] == "cancelled":
                return
            async with httpx.AsyncClient(timeout=httpx.Timeout(60, connect=15)) as c:
                if not job.get("tripo_task_id"):
                    setst(job, "uploading", progress=0)
                    toks = {}
                    for view, fn in job["selected"].items():
                        p = DATA / "jobs" / jid / fn
                        mime = "image/png" if fn.endswith("png") else "image/jpeg"
                        d = await tripo(c, "POST", "/files", files={"file": (fn, p.read_bytes(), mime)})
                        toks[view] = d["file_token"]
                    body = {"inputs": [{v: t} for v, t in toks.items()], "model": MODEL, **job["settings_sent"]}
                    d = await tripo(c, "POST", "/generation/multiview-to-model", json=body)
                    setst(job, "processing", tripo_task_id=d["task_id"], progress=0)
                deadline = time.time() + JOB_TIMEOUT
                url = None
                while time.time() < deadline:
                    d = await tripo(c, "GET", f"/tasks/{job['tripo_task_id']}")
                    st = d.get("status")
                    job["progress"] = d.get("progress", job.get("progress"))
                    job["credits"] = d.get("credits_consumed", job.get("credits"))
                    if st == "success":
                        out = d.get("output") or {}
                        url = out.get("model_url") or out.get("pbr_model") or out.get("model") or out.get("base_model")
                        break
                    if st in ("failed", "cancelled"):
                        return setst(job, "failed", error=f"Reconstruction {st} on the AI backend")
                    save(job)
                    await asyncio.sleep(3)
                if not url:
                    return setst(job, "failed", error="Timed out or backend returned no model URL")
                setst(job, "downloading", progress=100)
                out_path = DATA / "jobs" / jid / "model.glb"
                async with c.stream("GET", url) as r:
                    if r.status_code != 200:
                        return setst(job, "failed", error=f"Model download failed (HTTP {r.status_code})")
                    with open(out_path, "wb") as f:
                        async for chunk in r.aiter_bytes():
                            f.write(chunk)
                setst(job, "validating")
                v = validate_glb(out_path)
                if not v["ok"]:
                    return setst(job, "failed", error="Downloaded file failed structural validation", validation=v)
                setst(job, "completed", validation=v, result="model.glb")
    except asyncio.CancelledError:
        setst(load(jid), "cancelled")
        raise
    except Exception as e:  # never mark failures as completed
        log.exception("job %s failed", jid)
        setst(load(jid), "failed", error=str(e)[:300])
    finally:
        runners.pop(jid, None)


def start(jid):
    runners[jid] = asyncio.create_task(run_job(jid))


async def janitor():
    while True:
        await asyncio.sleep(600)
        for j in all_docs():
            if time.time() - j["created"] > RETENTION_H * 3600 and j["id"] not in runners:
                delete(j["id"])


@asynccontextmanager
async def lifespan(app):
    if not (TRIPO_KEY and TOKENS and len(SECRET) >= 16):
        raise RuntimeError("Set TRIPO_API_KEY, APP_TOKENS and LINK_SECRET (16+ chars) in the environment")
    for j in all_docs():  # resume interrupted jobs
        if j["status"] in ("queued", "uploading", "processing"):
            start(j["id"])
    t = asyncio.create_task(janitor())
    yield
    t.cancel()


app = FastAPI(title="NYZ REAL 3D AI", lifespan=lifespan)
if ORIGIN:
    app.add_middleware(CORSMiddleware, allow_origins=[ORIGIN], allow_methods=["GET", "POST"], allow_headers=["X-API-Token"])


def public(j):
    keys = ("id", "status", "progress", "error", "created", "updated", "preset", "settings_sent", "warnings",
            "images", "credits", "validation")
    d = {k: j.get(k) for k in keys}
    d["download_ready"] = j["status"] == "completed"
    return d


@app.get("/api/health")
async def health():
    return {"ok": True}


@app.post("/api/jobs")
async def create_job(request: Request, files: list[UploadFile] = File(...), labels: str = Form(...),
                     preset: str = Form("high"), custom: str = Form("{}"), x_api_token: str = Header(None)):
    owner = auth(x_api_token)
    rate(f"c:{owner}", 10, 3600)
    try:
        labels_l = json.loads(labels)
        custom_d = json.loads(custom)
        assert isinstance(labels_l, list) and isinstance(custom_d, dict)
    except Exception:
        raise HTTPException(400, "labels must be a JSON list and custom a JSON object")
    if not 1 <= len(files) <= MAX_FILES or len(labels_l) != len(files):
        raise HTTPException(400, f"Send 1 to {MAX_FILES} files with one label each")
    if preset not in PRESETS and preset != "custom":
        raise HTTPException(400, "Unknown preset")

    jid = uuid.uuid4().hex
    jdir = DATA / "jobs" / jid
    jdir.mkdir(parents=True)
    chosen, unused, saved = {}, [], {}
    try:
        for i, (f, lab) in enumerate(zip(files, labels_l)):
            data = await f.read(MAX_IMG + 1)
            if len(data) > MAX_IMG:
                raise HTTPException(413, f"{f.filename}: larger than 20 MB")
            mime, ext = sniff(data)
            if not mime:
                raise HTTPException(415, f"{f.filename}: only real JPEG or PNG files are accepted")
            lab = ALIASES.get(str(lab).lower(), str(lab).lower())
            fn = f"img{i}.{ext}"
            (jdir / fn).write_bytes(data)
            if lab in VIEWS and lab not in chosen:
                chosen[lab] = fn
                saved[fn] = f.filename
            else:
                why = "duplicate of an already selected view" if lab in VIEWS else \
                    f"view '{lab}' is not supported by this backend (only front/left/back/right)"
                unused.append({"file": f.filename, "reason": why})
        if "front" not in chosen or len(chosen) < 2:
            raise HTTPException(422, "Need a 'front' image plus at least one more of left/back/right")
    except HTTPException:
        for p in jdir.iterdir():
            p.unlink()
        jdir.rmdir()
        raise

    warnings = list(PRESET_WARNINGS.get(preset, []))
    if preset == "custom":
        settings = {}
        for k, v in custom_d.items():
            if k in CUSTOM_KEYS:
                settings[k] = v
            else:
                warnings.append(f"Setting '{k}' is not supported and was ignored.")
        fl = settings.get("face_limit")
        if fl is not None and not (isinstance(fl, int) and 500 <= fl <= 1500000):
            raise HTTPException(422, "face_limit must be an integer between 500 and 1500000")
        if settings.get("texture_quality", "standard") not in ("standard", "detailed", "extreme") or \
                settings.get("geometry_quality", "standard") not in ("standard", "detailed"):
            raise HTTPException(422, "Invalid texture_quality or geometry_quality")
    else:
        settings = dict(PRESETS[preset])
    if unused:
        warnings.append(f"{len(unused)} uploaded image(s) were NOT used: the backend accepts at most 4 views.")

    job = {"id": jid, "owner": owner, "created": time.time(), "status": "queued", "progress": 0, "preset": preset,
           "settings_sent": settings, "selected": chosen, "warnings": warnings,
           "images": {"used": [{"view": v, "file": saved[fn]} for v, fn in chosen.items()], "unused": unused}}
    save(job)
    start(jid)
    return public(job)


def mine(jid, owner):
    j = load(jid)
    if not j or j["owner"] != owner:
        raise HTTPException(404, "Job not found")
    return j


@app.get("/api/jobs")
async def list_jobs(x_api_token: str = Header(None)):
    return [public(j) for j in all_docs(auth(x_api_token))]


@app.get("/api/jobs/{jid}")
async def get_job(jid: str, x_api_token: str = Header(None)):
    return public(mine(jid, auth(x_api_token)))


@app.post("/api/jobs/{jid}/cancel")
async def cancel(jid: str, x_api_token: str = Header(None)):
    j = mine(jid, auth(x_api_token))
    if j["status"] != "queued" or jid not in runners:
        raise HTTPException(409, "Only jobs still waiting in the queue can be cancelled; "
                                 "cancelling a running Tripo task is not supported here")
    runners[jid].cancel()
    return {"cancelled": True}


@app.get("/api/jobs/{jid}/link")
async def link(jid: str, x_api_token: str = Header(None)):
    j = mine(jid, auth(x_api_token))
    if j["status"] != "completed":
        raise HTTPException(409, "Model is not ready")
    exp = int(time.time()) + 600
    return {"url": f"/api/download/{jid}?exp={exp}&sig={sign(jid, exp)}", "expires_in": 600}


@app.get("/api/download/{jid}")
async def download(jid: str, exp: int, sig: str):
    if exp < time.time() or not hmac.compare_digest(sig, sign(jid, exp)):
        raise HTTPException(403, "Link expired or invalid")
    p = DATA / "jobs" / jid / "model.glb"
    if not p.exists():
        raise HTTPException(404, "File no longer available (retention period passed)")
    return FileResponse(p, media_type="model/gltf-binary", filename="nyz-model.glb")
