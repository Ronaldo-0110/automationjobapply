"""Web app: upload an HR CSV (and optionally a resume) and send the emails.

Run:  uv run uvicorn ronaldo.api:app --reload
Open: http://127.0.0.1:8000
"""

from dataclasses import asdict

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse

from .emailer import preview, send_all

app = FastAPI(title="Job Application Mailer")

PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>Job Application Mailer</title>
<style>
 body{font-family:system-ui,sans-serif;max-width:640px;margin:40px auto;padding:0 16px;color:#222}
 label{display:block;margin:16px 0 4px;font-weight:600}
 button{margin-top:20px;padding:10px 18px;font-size:15px;cursor:pointer}
 pre{background:#f4f4f4;padding:12px;white-space:pre-wrap;border-radius:6px}
 .note{color:#666;font-size:14px}
</style></head><body>
<h1>Job Application Mailer</h1>
<p class="note">CSV needs an <b>email</b> column. Optional: <b>name</b>, <b>company</b>.</p>
<form id="f">
 <label>HR contacts CSV</label><input type="file" name="csv_file" accept=".csv" required>
 <label>Resume PDF (optional; otherwise RESUME_PATH from .env)</label><input type="file" name="resume" accept=".pdf">
 <label><input type="checkbox" name="send_for_real"> Actually send (leave unticked for a dry run)</label>
 <button type="button" onclick="go('/preview')">Preview email</button>
 <button type="submit">Run</button>
</form>
<pre id="out">Results appear here.</pre>
<script>
const f=document.getElementById('f'), out=document.getElementById('out');
async function go(url){
  const fd=new FormData(f);
  fd.set('dry_run', fd.get('send_for_real') ? 'false' : 'true');
  out.textContent='Working... (real sends wait between emails, this can take a while)';
  const r=await fetch(url,{method:'POST',body:fd});
  const ct=r.headers.get('content-type')||'';
  out.textContent= ct.includes('json') ? JSON.stringify(await r.json(),null,2) : await r.text();
}
f.onsubmit=e=>{e.preventDefault();
  if(new FormData(f).get('send_for_real') && !confirm('Send real emails to everyone in this CSV?'))return;
  go('/send-emails');};
</script></body></html>"""


async def _read_csv(upload: UploadFile) -> str:
    try:
        return (await upload.read()).decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(400, "CSV must be UTF-8. In Excel use Save As > CSV UTF-8.")


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return PAGE


@app.post("/preview")
async def preview_email(csv_file: UploadFile = File(...)):
    try:
        return {"preview": preview(await _read_csv(csv_file))}
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/send-emails")
async def send_emails(
    csv_file: UploadFile = File(...),
    resume: UploadFile | None = File(None),
    dry_run: bool = Form(True),
):
    csv_text = await _read_csv(csv_file)
    resume_bytes = resume_name = None
    if resume and resume.filename:
        if not resume.filename.lower().endswith(".pdf"):
            raise HTTPException(400, "Resume must be a PDF.")
        resume_bytes, resume_name = await resume.read(), resume.filename
    try:
        # smtplib is blocking, so keep it off the event loop.
        results = await run_in_threadpool(send_all, csv_text, resume_bytes, resume_name, dry_run)
    except (ValueError, FileNotFoundError, RuntimeError) as e:
        raise HTTPException(400, str(e))

    summary: dict[str, int] = {}
    for r in results:
        summary[r.status] = summary.get(r.status, 0) + 1
    return {"dry_run": dry_run, "summary": summary, "results": [asdict(r) for r in results]}
