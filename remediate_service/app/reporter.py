import os
import json
from datetime import datetime

TEMPLATE = (
    "# Remediation Report - Job {job_id}\n\n"
    "**Input:** {input}\n\n"
    "**Generated at:** {ts}\n\n"
    "### Summary\n\n"
    "- Baseline high/critical vulnerabilities: {before}\n"
    "- Selected version: {selected}\n\n"
    "### Candidates\n\n"
    "{candidates}\n\n"
    "### Replacements considered\n\n"
    "{replacements}\n\n"
    "### Artifacts\n\n"
    "- updated_package.json: {updated_path}\n"
)

def render_candidates(cands):
    if not cands:
        return "No candidates tested.\n"
    rows = []
    for c in cands:
        rows.append(f"- {c['version']}: high_count={c.get('high_count',0)}")
    return "\n".join(rows)

def render_replacements(repls):
    if not repls:
        return "No replacement candidates found.\n"
    rows = []
    for r in repls:
        note = r.get("migration_note","")
        rows.append(f"- {r['replacement']}: high_count={r.get('high_count',0)}. {note}")
    return "\n".join(rows)

def generate_report_from_remediation(job_id, input_spec, remediation, job_dir):
    updated = remediation.get("updated", {})
    before = remediation.get("before_count", updated.get("before_count", 0))
    selected = updated.get("selected_version") or updated.get("selected") or updated.get("package")
    candidates_md = render_candidates(updated.get("candidates", []))
    replacements_md = render_replacements(updated.get("replacements", []))
    ts = datetime.utcnow().isoformat() + "Z"

    content = TEMPLATE.format(
        job_id=job_id,
        input=input_spec,
        ts=ts,
        before=before,
        selected=selected,
        candidates=candidates_md,
        replacements=replacements_md,
        updated_path=remediation.get("updated_path", "n/a")
    )

    report_path = os.path.join(job_dir, "report.md")
    with open(report_path, "w") as f:
        f.write(content)
    return report_path
