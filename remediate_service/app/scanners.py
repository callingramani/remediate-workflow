import os
import json
import tempfile
import shutil
import subprocess
from .utils import run_cmd_capture_json

def extract_pypi_name(url_or_name: str) -> str:
    # Accept either full PyPI URL or "package==version" or "package/version" or "package"
    src = url_or_name.strip()
    if "pypi.org" in src:
        parts = src.rstrip("/").split("/")
        # last part may be name or name/version
        name_part = parts[-1]
        return name_part
    return src

def write_json_path(path: str, obj):
    with open(path, "w") as f:
        json.dump(obj, f, indent=2)

def scan_package_simple(url_or_name: str, job_dir: str) -> dict:
    pkg_spec = extract_pypi_name(url_or_name)
    out_path = os.path.join(job_dir, "pip_audit.json")

    # 1) Try direct pip-audit invocation with --package (works on some versions)
    cmd_try = ["pip-audit", "--format", "json", "--output", out_path, "--package", pkg_spec]
    res = run_cmd_capture_json(cmd_try)

    # If pip-audit returned parsed JSON or returncode == 0, accept it
    if res["parsed"] is not None or res["returncode"] == 0:
        vulns = res["parsed"] or []
        write_json_path(out_path, vulns)
        v_count = len(vulns) if isinstance(vulns, list) else 0
        return {
            "mode": "package",
            "package": pkg_spec,
            "pip_audit_raw": vulns,
            "vulns_count": v_count,
            "pip_audit_path": out_path,
            "scanner_stdout": res["stdout"],
            "scanner_stderr": res["stderr"],
            "scanner_returncode": res["returncode"],
            "method": "direct"
        }

    # 2) If direct invocation failed due to unrecognized args or usage, fallback to venv approach
    # Create temp venv and install the package into it, then run pip-audit inside that venv.
    tmpdir = tempfile.mkdtemp(prefix="pip_audit_")
    venv_dir = os.path.join(tmpdir, "venv")
    try:
        # create venv
        subprocess.check_call(["python3", "-m", "venv", venv_dir])
        pip_bin = os.path.join(venv_dir, "bin", "pip")
        audit_bin = os.path.join(venv_dir, "bin", "pip-audit")

        # install package and pip-audit into venv
        # ignore install errors but capture them
        install_pkg = subprocess.run([pip_bin, "install", pkg_spec], capture_output=True, text=True)
        install_audit = subprocess.run([pip_bin, "install", "pip-audit"], capture_output=True, text=True)

        # run pip-audit from venv (it will scan venv's installed packages)
        if os.path.exists(audit_bin):
            cmd_venv = [audit_bin, "--format", "json", "--output", out_path]
            p = subprocess.run(cmd_venv, capture_output=True, text=True)
            stdout = p.stdout or ""
            stderr = p.stderr or ""
            parsed = None
            try:
                if stdout:
                    parsed = json.loads(stdout)
            except Exception:
                parsed = None

            # If the CLI wrote a file, prefer that. Otherwise use parsed stdout if available.
            if os.path.exists(out_path):
                try:
                    with open(out_path, "r") as f:
                        parsed_file = json.load(f)
                except Exception:
                    parsed_file = parsed
            else:
                parsed_file = parsed or []

            write_json_path(out_path, parsed_file or [])
            v_count = len(parsed_file) if isinstance(parsed_file, list) else 0
            return {
                "mode": "package",
                "package": pkg_spec,
                "pip_audit_raw": parsed_file,
                "vulns_count": v_count,
                "pip_audit_path": out_path,
                "scanner_stdout": stdout,
                "scanner_stderr": stderr,
                "scanner_returncode": p.returncode,
                "method": "venv_fallback",
                "venv_install_stdout": install_pkg.stdout,
                "venv_install_stderr": install_pkg.stderr,
                "venv_audit_install_stdout": install_audit.stdout,
                "venv_audit_install_stderr": install_audit.stderr
            }
        else:
            # pip-audit installation failed; return what we have
            write_json_path(out_path, [])
            return {
                "mode": "package",
                "package": pkg_spec,
                "pip_audit_raw": [],
                "vulns_count": 0,
                "pip_audit_path": out_path,
                "scanner_stdout": install_audit.stdout if 'install_audit' in locals() else "",
                "scanner_stderr": install_audit.stderr if 'install_audit' in locals() else "pip-audit not available",
                "scanner_returncode": 127,
                "method": "venv_failed"
            }
    finally:
        # cleanup the temporary venv directory
        try:
            shutil.rmtree(tmpdir)
        except Exception:
            pass
