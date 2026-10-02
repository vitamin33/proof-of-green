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
    ("npm test", r"^(?:npm|pnpm|yarn|bun)\s+(?:run\s+)?(?:test|t)\b(?!:)"),
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
    ("rspec", r"(?:^|/)rspec\b"),
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
    out = " ".join(out.split())
    return out if len(out) <= limit else out[:limit] + "…"


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
                           "--tb", "--timeout", "-timeout", "--package")
            continue
        words.append(tok)
    ignore = {"test", "t", "run", "-m", "pytest", "unittest", "nextest", "exec", "--", "check",
              "verify", "vitest", "jest", "go"}
    rest = [w for w in words if w not in ignore and not re.match(r"^:?[\w:-]*[tT]est\w*$", w)
            and not re.match(r"^python[\d.]*$", w)]
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
    m = re.findall(r"=+ (.*?(?:passed|failed|error|errors|no tests ran|deselected|skipped).*?) in [\d.]+s", t)
    if m:  # pytest summary line
        s = m[-1]
        p = sum(_ints(r"(\d+) passed", s))
        f = sum(_ints(r"(\d+) failed", s)) + sum(_ints(r"(\d+) errors?", s))
        sk = sum(_ints(r"(\d+) skipped", s)) + sum(_ints(r"(\d+) xfailed", s))
        return p, f, p + f + sk
    m = re.search(r"Ran (\d+) tests? in", t)
    if m:  # unittest
        n = int(m.group(1))
        fm = re.search(r"FAILED \(([^)]*)\)", t)
        f = sum(_ints(r"(?:failures|errors)=(\d+)", fm.group(1))) if fm else 0
        return n - f, f, n
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
    return rec
