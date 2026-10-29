import os, uuid, asyncio, requests
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

app = FastAPI(title="Baper Rasta Premium REAL 3D Viewer")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
BASE = Path(".")
JOBS_DIR = BASE / "jobs"
JOBS_DIR.mkdir(exist_ok=True)
JOBS = {}
FRONTEND_HTML = """
<!DOCTYPE html>
<html lang="bn">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Baper Rasta Premium - REAL 3D Viewer</title>
<script type="module" src="https://unpkg.com/@google/model-viewer@3.4.0/dist/model-viewer.min.js"></script>
<style>
*{margin:0;padding:0;box-sizing:border-box;font-family:system-ui}
body{background:#07070a;color:#fff;min-height:100vh}
.top{padding:14px 18px;display:flex;justify-content:space-between;background:#101016;border-bottom:1px solid #222}
.logo{font-weight:900}.logo b{color:#8b5cf6}
.wrap{max-width:520px;margin:0 auto;padding:18px}
.card{background:#13131b;border:1px solid #23232f;border-radius:24px;padding:22px;margin-top:18px}
.title{font-size:28px;font-weight:900;text-align:center}.title span{background:linear-gradient(90deg,#8b5cf6,#ec4899);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.sub{color:#9ca3af;text-align:center;font-size:14px;margin:10px 0 18px}
.input{width:100%;margin-top:12px;background:#0a0a12;border:1px solid #252538;border-radius:12px;padding:12px;color:#fff}
.btn{width:100%;margin-top:14px;background:#8b5cf6;border:none;padding:15px;border-radius:14px;color:#fff;font-weight:800;font-size:16px;cursor:pointer}
.btn:disabled{opacity:0.5}
.status{margin-top:14px;background:#0e0e16;border:1px solid #23232f;border-radius:12px;padding:12px;font-size:13px;display:none;white-space:pre-wrap}
.done{margin-top:14px;display:none}
.done a{display:block;background:#10b981;color:#fff;text-align:center;padding:14px;border-radius:12px;text-decoration:none;font-weight:800;margin-top:10px}
.small{color:#8b5cf6;word-break:break-all;font-size:12px;background:#0a0a12;padding:8px;border-radius:8px;display:block;margin-top:8px}
model-viewer{width:100%;height:380px;background:#0a0a12;border-radius:16px;margin-top:14px}
.view-hint{font-size:12px;color:#9ca3af;text-align:center;margin-top:8px}
</style>
</head>
<body>
<div class="top"><div class="logo">BAPER <b>RASTA</b> PREMIUM</div><div style="font-size:11px;background:#10b981;color:#000;padding:4px 10px;border-radius:20px;font-weight:800">● LIVE • 3D VIEWER</div></div>
<div class="wrap">
<div class="title">ছবি থেকে <span>REAL 3D</span></div>
<div class="sub">আপলোড করো — GLB হবে — এখানেই ঘুরিয়ে দেখো</div>
<div class="card">
<input type="file" id="file" accept="image/*" style="width:100%;padding:10px;background:#0a0a12;border:1px dashed #333;border-radius:10px;color:#fff">
<img id="preview" style="display:none;width:100%;border-radius:12px;margin-top:12px;max-height:240px;object-fit:contain;background:#000">
<input id="label" class="input" placeholder="নাম: chair" value="my-model">
<button class="btn" id="genBtn">✨ 3D বানাও এখন</button>
<div class="status" id="status"></div>
<div class="done" id="done">
<div style="font-weight:800;font-size:16px">✅ মডেল রেডি! নিচে ঘুরিয়ে দেখো 👇</div>
<model-viewer id="viewer" ar auto-rotate camera-controls shadow-intensity="1" exposure="1" environment-image="neutral" alt="3D Model"></model-viewer>
<div class="view-hint">👆 এক আঙুলে ঘুরাও • দুই আঙুলে জুম • ডাবল ট্যাপে রিসেট</div>
<a id="dlBtn" href="#" target="_blank">⬇️ GLB ডাউনলোড</a>
<a id="arBtn" href="#" style="background:#8b5cf6">📱 ফোনে AR তে দেখো</a>
<a id="copyBtn" href="#" style="background:#23232f">🔗 লিংক কপি</a>
<span class="small" id="linkTxt"></span>
</div>
</div>
</div>
<script>
const fileInput=document.getElementById('file');
const preview=document.getElementById('preview');
const genBtn=document.getElementById('genBtn');
const statusBox=document.getElementById('status');
const doneBox=document.getElementById('done');
const linkTxt=document.getElementById('linkTxt');
const dlBtn=document.getElementById('dlBtn');
const viewer=document.getElementById('viewer');
const copyBtn=document.getElementById('copyBtn');
fileInput.addEventListener('change',function(){const f=this.files[0];if(f){preview.src=URL.createObjectURL(f);preview.style.display='block';}});
async function poll(jid){let t=0;while(t<200){try{const r=await fetch('/api/jobs/'+jid);const d=await r.json();const st=d.status||'processing';const pr=d.progress||'';statusBox.innerText='⏳ স্ট্যাটাস: '+st+' '+pr+'%\\nID: '+jid+'\\n'+(d.message||'Tripo AI 30-60s...');if(st==='completed'||st==='success'){const lr=await fetch('/api/jobs/'+jid+'/link');const ld=await lr.json();const url=ld.url||'/api/download/'+jid;const full=url.startsWith('http')?url:location.origin+url;linkTxt.innerText=full;dlBtn.href=full;viewer.src=full;viewer.style.display='block';doneBox.style.display='block';statusBox.innerText+='\\n\\n✅ হয়ে গেছে! নিচে 3D দেখো';break;}if(st==='failed'){statusBox.innerText+='\\n❌ ফেইল: '+(d.message||'');break;}}catch(e){statusBox.innerText='Poll error: '+e.message;}await new Promise(r=>setTimeout(r,3000));t++;}genBtn.disabled=false;genBtn.innerText='✨ 3D বানাও এখন';}
genBtn.addEventListener('click',async function(){const file=fileInput.files[0];if(!file){alert('আগে Choose File এ চাপ দিয়ে একটা ছবি নাও ভাই!');return;}const label=document.getElementById('label').value||'my-model';genBtn.disabled=true;genBtn.innerText='⏳ আপলোড হচ্ছে...';statusBox.style.display='block';statusBox.innerText='🚀 আপলোড হচ্ছে...\\n'+file.name;doneBox.style.display='none';viewer.style.display='none';const fd=new FormData();fd.append('files',file);fd.append('labels',label);fd.append('preset','high');try{const res=await fetch('/api/jobs',{method:'POST',body:fd});const text=await res.text();let data;try{data=JSON.parse(text);}catch(e){throw new Error(text);}if(!res.ok)throw new Error(JSON.stringify(data));const jid=data.jid;statusBox.innerText='✅ Job: '+jid+'\\nTripo তে পাঠানো হয়েছে...';genBtn.innerText='⏳ 3D বানানো হচ্ছে...';poll(jid);}catch(e){statusBox.innerText='❌ Error:\\n'+e.message;alert(e.message);genBtn.disabled=false;genBtn.innerText='✨ 3D বানাও এখন';}});
copyBtn.addEventListener('click',function(e){e.preventDefault();navigator.clipboard.writeText(linkTxt.innerText).then(()=>{copyBtn.innerText='✅ কপি হয়েছে!';setTimeout(()=>copyBtn.innerText='🔗 লিংক কপি',1500);});});
</script>
</body>
</html>
"""

TRIPO_API_KEY = os.getenv("TRIPO_API_KEY", "").strip()

def tripo_create_task(image_path: Path):
    if not TRIPO_API_KEY:
        return None
    try:
        url = "https://api.tripo3d.ai/v2/openapi/task"
        headers = {"Authorization": f"Bearer {TRIPO_API_KEY}"}
        with open(image_path, "rb") as f:
            files = {"file": f}
            data = {"type": "image_to_model"}
            resp = requests.post(url, headers=headers, files=files, data=data, timeout=90)
        resp.raise_for_status()
        j = resp.json()
        task_id = j.get("data", {}).get("task_id") or j.get("task_id")
        return task_id
    except Exception as e:
        print(f"create error {e}")
        return None

def tripo_get_task(task_id: str):
    try:
        url = f"https://api.tripo3d.ai/v2/openapi/task/{task_id}"
        headers = {"Authorization": f"Bearer {TRIPO_API_KEY}"}
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"get error {e}")
        return None

@app.get("/", response_class=HTMLResponse)
async def home():
    return FRONTEND_HTML

@app.get("/api/health")
async def health():
    return {"status":"ok","tripo_configured": bool(TRIPO_API_KEY), "jobs": len(JOBS)}

@app.post("/api/jobs")
async def create_job(files: UploadFile = File(None), labels: str = Form("test"), preset: str = Form("high")):
    if not files:
        raise HTTPException(status_code=400, detail="No file")
    jid = str(uuid.uuid4())[:8]
    job_dir = JOBS_DIR / jid
    job_dir.mkdir(exist_ok=True)
    img_path = job_dir / "input.jpg"
    img_path.write_bytes(await files.read())
    JOBS[jid] = {"status":"queued","progress":5,"label":labels,"tripo_task": None, "model_url": None, "message":"Queued"}
    async def process_job():
        try:
            JOBS[jid]["status"]="processing"
            JOBS[jid]["progress"]=10
            task_id = await asyncio.to_thread(tripo_create_task, img_path)
            if not task_id:
                JOBS[jid]["status"]="failed"
                JOBS[jid]["message"]="Tripo task failed - check API key"
                return
            JOBS[jid]["tripo_task"]=task_id
            JOBS[jid]["progress"]=20
            for _ in range(200):
                await asyncio.sleep(3)
                info = await asyncio.to_thread(tripo_get_task, task_id)
                if not info: continue
                data = info.get("data", {})
                st = data.get("status")
                prog = data.get("progress") or 0
                try: JOBS[jid]["progress"]= int(prog)
                except: pass
                if st in ["success","completed","succeeded"]:
                    output = data.get("output", {})
                    model_url = output.get("pbr_model") or output.get("model") or output.get("base_model") or ""
                    JOBS[jid]["model_url"]=model_url
                    JOBS[jid]["status"]="completed"
                    JOBS[jid]["progress"]=100
                    if model_url:
                        try:
                            r = requests.get(model_url, timeout=60)
                            if r.ok:
                                (job_dir / "model.glb").write_bytes(r.content)
                        except: pass
                    break
                if st in ["failed","error","cancelled"]:
                    JOBS[jid]["status"]="failed"
                    JOBS[jid]["message"]=str(data)
                    break
        except Exception as e:
            JOBS[jid]["status"]="failed"
            JOBS[jid]["message"]=str(e)
    asyncio.create_task(process_job())
    return {"jid": jid, "status":"queued"}

@app.get("/api/jobs/{jid}")
async def get_job(jid: str):
    job = JOBS.get(jid)
    if not job:
        raise HTTPException(status_code=404, detail="Not found")
    return {"jid": jid, **job}

@app.get("/api/jobs/{jid}/link")
async def get_link(jid: str):
    job = JOBS.get(jid)
    if job and job.get("model_url"):
        return {"url": job["model_url"], "jid": jid}
    fp = JOBS_DIR / jid / "model.glb"
    if fp.exists():
        return {"url": f"/api/download/{jid}", "jid": jid}
    return {"url": f"/api/download/{jid}", "jid": jid}

@app.get("/api/download/{jid}")
async def download(jid: str):
    job = JOBS.get(jid)
    fp = JOBS_DIR / jid / "model.glb"
    if job and job.get("model_url"):
        if fp.exists() and fp.stat().st_size>1000:
            return FileResponse(fp, media_type="model/gltf-binary", filename=f"{jid}.glb")
        return RedirectResponse(job["model_url"])
    if fp.exists():
        return FileResponse(fp, media_type="model/gltf-binary", filename=f"{jid}.glb")
    return JSONResponse({"message": job.get("message") if job else "Not found", "jid": jid})
