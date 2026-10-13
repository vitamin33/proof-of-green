#!/usr/bin/env python3
"""Build the blind re-judging set: 20 would-warn cases with the full turn from the transcript.

Reads the two private review files (warnings-sample.md, warnings-sample-2.md), keeps the cases
Claude judged fair or unfair, picks all fair ones plus unfair ones spread over both samples and
both agents (fixed seed), and for each finds the turn in the local Claude Code transcript or
Codex rollout: every step between the previous final reply and this one (assistant text, shell
commands with the tail of their output, file edits) plus the full final reply.
Writes ~/research/pog-data/review/rejudge-cases.json (mode 600). Prints counts only.
"""
import datetime
import glob
import json
import os
import random
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "analysis"))
import backfill  # noqa: E402
from proof_of_green import bashparse, codex  # noqa: E402

MAX_STEPS = 150

REVIEW = os.path.expanduser("~/research/pog-data/review")
OUT = os.path.join(REVIEW, "rejudge-cases.json")
TAIL = 600


def parse(path, sample):
    s = open(path, encoding="utf-8").read()
    out = []
    for block in re.split(r"(?m)^(?=## W\d\d)", s)[1:]:
        head = block.splitlines()[0]
        m = re.match(r"## (W\d\d)\s+(Claude Code|Codex) · (.*?) · ([\d-]+ [\d:]+) · session (\w+)", head)
        if not m:
            continue
        g = lambda rx: (re.search(rx, block, re.S) or [None, ""])[1]
        out.append({"key": "%s-%s" % (sample, m.group(1)), "agent": m.group(2), "project": m.group(3),
                    "when": m.group(4), "session": m.group(5),
                    "claims": g(r"Claims: (.*?)\n"), "warning": g(r"Warning that would show: `(.*?)`"),
                    "reply_start": g(r"Final reply.*?```\n(.*?)```").strip(),
                    "my_verdict": g(r"VERDICT: (\w+)"), "my_note": g(r"NOTE: (.*?)\n").strip()})
    return out


def when_ts(case):
    return datetime.datetime.strptime(case["when"], "%Y-%m-%d %H:%M").timestamp()  # local time, as in the review files


def ts_of(e):
    t = e.get("timestamp") or ""
    try:
        return datetime.datetime.strptime(t[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=datetime.timezone.utc).timestamp()
    except ValueError:
        return 0


def closest(cands, ents, case):
    return min(cands, key=lambda i: abs(ts_of(ents[i]) - when_ts(case))) if cands else None


def text_of(content):
    if isinstance(content, str):
        return content
    return "\n".join(x.get("text", "") for x in content or [] if isinstance(x, dict) and x.get("type") in ("text", None))


def claude_turn(case):
    files = glob.glob(os.path.expanduser("~/.claude/projects/*/%s*.jsonl" % case["session"]))
    probe = re.sub(r"\s+", " ", case["reply_start"])[:60]
    for f in files:
        ents = [json.loads(l) for l in open(f, errors="replace")]
        ends = [i for i, e in enumerate(ents) if e.get("type") == "assistant" and not e.get("isSidechain")
                and (e.get("message") or {}).get("stop_reason") in ("end_turn", "stop_sequence")]
        hit = closest([i for i in ends if probe and probe in re.sub(r"\s+", " ", text_of(ents[i]["message"].get("content")))], ents, case)
        if hit is None:
            continue
        mid = (ents[hit].get("message") or {}).get("id")
        # the unit of work is everything since your last own message (background notifications
        # can end a turn and start a short new one)
        prompts = [i for i, e in enumerate(ents[:hit]) if not e.get("isSidechain") and backfill.is_prompt(e)]
        start = prompts[-1] if prompts else 0
        k = len(prompts) - 1
        while k > 0 and k >= len(prompts) - 3 and sum(
                1 for e in ents[start:hit] if e.get("type") == "assistant" and "tool_use" in json.dumps(e.get("message", {}).get("content"))) < 10:
            k -= 1
            start = prompts[k]
        steps, pending = [], {}
        prompt = ""
        for e in ents[start:hit + 1]:
            if e.get("isSidechain"):
                continue
            c = (e.get("message") or {}).get("content")
            if not e.get("isSidechain") and backfill.is_prompt(e):
                said = (c if isinstance(c, str) else text_of(c))[:600]
                if not prompt:
                    prompt = said
                else:
                    steps.append({"kind": "you", "text": said})
            if e.get("type") == "assistant" and isinstance(c, list):
                for b in c:
                    if b.get("type") == "text" and b.get("text", "").strip() and (e.get("message") or {}).get("id") != mid:
                        steps.append({"kind": "say", "text": b["text"][:500]})
                    if b.get("type") == "tool_use":
                        tin = b.get("input") or {}
                        if b.get("name") == "Bash":
                            step = {"kind": "run", "cmd": tin.get("command", "")[:1500], "out": "", "failed": False}
                            if bashparse.detect_runner(bashparse.blank_heredocs(tin.get("command", "")))[0]:
                                step["test"] = True
                        elif b.get("name") in ("Edit", "Write", "MultiEdit"):
                            step = {"kind": "edit", "path": tin.get("file_path", "")}
                        else:
                            step = {"kind": "tool", "name": b.get("name"), "what": json.dumps(tin)[:200]}
                        pending[b.get("id")] = step
                        steps.append(step)
            if e.get("type") == "user" and isinstance(c, list):
                for b in c:
                    if isinstance(b, dict) and b.get("tool_use_id") in pending:
                        step = pending.pop(b["tool_use_id"])
                        if step["kind"] == "run":
                            body = text_of(b.get("content")) if not isinstance(b.get("content"), str) else b["content"]
                            step["out"] = body[-TAIL:]
                            step["failed"] = bool(b.get("is_error"))
        reply = "\n".join(text_of(e["message"].get("content")) for e in ents[start:hit + 1]
                           if e.get("type") == "assistant" and (e.get("message") or {}).get("id") == mid)
        return {"prompt": prompt, "steps": steps, "reply": reply}
    return None


def codex_turn(case):
    files = glob.glob(os.path.expanduser("~/.codex/sessions/**/*%s*.jsonl" % case["session"]), recursive=True) + \
        glob.glob(os.path.expanduser("~/.codex/archived_sessions/**/*%s*.jsonl" % case["session"]), recursive=True)
    probe = re.sub(r"\s+", " ", case["reply_start"])[:60]
    for f in files:
        ents = [json.loads(l) for l in open(f, errors="replace")]
        done = [i for i, e in enumerate(ents) if (e.get("payload") or {}).get("type") == "task_complete"]
        hit = closest([i for i in done if probe and probe in re.sub(r"\s+", " ", str(ents[i]["payload"].get("last_agent_message") or ""))], ents, case)
        if hit is None:
            continue
        prev = [i for i in done if i < hit]
        start, k = (prev[-1] + 1 if prev else 0), len(prev) - 1
        while k > 0 and k >= len(prev) - 3 and sum(
                1 for e in ents[start:hit] if (e.get("payload") or {}).get("type") == "custom_tool_call") < 5:
            k -= 1
            start = prev[k] + 1
        steps, calls, prompt = [], {}, ""
        for e in ents[start:hit + 1]:
            p = e.get("payload") or {}
            t = p.get("type")
            if t == "user_message":
                if not prompt:
                    prompt = str(p.get("message") or "")[:600]
                else:
                    steps.append({"kind": "you", "text": str(p.get("message") or "")[:600]})
            if t == "task_complete" and e is not ents[hit]:
                steps.append({"kind": "say", "text": "(earlier final reply) " + str(p.get("last_agent_message") or "")[:500]})
            if t == "agent_message" and p.get("message"):
                steps.append({"kind": "say", "text": str(p["message"])[:500]})
            if t == "custom_tool_call" and p.get("name") == "exec":
                calls[p.get("call_id")] = p.get("input") or ""
            if t == "custom_tool_call_output" and p.get("call_id") in calls:
                code = calls.pop(p["call_id"])
                for ev in codex.exec_events(code, p.get("output")):
                    if ev[0] == "patch":
                        steps.append({"kind": "edit", "path": ev[1]})
                    elif ev[0] == "cmd" and ev[1]:
                        res = ev[3] or {}
                        step = {"kind": "run", "cmd": ev[1][:1500], "out": (res.get("output") or "")[-TAIL:],
                                "failed": bool(res.get("exit_code")), "exit": res.get("exit_code")}
                        if bashparse.detect_runner(bashparse.blank_heredocs(ev[1]))[0]:
                            step["test"] = True
                        steps.append(step)
                    elif ev[0] == "finish":
                        steps.append({"kind": "run", "cmd": "(result of an earlier command that was still running)",
                                      "out": (ev[2].get("output") or "")[-TAIL:], "exit": ev[2].get("exit_code")})
        return {"prompt": prompt, "steps": steps, "reply": str(ents[hit]["payload"].get("last_agent_message") or "")}
    return None


def main():
    cases = parse(os.path.join(REVIEW, "warnings-sample.md"), "s1") + parse(os.path.join(REVIEW, "warnings-sample-2.md"), "s2")
    judged, seen = [], set()
    for c in cases:
        k = re.sub(r"\s+", " ", c["reply_start"])[:80]
        if c["my_verdict"] in ("fair", "unfair") and k not in seen:
            seen.add(k)
            judged.append(c)
    fair = [c for c in judged if c["my_verdict"] == "fair"]
    unfair = [c for c in judged if c["my_verdict"] == "unfair"]
    random.seed(20261012)
    pick = list(fair)
    for agent in ("Claude Code", "Codex"):
        for sample in ("s1", "s2"):
            group = [c for c in unfair if c["agent"] == agent and c["key"].startswith(sample)]
            pick += random.sample(group, min(4 if agent == "Codex" else 5, len(group)))
    pick = pick[:20]
    random.shuffle(pick)
    def finish(turn):
        for st in turn["steps"]:
            if st["kind"] == "run":
                writes, patch, _ = bashparse.write_targets(st["cmd"])
                if writes or patch:
                    st["writes"] = [w for w, _ in writes] + (["(patch)"] if patch else [])
        if len(turn["steps"]) > MAX_STEPS:
            turn["cut"] = len(turn["steps"]) - MAX_STEPS
            turn["steps"] = turn["steps"][-MAX_STEPS:]
        return turn

    out, missing = [], 0
    for n, c in enumerate(pick, 1):
        turn = claude_turn(c) if c["agent"] == "Claude Code" else codex_turn(c)
        if turn is None:
            missing += 1
            turn = {"prompt": "", "steps": [], "reply": c["reply_start"]}
        out.append(dict(c, id=n, **finish(turn)))
    fd = os.open(OUT, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        json.dump(out, fh, ensure_ascii=False)
    print("judged by Claude: %d (fair %d, unfair %d); picked %d; full turn found for %d; written to %s (mode 600)" % (
        len(judged), len(fair), len(unfair), len(out), len(out) - missing, OUT))


if __name__ == "__main__":
    main()
