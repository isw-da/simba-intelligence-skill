#!/usr/bin/env python3
"""Gate for simba-intelligence-skill. Exit 0 only if every named check RAN and PASSED.

This repo is instructions and scripts. Nothing here is compiled or imported by a
test suite, so the ways it breaks are quiet ones: a reference guide renamed while
the SKILL.md that points at it is not, a frontmatter block that stops parsing so
the skill never loads, an install script that only fails once it is on somebody
else's machine. Each check below fails when one of those happens.

A skip is not a pass. Where a check has nothing to look at, it reports
NOT APPLICABLE with a reason, and is still counted.

MIN_CHECKS is pinned so that deleting a check fails the gate rather than
shrinking it. Never lower it to make a run green.
"""
import os, re, subprocess, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
MIN_CHECKS = 4
CHECK_MANIFEST = [
    "skill_frontmatter_valid",
    "python_scripts_compile",
    "shell_scripts_parse",
    "relative_path_citations_resolve",
]

results = []


def record(name, state, detail=""):
    """state: True pass, False fail, None not applicable."""
    results.append((name, state, detail))
    label = {True: "PASS", False: "FAIL", None: "N/A "}[state]
    print("  %s  %-26s %s" % (label, name, detail))


def tracked(pattern):
    out = subprocess.run(["git", "-C", ROOT, "ls-files", pattern],
                         capture_output=True, text=True)
    return [f for f in out.stdout.split("\n") if f]


def check_frontmatter():
    files = [f for f in tracked("*.md") if os.path.basename(f) == "SKILL.md"]
    if not files:
        record("skill_frontmatter_valid", None, "no SKILL.md in the checkout")
        return
    bad = []
    for f in files:
        body = open(os.path.join(ROOT, f), encoding="utf-8").read()
        m = re.match(r"---\n(.*?)\n---\n", body, re.S)
        if not m:
            bad.append("%s: no frontmatter block" % f)
            continue
        fm = m.group(1)
        for key in ("name", "description"):
            if not re.search(r"^%s:\s*\S" % key, fm, re.M):
                bad.append("%s: frontmatter has no %s" % (f, key))
    record("skill_frontmatter_valid", not bad,
           "%d problems: %s" % (len(bad), bad[:3]) if bad
           else "%d SKILL.md files, each with name and description" % len(files))


def check_python():
    files = [f for f in tracked("*.py") if os.path.basename(f) != "verify-skill.py"]
    if not files:
        record("python_scripts_compile", None, "no tracked python")
        return
    bad = []
    for f in files:
        # compile() in this process rather than a py_compile subprocess: the
        # subprocess writes __pycache__ directories into the checkout, and a
        # gate that mutates the tree it is judging is a gate you cannot trust.
        try:
            compile(open(os.path.join(ROOT, f), encoding="utf-8").read(), f, "exec")
        except SyntaxError as e:
            bad.append("%s:%s: %s" % (f, e.lineno, e.msg))
    record("python_scripts_compile", not bad,
           "%d problems: %s" % (len(bad), bad[:3]) if bad
           else "%d scripts compile" % len(files))


def check_shell():
    # .command is a double-clickable macOS launcher and is shell, so include it.
    files = tracked("*.sh") + tracked("*.command") + tracked("*/Caddyfile")
    files = [f for f in files if f.endswith((".sh", ".command"))]
    if not files:
        record("shell_scripts_parse", None, "no tracked shell scripts")
        return
    bad = []
    for f in files:
        r = subprocess.run(["bash", "-n", os.path.join(ROOT, f)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            bad.append("%s: %s" % (f, r.stderr.strip().splitlines()[-1][:80]))
    record("shell_scripts_parse", not bad,
           "%d problems: %s" % (len(bad), bad[:3]) if bad
           else "%d shell scripts parse" % len(files))


def check_links():
    """Only citations that unambiguously point inside this repo.

    A markdown link target, or a path written with ./ or ../. Bare paths in
    prose are excluded on purpose: this repo cites files that live in other
    repos and inside the SI container image, and demanding those resolve
    produced ten false positives against one real defect. A gate that cries
    wolf gets ignored, which is worse than not having it.

    Citations are resolved against the citing file's directory, against any
    ancestor holding a SKILL.md (skills cite their own references/ folder from
    a sibling file), and against the repo root.
    """
    files = tracked("*.md")
    if not files:
        record("relative_path_citations_resolve", None, "no markdown in the checkout")
        return
    link = re.compile(r"\]\((?!https?://|mailto:|#)([^)]+)\)")
    rel = re.compile(r"(?<![A-Za-z0-9_./-])((?:\./|\.\./)[A-Za-z0-9_./-]*"
                     r"\.(?:md|py|sh|ps1|bat|command|json|yaml|yml))")

    def roots(f):
        out, cur = [os.path.dirname(f) or "."], os.path.dirname(f)
        while cur:
            if os.path.exists(os.path.join(ROOT, cur, "SKILL.md")):
                out.append(cur)
            cur = os.path.dirname(cur)
        return out + ["."]

    dead, count = [], 0
    for f in files:
        body = open(os.path.join(ROOT, f), encoding="utf-8").read()
        targets = {m.split("#")[0].strip() for m in link.findall(body)}
        targets |= set(rel.findall(body))
        for t in sorted(x for x in targets if x):
            count += 1
            if any(os.path.exists(os.path.normpath(os.path.join(ROOT, r, t)))
                   for r in roots(f)):
                continue
            dead.append("%s -> %s" % (f, t))
    if count == 0:
        # Zero citations checked is not a pass. Say so, rather than printing a
        # green line that means nothing happened.
        record("relative_path_citations_resolve", None,
               "no markdown links or ./ ../ paths in the checkout to resolve")
        return
    record("relative_path_citations_resolve", not dead,
           "%d dead of %d: %s" % (len(dead), count, dead[:3]) if dead
           else "%d citations across %d files all resolve" % (count, len(files)))


print("SIMBA INTELLIGENCE SKILL GATE")
check_frontmatter()
check_python()
check_shell()
check_links()

ran = {n for n, _, _ in results}
missing = [n for n in CHECK_MANIFEST if n not in ran]
unexpected = [n for n in ran if n not in CHECK_MANIFEST]
print("-" * 70)
print("manifest: %d | ran: %d | not applicable: %d | missing: %d | unexpected: %d"
      % (len(CHECK_MANIFEST), len(results),
         sum(1 for _, s, _ in results if s is None), len(missing), len(unexpected)))

if missing or unexpected or len(results) < MIN_CHECKS:
    print("GATE: RED  (the gate itself is wrong: %s)"
          % (("missing " + ", ".join(missing)) if missing else
             ("unexpected " + ", ".join(unexpected)) if unexpected else
             "%d checks ran, MIN_CHECKS=%d" % (len(results), MIN_CHECKS)))
    sys.exit(1)

failed = [n for n, s, _ in results if s is False]
if failed:
    print("GATE: RED  -> " + ", ".join(failed))
    sys.exit(1)
print("GATE: GREEN")
sys.exit(0)
