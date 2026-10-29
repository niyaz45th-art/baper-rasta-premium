
import os
import uuid
import asyncio
import requests

from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import (
    HTMLResponse,
    FileResponse,
    JSONResponse,
)
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI(title="NYZ REAL 3D AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE = Path(__file__).resolve().parent
JOBS_DIR = BASE / "jobs"
JOBS_DIR.mkdir(parents=True, exist_ok=True)

TRIPO_API_KEY = os.getenv("TRIPO_API_KEY", "").strip()
TRIPO_BASE = "https://openapi.tripo3d.ai/v3"

# কাজের অবস্থা
JOBS = {}

MAX_IMAGE_SIZE = 20 * 1024 * 1024
ALLOWED_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}


def tripo_headers():
    if not TRIPO_API_KEY:
        raise RuntimeError(
            "TRIPO_API_KEY সার্ভারে সেট করা নেই।"
        )

    return {
        "Authorization": f"Bearer {TRIPO_API_KEY}"
    }


def api_json(response):
    response.raise_for_status()
    result = response.json()

    if result.get("code", 0) not in (0, None):
        raise RuntimeError(
            f"Tripo API error: {result}"
        )

    return result


def upload_image(image_path: Path) -> str:
    """Tripo-তে ছবি আপলোড করে file_token নেয়।"""

    with image_path.open("rb") as image:
        response = requests.post(
            f"{TRIPO_BASE}/files",
            headers=tripo_headers(),
            files={
                "file": (
                    image_path.name,
                    image,
                    "application/octet-stream",
                )
            },
            timeout=120,
        )

    result = api_json(response)
    data = result.get("data", {})
    token = data.get("file_token")

    if not token:
        raise RuntimeError(
            f"ছবির file_token পাওয়া যায়নি: {result}"
        )

    return token


def create_tripo_task(image_tokens: dict) -> str:
    """একটি ছবি বা একাধিক ভিউ থেকে আসল 3D মডেল তৈরি করে।"""

    if len(image_tokens) == 1:
        token = next(iter(image_tokens.values()))

        url = f"{TRIPO_BASE}/generation/image-to-model"

        payload = {
            "input": token,
            "model": "v3.1-20260211",
            "texture": True,
            "pbr": True,
        }

    else:
        if "front" not in image_tokens:
            raise RuntimeError(
                "একাধিক ছবি ব্যবহারে সামনের ছবিটি প্রয়োজন।"
            )

        inputs = [
            {view: token}
            for view, token in image_tokens.items()
        ]

        url = f"{TRIPO_BASE}/generation/multiview-to-model"

        payload = {
            "inputs": inputs,
            "model": "v3.1-20260211",
            "texture": True,
            "pbr": True,
            "geometry_quality": "detailed",
            "texture_quality": "detailed",
        }

    response = requests.post(
        url,
        headers={
            **tripo_headers(),
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=90,
    )

    result = api_json(response)
    task_id = result.get("data", {}).get("task_id")

    if not task_id:
        raise RuntimeError(
            f"Tripo task ID পাওয়া যায়নি: {result}"
        )

    return task_id


def get_tripo_task(task_id: str):
    response = requests.get(
        f"{TRIPO_BASE}/tasks/{task_id}",
        headers=tripo_headers(),
        timeout=30,
    )

    return api_json(response).get("data", {})


def download_and_validate_glb(url: str, destination: Path):
    """সম্পূর্ণ ফাইল নামিয়ে GLB-এর সিগনেচার যাচাই করে।"""

    if not url or not url.startswith("https://"):
        raise RuntimeError(
            "Tripo থেকে বৈধ HTTPS মডেল URL পাওয়া যায়নি।"
        )

    temp_path = destination.with_suffix(".tmp")

    try:
        with requests.get(
            url,
            stream=True,
            timeout=(20, 180),
            allow_redirects=True,
        ) as response:

            response.raise_for_status()

            content_type = response.headers.get(
                "content-type", ""
            ).lower()

            if "text/html" in content_type:
                raise RuntimeError(
                    "মডেলের বদলে HTML পেজ পাওয়া গেছে।"
                )

            total = 0

            with temp_path.open("wb") as output:
                for chunk in response.iter_content(
                    chunk_size=1024 * 256
                ):
                    if not chunk:
                        continue

                    total += len(chunk)

                    if total > 500 * 1024 * 1024:
                        raise RuntimeError(
                            "GLB ফাইল 500 MB সীমা ছাড়িয়েছে।"
                        )

                    output.write(chunk)

        if total < 1000:
            raise RuntimeError(
                "GLB ফাইল অসম্পূর্ণ বা খুব ছোট।"
            )

        with temp_path.open("rb") as model:
            header = model.read(12)

        if (
            len(header) < 12
            or header[:4] != b"glTF"
            or int.from_bytes(
                header[4:8], "little"
            ) != 2
        ):
            raise RuntimeError(
                "ডাউনলোড করা ফাইল বৈধ GLB 2.0 নয়।"
            )

        declared_size = int.from_bytes(
            header[8:12], "little"
        )

        if declared_size != total:
            raise RuntimeError(
                "GLB ফাইলের সাইজ যাচাই ব্যর্থ হয়েছে।"
            )

        temp_path.replace(destination)

    finally:
        if temp_path.exists():
            temp_path.unlink()


async def process_job(jid: str, image_paths: dict):
    job = JOBS[jid]
    job_dir = JOBS_DIR / jid

    try:
        job.update(
            status="processing",
            progress=5,
            message="ছবি Tripo3D-তে আপলোড হচ্ছে...",
        )

        tokens = {}

        for index, (view, path) in enumerate(
            image_paths.items()
        ):
            token = await asyncio.to_thread(
                upload_image, path
            )

            tokens[view] = token

            job["progress"] = min(
                5 + int((index + 1) / len(image_paths) * 15),
                20,
            )

        job["message"] = (
            "AI দিয়ে বাস্তব 3D মডেল তৈরি হচ্ছে..."
        )

        task_id = await asyncio.to_thread(
            create_tripo_task, tokens
        )

        job["tripo_task"] = task_id
        job["progress"] = 20

        # সর্বোচ্চ প্রায় 15 মিনিট অপেক্ষা
        for attempt in range(180):
            await asyncio.sleep(5)

            info = await asyncio.to_thread(
                get_tripo_task, task_id
            )

            status = str(
                info.get("status", "")
            ).lower()

            progress = info.get("progress", 0)

            try:
                progress = int(progress)
            except (TypeError, ValueError):
                progress = 0

            job["progress"] = min(
                20 + int(progress * 0.75), 95
            )

            if status in {
                "failed", "error", "cancelled"
            }:
                raise RuntimeError(
                    f"Tripo AI task ব্যর্থ: {info}"
                )

            if status in {"success", "completed", "succeeded"}:
                output = info.get("output") or {}

                model_url = (
                    output.get("model_url")
                    or output.get("pbr_model")
                    or output.get("base_model")
                    or output.get("model")
                )

                if not model_url:
                    raise RuntimeError(
                        "AI সফল বলেছে, কিন্তু GLB URL পাওয়া যায়নি।"
                    )

                job["message"] = (
                    "মডেল ডাউনলোড ও যাচাই হচ্ছে..."
                )

                model_path = job_dir / "model.glb"

                await asyncio.to_thread(
                    download_and_validate_glb,
                    model_url,
                    model_path,
                )

                # যাচাই সম্পন্ন হওয়ার পরেই completed
                job.update(
                    status="completed",
                    progress=100,
                    message="বাস্তব GLB প্রস্তুত।",
                    model_url=f"/api/download/{jid}",
                    model_size=model_path.stat().st_size,
                )

                return

        raise RuntimeError(
            "AI নির্ধারিত সময়ের মধ্যে শেষ হয়নি। "
            "কিছুক্ষণ পরে আবার task status পরীক্ষা করো।"
        )

    except Exception as exc:
        job.update(
            status="failed",
            progress=0,
            message=str(exc),
            model_url=None,
        )


@app.get("/", response_class=HTMLResponse)
async def home():
    return FRONTEND_HTML


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "engine": "Tripo3D",
        "tripo_configured": bool(TRIPO_API_KEY),
    }


@app.post("/api/jobs")
async def create_job(
    front: UploadFile = File(...),
    left: Optional[UploadFile] = File(None),
    back: Optional[UploadFile] = File(None),
    right: Optional[UploadFile] = File(None),
):
    if not TRIPO_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="সার্ভারে TRIPO_API_KEY সেট করা নেই।",
        )

    uploads = {
        "front": front,
        "left": left,
        "back": back,
        "right": right,
    }

    selected = {
        view: upload
        for view, upload in uploads.items()
        if upload is not None
        and upload.filename
    }

    if not selected:
        raise HTTPException(
            status_code=400,
            detail="কমপক্ষে একটি ছবি আপলোড করো।",
        )

    if len(selected) > 1 and "front" not in selected:
        raise HTTPException(
            status_code=400,
            detail="একাধিক ছবি দিলে Front ছবিটি আবশ্যক।",
        )

    jid = str(uuid.uuid4())[:12]
    job_dir = JOBS_DIR / jid
    job_dir.mkdir(parents=True, exist_ok=False)

    saved_paths = {}

    try:
        for view, upload in selected.items():
            if upload.content_type not in ALLOWED_TYPES:
                raise HTTPException(
                    status_code=415,
                    detail=f"{view} ছবির ফরম্যাট সমর্থিত নয়।",
                )

            content = await upload.read(
                MAX_IMAGE_SIZE + 1
            )

            if not content or len(content) > MAX_IMAGE_SIZE:
                raise HTTPException(
                    status_code=413,
                    detail=(
                        f"{view} ছবি খালি অথবা 20 MB-এর বেশি।"
                    ),
                )

            path = job_dir / f"{view}.image"
            path.write_bytes(content)
            saved_paths[view] = path

    except Exception:
        import shutil
        shutil.rmtree(job_dir, ignore_errors=True)
        raise

    JOBS[jid] = {
        "status": "queued",
        "progress": 0,
        "message": "কাজ শুরু হচ্ছে...",
        "tripo_task": None,
        "model_url": None,
        "model_size": 0,
    }

    asyncio.create_task(
        process_job(jid, saved_paths)
    )

    return {
        "jid": jid,
        "status": "queued",
        "message": "AI কাজ শুরু হয়েছে।",
    }


@app.get("/api/jobs/{jid}")
async def get_job(jid: str):
    job = JOBS.get(jid)

    if not job:
        raise HTTPException(
            status_code=404,
            detail="এই Job পাওয়া যায়নি।",
        )

    return {"jid": jid, **job}


@app.get("/api/download/{jid}")
async def download(jid: str):
    job = JOBS.get(jid)

    if not job:
        raise HTTPException(
            status_code=404,
            detail="Job পাওয়া যায়নি।",
        )

    path = JOBS_DIR / jid / "model.glb"

    if (
        job.get("status") != "completed"
        or not path.is_file()
        or path.stat().st_size < 1000
    ):
        raise HTTPException(
            status_code=409,
            detail="GLB এখনো প্রস্তুত নয়।",
        )

    with path.open("rb") as model:
        if model.read(4) != b"glTF":
            raise HTTPException(
                status_code=500,
                detail="GLB যাচাই ব্যর্থ।",
            )

    return FileResponse(
        path,
        media_type="model/gltf-binary",
        filename=f"{jid}.glb",
    )


FRONTEND_HTML = r"""
<!doctype html>
<html lang="bn">
<head>
<meta charset="utf-8">
<meta name="viewport"
 content="width=device-width,initial-scale=1">
<title>NYZ REAL 3D AI</title>

<script type="module"
 src="https://ajax.googleapis.com/ajax/libs/model-viewer/4.0.0/model-viewer.min.js">
</script>

<style>
*{box-sizing:border-box}
body{margin:0;padding:18px;background:#09111f;
color:#f4f7ff;font-family:Arial,sans-serif}
main{max-width:760px;margin:auto}
h1{color:#ffbd45}
p{color:#bdc8d9;line-height:1.6}
.panel{background:#111d30;padding:16px;
border-radius:16px;margin:15px 0}
label{display:block;margin:13px 0}
input{display:block;width:100%;margin-top:8px;
padding:10px;background:#fff;color:#111;border-radius:8px}
button,.download{display:inline-block;border:0;
border-radius:10px;padding:13px 17px;margin:5px 3px;
font-weight:bold;background:#ffbd45;color:#151515;
text-decoration:none}
button:disabled{opacity:.4}
#status{white-space:pre-wrap;overflow-wrap:anywhere}
progress{width:100%;height:18px}
model-viewer{width:100%;height:420px;background:#17253a;
border-radius:14px}
.hidden{display:none}
</style>
</head>

<body>
<main>
<h1>NYZ REAL 3D AI</h1>
<p>তোমার ছবিগুলো থেকে Tripo3D AI দিয়ে 3D মডেল তৈরি করো।
একাধিক ছবি দিলে একই বস্তুর বিভিন্ন দিকের ছবি দেবে।</p>

<section class="panel">
<form id="form">
<label>সামনের ছবি (Front) — আবশ্যক
<input name="front" type="file"
 accept="image/jpeg,image/png,image/webp" required>
</label>

<label>বাম পাশের ছবি (Left) — ঐচ্ছিক
<input name="left" type="file"
 accept="image/jpeg,image/png,image/webp">
</label>

<label>পেছনের ছবি (Back) — ঐচ্ছিক
<input name="back" type="file"
 accept="image/jpeg,image/png,image/webp">
</label>

<label>ডান পাশের ছবি (Right) — ঐচ্ছিক
<input name="right" type="file"
 accept="image/jpeg,image/png,image/webp">
</label>

<button id="submit" type="submit">
বাস্তব 3D মডেল তৈরি করো
</button>
</form>
</section>

<section class="panel">
<div id="status">এখনো কোনো কাজ শুরু হয়নি।</div>
<progress id="progress" max="100" value="0"></progress>
</section>

<section id="viewer-panel" class="panel hidden">
<h2>তোমার তৈরি আসল GLB মডেল</h2>

<model-viewer id="viewer"
 camera-controls
 touch-action="pan-y"
 auto-rotate
 shadow-intensity="1"
 exposure="1"
 environment-image="neutral"
 alt="AI generated 3D model">
</model-viewer>

<p>এক আঙুলে ঘোরাও, দুই আঙুলে জুম করো।</p>

<a id="download" class="download hidden"
 href="#" download>GLB ডাউনলোড</a>
</section>
</main>

<script>
const form = document.getElementById("form");
const statusBox = document.getElementById("status");
const progress = document.getElementById("progress");
const submit = document.getElementById("submit");
const viewer = document.getElementById("viewer");
const viewerPanel = document.getElementById("viewer-panel");
const download = document.getElementById("download");

let active = false;

form.addEventListener("submit", async event => {
  event.preventDefault();
  if (active) return;

  const data = new FormData(form);

  for (const key of ["front", "left", "back", "right"]) {
    const input = form.elements[key];
    if (!input.files.length) data.delete(key);
  }

  active = true;
  submit.disabled = true;
  viewerPanel.classList.add("hidden");
  download.classList.add("hidden");
  viewer.removeAttribute("src");
  progress.value = 0;

  try {
    const response = await fetch("/api/jobs", {
      method: "POST",
      body: data
    });

    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.detail || "Job শুরু হয়নি");
    }

    const jid = result.jid;
    statusBox.textContent = "AI কাজ শুরু হয়েছে...";

    for (;;) {
      await new Promise(resolve => setTimeout(resolve, 3000));

      const check = await fetch("/api/jobs/" + jid);
      const job = await check.json();

      if (!check.ok) {
        throw new Error(job.detail || "Job status পাওয়া যায়নি");
      }

      progress.value = job.progress || 0;
      statusBox.textContent =
        job.message + "\nঅগ্রগতি: " + progress.value + "%";

      if (job.status === "failed") {
        throw new Error(job.message || "AI মডেল তৈরি ব্যর্থ");
      }

      if (job.status === "completed") {
        if (!job.model_url) {
          throw new Error("GLB URL পাওয়া যায়নি");
        }

        const modelResponse = await fetch(job.model_url);

        if (!modelResponse.ok) {
          throw new Error("GLB ডাউনলোড যাচাই ব্যর্থ");
        }

        const blob = await modelResponse.blob();

        if (blob.size < 1000) {
          throw new Error("GLB ফাইল অসম্পূর্ণ");
        }

        const bytes = new Uint8Array(
          await blob.slice(0, 4).arrayBuffer()
        );

        if (String.fromCharCode(...bytes) !== "glTF") {
          throw new Error("এটি বৈধ GLB ফাইল নয়");
        }

        const objectURL = URL.createObjectURL(blob);
        viewer.src = objectURL;

        viewerPanel.classList.remove("hidden");
        download.href = job.model_url;
        download.classList.remove("hidden");

        statusBox.textContent =
          "সফল! আসল GLB তৈরি ও যাচাই সম্পন্ন হয়েছে।";

        break;
      }
    }

  } catch (error) {
    statusBox.textContent = "সমস্যা: " + error.message;
  } finally {
    active = false;
    submit.disabled = false;
  }
});
</script>
</body>
</html>
"""
