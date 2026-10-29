import os, uuid, asyncio
from fastapi import FastAPI, Header, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import json

app = FastAPI(title="NYZ REAL 3D AI")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
BASE = Path(".")
JOBS_DIR = BASE / "jobs"
JOBS_DIR.mkdir(exist_ok=True)
JOBS = {}

FRONTEND_HTML = """<!DOCTYPE html><html lang="bn"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Baper Rasta Premium</title><style>*{margin:0;padding:0;box-sizing:border-box;font-family:system-ui}body{background:#0a0a0f;color:#fff;min-height:100vh}.nav{padding:18px 24px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #1f1f2a}.logo{font-weight:900;font-size:20px}.logo span{color:#8b5cf6}.badge{background:#8b5cf6;padding:6px 12px;border-radius:20px;font-size:12px}.hero{max-width:900px;margin:40px auto;padding:20px;text-align:center}.h1{font-size:42px;font-weight:900}.h1 span{background:linear-gradient(90deg,#8b5cf6,#ec4899);-webkit-background-clip:text;-webkit-text-fill-color:transparent}.sub{color:#9ca3af;margin-bottom:30px}.card{background:#15151f;border:1px solid #222230;border-radius:20px;padding:28px;max-width:560px;margin:0 auto}.upload{border:2px dashed #2a2a3a;border-radius:16px;padding:40px 20px;cursor:pointer}.btn{width:100%;margin-top:20px;background:#8b5cf6;border:none;padding:16px;border-radius:12px;color:#fff;font-weight:700;font-size:16px;cursor:pointer}.status{margin-top:18px;padding:14px;background:#1e1e2e;border-radius:10px;display:none;text-align:left;font-size:13px}.viewer{margin-top:20px;display:none}.link{color:#8b5cf6;word-break:break-all}</style></head><body><div class="nav"><div class="logo">BAPER <span>RASTA</span> PREMIUM</div><div class="badge">LIVE</div></div><div class="hero"><div class="h1">ছবি থেকে <span>REAL 3D</span> মডেল বানাও</div><p class="sub">একটা ছবি আপলোড দাও, ১ মিনিটে GLB রেডি</p><div class="card"><div class="upload" id="drop"><input type="file" id="file" accept="image/*"><div id="uploadText">📸 ক্লিক করে ছবি আপলোড দাও</div><img id="preview" style="display:none;max-width:100%;border-radius:10px;margin-top:10px"></div><input type="text" id="label" value="test" style="width:100%;margin-top:14px;background:#0f0f18;border:1px solid #222230;padding:12px;border-radius:10px;color:#fff"><button class="btn" id="generateBtn">✨ 3D বানাও</button><div class="status" id="status"></div><div class="viewer" id="viewer"><div style="margin:12px 0;font-weight:700">✅ মডেল রেডি!</div><a id="downloadBtn" href="#" target="_blank" class="btn" style="background:#10b981;display:block;text-align:center;text-decoration:none">⬇️ GLB ডাউনলোড</a><div style="margin-top:12px"><small>লিংক:</small> <span id="modelLink" class="link"></span></div></div></div></div><script>const fileInput=document.getElementById('file');const drop=document.getElementById('drop');const preview=document.getElementById('preview');const uploadText=document.getElementById('uploadText');const btn=document.getElementById('generateBtn');const status=document.getElementById('status');const viewer=document.getElementById('viewer');let selectedFile=null;drop.onclick=()=>fileInput.click();drop.ondragover=(e)=>{e.preventDefault()};drop.ondrop=(e)=>{e.preventDefault();handleFile(e.dataTransfer.files[0])};fileInput.onchange=(e)=>handleFile(e.target.files[0]);function handleFile(f){if(!f)return;selectedFile=f;preview.src=URL.createObjectURL(f);preview.style.display='block';uploadText.innerHTML='✅ '+f.name}async function pollJob(jid){status.style.display='block';let tries=0;while(tries<120){const res=await fetch('/api/jobs/'+jid);const data=await res.json();status.innerHTML='⏳ Status: '+(data.status||'processing')+' - '+(data.progress||'')+'%<br><small>jid: '+jid+'</small>';if(data.status==='completed'||data.status==='success'){const linkRes=await fetch('/api/jobs/'+jid+'/link');const linkData=await linkRes.json();const url=linkData.url||'/api/download/'+jid;document.getElementById('modelLink').innerText=url;document.getElementById('downloadBtn').href=url;viewer.style.display='block';status.innerHTML+='<br>✅ Done!';break}if(data.status==='failed'){status.innerHTML+='<br>❌ Failed';break}await new Promise(r=>setTimeout(r,3000));tries++}}btn.onclick=async()=>{if(!selectedFile){alert('আগে ছবি আপলোড দাও');return}const label=document.getElementById('label').value||'test';btn.disabled=true;btn.innerText='⏳ বানানো হচ্ছে...';status.style.display='block';status.innerText='🚀 আপলোড হচ্ছে...';viewer.style.display='none';const form=new FormData();form.append('files',selectedFile);form.append('labels',label);form.append('preset','high');try{const res=await fetch('/api/jobs',{method:'POST',headers:{'x-api-token':'nexxx123'},body:form});const data=await res.json();if(!res.ok)throw new Error(JSON.stringify(data));const jid=data.jid||data.id;status.innerText='✅ Job: '+jid+'\\nএখন 3D বানানো হচ্ছে...';pollJob(jid)}catch(e){status.innerText='❌ Error: '+e.message}btn.disabled=false;btn.innerText='✨ 3D বানাও'}};</script></body></html>"""

@app.get("/", response_class=HTMLResponse)
async def home():
    return FRONTEND_HTML

@app.get("/api/health")
async def health():
    return {"status": "ok", "tripo_configured": bool(os.getenv("TRIPO_API_KEY")), "jobs": len(JOBS)}

@app.post("/api/jobs")
async def create_job(x_api_token: str = Header(None), files: UploadFile = File(None), labels: str = Form("test"), preset: str = Form("high")):
    token_expected = os.getenv("APP_TOKENS", "nexxx123")
    if x_api_token != token_expected:
        raise HTTPException(status_code=401, detail="Invalid token")
    jid = str(uuid.uuid4())[:8]
    job_path = JOBS_DIR / jid
    job_path.mkdir(exist_ok=True)
    if files:
        content = await files.read()
        (job_path / "input.jpg").write_bytes(content)
    JOBS[jid] = {"status": "processing", "progress": 10, "label": labels}
    async def process():
        await asyncio.sleep(1)
        JOBS[jid]["progress"]=50
        await asyncio.sleep(1)
        JOBS[jid]["progress"]=100
        JOBS[jid]["status"]="completed"
        (job_path / "model.glb").write_bytes(b"placeholder")
    asyncio.create_task(process())
    return {"jid": jid, "status": "queued"}

@app.get("/api/jobs/{jid}")
async def get_job(jid: str):
    job = JOBS.get(jid)
    if not job:
        if (JOBS_DIR / jid).exists():
            return {"jid": jid, "status": "completed", "progress": 100}
        raise HTTPException(status_code=404, detail="Job not found")
    return {"jid": jid, **job}

@app.get("/api/jobs/{jid}/link")
async def get_link(jid: str):
    return {"url": f"/api/download/{jid}", "jid": jid}

@app.get("/api/download/{jid}")
async def download(jid: str):
    fp = JOBS_DIR / jid / "model.glb"
    if fp.exists() and fp.stat().st_size>0:
        return FileResponse(fp, media_type="model/gltf-binary", filename=f"{jid}.glb")
    return JSONResponse({"message": "Placeholder - add real Tripo logic", "jid": jid})
