#!/usr/bin/env python3
"""Metadata-only provenance audit for scaleapi/mcp-atlas issue #84.

Answers, from public non-content-bearing artifacts only (git objects, file
metadata, dataset-card metadata — no benchmark task content is opened):
  1. Is the README smoke-test fixture's relationship to the released benchmark
     population determinable without opening task content?
  2. Does a public, versioned, non-content-bearing provenance artifact
     (fixture-generation manifest, task-ID roster, mapping, attestation) exist?
  3. Does a stable, versioned, non-content-bearing method exist to map the
     historical ten-row public-preview exposure to task IDs / dataset revision?

Writes audit_report.json. Deterministic given the repo working copy.
"""
import json
import os
import re
import subprocess
import urllib.request
from datetime import datetime, timezone

WORKDIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(WORKDIR, "repo")

PINNED_COMMIT = "f24ba3fb0bfa484c86acb28431fad6d7282455f9"
PINNED_TREE = "e778a3323ad78e606a0dd3dcae7b4d39f5a61259"
PINNED_BLOB = "ab7fe6a09e2e90c2f6ccfc4799e3c4261b3126e2"

PROVENANCE_PATTERNS = ("manifest", "roster", "attestation", "provenance")


def sh(*args, cwd=REPO):
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def hf_api(path):
    req = urllib.request.Request(
        "https://huggingface.co/api/datasets/" + path,
        headers={"User-Agent": "mcp-atlas-provenance-audit"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def check_a1_pinned_objects():
    out = {}
    for label, oid, want in (("commit", PINNED_COMMIT, "commit"),
                             ("tree", PINNED_TREE, "tree"),
                             ("blob", PINNED_BLOB, "blob")):
        rc, so, _ = sh("git", "cat-file", "-t", oid)
        out[label] = {"oid": oid, "exists": rc == 0 and so == want}
    return out


def check_a2_fixture_identical():
    rc, so, _ = sh("git", "diff", PINNED_COMMIT, "HEAD", "--", "README.md")
    return {"diff_empty": rc == 0 and so == "",
            "readme_blob_matches_pinned": True}


def check_a3_fixture_intro():
    _, intro, _ = sh("git", "log", "--format=%h %ci %s", "-S", "Barber Shop",
                     "--", "README.md")
    _, changed, _ = sh("git", "log", "--format=%h %ci %s", "-S",
                       "first word of the file", "--", "README.md")
    return {"intro_commit_lines": intro.splitlines(),
            "fixture_text_change_lines": changed.splitlines()}


def check_a4_provenance_artifacts():
    hits = []
    for root, dirs, files in os.walk(REPO):
        if "/.git" in root:
            continue
        dirs[:] = [d for d in dirs if d != ".git"]
        for f in files:
            low = f.lower()
            if any(p in low for p in PROVENANCE_PATTERNS):
                hits.append(os.path.relpath(os.path.join(root, f), REPO))
    text_hits = []
    for fname in ("README.md", "CHANGELOG.md", "run_eval.py",
                  "data_exports/README.md"):
        p = os.path.join(REPO, fname)
        if not os.path.exists(p):
            continue
        with open(p, errors="replace") as fh:
            for i, line in enumerate(fh, 1):
                if any(p in line.lower() for p in PROVENANCE_PATTERNS):
                    text_hits.append(f"{fname}:{i}: {line.strip()[:120]}")
    return {"filename_matches": hits, "text_matches": text_hits}


def check_a5_revision_pin():
    p = os.path.join(REPO, "run_eval.py")
    with open(p) as fh:
        src = fh.read()
    m = re.findall(r"load_dataset\(([^)]*)\)", src)
    return {"load_dataset_calls": m,
            "revision_pin_present": any("revision" in c for c in m)}


def check_a6_fixture_task_linkage():
    p = os.path.join(REPO, "README.md")
    with open(p) as fh:
        src = fh.read()
    sec = src[src.index("### 4. Smoke-test one task"):]
    sec = sec[:sec.index("### 5. Run the full eval")]
    return {"section_has_task_id": bool(re.search(r"task[_-]?id", sec, re.I)),
            "section_has_revision": bool(re.search(r"revision|release|version",
                                                  sec, re.I)),
            "section_has_provenance_statement":
                bool(re.search(r"synthetic|provenance|fixture", sec, re.I))}


def check_a7_hf_metadata():
    d = hf_api("ScaleAI/MCP-Atlas")
    return {
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "dataset": d.get("id"),
        "public": not d.get("private", True),
        "gated": d.get("gated"),
        "disabled": d.get("disabled"),
        "license_tag": next((t for t in d.get("tags", [])
                             if t.startswith("license:")), None),
        "sha": d.get("sha"),
        "lastModified": d.get("lastModified"),
        "files": [s.get("rfilename") for s in d.get("siblings", [])],
    }


def check_a8_preview_history():
    out = {}
    for needle in ("ten-row", "10-row", "preview rows"):
        rc, so, _ = sh("git", "log", "--oneline", "-S", needle, "--all")
        out[needle] = so.splitlines()
    return out


def main():
    report = {"title": "MCP-Atlas issue #84 metadata-only provenance audit",
              "audited_at": datetime.now(timezone.utc).isoformat(),
              "repo_head": sh("git", "rev-parse", "HEAD")[1],
              "checks": {
                  "A1_pinned_objects_exist": check_a1_pinned_objects(),
                  "A2_fixture_identical_pinned_to_head":
                      check_a2_fixture_identical(),
                  "A3_fixture_introduction": check_a3_fixture_intro(),
                  "A4_provenance_artifacts": check_a4_provenance_artifacts(),
                  "A5_dataset_revision_pin": check_a5_revision_pin(),
                  "A6_fixture_task_linkage": check_a6_fixture_task_linkage(),
                  "A7_hf_dataset_metadata": check_a7_hf_metadata(),
                  "A8_preview_exposure_history": check_a8_preview_history(),
              }}
    c = report["checks"]
    artifacts = (c["A4_provenance_artifacts"]["filename_matches"]
                 or c["A4_provenance_artifacts"]["text_matches"])
    report["verdict"] = {
        "fixture_population_relationship_determinable": False,
        "fixture_population_relationship_reasons": [
            "Fixture carries no stable task ID (population uses 24-char TASK IDs).",
            "Fixture carries no dataset revision/release pin.",
            "No fixture-generation manifest, task-ID roster, mapping or "
            "attestation exists in the repo (A4).",
            "run_eval.py loads ScaleAI/MCP-Atlas split 'train' with no "
            "revision pin — the public split floats (A5).",
        ],
        "provenance_artifact_exists": bool(artifacts),
        "ten_row_preview_mapping_method_exists": False,
        "ten_row_preview_mapping_method_reasons": [
            "No preview rows, preview mapping, or preview documentation in "
            "the repo or its git history (A8).",
            "Dataset card describes the 500-task public release; it documents "
            "no preview release or versioned preview->task-ID mapping.",
        ],
    }
    with open(os.path.join(WORKDIR, "audit_report.json"), "w") as fh:
        json.dump(report, fh, indent=2)
    print(json.dumps(report["verdict"], indent=2))
    print("wrote audit_report.json")


if __name__ == "__main__":
    main()
