#!/usr/bin/env python3
"""Validate the issue-#84 provenance fix.

FAILS on the before state (no PROVENANCE.md, unpinned dataset load),
PASSES on the after state.

Checks:
  1. repo/PROVENANCE.md exists and carries the pinned git object IDs,
     the fixture section hash, and an honest NOT-DETERMINABLE verdict.
  2. PROVENANCE.md invents nothing: no task ID is assigned to the fixture.
  3. The README fixture section in the working copy still hashes to the
     value the document records (document has not drifted from reality).
  4. run_eval.py pins the public dataset split to a 40-hex-char revision
     and passes it to load_dataset.
"""
import hashlib
import os
import re
import sys

WORKDIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(WORKDIR, "repo")

PINNED_COMMIT = "f24ba3fb0bfa484c86acb28431fad6d7282455f9"
PINNED_TREE = "e778a3323ad78e606a0dd3dcae7b4d39f5a61259"
PINNED_BLOB = "ab7fe6a09e2e90c2f6ccfc4799e3c4261b3126e2"
FIXTURE_SECTION_SHA256 = ("792b13907089a327f72c5f43970ca15c3d9516e9"
                          "3cea2fc714d283884f6716e9")

failures = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f" — {detail}" if detail else ""))
    if not cond:
        failures.append(name)


def fixture_section_bytes():
    with open(os.path.join(REPO, "README.md")) as fh:
        lines = fh.read().splitlines()
    start = next(i for i, l in enumerate(lines)
                 if l.strip().startswith("### 4. Smoke-test one task"))
    block = lines[start:start + 3]  # heading, blank, "Expected answer:" line
    return ("\n".join(block) + "\n").encode()


def main():
    doc_path = os.path.join(REPO, "PROVENANCE.md")
    check("1. PROVENANCE.md exists", os.path.exists(doc_path))
    doc = open(doc_path).read() if os.path.exists(doc_path) else ""

    for label, oid in (("pinned commit", PINNED_COMMIT),
                       ("pinned tree", PINNED_TREE),
                       ("pinned blob", PINNED_BLOB),
                       ("fixture section sha256", FIXTURE_SECTION_SHA256)):
        check(f"1b. PROVENANCE.md records {label}",
              oid in doc, oid[:12] + "…")

    check("1c. verdict is honestly NOT DETERMINABLE",
          "NOT DETERMINABLE" in doc)

    # No invented task-ID assignment for the fixture.
    invented = re.search(r"fixture.{0,80}?task[_ -]?id.{0,40}[:=].{0,8}[A-Za-z0-9]{24}",
                         doc, re.I | re.S)
    check("2. no invented task ID assigned to fixture", not invented,
          "found one" if invented else "")

    actual = hashlib.sha256(fixture_section_bytes()).hexdigest()
    check("3. README fixture matches the documented hash",
          actual == FIXTURE_SECTION_SHA256, actual[:16] + "…")

    rp = os.path.join(REPO, "run_eval.py")
    src = open(rp).read()
    m = re.search(r'DATASET_REVISION\s*=\s*"([0-9a-f]{40})"', src)
    check("4a. run_eval.py has DATASET_REVISION pin",
          bool(m), m.group(1)[:12] + "…" if m else "")
    check("4b. load_dataset uses the revision pin",
          "revision=DATASET_REVISION" in src)

    print()
    if failures:
        print(f"RESULT: FAIL ({len(failures)} checks failed)")
        return 1
    print("RESULT: PASS (all checks green)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
