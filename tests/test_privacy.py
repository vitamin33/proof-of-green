"""Item 4: the sessions folder holds project hashes and relative paths only; the report never prints a path."""
import os

from conftest import Session
from proof_of_green import ledger, report


def _project(tmp_path, name):
    root = tmp_path / "clients" / name
    (root / "src").mkdir(parents=True)
    (root / "src" / "billing.py").write_text("x = 1\n")
    return str(root)


def test_no_absolute_paths_in_sessions_folder(data, tmp_path):
    root = _project(tmp_path, "acme-secret-project")
    s = Session(sid="priv1", cwd=root)
    s.start()
    s.prompt()
    s.edit(os.path.join(root, "src", "billing.py"))
    s.edit("/Users/someone/elsewhere/acme-notes.py")
    s.bash("cd %s && python3 -m pytest %s/src -q" % (root, root), "==== 2 passed in 0.1s ====")
    s.bash("cat " + " ".join("%s/src/f%d.py" % (root, i) for i in range(12)))  # longer than the 240-char cut
    s.bash("ls %s" % os.path.expanduser("~/Documents"))
    s.stop("Fixed the billing rounding. All tests pass.")

    raw = "".join(open(os.path.join(dp, f), encoding="utf-8").read()
                  for dp, _, files in os.walk(str(data)) for f in files)
    assert "acme-secret-project" not in raw and str(tmp_path) not in raw
    assert "acme-notes" not in raw and "/Users/someone" not in raw
    assert os.path.expanduser("~") not in raw
    recs = s.records()
    assert recs[0]["project"] == ledger.project_hash(root) and "cwd" not in recs[0]
    assert [r["path"] for r in recs if r["kind"] == "edit"] == ["src/billing.py", "(outside project)"]
    assert [r["code"] for r in recs if r["kind"] == "edit"] == [True, False]
    run = [r for r in recs if r["kind"] == "test_run"][0]
    assert run["command"] == "cd . && python3 -m pytest src -q"


def test_relativize_respects_path_boundaries():
    from proof_of_green.bashparse import relativize
    assert relativize("ls /repo /repository /repo/a", "/repo") == "ls . <path> a"


def test_paths_outside_the_project_are_masked():
    from proof_of_green.bashparse import redact
    home = os.path.expanduser("~")
    raw = "cd %s/clients/acme && /opt/acme/bin/run --cfg=/etc/acme.cfg; cp a.py ~/acme/b.py; cd ~; python -c 'print(1/2)'" % home
    out = redact(raw, "/repo")
    assert "acme" not in out
    assert out == "cd <path> && <path> --cfg=<path>; cp a.py <path>; cd <path>; python -c 'print(1/2)'"


def test_report_all_shows_project_hash_not_path(data, tmp_path, capsys):
    roots = [_project(tmp_path, "acme-secret-project"), _project(tmp_path, "other-client")]
    for i, root in enumerate(roots):
        s = Session(sid="rep%d" % i, cwd=root)
        s.start()
        s.prompt()
        s.edit(os.path.join(root, "src", "billing.py"))
        s.stop("Done.")
    report.main(["--all", "--data", str(data)])
    lines = capsys.readouterr().out.splitlines()
    assert lines[-1].startswith("data: ")  # the plugin's own data folder, not a project
    out = "\n".join(lines[:-1])
    for root in roots:
        assert ledger.project_hash(root)[:6] in out
    assert "2 sessions in 2 projects" in out
    assert "acme" not in out and "other-client" not in out and str(tmp_path) not in out
    assert "project %s session rep0" % ledger.project_hash(roots[0])[:6] in out


def test_old_ledger_with_cwd_is_hashed_in_report(data, capsys):
    s = Session(sid="old")
    ledger.append("old", {"kind": "session", "session_id": "old", "cwd": "/Users/x/clients/acme"})
    s.prompt()
    report.main(["--data", str(data)])
    out = capsys.readouterr().out
    assert ledger.project_hash("/Users/x/clients/acme")[:6] in out and "acme" not in out


def test_agent_id_is_stored_for_subagent_records(data):
    s = Session(sid="agents")
    s.start()
    s.fire("PostToolUse:edit", {"hook_event_name": "PostToolUse", "tool_name": "Edit", "agent_id": "a30aca86184812420",
                                "agent_type": "general-purpose", "tool_input": {"file_path": "/repo/calc.py"}})
    s.fire("PostToolUse:bash", {"hook_event_name": "PostToolUse", "tool_name": "Bash", "agent_id": "a30aca86184812420",
                                "tool_input": {"command": "pytest"}, "tool_response": {"stdout": "== 1 passed in 0.1s =="}})
    s.edit()  # parent's own edit
    recs = [r for r in s.records() if r["kind"] in ("edit", "test_run")]
    assert [r.get("agent_id") for r in recs] == ["a30aca86184812420", "a30aca86184812420", None]
