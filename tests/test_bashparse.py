import pytest

from conftest import load
from falsegreen import bashparse as bp

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
]


@pytest.mark.parametrize("command,runner,scope", RUNNERS)
def test_runner_and_scope(command, runner, scope):
    got, seg = bp.detect_runner(command)
    assert got == runner
    assert bp.detect_scope(got, seg) == scope


@pytest.mark.parametrize("command", ["ls -la", "git status", "npm install", "pip install pytest",
                                     "cat tests/test_a.py", "npm run test:e2e:setup", "echo test"])
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


def test_redaction_keeps_harmless_commands():
    assert bp.redact("pytest -q tests/") == "pytest -q tests/"
    assert bp.redact("mkdir -p build && make test") == "mkdir -p *** && make test"
