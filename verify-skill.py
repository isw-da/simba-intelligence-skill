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
MIN_CHECKS = 5
CHECK_MANIFEST = [
    "skill_frontmatter_keys",
    "skill_frontmatter_parses",
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
    """Two checks, because they fail differently.

    The keys check is a regex and always runs. The parse check needs pyyaml and
    reports NOT APPLICABLE without it, named and counted.

    A fresh reviewer broke the first version of this in one move: an unterminated
    quote in the frontmatter made the block unloadable while `name:` and
    `description:` were still greppable, so the gate stayed green on a skill that
    could never load. Grepping for a key is not parsing.
    """
    files = [f for f in tracked("*.md") if os.path.basename(f) == "SKILL.md"]
    if not files:
        record("skill_frontmatter_keys", None, "no SKILL.md in the checkout")
        record("skill_frontmatter_parses", None, "no SKILL.md in the checkout")
        return

    blocks, bad = {}, []
    for f in files:
        body = open(os.path.join(ROOT, f), encoding="utf-8").read()
        m = re.match(r"---\n(.*?)\n---\n", body, re.S)
        if not m:
            bad.append("%s: no frontmatter block" % f)
            continue
        blocks[f] = m.group(1)
        for key in ("name", "description"):
            if not re.search(r"^%s:\s*\S" % key, blocks[f], re.M):
                bad.append("%s: frontmatter has no %s" % (f, key))
    record("skill_frontmatter_keys", not bad,
           "%d problems: %s" % (len(bad), bad[:3]) if bad
           else "%d SKILL.md files, each with name and description" % len(files))

    try:
        import yaml
    except ImportError:
        record("skill_frontmatter_parses", None,
               "pyyaml not installed; python3 -m pip install pyyaml to run this check")
        return
    unloadable = []
    for f, block in blocks.items():
        try:
            data = yaml.safe_load(block)
        except Exception as e:
            unloadable.append("%s: %s" % (f, str(e).splitlines()[0][:80]))
            continue
        if not isinstance(data, dict):
            unloadable.append("%s: frontmatter is not a mapping" % f)
    record("skill_frontmatter_parses", not unloadable,
           "%d unloadable: %s" % (len(unloadable), unloadable[:3]) if unloadable
           else "%d frontmatter blocks load as YAML mappings" % len(blocks))


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

    Three shapes qualify: a markdown link target, a path written with ./ or ../,
    and a bare path beginning `references/` or `universal/`, which in this repo
    can only mean a skill's own directory.

    Everything else in prose is excluded on purpose: this repo cites files that
    live in other repos (`composer-mcp/README.md`) and inside the SI container
    image (`services/redis_service.py`), and demanding those resolve produced ten
    false positives against one real defect. A gate that cries wolf gets ignored.

    The first version excluded ALL bare paths, which made it near-vacuous: a
    fresh reviewer renamed `si-analytics-agent/references/validation.md` out from
    under the SKILL.md that cites it and the gate stayed green. That citation is
    the whole reason this check exists, so `references/` is back in.

    Citations are resolved against the citing file's directory, against any
    ancestor holding a SKILL.md (skills cite their own references/ folder from
    a sibling file), and against the repo root.
    """
    files = tracked("*.md")
    if not files:
        record("relative_path_citations_resolve", None, "no markdown in the checkout")
        return
    link = re.compile(r"\]\((?!https?://|mailto:|#)([^)]+)\)")
    # `references/x.md`, `universal/x.md`, and the same two written with the
    # skill directory in front. Anchored so a longer path ending in one of them
    # is matched whole rather than from the middle.
    rel = re.compile(r"(?<![A-Za-z0-9_./-])("
                     r"(?:(?:\./|\.\./)[A-Za-z0-9_./-]*"
                     r"|(?:[A-Za-z0-9_-]+/)?(?:references|universal)/[A-Za-z0-9_./-]*)"
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
check_frontmatter()   # two checks
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
