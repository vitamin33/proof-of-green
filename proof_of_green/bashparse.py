"""Turn one Bash tool call into parsed facts: runner, scope, flags, counts.

Raw output is only read here, never returned or stored.
"""
import os
import re
import shlex

# name -> regex matched against one command segment (after prefixes are stripped)
RUNNERS = [
    ("pytest", r"(?:^|/)py\.?test\b|\bpython[\d.]*\s+-m\s+pytest\b"),
    ("unittest", r"\bpython[\d.]*\s+-m\s+unittest\b"),
    ("vitest", r"(?:^|/)vitest\b"),
    ("jest", r"(?:^|/)jest\b"),
    ("npm test", r"^(?:npm|pnpm|yarn|bun)\s+(?:-{1,2}[\w-]+(?:[= ](?!(?:run|test|t)\b)[^\s-]\S*)?\s+)*"
                 r"(?:run\s+)?(?:test|t)(?::[\w:-]+)?(?=\s|$)"),
    ("go test", r"^go\s+test\b"),
    ("cargo test", r"^cargo\s+(?:test|nextest\s+run)\b"),
    ("flutter test", r"^flutter\s+test\b"),
    ("dart test", r"^dart\s+(?:run\s+)?test\b"),
    ("dotnet test", r"^dotnet\s+test\b"),
    ("gradle test", r"^(?:\./)?gradlew?\b.*\s:?[\w:-]*[tT]est\w*\b"),
    ("mvn test", r"^(?:\./)?mvnw?\b.*\s(?:test|verify)\b"),
    ("make test", r"^make\b.*\s(?:test|check)\b"),
    ("xcodebuild test", r"^xcodebuild\b.*\btest\b"),
    ("swift test", r"^swift\s+test\b"),
    ("fastlane", r"^fastlane\s+(?:(?:ios|android|mac)\s+)?(?:test|tests|scan|run_tests|unit_tests?)\b"),
    ("rspec", r"(?:^|/)rspec\b"),
    ("node --test", r"^node\s+(?:\S+\s+)*--test(?:\s|$)"),
    ("phpunit", r"(?:^|/)phpunit\b"),
]

PREFIX = re.compile(
    r"^(?:\w+=\S*\s+|sudo\s+|time\s+|timeout\s+\S+\s+|env\s+|exec\s+|"
    r"(?:uv|poetry|pipenv|hatch|pdm|rye)\s+run\s+|bundle\s+exec\s+|"
    r"npx\s+(?:-y\s+)?|bunx\s+|pnpm\s+(?:exec|dlx)\s+|yarn\s+(?:exec\s+)?(?=jest|vitest))")

DEPLOY = re.compile(
    r"\b(?:vercel\s+(?:deploy|--prod)|netlify\s+deploy|fly(?:ctl)?\s+deploy|"
    r"firebase\s+deploy|gcloud\s+.*\bdeploy\b|kubectl\s+(?:apply|rollout)|helm\s+(?:upgrade|install)|"
    r"railway\s+up|render\s+deploy|wrangler\s+(?:deploy|publish)|serverless\s+deploy|sls\s+deploy|"
    r"cdk\s+deploy|terraform\s+apply|heroku\s+.*deploy|eas\s+(?:submit|update)|fastlane\s+\w+|"
    r"npm\s+publish|twine\s+upload|docker\s+push)")

SUSPICIOUS = [
    ("|| true", r"\|\|\s*(?:true|:)(?:\s|$|;|\))"),
    ("; true", r";\s*(?:true|:)\s*$"),
    ("--collect-only", r"--collect-only\b|\s--co\b"),
    ("--passWithNoTests", r"--passWithNoTests\b"),
    ("--no-run", r"--no-run\b"),
    ("set +e", r"\bset\s+\+e\b"),
]

# runner -> narrowing flags (scope "partial")
NARROW = r"(?:^|\s)(?:-k|-t|-m|-run|--filter|--tests|--testNamePattern|--testPathPattern|" \
         r"--test-name-pattern|--plain-name|--name|-Dtest|-only-testing|--only-testing|--exact|-e)(?:[=:\s]|$)"
FULL_DIRS = {"test", "tests", "spec", "__tests__", "./...", "...", "./"}

SECRET_NAME = r"[A-Za-z_]*(?:SECRET|TOKEN|KEY|PASSWORD|PASSWD|PWD|AUTH|CREDENTIAL)[A-Za-z0-9_]*"
REDACTIONS = [
    (re.compile(r"(?<![\w-])(" + SECRET_NAME + r")=(\"[^\"]*\"|'[^']*'|\S+)", re.I), r"\1=***"),
    (re.compile(r"(\w+://)[^\s/@:]+:[^\s/@]+@"), r"\1***@"),
    (re.compile(r"((?<!-)(?:token|password|passwd|secret|api_?key|access_?key)=)[^\s&'\"]+", re.I), r"\1***"),
    (re.compile(r"(--(?:token|api-key|apikey|secret)(?:=|\s+))(\"[^\"]*\"|'[^']*'|\S+)", re.I), r"\1***"),
    (re.compile(r"\b(mysql|mariadb|mysqldump)\b([^|;&]*?\s)-p(?!\*)\S+"), r"\1\2-p***"),
    (re.compile(r"(Bearer|Basic)\s+[A-Za-z0-9._~+/=-]+", re.I), r"\1 ***"),
    (re.compile(r"\b(?:sk-[A-Za-z0-9_-]{10,}|gh[pousr]_[A-Za-z0-9]{10,}|github_pat_\w{10,}|"
                r"xox[abprs]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16})\b"), "***"),
]


# -p / --password: redacted unless the value is an existing path (mkdir -p build, cp -p a b).
PATH_OR_SECRET = re.compile(r"((?<!\S)-p\s+(?!-)|--(?:password|passwd)(?:=|\s+))(\"[^\"]*\"|'[^']*'|\S+)", re.I)


def _is_path(value, cwd):
    value = os.path.expanduser(value.strip("'\""))
    if not value:
        return False
    return os.path.exists(value if os.path.isabs(value) else os.path.join(cwd or os.getcwd(), value))


def redact(command, cwd=None, limit=240):
    out = command or ""
    for rx, repl in REDACTIONS:
        out = rx.sub(repl, out)
    out = PATH_OR_SECRET.sub(lambda m: m.group(0) if _is_path(m.group(2), cwd) else m.group(1) + "***", out)
    out = relativize(out, cwd)  # before the length cut, so no path is stored half-replaced
    out = " ".join(out.split())
    return out if len(out) <= limit else out[:limit] + "…"


OTHER_PATH = re.compile(r"(?<![\w.:/~<>*-])(?:~/|/)[^\s'\";|&)]*|(?<![\w.:/~-])~(?=[\s'\";|&)]|$)")


def relativize(command, cwd):
    """Store paths relative to the session folder: <cwd>/x -> x, <cwd> -> ., any other path -> <path>."""
    roots = [(r, "") for r in {cwd.rstrip("/"), os.path.realpath(cwd).rstrip("/")} if r] if cwd else []
    home = os.path.expanduser("~").rstrip("/")
    for root, _ in sorted(roots, key=lambda x: len(x[0]), reverse=True):
        command = re.sub(re.escape(root) + r"/", "", command)
        command = re.sub(re.escape(root) + r"(?![\w.-])", ".", command)
    if home:
        command = re.sub(re.escape(home) + r"(?![\w.-])", "~", command)
    return OTHER_PATH.sub("<path>", command)


def segments(command):
    """Split on &&, ||, ;, | and newlines (quotes are not respected; good enough here)."""
    parts = re.split(r"&&|\|\||[;\n|]", command or "")
    out = []
    for part in parts:
        seg = part.strip().lstrip("(").strip()
        prev = None
        while seg and seg != prev:
            prev = seg
            seg = PREFIX.sub("", seg, count=1).strip()
        if seg:
            out.append(seg)
    return out


def detect_runner(command, test_command=None):
    if test_command and test_command.strip() and test_command.strip() in (command or ""):
        return "custom", test_command.strip()
    for seg in segments(command):
        for name, rx in RUNNERS:
            m = re.search(rx, seg)
            if m:
                return (seg.split()[0] + " test" if name == "npm test" else name), seg
    return None, None


def detect_scope(runner, seg):
    if runner == "custom":
        return "all"
    seg = re.sub(r"^python[\d.]*\s+-m\s+", "", seg)
    if re.search(NARROW, seg) or "::" in seg:
        return "partial"
    try:
        toks = shlex.split(seg)
    except ValueError:
        return "unknown"
    # drop runner words, options and option values we know take one
    words = []
    skip = False
    for tok in toks[1:]:
        if skip or re.match(r"^\d*[<>]", tok):
            skip = tok in (">", ">>", "<", "2>")
            continue
        if tok.startswith("-"):
            skip = tok in ("-c", "--config", "-p", "--reporter", "--maxfail", "-n", "--workers",
                           "--project", "--configuration", "-scheme", "-destination", "-workspace",
                           "--tb", "--timeout", "-timeout", "--package", "--test-reporter",
                           "--test-reporter-destination", "--test-concurrency")
            continue
        words.append(tok)
    ignore = {"test", "t", "run", "-m", "pytest", "unittest", "nextest", "exec", "--", "check",
              "verify", "vitest", "jest", "go"}
    rest = [w for w in words if w not in ignore and not re.match(r"^:?[\w:-]*[tT]est\w*$", w)
            and not re.match(r"^python[\d.]*$", w)]
    if runner.split()[0] in ("npm", "pnpm", "yarn", "bun") and re.search(r"\btest:[\w:-]+", seg):
        return "unknown"  # a named sub-suite such as test:unit
    if runner == "fastlane":
        return "partial" if re.search(r"only_testing|testplan", seg) else "unknown"
    if runner == "npm test" and " -- " not in " %s " % seg:
        return "all"
    if not rest:
        return "all"
    if all(w.rstrip("/") in FULL_DIRS or w in FULL_DIRS for w in rest):
        return "all"
    if runner == "go test" and rest == ["."]:
        return "unknown"
    return "partial"


def detect_flags(command, run_in_background=False):
    flags = [name for name, rx in SUSPICIOUS if re.search(rx, command or "")]
    if run_in_background:
        flags.append("run_in_background")
    return flags


def _ints(rx, text):
    return [int(m) for m in re.findall(rx, text, re.I)]


def parse_counts(text):
    """Return (passed, failed, collected); None where unknown. First matching format wins."""
    if not text:
        return None, None, None
    t = text[-20000:]
    m = re.findall(r"=+ (.*?(?:passed|failed|error|errors|no tests ran|deselected|skipped).*?) in [\d.]+s", t) or \
        re.findall(r"(?m)^\s*((?:\d+ (?:passed|failed|errors?|skipped|xfailed|xpassed|deselected|warnings?),? ?)+)"
                   r" in [\d.]+s\s*$", t)
    if m:  # pytest summary line, with or without the ==== banner (-q)
        s = m[-1]
        p = sum(_ints(r"(\d+) passed", s))
        f = sum(_ints(r"(\d+) failed", s)) + sum(_ints(r"(\d+) errors?", s))
        sk = sum(_ints(r"(\d+) skipped", s)) + sum(_ints(r"(\d+) xfailed", s))
        return p, f, p + f + sk
    m = re.search(r"Interrupted: (\d+) errors? during collection", t)
    if m:  # pytest stopped before running anything
        return 0, int(m.group(1)), int(m.group(1))
    m = re.search(r"Ran (\d+) tests? in", t)
    if m:  # unittest
        n = int(m.group(1))
        fm = re.search(r"FAILED \(([^)]*)\)", t)
        f = sum(_ints(r"(?:failures|errors)=(\d+)", fm.group(1))) if fm else 0
        return n - f, f, n
    # node:test summary lines; also when an agent echoed them onto one line ("unit: # pass 5 # fail 0")
    tests = [int(x) for x in re.findall(r"(?m)(?:^|[\s:])(?:#|ℹ) tests (\d+)(?=\s|$)", t)]
    passes = [int(x) for x in re.findall(r"(?m)(?:^|[\s:])(?:#|ℹ) pass (\d+)(?=\s|$)", t)]
    fails = [int(x) for x in re.findall(r"(?m)(?:^|[\s:])(?:#|ℹ) (?:fail|cancelled) (\d+)(?=\s|$)", t)]
    if tests or (passes and fails):  # node:test summary, TAP (#) or spec (ℹ); also when grep kept only pass/fail
        p, f = sum(passes), sum(fails)
        return p, f, sum(tests) if tests else p + f
    m = re.findall(r"Tests?:\s+(.*?\d+ total)", t)
    if m:  # jest
        s = m[-1]
        return (sum(_ints(r"(\d+) passed", s)), sum(_ints(r"(\d+) failed", s)),
                sum(_ints(r"(\d+) total", s)))
    m = re.findall(r"Tests\s+(.*?)\((\d+)\)", t)
    if m:  # vitest
        s, n = m[-1]
        return sum(_ints(r"(\d+) passed", s)), sum(_ints(r"(\d+) failed", s)), int(n)
    if re.search(r"No test files found", t):
        return 0, 0, 0
    m = re.findall(r"test result: \w+\. (\d+) passed; (\d+) failed; (\d+) ignored", t)
    if m:  # cargo (one line per test binary)
        p = sum(int(a) for a, _, _ in m)
        f = sum(int(b) for _, b, _ in m)
        return p, f, p + f + sum(int(c) for _, _, c in m)
    m = re.findall(r"\+(\d+)(?: ~\d+)?(?: -(\d+))?: (?:All tests passed|Some tests failed)", t)
    if m:  # flutter / dart
        p, f = int(m[-1][0]), int(m[-1][1] or 0)
        return p, f, p + f
    m = re.search(r"Failed:\s*(\d+), Passed:\s*(\d+), Skipped:\s*(\d+), Total:\s*(\d+)", t)
    if m:  # dotnet
        return int(m.group(2)), int(m.group(1)), int(m.group(4))
    m = re.findall(r"Tests run: (\d+), Failures: (\d+), Errors: (\d+)", t)
    if m:  # maven: last line is the summary
        n, f, e = (int(x) for x in m[-1])
        return n - f - e, f + e, n
    m = re.search(r"(\d+) tests? completed, (\d+) failed", t)
    if m:  # gradle
        n, f = int(m.group(1)), int(m.group(2))
        return n - f, f, n
    m = re.findall(r"(\d+) examples?, (\d+) failures?", t)
    if m:  # rspec
        n, f = int(m[-1][0]), int(m[-1][1])
        return n - f, f, n
    m = re.search(r"OK \((\d+) tests?, \d+ assertions?\)", t)
    if m:  # phpunit ok
        return int(m.group(1)), 0, int(m.group(1))
    m = re.search(r"Tests: (\d+), Assertions: \d+(?:, Errors: (\d+))?(?:, Failures: (\d+))?", t)
    if m:  # phpunit failing
        n = int(m.group(1))
        f = int(m.group(2) or 0) + int(m.group(3) or 0)
        return n - f, f, n
    m = re.findall(r"Executed (\d+) tests?, with (\d+) failures?", t)
    if m:  # xctest / swift test
        n, f = int(m[-1][0]), int(m[-1][1])
        return n - f, f, n
    m = re.search(r"\|\s*Number of tests\s*\|\s*(\d+)\s*\|[\s\S]*?\|\s*Number of failures\s*\|\s*(\d+)\s*\|", t)
    if m:  # fastlane scan summary table
        n, f = int(m.group(1)), int(m.group(2))
        return n - f, f, n
    m = re.search(r"Test run with (\d+) tests? (?:in \d+ suites? )?(passed|failed)", t)
    if m:  # swift-testing
        n = int(m.group(1))
        return (n, 0, n) if m.group(2) == "passed" else (None, max(1, len(re.findall(r"✘", t))), n)
    oks = re.findall(r"^ok\s+\S+\s+[\d.]+s", t, re.M)
    fails = re.findall(r"^(?:FAIL\s+\S+|--- FAIL:)", t, re.M)
    if oks or fails:  # go test (packages / failed tests)
        return len(oks), len(fails), len(oks) + len(fails)
    if re.search(r"no tests ran|collected 0 items|No tests found|0 tests", t, re.I):
        return 0, 0, 0
    return None, None, None


def response_text(payload):
    """Collect output text from either schema variant. Used for parsing only."""
    resp = payload.get("tool_response")
    if resp is None:
        resp = payload.get("tool_output")
    chunks = []
    if isinstance(resp, str):
        chunks.append(resp)
    elif isinstance(resp, dict):
        for key in ("stdout", "stderr", "output", "text", "content", "error"):
            val = resp.get(key)
            if isinstance(val, str):
                chunks.append(val)
    elif isinstance(resp, list):
        chunks.extend(x.get("text", "") for x in resp if isinstance(x, dict))
    if isinstance(payload.get("error"), str):
        chunks.append(payload["error"])
    return resp, "\n".join(chunks)


def exit_code(payload, resp, text):
    if isinstance(resp, dict):
        for key in ("exit_code", "exitCode", "returncode", "returnCode", "code"):
            val = resp.get(key)
            if isinstance(val, int) and not isinstance(val, bool):
                return val
        if resp.get("interrupted") is True:
            return None
    m = re.search(r"exit(?:ed with)? code[:\s]+(\d+)", text or "", re.I)
    if m:
        return int(m.group(1))
    if payload.get("hook_event_name") == "PostToolUseFailure":
        return 1
    return 0


def parse_bash(payload, test_command=None):
    tin = payload.get("tool_input") or {}
    command = tin.get("command") if isinstance(tin, dict) else None
    command = command if isinstance(command, str) else ""
    background = bool(isinstance(tin, dict) and tin.get("run_in_background"))
    resp, text = response_text(payload)
    code = None if background else exit_code(payload, resp, text)
    runner, seg = detect_runner(command, test_command)
    cwd = payload.get("cwd") if isinstance(payload.get("cwd"), str) else None
    rec = {"command": redact(command, cwd), "exit_code": code}
    if not runner:
        rec["kind"] = "other"
        if DEPLOY.search(command):
            rec["deploy"] = True
        return rec
    passed, failed, collected = (None, None, None) if background else parse_counts(text)
    rec.update({
        "kind": "test_run", "runner": runner, "scope": detect_scope(runner, seg),
        "passed": passed, "failed": failed, "collected": collected,
        "flags": detect_flags(command, background),
    })
    if exit_masked(command, seg):
        rec["exit_masked"] = True
    return rec


def exit_masked(command, seg):
    """True when the test command's output is piped into another command (`npm test | tail -20`)
    without pipefail: the exit code then belongs to the last command, not to the tests."""
    if not seg or re.search(r"\bpipefail\b|PIPESTATUS", command or ""):
        return False
    at = (command or "").find(seg)
    if at < 0:
        return False
    rest = command[at + len(seg):]
    return bool(re.match(r"\s*\|(?!\|)", rest))


# --- writes made through the shell (v0.2, DECISIONS.md D6) -------------------------------------
CODE_FILE = re.compile(r"(?<![\w<>$/])((?:/|~/)?(?:[\w.~-]+/)*[\w.-]+\.(?:py|ts|tsx|js|jsx|mjs|cjs|dart|swift|kt|kts|java|go|"
                       r"rs|rb|php|cs|vue|svelte|sql))(?![\w])")
REDIRECT_INTO = re.compile(r"(?<![<>&\d])>{1,2}\s*([\w.~/-]+)")
TEE_INTO = re.compile(r"\btee\s+(?:-a\s+)?([\w.~/-]+)")
IN_PLACE = re.compile(r"\bsed\s+(?:-\S+\s+)*-i\b|\bperl\s+-\w*i")
SCRIPT_HEREDOC = re.compile(r"\b(?:python3?|node|ruby|perl)\s+-\s*<<")
SCRIPT_WRITES = re.compile(r"\.write_text\(|\.write_bytes\(|open\([^)]*['\"][wa]\+?['\"]|writeFile")
APPLIES_PATCH = re.compile(r"\bpatch\s|\bgit\s+apply\b")
QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"")


_LIT = r"(['\"])([^'\"\n]+)\1"
_WRITE_CALLS = [
    re.compile(r"\bopen\(\s*" + _LIT + r"\s*,\s*['\"][wa]"),                       # open("x.py", "w")
    re.compile(r"\bPath\(\s*" + _LIT + r"\s*\)\.write_(?:text|bytes)\("),           # Path("x.py").write_text(
    re.compile(r"\bwriteFile(?:Sync)?\(\s*" + _LIT),                                # fs.writeFileSync("x.js"
]
_WRITE_VARS = [
    re.compile(r"\bopen\(\s*([A-Za-z_]\w*)\s*,\s*['\"][wa]"),                       # open(p, "w")
    re.compile(r"\b([A-Za-z_]\w*)\.write_(?:text|bytes)\("),                         # p.write_text(
    re.compile(r"\bwriteFile(?:Sync)?\(\s*([A-Za-z_]\w*)\s*,"),                       # writeFileSync(p,
]


def script_write_targets(script):
    """Files a heredoc script writes: literal targets of open(..., "w"), Path(...).write_text and
    writeFileSync, plus variables resolved to their string assignment (p = "x.py"; open(p, "w"))."""
    out = []
    for rx in _WRITE_CALLS:
        out += [m.group(2) for m in rx.finditer(script)]
    for rx in _WRITE_VARS:
        for var in set(m.group(1) for m in rx.finditer(script)):
            assign = re.compile(r"\b(?:const\s+|let\s+|var\s+)?" + re.escape(var) +
                                r"\s*=\s*(?:Path\(|pathlib\.Path\()?\s*" + _LIT)
            out += [m.group(2) for m in assign.finditer(script)]
    return out


def _code_files(text):
    return [m for m in CODE_FILE.findall(text) if CODE_FILE.fullmatch(m)]


def write_targets(command):
    """Code files a shell command writes, best effort. Returns (writes, applies_patch, first_pos).

    writes is [(path, cd_dir)]: path as written in the command, cd_dir the last `cd` before it
    in the same command (or ""). Only explicit writes count: > or >> into a code file, tee,
    sed -i / perl -i on a code file, and a python/node/ruby/perl heredoc script that opens files
    for writing and names a code file. Reading a file never counts.
    """
    command = command or ""
    writes, first = [], None
    cd, pos = "", 0
    for seg in re.split(r"(&&|\|\||[;\n|])", command):
        start = command.find(seg, pos) if seg else pos
        pos = start + len(seg)
        s = seg.strip()
        m = re.match(r"^cd\s+(\S+)", s)
        if m:
            cd = m.group(1).strip("'\"")
            continue
        found = [t for t in REDIRECT_INTO.findall(s) if CODE_FILE.fullmatch(t)]
        found += [t for t in TEE_INTO.findall(s) if CODE_FILE.fullmatch(t)]
        if IN_PLACE.search(s):
            found += _code_files(QUOTED.sub(" ", s))
        for path in found:
            writes.append((path, cd))
            first = start if first is None else first
    if SCRIPT_HEREDOC.search(command) and SCRIPT_WRITES.search(command):
        at = SCRIPT_HEREDOC.search(command).start()
        before = [m.group(1) for m in re.finditer(r"(?:^|&&|;|\n)\s*cd\s+(\S+)", command[:at])]
        targets = [t for t in script_write_targets(command[at:]) if CODE_FILE.fullmatch(t)]
        for path in targets:
            writes.append((path, before[-1].strip("'\"") if before else ""))
        if targets:
            first = at if first is None else min(first, at)
    patch = bool(APPLIES_PATCH.search(command))
    if patch:
        at = APPLIES_PATCH.search(command).start()
        first = at if first is None else min(first, at)
    seen, unique = set(), []
    for w in writes:
        if w not in seen:
            seen.add(w)
            unique.append(w)
    return unique, patch, first
