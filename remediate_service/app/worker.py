import os, json, traceback
from .remediator import choose_best_version
from .reporter import generate_report_from_remediation

def enqueue_package_job(job_id: str, package_input: str, max_candidates: int = 5):
    job_dir = os.path.join("/app", "data", "jobs", job_id)
    os.makedirs(job_dir, exist_ok=True)
    out = {"job_id": job_id, "package_input": package_input}
    try:
        res = choose_best_version(package_input, job_dir, max_candidates=max_candidates)
        out['remediation'] = res
        # write updated_package.json if remediator produced it
        try:
            upd = res.get('updated')
            if upd:
                with open(os.path.join(job_dir,'updated_package.json'),'w') as f:
                    json.dump(upd, f, indent=2)
        except Exception:
            pass
        try:
            report = generate_report_from_remediation(job_id, package_input, res, job_dir)
            out['report_path'] = report
        except Exception as e:
            out['report_error'] = str(e)
            with open(os.path.join(job_dir,'report_error.txt'),'w') as ferr:
                ferr.write(traceback.format_exc())
    except Exception as e:
        out['error'] = str(e)
        with open(os.path.join(job_dir,'error.txt'),'w') as ferr:
            ferr.write(traceback.format_exc())
    # always return out so RQ stores the result
    try:
        with open(os.path.join(job_dir,'worker_result.json'),'w') as fw:
            json.dump(out, fw, indent=2)
    except Exception:
        pass
    return out
