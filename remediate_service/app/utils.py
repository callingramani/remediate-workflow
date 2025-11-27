import os

def make_job_dir(job_id: str) -> str:
    base = os.path.abspath(os.path.join("/app", "data", "jobs"))
    os.makedirs(base, exist_ok=True)
    path = os.path.join(base, job_id)
    os.makedirs(path, exist_ok=True)
    return path

