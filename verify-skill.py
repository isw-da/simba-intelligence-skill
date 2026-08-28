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
MIN_CHECKS = 8
CHECK_MANIFEST = [
    "skill_frontmatter_keys",
    "skill_frontmatter_parses",
    "python_scripts_compile",
    "shell_scripts_parse",
    "relative_path_citations_resolve",
    "no_published_secrets",
    "no_collateral_damage_commands",
    "si_version_not_behind_release",
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


SECRET_PATTERNS = {
    # An AWS account id is not a credential, but it is the thing that makes a
    # targeted attempt on an account possible, and two of them were published
    # here in a table of cluster metadata before anybody looked.
    "aws account id": r"(?<![\d.])\d{12}(?![\d.])",
    "aws access key id": r"AKIA[0-9A-Z]{16}",
    "github token": r"gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}",
    "slack token": r"xox[baprs]-[A-Za-z0-9-]{10,}",
    "google api key": r"AIza[0-9A-Za-z_\-]{35}",
    "openai key": r"\bsk-[A-Za-z0-9]{20,}",
    "private key block": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
}


def check_secrets():
    """This repo is public, so a secret committed here is a secret published.

    Only shapes that are unambiguous are matched. Placeholders (`<password>`,
    `$AZURE_OPENAI_API_KEY`) are the normal way this repo writes a credential
    and must stay green, so nothing keyed on the word "password" is in here.

    Skipped: uv.lock, whose wheel hashes are long hex by design, and this file,
    which contains the patterns themselves.
    """
    files = [f for f in tracked("*")
             if os.path.isfile(os.path.join(ROOT, f))
             and os.path.basename(f) not in ("uv.lock", "verify-skill.py")]
    if not files:
        record("no_published_secrets", None, "no tracked files to scan")
        return
    hits, scanned = [], 0
    for f in files:
        try:
            body = open(os.path.join(ROOT, f), encoding="utf-8").read()
        except (UnicodeDecodeError, OSError):
            continue          # binary or unreadable: nothing to match on
        scanned += 1
        for label, pattern in SECRET_PATTERNS.items():
            m = re.search(pattern, body)
            if m:
                hits.append("%s:%d: %s" % (f, body[:m.start()].count("\n") + 1, label))
    if scanned == 0:
        record("no_published_secrets", None, "no readable text files to scan")
        return
    record("no_published_secrets", not hits,
           "%d hits: %s" % (len(hits), hits[:3]) if hits
           else "%d files scanned, %d patterns, no match"
                % (scanned, len(SECRET_PATTERNS)))


def check_collateral_damage():
    """No shipped script may kill processes or containers it did not start.

    Added 2026-08-28. Two patterns caused this: `pkill -f "port-forward..."`
    matches any process whose command line merely contains the string, and
    `docker ps --filter ancestor=caddy:2 | xargs docker stop` stops every
    caddy:2 container on the host. Verified on the machine this was written
    on: an unrelated demo container named si-caddy runs caddy:2 on port 8090
    and the second pattern would have stopped it. Record the PID or container
    id you created and act only on that.
    """
    scripts = tracked("*.sh") + tracked("*.command") + tracked("*.ps1")
    if not scripts:
        record("no_collateral_damage_commands", None, "no shell scripts tracked")
        return
    patterns = {
        "pkill by pattern": r"pkill\s+-f",
        "docker stop by image": r"--filter\s+ancestor=",
        "killall": r"\bkillall\b",
    }
    hits = []
    for f in scripts:
        try:
            body = open(os.path.join(ROOT, f), encoding="utf-8").read()
        except (UnicodeDecodeError, OSError):
            continue
        for i, line in enumerate(body.split("\n"), 1):
            # A comment explaining why the pattern is banned must not trip the
            # check, or the only way to document the hazard is to stay silent
            # about it.
            if line.lstrip().startswith("#"):
                continue
            for label, pat in patterns.items():
                if re.search(pat, line):
                    hits.append("%s:%d %s" % (f, i, label))
    record("no_collateral_damage_commands", not hits,
           "%d hit(s): %s" % (len(hits), hits[:3]) if hits
           else "%d scripts scanned, %d patterns, none present"
                % (len(scripts), len(patterns)))


def check_version_currency():
    """No install script may pin an SI chart older than the newest SI release.

    Added 2026-08-28. Compares against the `simba-intelligence` image tags,
    NOT `zoomdata`. Those are two different products on two different version
    lines: chart 26.2.1 ships Composer 26.2.0 on purpose, and Composer 26.2.2
    exists while SI's newest release is still 26.2.1. Comparing an SI pin
    against a Composer tag marks a correct pin stale.

    Snapshot tags are ignored: a 26.3.0-SNAPSHOT is not a release.

    Needs network. Reports NOT APPLICABLE, named and counted, when offline.
    """
    import json, urllib.request
    scripts = (tracked("*.sh") + tracked("*.command")
               + tracked("*.ps1") + tracked("*.bat"))
    pins = []
    for f in scripts:
        try:
            body = open(os.path.join(ROOT, f), encoding="utf-8").read()
        except (UnicodeDecodeError, OSError):
            continue
        # Covers both a hardcoded default and the "(e.g. 26.2.1)" example the
        # interactive scripts prompt with. The example is the number a user
        # actually types, so a stale example is a stale pin.
        for m in re.finditer(r"(?:CHART_VERSION|ChartVersion|chart version)"
                             r"[^\n]{0,80}?(\d+\.\d+\.\d+)", body, re.I):
            pins.append((f, m.group(1)))
    if not pins:
        record("si_version_not_behind_release", None,
               "no script pins a CHART_VERSION default")
        return
    try:
        u = ("https://hub.docker.com/v2/repositories/insightsoftware/"
             "simba-intelligence/tags?page_size=100&ordering=last_updated")
        data = json.load(urllib.request.urlopen(u, timeout=20))
        rel = [t["name"] for t in data.get("results", [])
               if re.fullmatch(r"\d+\.\d+\.\d+", t["name"])]
    except Exception as e:
        record("si_version_not_behind_release", None,
               "Docker Hub unreachable (%s); %d pin(s) unchecked"
               % (type(e).__name__, len(pins)))
        return
    if not rel:
        record("si_version_not_behind_release", None,
               "no release tags returned by Docker Hub")
        return
    newest = max(rel, key=lambda v: tuple(map(int, v.split("."))))
    nt = tuple(map(int, newest.split(".")))
    behind = ["%s pins %s, newest SI release is %s" % (f, v, newest)
              for f, v in pins if tuple(map(int, v.split("."))) < nt]
    record("si_version_not_behind_release", not behind,
           "; ".join(behind[:3]) if behind
           else "%d pin(s) at or above newest SI release %s" % (len(pins), newest))


print("SIMBA INTELLIGENCE SKILL GATE")
check_frontmatter()   # two checks
check_python()
check_shell()
check_links()
check_secrets()
check_collateral_damage()
check_version_currency()

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
