"""Reading Codex tool calls (v0.2). Codex sends the same hook payload fields as Claude Code, but
its tools differ: `exec_command` takes `cmd`, `apply_patch` takes a patch text, and in code mode
one `exec` call runs JavaScript that calls those tools. Same helpers serve analysis/backfill_codex.py.
"""
import json
import re

PATCH_FILE = re.compile(r"^\*\*\* (?:Update|Add|Delete) File: (.+)$|^\*\*\* Move to: (.+)$", re.M)


def js_string(src, i):
    """Read a JS string literal starting at src[i] (one of ' " `). Returns (value, end) or (None, i)."""
    if i >= len(src) or src[i] not in "'\"`":
        return None, i
    q, j, out = src[i], i + 1, []
    while j < len(src):
        ch = src[j]
        if ch == "\\" and j + 1 < len(src):
            nxt = src[j + 1]
            out.append({"n": "\n", "t": "\t", "r": "\r", "0": "\0"}.get(nxt, nxt))
            j += 2
            continue
        if ch == q:
            return "".join(out), j + 1
        out.append(ch)
        j += 1
    return None, i


def strings_in(src):
    out, i = [], 0
    while i < len(src):
        if src[i] in "'\"`":
            s, j = js_string(src, i)
            if s is not None:
                out.append(s)
                i = j
                continue
        i += 1
    return out


def calls_in(code):
    """Tool calls in JS code, in source order: ("exec", cmd, workdir) and ("stdin", process id).
    cmd is None when it is not a literal. A for-of loop over literal commands expands to one each."""
    out = []
    loops = [(m.start(), m.group(1), strings_in(code[m.end():m.end() + code[m.end():].find("]")]))
             for m in re.finditer(r"for\s*\(\s*(?:const|let|var)\s+(\w+)\s+of\s*\[", code)]
    for m in re.finditer(r"(exec_command|write_stdin)\s*\(\s*\{", code):
        start = m.end()
        if m.group(1) == "write_stdin":
            sid = re.match(r"[^}]*?[\"']?session_id[\"']?\s*:\s*(\d+)", code[start:start + 300])
            out.append(("stdin", int(sid.group(1)) if sid else None))
            continue
        # the cmd string may itself contain "})" (a heredoc with JS), so read it before looking for the end
        c = re.match(r"[^\"'`]*?[\"']?cmd[\"']?\s*:\s*", code[start:start + 300])
        cmd, after = (js_string(code, start + c.end()) if c else (None, start))
        end = code.find("})", after)
        body = code[start:end if end > 0 else start + 2000]
        wd = re.search(r"[\"']?workdir[\"']?\s*:\s*", body)
        workdir = js_string(body, wd.end())[0] if wd else None
        if cmd is None and re.match(r"\s*cmd\s*[,}]", code[start:start + 50]):
            loop = [lp for lp in loops if lp[0] < m.start() and lp[1] == "cmd"]
            if loop:
                out.extend(("exec", s, workdir) for s in loop[-1][2])
                continue
        out.append(("exec", cmd, workdir))
    return out


def commands_in(code):
    """[(cmd, workdir)] for every exec_command in JS code, in source order."""
    return [(c[1], c[2]) for c in calls_in(code) if c[0] == "exec"]


def exec_events(code, output):
    """What one code-mode `exec` call did, in order:
      ("patch", file)                     apply_patch touched a file
      ("cmd", cmd, workdir, result)       a shell command; result None when unreadable
      ("finish", process id, result)      write_stdin polled a running process and it exited
    result: {"output", "exit_code" (None = unknown), "process" (set while still running)}."""
    events = [("patch", f) for f in patch_files(code)]
    calls, results, raw = calls_in(code), results_in(output), raw_text(output)
    if len(calls) == len(results):
        pairs = list(zip(calls, results))
    elif len([c for c in calls if c[0] == "exec"]) == 1 and len(calls) == 1 and not results and raw:
        pairs = [(calls[0], {"output": raw, "exit_code": None})]
    else:
        pairs = [(c, None) for c in calls]
    for call, r in pairs:
        res = None
        if r is not None:
            code_ = r.get("exit_code") if isinstance(r.get("exit_code"), int) else None
            running = code_ is None and isinstance(r.get("session_id"), int)
            res = {"output": r.get("output") or "", "exit_code": code_,
                   "process": r["session_id"] if running else None}
        if call[0] == "exec":
            events.append(("cmd", call[1], call[2], res))
        elif res is not None and res["exit_code"] is not None and call[1] is not None:
            events.append(("finish", call[1], res))
    return events


def patch_text_files(text):
    return [(a or b).strip() for a, b in PATCH_FILE.findall(text or "")]


def patch_files(code):
    """Files touched by apply_patch(...) calls inside JS code."""
    files = []
    for m in re.finditer(r"apply_patch\s*\(\s*", code):
        text, _ = js_string(code, m.end())
        files += patch_text_files(text)
    return files


def results_in(output):
    """Command results from an exec output list, in order: dicts with exit_code / output."""
    out = []
    for item in output[1:] if isinstance(output, list) else []:
        t = item.get("text", "") if isinstance(item, dict) else ""
        try:
            j = json.loads(t)
        except ValueError:
            continue
        if isinstance(j, dict) and isinstance(j.get("value"), dict):
            j = j["value"]  # Promise.allSettled
        if isinstance(j, dict) and "output" in j and ("exit_code" in j or "session_id" in j):
            out.append(j)
    return out


def single_result(resp):
    """The result of one direct exec_command / write_stdin call, in exec_events' shape, or None."""
    j = resp
    if isinstance(resp, str):
        try:
            j = json.loads(resp)
        except ValueError:
            return None
    if not isinstance(j, dict) or not ("exit_code" in j or "session_id" in j):
        return None
    code_ = j.get("exit_code") if isinstance(j.get("exit_code"), int) else None
    running = code_ is None and isinstance(j.get("session_id"), int)
    return {"output": j.get("output") or "", "exit_code": code_, "process": j["session_id"] if running else None}


def raw_text(output):
    if isinstance(output, list):
        return "\n".join(x.get("text", "") for x in output[1:] if isinstance(x, dict))
    return output if isinstance(output, str) else ""


def text_of(value):
    """The one string a tool input carries, whatever its wrapping."""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("input", "code", "patch", "source", "script"):
            if isinstance(value.get(key), str):
                return value[key]
    return ""
