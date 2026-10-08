import pytest

from conftest import load
from proof_of_green import bashparse as bp

RUNNERS = [
    ("pytest -q", "pytest", "all"),
    ("python3 -m pytest tests/", "pytest", "all"),
    ("pytest tests/test_api.py::test_login", "pytest", "partial"),
    ("pytest -k login", "pytest", "partial"),
    ("cd app && uv run pytest -x 2>&1 | tail -20", "pytest", "all"),
    ("python -m unittest", "unittest", "all"),
    ("python3 -m unittest tests.test_calc", "unittest", "partial"),
    ("npm test", "npm test", "all"),
    ("npm run test -- auth", "npm test", "partial"),
    ("pnpm test", "pnpm test", "all"),
    ("yarn test src/a.test.ts", "yarn test", "partial"),
    ("bun test", "bun test", "all"),
    ("npx vitest run", "vitest", "all"),
    ("npx vitest run src/api.test.ts", "vitest", "partial"),
    ("npx jest", "jest", "all"),
    ("npx jest --testPathPattern auth", "jest", "partial"),
    ("npx jest -t 'logs in'", "jest", "partial"),
    ("go test ./...", "go test", "all"),
    ("go test ./pkg/parser -run TestParse", "go test", "partial"),
    ("go test .", "go test", "unknown"),
    ("cargo test", "cargo test", "all"),
    ("cargo test parse_header", "cargo test", "partial"),
    ("flutter test", "flutter test", "all"),
    ("flutter test test/widget_test.dart", "flutter test", "partial"),
    ("dart test", "dart test", "all"),
    ("dotnet test", "dotnet test", "all"),
    ("dotnet test --filter Category=Fast", "dotnet test", "partial"),
    ("./gradlew test", "gradle test", "all"),
    ("./gradlew test --tests com.acme.FooTest", "gradle test", "partial"),
    ("mvn -q test", "mvn test", "all"),
    ("mvn test -Dtest=FooTest", "mvn test", "partial"),
    ("make test", "make test", "all"),
    ("xcodebuild test -scheme App -destination 'platform=iOS Simulator,name=iPhone 16'", "xcodebuild test", "all"),
    ("xcodebuild test -scheme App -only-testing:AppTests/LoginTests", "xcodebuild test", "partial"),
    ("swift test", "swift test", "all"),
    ("swift test --filter ParserTests", "swift test", "partial"),
    ("bundle exec rspec", "rspec", "all"),
    ("bundle exec rspec spec/models/user_spec.rb", "rspec", "partial"),
    ("vendor/bin/phpunit", "phpunit", "all"),
    ("vendor/bin/phpunit --filter testLogin", "phpunit", "partial"),
    # runners used on the observe-run projects
    ("flutter test --coverage", "flutter test", "all"),
    ("flutter test test/foo_test.dart", "flutter test", "partial"),
    ("dart test test/a_test.dart", "dart test", "partial"),
    ("xcodebuild -scheme App -destination 'platform=iOS Simulator,name=iPhone 16' test", "xcodebuild test", "all"),
    ("fastlane test", "fastlane", "unknown"),
    ("fastlane ios test", "fastlane", "unknown"),
    ("bundle exec fastlane scan", "fastlane", "unknown"),
    ("fastlane ios test only_testing:AppTests/LoginTests", "fastlane", "partial"),
    ("npm run test:unit", "npm test", "unknown"),
    ("pnpm run test:e2e", "pnpm test", "unknown"),
    ("yarn test:ci", "yarn test", "unknown"),
    ("pnpm -r test", "pnpm test", "all"),
    ("pnpm --filter web test", "pnpm test", "partial"),
    ("make check", "make test", "all"),
    ("node --test", "node --test", "all"),
    ("node --test test/a.test.js", "node --test", "partial"),
    ("node --test --test-reporter spec", "node --test", "all"),
    ("node --test --test-name-pattern login", "node --test", "partial"),
    # v0.2: missed in the warning-precision review
    ("PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s ops/tools -q", "unittest", "partial"),
    ("python3 -B -m unittest", "unittest", "all"),
    ("python3 -m unittest test_calc", "unittest", "partial"),
    (".venv/bin/python3 -B -m pytest tests/test_a.py -q", "pytest", "partial"),
    ("python3 -B ops/tools/test_sources_mutations.py", "python test file", "partial"),
    ("python3 tools/parser_test.py > log 2>&1", "python test file", "partial"),
    ("./scripts/node.sh npm test", "npm test", "all"),
    ("./scripts/node.sh npx vitest run test/api/a.test.ts", "vitest", "partial"),
    ("npm run verify > out.txt 2>&1", "npm test", "unknown"),
    ("npm run e2e", "npm test", "unknown"),
    ("npx playwright test", "playwright", "all"),
    ("npx playwright test e2e/login.spec.ts", "playwright", "partial"),
]

NOT_RUNNERS = [
    "python3 - <<'PY'\nopen('test_a.py').read()\nPY",
    "python3 tools/make_test_data.py",
    "cat tests/test_a.py",
    "npm run check",
    "npm run typecheck",
    "./scripts/build.sh",
]


@pytest.mark.parametrize("command", NOT_RUNNERS)
def test_not_a_test_run(command):
    assert bp.detect_runner(command) == (None, None)


@pytest.mark.parametrize("command,runner,scope", RUNNERS)
def test_runner_and_scope(command, runner, scope):
    got, seg = bp.detect_runner(command)
    assert got == runner
    assert bp.detect_scope(got, seg) == scope


@pytest.mark.parametrize("command", ["ls -la", "git status", "npm install", "pip install pytest",
                                     "cat tests/test_a.py", "echo test", "npm run build", "pnpm -r build",
                                     "fastlane beta", "git stash", "git checkout main -- calc.py",
                                     "git worktree add ../wt feature", "node scripts/build.js", "node --version"])
def test_non_test_commands(command):
    assert bp.detect_runner(command) == (None, None)


def test_custom_test_command_is_full_scope():
    runner, seg = bp.detect_runner("make ci-full", test_command="make ci-full")
    assert runner == "custom" and bp.detect_scope(runner, seg) == "all"


@pytest.mark.parametrize("command,flag", [
    ("pytest || true", "|| true"),
    ("npm test; true", "; true"),
    ("pytest --collect-only", "--collect-only"),
    ("npx jest --passWithNoTests", "--passWithNoTests"),
    ("cargo test --no-run", "--no-run"),
    ("set +e; pytest", "set +e"),
])
def test_suspicious_flags(command, flag):
    assert flag in bp.detect_flags(command)


def test_background_flag():
    rec = bp.parse_bash({"tool_input": {"command": "pytest", "run_in_background": True}})
    assert "run_in_background" in rec["flags"] and rec["exit_code"] is None


COUNTS = [
    ("============ 3 failed, 10 passed, 1 skipped in 0.52s ============", (10, 3, 14)),
    ("collected 5 items\n\n===== 5 passed in 0.10s =====", (5, 0, 5)),
    ("==== no tests ran in 0.01s ====", (0, 0, 0)),
    ("Ran 12 tests in 0.004s\n\nFAILED (failures=2, errors=1)", (9, 3, 12)),
    ("Ran 4 tests in 0.002s\n\nOK", (4, 0, 4)),
    ("Tests:       1 failed, 4 passed, 5 total", (4, 1, 5)),
    (" Test Files  2 passed (2)\n      Tests  1 failed | 7 passed (8)", (7, 1, 8)),
    ("No test files found, exiting with code 1", (0, 0, 0)),
    ("test result: ok. 5 passed; 0 failed; 1 ignored; 0 measured\n"
     "test result: FAILED. 2 passed; 1 failed; 0 ignored", (7, 1, 9)),
    ("00:02 +3 -1: Some tests failed.", (3, 1, 4)),
    ("00:01 +12: All tests passed!", (12, 0, 12)),
    ("Passed!  - Failed:     0, Passed:    12, Skipped:     0, Total:    12", (12, 0, 12)),
    ("Tests run: 3, Failures: 0, Errors: 0, Skipped: 0\n\nResults:\n\nTests run: 9, Failures: 1, Errors: 1, Skipped: 0", (7, 2, 9)),
    ("12 tests completed, 2 failed", (10, 2, 12)),
    ("Finished in 0.3 seconds\n14 examples, 1 failure", (13, 1, 14)),
    ("OK (8 tests, 20 assertions)", (8, 0, 8)),
    ("Tests: 8, Assertions: 20, Failures: 2.", (6, 2, 8)),
    ("Executed 15 tests, with 1 failure (0 unexpected) in 0.2 seconds", (14, 1, 15)),
    ("ok  \tgithub.com/acme/api/pkg/a\t0.012s\nFAIL\tgithub.com/acme/api/pkg/b\t0.020s", (1, 1, 2)),
    ("00:05 +10 ~1: All tests passed!", (10, 0, 10)),
    ("00:07 +10 ~1 -2: Some tests failed.", (10, 2, 12)),
    ("+-----------------------+----+\n| Number of tests       | 42 |\n| Number of failures    | 1  |\n+---", (41, 1, 42)),
    ("Test Suite 'All tests' failed\n\t Executed 30 tests, with 2 failures (0 unexpected) in 1.1 (1.2) seconds\n** TEST FAILED **",
     (28, 2, 30)),
    ("random text", (None, None, None)),
]


@pytest.mark.parametrize("text,expected", COUNTS)
def test_parse_counts(text, expected):
    assert bp.parse_counts(text) == expected


@pytest.mark.parametrize("name,code,failed", [
    ("post_bash_pass.tool_response.json", 0, 0),
    ("post_bash_pass.tool_output.json", 0, 0),
    ("post_bash_pass.tool_output_text.json", 0, 0),
    ("post_bash_fail.failure.json", 1, 1),
    ("post_bash_fail.tool_response.json", 1, 1),
    ("post_bash_fail.tool_output.json", 1, 1),
])
def test_both_schema_variants(name, code, failed):
    rec = bp.parse_bash(load(name))
    assert rec["kind"] == "test_run" and rec["runner"] == "unittest"
    assert rec["exit_code"] == code and rec["failed"] == failed and rec["collected"] == 4


def test_other_command_keeps_no_output():
    rec = bp.parse_bash(load("post_bash_other.tool_response.json"))
    assert rec["kind"] == "other"
    assert "SENTINEL" not in str(rec) and "ghp_" not in rec["command"]


def test_deploy_command_is_marked():
    assert bp.parse_bash({"tool_input": {"command": "vercel deploy --prod"}}).get("deploy") is True
    assert bp.parse_bash({"tool_input": {"command": "npm i -g vercel"}}).get("deploy") is None


@pytest.mark.parametrize("raw,secret", [
    ("mysql -u root -p hunter2 db", "hunter2"),
    ("mysql -u root -phunter2 db", "hunter2"),
    ("psql --password=hunter2", "hunter2"),
    ("curl https://api.x.io/v1?token=abc123def&x=1", "abc123def"),
    ("git clone https://bob:s3cr3t@github.com/acme/repo", "s3cr3t"),
    ("API_KEY=sk-live-123456789012 npm test", "sk-live-123456789012"),
    ("export GITHUB_TOKEN=ghp_aaaaaaaaaaaaaaaa1234", "ghp_aaaaaaaaaaaaaaaa1234"),
    ("MY_SECRET='a b c' pytest", "a b c"),
    ("curl -H 'Authorization: Bearer eyJhbGciOi.xyz' https://x", "eyJhbGciOi.xyz"),
    ("deploy --token abcdef", "abcdef"),
])
def test_redaction(raw, secret):
    out = bp.redact(raw)
    assert secret not in out and "***" in out


def test_redaction_keeps_harmless_commands(tmp_path):
    (tmp_path / "build").mkdir()
    (tmp_path / "a.txt").write_text("x")
    cwd = str(tmp_path)
    assert bp.redact("pytest -q tests/", cwd) == "pytest -q tests/"
    assert bp.redact("mkdir -p build && make test", cwd) == "mkdir -p build && make test"
    assert bp.redact("mkdir -p %s/build" % cwd, "/") == "mkdir -p <path>"  # not ***; outside-project paths are masked
    assert bp.redact("cp -p a.txt build/", cwd) == "cp -p a.txt build/"
    assert bp.redact("tool --password build", cwd) == "tool --password build"


@pytest.mark.parametrize("raw,expected", [
    ("mysql -u root -p hunter2 db", "mysql -u root -p *** db"),
    ("psql --password=hunter2 -h db", "psql --password=*** -h db"),
    ("tool --password 'not a path'", "tool --password ***"),
    ("mkdir -p does/not/exist", "mkdir -p ***"),
    ("pytest -p no:cacheprovider", "pytest -p ***"),
])
def test_p_and_password_redacted_unless_existing_path(raw, expected, tmp_path):
    assert bp.redact(raw, str(tmp_path)) == expected


def test_parse_bash_uses_payload_cwd(tmp_path):
    (tmp_path / "out").mkdir()
    rec = bp.parse_bash({"cwd": str(tmp_path), "tool_input": {"command": "mkdir -p out"}})
    assert rec["command"] == "mkdir -p out"


def test_fastlane_release_lane_is_deploy_not_test():
    rec = bp.parse_bash({"tool_input": {"command": "bundle exec fastlane ios beta"}})
    assert rec["kind"] == "other" and rec.get("deploy") is True
    assert bp.parse_bash({"tool_input": {"command": "fastlane test"}})["kind"] == "test_run"


NODE_TEST = [  # real node v22.22.0 output, 2026-10-05; local paths replaced with /project
    ("pass_default.txt", (2, 0, 3)),     # 2 pass + 1 skipped
    ("mixed_default.txt", (3, 1, 5)),    # default reporter when piped = TAP
    ("mixed_tap.txt", (3, 1, 5)),
    ("mixed_spec.txt", (3, 1, 5)),       # spec reporter: "ℹ tests 5", summary before failure details
    ("mixed_npm_grep.txt", (3, 1, 5)),   # npm test 2>&1 | grep -E "^# (tests|pass|fail)|^not ok"
    ("npm_grep_passfail.txt", (3, 1, 4)),        # grep -E "^# (pass|fail)": no "# tests" line, skips not counted
    ("npm_grep_passfail_notok.txt", (3, 1, 4)),  # grep -E "^# (pass|fail)|^not ok"
    ("pass_grep_passfail.txt", (2, 0, 2)),
]


@pytest.mark.parametrize("text", ["# pass 3\n", "# fail 0\n", "ok 1 - a\nnot ok 2 - b\n"])
def test_node_test_partial_summaries_stay_unknown(text):
    assert bp.parse_counts(text) == (None, None, None)


@pytest.mark.parametrize("name,expected", NODE_TEST)
def test_node_test_summary(name, expected):
    import os
    from conftest import FIXTURES
    with open(os.path.join(FIXTURES, "node_test", name), encoding="utf-8") as fh:
        assert bp.parse_counts(fh.read()) == expected


@pytest.mark.parametrize("text,expected", [
    ("....\n4 passed in 0.02s\n", (4, 0, 4)),                         # pytest -q, no banner
    ("F..\n1 failed, 2 passed, 1 skipped in 0.10s\n", (2, 1, 4)),
    ("!!!!!!!! Interrupted: 2 errors during collection !!!!!!!!", (0, 2, 2)),
    ("unit: # pass 5 # fail 0\n", (5, 0, 5)),                           # node summary echoed on one line
    ("api: # tests 7 # pass 6 # fail 1", (6, 1, 7)),
])
def test_v02_parser_formats(text, expected):
    assert bp.parse_counts(text) == expected


@pytest.mark.parametrize("command,writes,patch", [
    ('sed -i "" "s/x/y/" cycles/erasure.js && npm test', [("cycles/erasure.js", "")], False),
    ('cd functions && sed -i "" "s/x/y/" index.js lib/a.ts', [("index.js", "functions"), ("lib/a.ts", "functions")], False),
    ("cat > src/api/client.ts <<EOF\nexport const x = 1\nEOF", [("src/api/client.ts", "")], False),
    ("cat >> test/a.test.js <<EOF\nx\nEOF", [("test/a.test.js", "")], False),
    ('python3 - <<"EOF"\np="cycles/erasure.js"\nopen(p, "w").write(s)\nEOF', [("cycles/erasure.js", "")], False),
    ('python3 - <<"EOF"\nprint(open("a.py").read())\nEOF', [], False),
    ('python3 - <<"EOF"\nsrc = open("lib/a.py").read()\nopen("report.json", "w").write(src)\nEOF', [], False),
    ('python3 - <<"EOF"\nfrom pathlib import Path\nPath("src/b.ts").write_text("x")\nEOF', [("src/b.ts", "")], False),
    ('python3 - <<"EOF"\nfor f in ["a.py", "b.py", "c.py"]:\n    print(open(f).read())\nEOF', [], False),
    ("node - <<'EOF'\nconst fs = require('fs'); const p = 'src/x.js'; fs.writeFileSync(p, 'y')\nEOF", [("src/x.js", "")], False),
    ("cat src/a.ts | tee src/b.ts", [("src/b.ts", "")], False),
    ("git apply fix.patch", [], True),
    ("node scripts/gen.js > out.log", [], False),
    ("grep -n foo src/a.ts > /tmp/x.txt", [], False),
    ("sed -n 10,20p src/a.ts", [], False),
    ("echo x > README.md", [], False),
    ("npm test 2>&1 | grep -E '^# (pass|fail)'", [], False),
    # v0.2 review: the word "patch" in text, read-only applies, heredoc bodies are data
    ("python3 - <<'PY'\np='STATUS.md';s=open(p).read()+'native patch now accepts text'\nopen(p,'w').write(s)\nPY", [], False),
    ("git commit -m 'fix: patch the parser'", [], False),
    ("git apply --check fix.diff", [], False),
    ("git -C repo apply fix.diff && npm test", [], True),
    ("patch -p1 < fix.diff", [], True),
    ("cat > $S/dry4.py <<'EOF'\nimport os\nprint(1) if x > 2 else None\nwith open(out, 'w') as f: f.write(a >> b.py)\nEOF", [], False),
    ("cat > notes.md <<'EOF'\nrun: echo x > src/a.py\nEOF", [], False),
])
def test_write_targets(command, writes, patch):
    got, got_patch, _ = bp.write_targets(command)
    assert got == writes and got_patch is patch


@pytest.mark.parametrize("command,masked", [
    ("npm test 2>&1 | tail -20", True),
    ("cd app && pytest -q | tail -5", True),
    ("npm test | grep -c FAIL", True),
    ("pytest -q", False),
    ("pytest -q || true", False),                       # flagged as suspicious instead
    ("set -o pipefail; npm test | tail -20", False),
    ("npm test | tee out.log; echo ${PIPESTATUS[0]}", False),
    ("npm test && echo done | cat", False),             # the pipe belongs to echo, not to the tests
])
def test_exit_masked(command, masked):
    rec = bp.parse_bash({"tool_input": {"command": command}, "tool_response": {"stdout": ""}})
    assert rec["kind"] == "test_run"
    assert bool(rec.get("exit_masked")) is masked
