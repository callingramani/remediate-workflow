import json
import tempfile
import shutil
import subprocess
import os
from packaging.version import parse as parse_version
import requests

PYPI_JSON = "https://pypi.org/pypi/{pkg}/json"
REPLACEMENTS_PATH = os.path.join(os.path.dirname(__file__), "replacements.json")

def get_pypi_versions(pkg):
    try:
        r = requests.get(PYPI_JSON.format(pkg=pkg), timeout=10)
        r.raise_for_status()
        data = r.json()
        versions = sorted(list(data.get("releases", {}).keys()), key=parse_version)
        return versions
    except Exception:
        return []

def venv_scan(pkg_spec, out_path=None):
    tmp = tempfile.mkdtemp(prefix="remediate_")
    venv = os.path.join(tmp, "venv")
    try:
        subprocess.check_call(["python3", "-m", "venv", venv])
        pip = os.path.join(venv, "bin", "pip")
        audit = os.path.join(venv, "bin", "pip-audit")
        subprocess.run([pip, "install", pkg_spec], capture_output=True, text=True)
        subprocess.run([pip, "install", "pip-audit"], capture_output=True, text=True)
        if not os.path.exists(audit):
            return [], 127, "", "pip-audit missing"
        p = subprocess.run([audit, "--format", "json"], capture_output=True, text=True)
        out = p.stdout or ""
        try:
            parsed = json.loads(out) if out else []
        except Exception:
            parsed = []
        if out_path:
            try:
                with open(out_path, "w") as f:
                    json.dump(parsed, f, indent=2)
            except Exception:
                pass
        return parsed, p.returncode, p.stdout, p.stderr
    finally:
        try:
            shutil.rmtree(tmp)
        except Exception:
            pass

def count_high_critical(vulns):
    cnt = 0
    for v in vuln_list_or_empty(vulns):
        if isinstance(v, dict) and "vulns" in v and isinstance(v["vulns"], list):
            for sub in v["vulns"]:
                sev = sub.get("severity") or (sub.get("cvss") or {}).get("baseScore")
                if isinstance(sev, str) and sev.lower() in ("high","critical"):
                    cnt += 1
                elif isinstance(sev, (int,float)) and float(sev) >= 7.0:
                    cnt += 1
        else:
            sev = None
            if isinstance(v, dict):
                sev = v.get("severity") or (v.get("cvss") or {}).get("baseScore")
            if isinstance(sev, str) and sev.lower() in ("high","critical"):
                cnt += 1
            elif isinstance(sev, (int,float)) and float(sev) >= 7.0:
                cnt += 1
    return cnt

def vuln_list_or_empty(v):
    if v is None:
        return []
    if isinstance(v, list):
        return v
    return [v]

def load_replacements():
    try:
        with open(REPLACEMENTS_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def test_replacements(original_pkg, baseline_high_count, job_dir):
    name = original_pkg.split("==")[0].split("/")[0].strip()
    replacements = load_replacements().get(name, [])
    successful = []
    for repl in replacements:
        spec = repl
        out_path = os.path.join(job_dir, f"replacement_{repl}.json")
        parsed, rc, stdout, stderr = venv_scan(spec, out_path)
        highcnt = count_high_critical(parsed)
        candidate = {
            "replacement": repl,
            "high_count": highcnt,
            "rc": rc,
            "stdout": stdout,
            "stderr": stderr,
            "path": out_path
        }
        if highcnt < baseline_high_count:
            candidate["migration_note"] = f"Replace {name} with {repl}. Tested pip-audit shows {highcnt} high/critical vs baseline {baseline_high_count}."
            successful.append(candidate)
    return successful

def choose_best_version(package_spec, job_dir, max_candidates=5):
    pkg = package_spec
    pinned = None
    if "==" in package_spec:
        pkg, pinned = package_spec.split("==",1)
    elif "/" in package_spec:
        parts = package_spec.split("/")
        pkg = parts[0]
        pinned = parts[-1] if len(parts)>1 else None
    pkg = pkg.strip()

    versions = get_pypi_versions(pkg)
    if not versions:
        return {"error":"no_versions_found","package":pkg}

    if pinned and pinned in versions:
        start_idx = versions.index(pinned)
    else:
        start_idx = max(0, len(versions)-1)

    candidate_versions = versions[start_idx: start_idx + max_candidates]
    candidate_versions = sorted(list(dict.fromkeys(candidate_versions)), key=parse_version)

    results = []
    baseline = None
    for v in candidate_versions:
        spec = f"{pkg}=={v}"
        out_path = os.path.join(job_dir, f"pip_audit_{v}.json")
        parsed, rc, stdout, stderr = venv_scan(spec, out_path)
        highcnt = count_high_critical(parsed)
        results.append({"version":v, "high_count":highcnt, "rc":rc, "stdout":stdout, "stderr":stderr, "path":out_path})
        if baseline is None:
            baseline = highcnt

    sorted_results = sorted(results, key=lambda r:(r["high_count"], parse_version(r["version"])))
    best = sorted_results[0] if sorted_results else None
    selected = best["version"] if best else None

    replacements_found = []
    if best and best["high_count"] >= baseline:
        replacements_found = test_replacements(package_spec, baseline, job_dir)

    updated = {
        "package": pkg,
        "selected_version": selected,
        "candidates": results,
        "replacements": replacements_found
    }

    updated_path = os.path.join(job_dir, "updated_package.json")
    try:
        with open(updated_path, "w") as f:
            json.dump(updated, f, indent=2)
    except Exception:
        pass

    return {"updated_path": updated_path, "updated": updated, "before_count": baseline}
