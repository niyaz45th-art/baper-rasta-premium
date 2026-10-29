import os, uuid, asyncio, base64
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import requests

app = FastAPI(title="BAPER RASTA V3")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
JOBS_DIR = Path("jobs")
JOBS_DIR.mkdir(exist_ok=True)
JOBS = {}
TRIPO_API_KEY = os.getenv("TRIPO_API_KEY","").strip()

FRONT = """<!DOCTYPE html><html lang="bn"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>BAPER RASTA V3</title><script type="module" src="https://unpkg.com/@google/model-viewer@3.4.0/dist/model-viewer.min.js"></script><style>*{margin:0;padding:0;box-sizing:border-box;font-family:system-ui}body{background:#07070a;color:#fff}.top{padding:14px 18px;display:flex;justify-content:space-between;background:#101016;border-bottom:1px solid #222}.wrap{max-width:520px;margin:0 auto;padding:18px}.card{background:#13131b;border:1px solid #23232f;border-radius:24px;padding:22px;margin-top:18px}.btn{width:100%;margin-top:14px;background:#8b5cf6;border:none;padding:15px;border-radius:14px;color:#fff;font-weight:800;font-size:16px;cursor:pointer}.status{margin-top:14px;background:#0e0e16;border:1px solid #23232f;border-radius:12px;padding:12px;font-size:13px;display:none;white-space:pre-wrap}.done{margin-top:14px;display:none}model-viewer{width:100%;height:380px;background:#0a0a12;border-radius:16px;margin-top:14px}</style></head><body><div class="top"><div style="font-weight:900">BAPER <b style="color:#8b5cf6">RASTA</b> PREMIUM</div><div style="font-size:11px;background:#10b981;color:#000;padding:4px 10px;border-radius:20px;font-weight:800">● LIVE • V3 REAL 3D</div></div><div class="wrap"><div style="font-size:28px;font-weight:900;text-align:center">ছবি থেকে <span style="background:linear-gradient(90deg,#8b5cf6,#ec4899);-webkit-background-clip:text;-webkit-text-fill-color:transparent">REAL 3D V3</span></div><div class="card"><input type="file" id="file" accept="image/*" style="width:100%;padding:10px;background:#0a0a12;border:1px dashed #333;border-radius:10px;color:#fff"><img id="preview" style="display:none;width:100%;border-radius:12px;margin-top:12px;max-height:240px;object-fit:contain;background:#000"><button class="btn" id="genBtn">✨ 3D বানাও এখন (V3)</button><div class="status" id="status"></div><div class="done" id="done"><div style="font-weight:800">✅ আসল মডেল রেডি!</div><model-viewer id="viewer" ar auto-rotate camera-controls shadow-intensity="1" exposure="1"></model-viewer><a id="dlBtn" href="#" target="_blank" style="display:block;background:#10b981;color:#fff;text-align:center;padding:14px;border-radius:12px;text-decoration:none;font-weight:800;margin-top:10px">⬇️ GLB ডাউনলোড</a></div></div></div><script>const fileInput=document.getElementById('file'),preview=document.getElementById('preview'),genBtn=document.getElementById('genBtn'),statusBox=document.getElementById('status'),doneBox=document.getElementById('done'),dlBtn=document.getElementById('dlBtn'),viewer=document.getElementById('viewer');fileInput.addEventListener('change',function(){const f=this.files[0];if(f){preview.src=URL.createObjectURL(f);preview.style.display='block';}});async function poll(jid){let t=0;while(t<200){try{const r=await fetch('/api/jobs/'+jid);const d=await r.json();statusBox.innerText='⏳ '+d.status+' '+ (d.progress||'') +'%\\n'+(d.message||'');if(d.status==='completed'){const lr=await fetch('/api/jobs/'+jid+'/link');const ld=await lr.json();const url=ld.url;const full=url.startsWith('http')?url:location.origin+url;dlBtn.href=full;viewer.src=full;doneBox.style.display='block';statusBox.innerText+='\\n✅ Done!';break;}if(d.status==='failed'){statusBox.innerText+='\\n❌ '+d.message;break;}}catch(e){}await new Promise(r=>setTimeout(r,3000));t++;}genBtn.disabled=false;genBtn.innerText='✨ 3D বানাও এখন (V3)';}genBtn.addEventListener('click',async function(){const file=fileInput.files[0];if(!file){alert('ছবি নাও!');return;}genBtn.disabled=true;genBtn.innerText='⏳ আপলোড...';statusBox.style.display='block';statusBox.innerText='🚀 Uploading...';doneBox.style.display='none';const fd=new FormData();fd.append('files',file);try{const res=await fetch('/api/jobs',{method:'POST',body:fd});const data=await res.json();if(!res.ok)throw new Error(JSON.stringify(data));poll(data.jid);}catch(e){statusBox.innerText='❌ '+e.message;genBtn.disabled=false;}});</script></body></html>"""

@app.get("/", response_class=HTMLResponse)
async def home(): return FRONT

@app.get("/api/health")
async def health(): return {"v3": True, "key_set": bool(TRIPO_API_KEY), "key_len": len(TRIPO_API_KEY)}

def v3_create_task(image_path: Path):
    if not TRIPO_API_KEY: raise Exception("TRIPO_API_KEY not set")
    headers = {"Authorization": f"Bearer {TRIPO_API_KEY}"}
    # 1. Upload file to V3 /v3/files
    with open(image_path, "rb") as f:
        r = requests.post("https://api.tripo3d.ai/v3/files", headers=headers, files={"file": f}, timeout=60)
    print("V3 FILES:", r.status_code, r.text[:800])
    r.raise_for_status()
    j = r.json()
    # V3 returns file_token in different fields
    data = j.get("data") or j
    file_token = data.get("file_token") or data.get("id") or data.get("file") or data.get("token")
    if isinstance(file_token, dict):
        file_token = file_token.get("file_token") or file_token.get("id")
    if not file_token:
        raise Exception(f"V3 file_token not found: {r.text[:500]}")
    # 2. Create image-to-model task V3
    payload = {
        "type": "image_to_model",  # some V3 still accepts but we try without type too
        "file": {"file_token": file_token, "type": "image"},
        "model_version": "v2.5-20250123",
        "texture_quality": "standard"
    }
    # Primary V3 endpoint
    r2 = requests.post("https://api.tripo3d.ai/v3/generation/image-to-model", headers={**headers, "Content-Type": "application/json"}, json={
        "file_token": file_token,
        "model_version": "v2.5-20250123"
    }, timeout=60)
    print("V3 GEN1:", r2.status_code, r2.text[:800])
    if r2.status_code != 200:
        # fallback with file param
        r2 = requests.post("https://api.tripo3d.ai/v3/generation/image-to-model", headers={**headers, "Content-Type": "application/json"}, json=payload, timeout=60)
        print("V3 GEN2:", r2.status_code, r2.text[:800])
    r2.raise_for_status()
    jd = r2.json()
    d = jd.get("data") or jd
    task_id = d.get("task_id") or d.get("id") or d.get("taskId")
    if not task_id: raise Exception(f"task_id not found {r2.text[:600]}")
    return task_id

def v3_get_task(task_id: str):
    headers = {"Authorization": f"Bearer {TRIPO_API_KEY}"}
    r = requests.get(f"https://api.tripo3d.ai/v3/tasks/{task_id}", headers=headers, timeout=30)
    print("V3 TASK:", r.status_code, r.text[:800])
    r.raise_for_status()
    return r.json()

@app.post("/api/jobs")
async def create_job(files: UploadFile = File(None)):
    if not files: raise HTTPException(400,"No file")
    jid = str(uuid.uuid4())[:8]
    jd = JOBS_DIR / jid
    jd.mkdir(exist_ok=True)
    img = jd / "input.jpg"
    img.write_bytes(await files.read())
    JOBS[jid] = {"status":"queued","progress":5,"message":"V3 queued"}
    async def proc():
        try:
            JOBS[jid]["status"]="processing"; JOBS[jid]["progress"]=10; JOBS[jid]["message"]="V3 upload..."
            task_id = await asyncio.to_thread(v3_create_task, img)
            JOBS[jid]["tripo_task"]=task_id; JOBS[jid]["progress"]=25; JOBS[jid]["message"]=f"V3 Task {task_id}"
            for _ in range(200):
                await asyncio.sleep(3)
                info = await asyncio.to_thread(v3_get_task, task_id)
                d = info.get("data") or info
                st = str(d.get("status") or d.get("state") or "").lower()
                prog = d.get("progress") or 0
                try: JOBS[jid]["progress"]=int(prog) if prog else min(95, JOBS[jid]["progress"]+1)
                except: pass
                if st in ["success","completed","succeeded"]:
                    out = d.get("output") or {}
                    url = out.get("pbr_model") or out.get("model") or out.get("glb") or out.get("base_model") or ""
                    if url:
                        JOBS[jid]["model_url"]=url
                        try:
                            rr = requests.get(url, timeout=60)
                            if rr.ok: (jd / "model.glb").write_bytes(rr.content)
                        except: pass
                    JOBS[jid]["status"]="completed"; JOBS[jid]["progress"]=100; JOBS[jid]["message"]="V3 Completed!"
                    break
                if st in ["failed","error","cancelled"]:
                    JOBS[jid]["status"]="failed"; JOBS[jid]["message"]=str(d); break
        except Exception as e:
            import traceback; traceback.print_exc()
            JOBS[jid]["status"]="failed"; JOBS[jid]["message"]=str(e)
    asyncio.create_task(proc())
    return {"jid": jid}

@app.get("/api/jobs/{jid}")
async def get_job(jid: str):
    job = JOBS.get(jid)
    if not job: raise HTTPException(404,"not found")
    return {"jid": jid, **job}

@app.get("/api/jobs/{jid}/link")
async def get_link(jid: str):
    job = JOBS.get(jid)
    if job and job.get("model_url"): return {"url": job["model_url"]}
    fp = JOBS_DIR / jid / "model.glb"
    if fp.exists(): return {"url": f"/api/download/{jid}"}
    return {"url": f"/api/download/{jid}"}

@app.get("/api/download/{jid}")
async def dl(jid: str):
    job = JOBS.get(jid)
    fp = JOBS_DIR / jid / "model.glb"
    if job and job.get("model_url") and job["model_url"].startswith("http"):
        if fp.exists() and fp.stat().st_size>1000:
            return FileResponse(fp, media_type="model/gltf-binary", filename=f"{jid}.glb")
        return RedirectResponse(job["model_url"])
    if fp.exists(): return FileResponse(fp, media_type="model/gltf-binary", filename=f"{jid}.glb")
    raise HTTPException(404,"not ready")
