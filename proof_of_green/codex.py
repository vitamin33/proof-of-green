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


def commands_in(code):
    """[(cmd, workdir)] for every exec_command in JS code, in source order (cmd None when not literal)."""
    out = []
    loops = [(m.start(), m.group(1), strings_in(code[m.end():m.end() + code[m.end():].find("]")]))
             for m in re.finditer(r"for\s*\(\s*(?:const|let|var)\s+(\w+)\s+of\s*\[", code)]
    for m in re.finditer(r"exec_command\s*\(\s*\{", code):
        start = m.end()
        end = code.find("})", start)
        body = code[start:end if end > 0 else start + 2000]
        wd = re.search(r"[\"']?workdir[\"']?\s*:\s*", body)
        workdir = js_string(body, wd.end())[0] if wd else None
        c = re.search(r"[\"']?cmd[\"']?\s*:\s*", body)
        if c:
            out.append((js_string(body, c.end())[0], workdir))
            continue
        if re.match(r"\s*cmd\s*[,}]", body):
            loop = [lp for lp in loops if lp[0] < m.start() and lp[1] == "cmd"]
            if loop:
                out.extend((s, workdir) for s in loop[-1][2])
                continue
        out.append((None, workdir))
    return out


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
