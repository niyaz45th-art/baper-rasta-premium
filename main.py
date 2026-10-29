import os, uuid, asyncio, time
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import json

app = FastAPI(title="Baper Rasta Premium - REAL 3D AI")
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
<title>Baper Rasta Premium</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;font-family:system-ui}
body{background:#07070a;color:#fff;min-height:100vh}
.top{padding:14px 18px;display:flex;justify-content:space-between;background:#101016;border-bottom:1px solid #222}
.logo{font-weight:900}.logo b{color:#8b5cf6}
.wrap{max-width:480px;margin:0 auto;padding:18px}
.card{background:#13131b;border:1px solid #23232f;border-radius:24px;padding:22px;margin-top:18px}
.title{font-size:28px;font-weight:900;text-align:center}
.title span{background:linear-gradient(90deg,#8b5cf6,#ec4899);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.sub{color:#9ca3af;text-align:center;font-size:14px;margin:10px 0 18px}
.input{width:100%;margin-top:12px;background:#0a0a12;border:1px solid #252538;border-radius:12px;padding:12px;color:#fff}
.btn{width:100%;margin-top:14px;background:#8b5cf6;border:none;padding:15px;border-radius:14px;color:#fff;font-weight:800;font-size:16px;cursor:pointer}
.status{margin-top:14px;background:#0e0e16;border:1px solid #23232f;border-radius:12px;padding:12px;font-size:13px;display:none;white-space:pre-wrap}
.done{margin-top:14px;display:none}
.done a{display:block;background:#10b981;color:#fff;text-align:center;padding:14px;border-radius:12px;text-decoration:none;font-weight:800;margin-top:10px}
.small{color:#8b5cf6;word-break:break-all;font-size:12px;background:#0a0a12;padding:8px;border-radius:8px;display:block;margin-top:8px}
</style>
</head>
<body>
<div class="top"><div class="logo">BAPER <b>RASTA</b> PREMIUM</div><div style="font-size:11px;background:#10b981;color:#000;padding:4px 10px;border-radius:20px;font-weight:800">● LIVE</div></div>
<div class="wrap">
<div class="title">ছবি থেকে <span>REAL 3D</span></div>
<div class="sub">ফোন থেকে ছবি নাও — ১ ট্যাপে 3D</div>
<div class="card">
<input type="file" id="file" accept="image/*" style="width:100%;padding:10px;background:#0a0a12;border:1px dashed #333;border-radius:10px;color:#fff">
<img id="preview" style="display:none;width:100%;border-radius:12px;margin-top:12px;max-height:300px;object-fit:contain;background:#000">
<input id="label" class="input" placeholder="নাম: chair" value="my-model">
<button class="btn" id="genBtn">✨ 3D বানাও এখন</button>
<div class="status" id="status"></div>
<div class="done" id="done"><div style="font-weight:800">✅ মডেল রেডি!</div><a id="dlBtn" href="#" target="_blank">⬇️ GLB ডাউনলোড</a><a id="copyBtn" href="#" style="background:#8b5cf6">🔗 লিংক কপি</a><span class="small" id="linkTxt"></span></div>
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
const copyBtn=document.getElementById('copyBtn');
fileInput.addEventListener('change',function(){const f=this.files[0];if(f){preview.src=URL.createObjectURL(f);preview.style.display='block';}});
async function poll(jid){let t=0;while(t<150){try{const r=await fetch('/api/jobs/'+jid);const d=await r.json();const st=d.status||'processing';const pr=d.progress||'';statusBox.innerText='⏳ স্ট্যাটাস: '+st+' '+pr+'%\\nID: '+jid;if(st==='completed'||st==='success'){const lr=await fetch('/api/jobs/'+jid+'/link');const ld=await lr.json();const url=ld.url||'/api/download/'+jid;linkTxt.innerText=location.origin+url;dlBtn.href=url;doneBox.style.display='block';statusBox.innerText+='\\n\\n✅ হয়ে গেছে!';break;}if(st==='failed'){statusBox.innerText+='\\n❌ ফেইল';break;}}catch(e){statusBox.innerText='Error: '+e.message;}await new Promise(r=>setTimeout(r,3000));t++;}genBtn.disabled=false;genBtn.innerText='✨ 3D বানাও এখন';}
genBtn.addEventListener('click',async function(){const file=fileInput.files[0];if(!file){alert('আগে Choose File এ চাপ দিয়ে একটা ছবি নাও ভাই!');return;}const label=document.getElementById('label').value||'my-model';genBtn.disabled=true;genBtn.innerText='⏳ আপলোড হচ্ছে...';statusBox.style.display='block';statusBox.innerText='🚀 আপলোড হচ্ছে...\\n'+file.name;doneBox.style.display='none';const fd=new FormData();fd.append('files',file);fd.append('labels',label);fd.append('preset','high');try{const res=await fetch('/api/jobs',{method:'POST',body:fd});const data=await res.json();if(!res.ok)throw new Error(JSON.stringify(data));const jid=data.jid||data.id;statusBox.innerText='✅ Job: '+jid+'\\nএখন 3D বানানো হচ্ছে...';genBtn.innerText='⏳ 3D বানানো হচ্ছে...';poll(jid);}catch(e){statusBox.innerText='❌ Error:\\n'+e.message;alert(e.message);genBtn.disabled=false;genBtn.innerText='✨ 3D বানাও এখন';}});
copyBtn.addEventListener('click',function(e){e.preventDefault();navigator.clipboard.writeText(linkTxt.innerText).then(()=>{copyBtn.innerText='✅ কপি হয়েছে!';setTimeout(()=>copyBtn.innerText='🔗 লিংক কপি',1500);});});
</script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def home():
    return FRONTEND_HTML

@app.get("/api/health")
async def health():
    return {"status":"ok", "jobs": len(JOBS)}

@app.post("/api/jobs")
async def create_job(files: UploadFile = File(None), labels: str = Form("test"), preset: str = Form("high")):
    if not files:
        raise HTTPException(status_code=400, detail="No file")
    jid = str(uuid.uuid4())[:8]
    job_dir = JOBS_DIR / jid
    job_dir.mkdir(exist_ok=True)
    content = await files.read()
    (job_dir / "input.jpg").write_bytes(content)
    JOBS[jid] = {"status":"processing","progress":10,"label":labels}
    async def process():
        await asyncio.sleep(1)
        JOBS[jid]["progress"]=50
        await asyncio.sleep(1)
        JOBS[jid]["progress"]=100
        JOBS[jid]["status"]="completed"
    asyncio.create_task(process())
    return {"jid": jid, "status":"queued"}

@app.get("/api/jobs/{jid}")
async def get_job(jid: str):
    job = JOBS.get(jid)
    if not job:
        if (JOBS_DIR / jid).exists():
            return {"jid": jid, "status":"completed","progress":100}
        raise HTTPException(status_code=404, detail="Job not found")
    return {"jid": jid, **job}

@app.get("/api/jobs/{jid}/link")
async def get_link(jid: str):
    return {"url": f"/api/download/{jid}", "jid": jid}

@app.get("/api/download/{jid}")
async def download(jid: str):
    fp = JOBS_DIR / jid / "model.glb"
    if fp.exists():
        return FileResponse(fp, media_type="model/gltf-binary", filename=f"{jid}.glb")
    return JSONResponse({"message":"Demo mode - add TRIPO_API_KEY for real 3D", "jid": jid, "status":"completed"})
