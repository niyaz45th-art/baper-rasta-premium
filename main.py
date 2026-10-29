import os, uuid, asyncio
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import requests

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
JOBS_DIR = Path("jobs")
JOBS_DIR.mkdir(exist_ok=True)
JOBS = {}

TRIPO_API_KEY = os.getenv("TRIPO_API_KEY","").strip()
print(f"TRIPO KEY SET: {bool(TRIPO_API_KEY)} len={len(TRIPO_API_KEY)}")

FRONTEND_HTML = """<!DOCTYPE html><html lang="bn"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>BAPER RASTA REAL 3D</title><script type="module" src="https://unpkg.com/@google/model-viewer@3.4.0/dist/model-viewer.min.js"></script><style>*{margin:0;padding:0;box-sizing:border-box;font-family:system-ui}body{background:#07070a;color:#fff}.top{padding:14px 18px;display:flex;justify-content:space-between;background:#101016;border-bottom:1px solid #222}.wrap{max-width:520px;margin:0 auto;padding:18px}.card{background:#13131b;border:1px solid #23232f;border-radius:24px;padding:22px;margin-top:18px}.title{font-size:28px;font-weight:900;text-align:center}.title span{background:linear-gradient(90deg,#8b5cf6,#ec4899);-webkit-background-clip:text;-webkit-text-fill-color:transparent}.sub{color:#9ca3af;text-align:center;font-size:14px;margin:10px 0 18px}.btn{width:100%;margin-top:14px;background:#8b5cf6;border:none;padding:15px;border-radius:14px;color:#fff;font-weight:800;font-size:16px;cursor:pointer}.btn:disabled{opacity:.5}.status{margin-top:14px;background:#0e0e16;border:1px solid #23232f;border-radius:12px;padding:12px;font-size:13px;display:none;white-space:pre-wrap}.done{margin-top:14px;display:none}.done a{display:block;background:#10b981;color:#fff;text-align:center;padding:14px;border-radius:12px;text-decoration:none;font-weight:800;margin-top:10px}model-viewer{width:100%;height:380px;background:#0a0a12;border-radius:16px;margin-top:14px}</style></head><body><div class="top"><div style="font-weight:900">BAPER <b style="color:#8b5cf6">RASTA</b> PREMIUM</div><div style="font-size:11px;background:#10b981;color:#000;padding:4px 10px;border-radius:20px;font-weight:800">● LIVE • REAL 3D</div></div><div class="wrap"><div class="title">ছবি থেকে <span>REAL 3D</span></div><div class="sub">আপলোড করো — আসল GLB হবে — এখানেই ঘুরিয়ে দেখো</div><div class="card"><input type="file" id="file" accept="image/*" style="width:100%;padding:10px;background:#0a0a12;border:1px dashed #333;border-radius:10px;color:#fff"><img id="preview" style="display:none;width:100%;border-radius:12px;margin-top:12px;max-height:240px;object-fit:contain;background:#000"><input id="label" style="width:100%;margin-top:12px;background:#0a0a12;border:1px solid #252538;border-radius:12px;padding:12px;color:#fff" placeholder="নাম: chair" value="my-model"><button class="btn" id="genBtn">✨ 3D বানাও এখন</button><div class="status" id="status"></div><div class="done" id="done"><div style="font-weight:800">✅ আসল মডেল রেডি! নিচে ঘুরিয়ে দেখো 👇</div><model-viewer id="viewer" ar auto-rotate camera-controls shadow-intensity="1" exposure="1" environment-image="neutral"></model-viewer><div style="font-size:12px;color:#9ca3af;text-align:center;margin-top:8px">👆 এক আঙুলে ঘুরাও • দুই আঙুলে জুম</div><a id="dlBtn" href="#" target="_blank">⬇️ GLB ডাউনলোড</a></div></div></div><script>const fileInput=document.getElementById('file');const preview=document.getElementById('preview');const genBtn=document.getElementById('genBtn');const statusBox=document.getElementById('status');const doneBox=document.getElementById('done');const dlBtn=document.getElementById('dlBtn');const viewer=document.getElementById('viewer');fileInput.addEventListener('change',function(){const f=this.files[0];if(f){preview.src=URL.createObjectURL(f);preview.style.display='block';}});async function poll(jid){let t=0;while(t<200){try{const r=await fetch('/api/jobs/'+jid);const d=await r.json();const st=d.status||'processing';const pr=d.progress||'';statusBox.innerText='⏳ স্ট্যাটাস: '+st+' '+pr+'%\\nID: '+jid+'\\n'+(d.message||'Tripo AI 30-60s...');if(st==='completed'||st==='success'){const lr=await fetch('/api/jobs/'+jid+'/link');const ld=await lr.json();const url=ld.url||'/api/download/'+jid;const full=url.startsWith('http')?url:location.origin+url;dlBtn.href=full;viewer.src=full;doneBox.style.display='block';statusBox.innerText+='\\n\\n✅ হয়ে গেছে! নিচে 3D দেখো';break;}if(st==='failed'){statusBox.innerText+='\\n❌ ফেইল: '+(d.message||'');break;}}catch(e){statusBox.innerText='Poll error: '+e.message;}await new Promise(r=>setTimeout(r,3000));t++;}genBtn.disabled=false;genBtn.innerText='✨ 3D বানাও এখন';}genBtn.addEventListener('click',async function(){const file=fileInput.files[0];if(!file){alert('আগে ছবি নাও!');return;}genBtn.disabled=true;genBtn.innerText='⏳ আপলোড হচ্ছে...';statusBox.style.display='block';statusBox.innerText='🚀 আপলোড হচ্ছে...\\n'+file.name;doneBox.style.display='none';const fd=new FormData();fd.append('files',file);fd.append('labels','test');try{const res=await fetch('/api/jobs',{method:'POST',body:fd});const data=await res.json();if(!res.ok)throw new Error(JSON.stringify(data));const jid=data.jid;statusBox.innerText='✅ Job: '+jid+'\\nTripo তে পাঠানো হয়েছে...';genBtn.innerText='⏳ 3D বানানো হচ্ছে...';poll(jid);}catch(e){statusBox.innerText='❌ Error:\\n'+e.message;genBtn.disabled=false;genBtn.innerText='✨ 3D বানাও এখন';}});</script></body></html>"""

@app.get("/", response_class=HTMLResponse)
async def home(): return FRONTEND_HTML

@app.get("/api/health")
async def health(): return {"status":"ok","tripo_configured": bool(TRIPO_API_KEY), "key_len": len(TRIPO_API_KEY) if TRIPO_API_KEY else 0}

@app.post("/api/jobs")
async def create_job(files: UploadFile = File(None)):
    if not files: raise HTTPException(400,"No file")
    if not TRIPO_API_KEY: raise HTTPException(500,"TRIPO_API_KEY Render Environment এ সেট নাই")
    jid = str(uuid.uuid4())[:8]
    job_dir = JOBS_DIR / jid
    job_dir.mkdir(exist_ok=True)
    img_path = job_dir / "input.jpg"
    img_path.write_bytes(await files.read())
    JOBS[jid] = {"status":"queued","progress":5,"message":"Queued - SDK init"}

    async def process_job():
        try:
            from tripo3d import TripoClient
            JOBS[jid]["status"]="processing"; JOBS[jid]["progress"]=10; JOBS[jid]["message"]="Tripo SDK: uploading..."
            async with TripoClient(api_key=TRIPO_API_KEY) as client:
                JOBS[jid]["message"]="Tripo SDK: image_to_model..."
                task_id = await client.image_to_model(image=str(img_path), model_version="v2.5-20250123", texture_quality="standard", face_limit=40000)
                JOBS[jid]["tripo_task"]=task_id; JOBS[jid]["progress"]=30; JOBS[jid]["message"]=f"Task {task_id} - processing 30-60s"
                task = await client.wait_for_task(task_id, timeout=300, verbose=True)
                status = str(task.status)
                if "SUCCESS" in status.upper() or "COMPLETED" in status.upper():
                    # download
                    try:
                        files_map = await client.download_task_models(task, str(job_dir))
                        # files_map is dict
                        glb_path = None
                        for k,v in files_map.items():
                            if v and str(v).endswith(".glb"): glb_path = Path(v)
                        if glb_path and glb_path.exists():
                            (job_dir / "model.glb").write_bytes(glb_path.read_bytes())
                            JOBS[jid]["status"]="completed"; JOBS[jid]["progress"]=100; JOBS[jid]["message"]="Completed!"; JOBS[jid]["model_url"]=f"/api/download/{jid}"
                        else:
                            # fallback get url from task output
                            output = getattr(task, 'output', {}) or {}
                            if isinstance(output, dict):
                                model_url = output.get("pbr_model") or output.get("model") or ""
                                if model_url:
                                    r = requests.get(model_url, timeout=60)
                                    if r.ok: (job_dir / "model.glb").write_bytes(r.content)
                                    JOBS[jid]["model_url"]=model_url
                            JOBS[jid]["status"]="completed"; JOBS[jid]["progress"]=100
                    except Exception as de:
                        JOBS[jid]["status"]="completed"; JOBS[jid]["progress"]=100; JOBS[jid]["message"]=f"Completed but download issue: {de}"
                        # try get url from task
                        try:
                            out = task.output if hasattr(task,'output') else {}
                            if isinstance(out, dict) and out.get("model"):
                                JOBS[jid]["model_url"]=out.get("model")
                        except: pass
                else:
                    JOBS[jid]["status"]="failed"; JOBS[jid]["message"]=f"Task status {status}"
        except Exception as e:
            import traceback; traceback.print_exc()
            JOBS[jid]["status"]="failed"; JOBS[jid]["message"]=str(e)

    asyncio.create_task(process_job())
    return {"jid": jid}

@app.get("/api/jobs/{jid}")
async def get_job(jid: str):
    job = JOBS.get(jid)
    if not job: raise HTTPException(404,"Job not found")
    return {"jid": jid, **job}

@app.get("/api/jobs/{jid}/link")
async def get_link(jid: str):
    job = JOBS.get(jid)
    if job and job.get("model_url"): return {"url": job["model_url"]}
    fp = JOBS_DIR / jid / "model.glb"
    if fp.exists(): return {"url": f"/api/download/{jid}"}
    return {"url": f"/api/download/{jid}"}

@app.get("/api/download/{jid}")
async def download(jid: str):
    job = JOBS.get(jid)
    fp = JOBS_DIR / jid / "model.glb"
    if job and job.get("model_url") and job["model_url"].startswith("http"):
        if fp.exists() and fp.stat().st_size>1000:
            return FileResponse(fp, media_type="model/gltf-binary", filename=f"{jid}.glb")
        return RedirectResponse(job["model_url"])
    if fp.exists(): return FileResponse(fp, media_type="model/gltf-binary", filename=f"{jid}.glb")
    raise HTTPException(404, f"Not ready: {job}")
