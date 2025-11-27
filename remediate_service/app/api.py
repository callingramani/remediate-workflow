from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import uuid, os, json
import redis
from rq import Queue
from .utils import make_job_dir
from .reporter import generate_report_from_remediation

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
rconn = redis.from_url(REDIS_URL)
q = Queue(connection=rconn, default_timeout=1200)

router = APIRouter()

class JobRequest(BaseModel):
    mode: str
    input: str
    callback_url: str | None = None

@router.post("/jobs")
def create_job(req: JobRequest):
    if req.mode not in ("package","image"):
        raise HTTPException(status_code=400, detail="mode must be package or image")
    job_id = str(uuid.uuid4())
    job_dir = make_job_dir(job_id)

    if req.mode == "package":
        # lazy import worker function so module import works during build
        from .worker import enqueue_package_job
        job = q.enqueue(enqueue_package_job, job_id, req.input)
        return {"job_id": job_id, "status": "queued", "rq_job_id": job.id}
    else:
        # keep image synchronous for now
        try:
            from .image_api import handle_image_mode
            res = handle_image_mode(req.input, job_dir)
            report = generate_report_from_remediation(job_id, req.input, {"updated": {}, "before_count":0}, job_dir)
            return {"job_id": job_id, "status": "completed", "image_remediation": res, "report": report}
        except Exception as e:
            return {"job_id": job_id, "status": "error", "error": str(e)}

@router.get("/jobs/{job_id}")
def job_status(job_id: str):
    job_dir = os.path.join("/app","data","jobs", job_id)
    updated_path = os.path.join(job_dir, "updated_package.json")
    report_path = os.path.join(job_dir, "report.md")
    if os.path.exists(updated_path):
        try:
            with open(updated_path) as f:
                updated = json.load(f)
        except Exception:
            updated = None
        return {"job_id": job_id, "status": "completed", "updated": updated, "updated_path": updated_path, "report_path": report_path}
    if os.path.exists(job_dir):
        return {"job_id": job_id, "status": "queued_or_processing", "job_dir": job_dir}
    return {"job_id": job_id, "status": "not_found"}
