import os, uuid, asyncio
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import requests

# TRY SDK - V3 compatible
try:
    from tripo3d import TripoClient, TaskStatus
    HAS_SDK = True
except:
    HAS_SDK = False

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
JOBS_DIR = Path("jobs"); JOBS_DIR.mkdir(exist_ok=True)
JOBS = {}
TRIPO_API_KEY = os.getenv("TRIPO_API_KEY","").strip()

FRONT = """<!DOCTYPE html><html lang="bn"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>BAPER RASTA V3</title><script type="module" src="https://unpkg.com/@google/model-viewer@3.4.0/dist/model-viewer.min.js"></script><style>*{margin:0;padding:0;box-sizing:border-box;font-family:system-ui}body{background:#07070a;color:#fff}.top{padding:14px 18px;display:flex;justify-content:space-between;background:#101016;border-bottom:1px solid #222}.wrap{max-width:520px;margin:0 auto;padding:18px}.card{background:#13131b;border:1px solid #23232f;border-radius:24px;padding:22px;margin-top:18px}.btn{width:100%;margin-top:14px;background:#8b5cf6;border:none;padding:15px;border-radius:14px;color:#fff;font-weight:800;font-size:16px;cursor:pointer}.status{margin-top:14px;background:#0e0e16;border:1px solid #23232f;border-radius:12px;padding:12px;font-size:13px;display:none;white-space:pre-wrap}.done{margin-top:14px;display:none}model-viewer{width:100%;height:380px;background:#0a0a12;border-radius:16px;margin-top:14px}</style></head><body><div class="top"><div style="font-weight:900">BAPER <b style="color:#8b5cf6">RASTA</b> PREMIUM</div><div style="font-size:11px;background:#10b981;color:#000;padding:4px 10px;border-radius:20px;font-weight:800">● LIVE • V3 REAL 3D</div></div><div class="wrap"><div style="font-size:28px;font-weight:900;text-align:center">ছবি থেকে <span style="background:linear-gradient(90deg,#8b5cf6,#ec4899);-webkit-background-clip:text;-webkit-text-fill-color:transparent">REAL 3D V3</span></div><div class="card"><input type="file" id="file" accept="image/*" style="width:100%;padding:10px;background:#0a0a12;border:1px dashed #333;border-radius:10px;color:#fff"><img id="preview" style="display:none;width:100%;border-radius:12px;margin-top:12px;max-height:240px;object-fit:contain;background:#000"><button class="btn" id="genBtn">✨ 3D বানাও এখন (V3)</button><div class="status" id="status"></div><div class="done" id="done"><div style="font-weight:800">✅ আসল মডেল রেডি!</div><model-viewer id="viewer" ar auto-rotate camera-controls shadow-intensity="1" exposure="1"></model-viewer><a id="dlBtn" href="#" target="_blank" style="display:block;background:#10b981;color:#fff;text-align:center;padding:14px;border-radius:12px;text-decoration:none;font-weight:800;margin-top:10px">⬇️ GLB ডাউনলোড</a></div></div></div><script>const fileInput=document.getElementById('file'),preview=document.getElementById('preview'),genBtn=document.getElementById('genBtn'),statusBox=document.getElementById('status'),doneBox=document.getElementById('done'),dlBtn=document.getElementById('dlBtn'),viewer=document.getElementById('viewer');fileInput.addEventListener('change',function(){const f=this.files[0];if(f){preview.src=URL.createObjectURL(f);preview.style.display='block';}});async function poll(jid){let t=0;while(t<200){try{const r=await fetch('/api/jobs/'+jid);const d=await r.json();statusBox.innerText='⏳ '+d.status+' '+(d.progress||'')+'%\\n'+(d.message||'');if(d.status==='completed'){const lr=await fetch('/api/jobs/'+jid+'/link');const ld=await lr.json();const url=ld.url;const full=url.startsWith('http')?url:location.origin+url;dlBtn.href=full;viewer.src=full;doneBox.style.display='block';statusBox.innerText+='\\n✅ Done!';break;}if(d.status==='failed'){statusBox.innerText+='\\n❌ '+d.message;break;}}catch(e){}await new Promise(r=>setTimeout(r,3000));t++;}genBtn.disabled=false;genBtn.innerText='✨ 3D বানাও এখন (V3)';}genBtn.addEventListener('click',async function(){const file=fileInput.files[0];if(!file){alert('ছবি নাও!');return;}genBtn.disabled=true;genBtn.innerText='⏳ আপলোড...';statusBox.style.display='block';statusBox.innerText='🚀 Uploading to Tripo V3...';doneBox.style.display='none';const fd=new FormData();fd.append('files',file);try{const res=await fetch('/api/jobs',{method:'POST',body:fd});const data=await res.json();if(!res.ok)throw new Error(JSON.stringify(data));poll(data.jid);}catch(e){statusBox.innerText='❌ '+e.message;genBtn.disabled=false;}});</script></body></html>"""

@app.get("/", response_class=HTMLResponse)
async def home(): return FRONT
@app.get("/api/health")
async def health(): return {"v3":True,"has_sdk":HAS_SDK,"key_set":bool(TRIPO_API_KEY),"key_len":len(TRIPO_API_KEY)}

async def run_tripo_sdk(image_path: Path, job_dir: Path):
    # OFFICIAL Tripo V3 SDK way - this auto handles upload
    async with TripoClient(api_key=TRIPO_API_KEY) as client:
        task_id = await client.image_to_model(
            image=str(image_path),
            model_version="v2.5-20250123",
            texture_quality="standard"
        )
        print("V3 Task:", task_id)
        task = await client.wait_for_task(task_id, verbose=True)
        print("V3 Result:", task)
        if task.status == TaskStatus.SUCCESS or str(task.status).lower()=="success":
            # download
            files = await client.download_task_models(task, str(job_dir))
            print("Downloaded:", files)
            # find glb
            for p in job_dir.glob("*.glb"):
                return str(p), task_id
            for p in job_dir.glob("**/*.glb"):
                return str(p), task_id
            # if SDK returns URLs
            if hasattr(task, 'output'):
                out = task.output or {}
                return out.get('pbr_model') or out.get('model'), task_id
        raise Exception(f"Task failed: {task}")

@app.post("/api/jobs")
async def create_job(files: UploadFile = File(None)):
    if not files: raise HTTPException(400,"No file")
    if not TRIPO_API_KEY: raise HTTPException(500,"TRIPO_API_KEY missing")
    jid = str(uuid.uuid4())[:8]
    jd = JOBS_DIR / jid; jd.mkdir(exist_ok=True)
    img = jd / "input.jpg"; img.write_bytes(await files.read())
    JOBS[jid] = {"status":"queued","progress":5,"message":"V3 queued with SDK"}
    async def proc():
        try:
            JOBS[jid]["status"]="processing"; JOBS[jid]["progress"]=15; JOBS[jid]["message"]="Tripo V3 generating (30-60s)..."
            if not HAS_SDK:
                raise Exception("tripo3d SDK not installed")
            result_path, task_id = await run_tripo_sdk(img, jd)
            JOBS[jid]["tripo_task"]=task_id
            if result_path and result_path.startswith("http"):
                JOBS[jid]["model_url"]=result_path
                # try download
                try:
                    r = requests.get(result_path, timeout=60)
                    if r.ok: (jd/"model.glb").write_bytes(r.content)
                except: pass
            else:
                # local file
                if Path(result_path).exists():
                    # copy to model.glb
                    import shutil
                    shutil.copy(result_path, jd/"model.glb")
            JOBS[jid]["status"]="completed"; JOBS[jid]["progress"]=100; JOBS[jid]["message"]="Completed V3!"
        except Exception as e:
            import traceback; traceback.print_exc()
            JOBS[jid]["status"]="failed"; JOBS[jid]["message"]=str(e)[:1000]
    asyncio.create_task(proc())
    return {"jid": jid}

@app.get("/api/jobs/{jid}")
async def get_job(jid: str):
    job = JOBS.get(jid)
    if not job: raise HTTPException(404,"not found")
    return {"jid":jid, **job}

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
