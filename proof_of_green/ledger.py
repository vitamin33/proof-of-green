"""Per-session append-only JSONL ledger under ${CLAUDE_PLUGIN_DATA}.

Every record gets a monotonically increasing `seq` assigned under an exclusive
file lock, so concurrent subagent hooks never interleave or reuse a number.
"""
import json
import os
import re
import time
import traceback

try:
    import fcntl
except ImportError:  # Windows: append-only lines still work, seq may repeat
    fcntl = None


def data_dir():
    return os.environ.get("CLAUDE_PLUGIN_DATA") or None


def sessions_dir(base=None):
    base = base or data_dir()
    return os.path.join(base, "sessions") if base else None


def session_path(session_id, base=None):
    sdir = sessions_dir(base)
    if not sdir or not session_id:
        return None
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", str(session_id))[:128]
    return os.path.join(sdir, safe + ".jsonl")


def _parse(lines):
    out = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out


def read(path):
    if not path or not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return _parse(fh)


def current_turn(records):
    turn = 0
    for rec in records:
        if rec.get("kind") == "turn":
            turn = max(turn, int(rec.get("turn") or 0))
    return turn


def _last_record(fh, size):
    """Last complete record of the file, read from the tail. None if it cannot be parsed."""
    block = 4096
    while True:
        start = max(0, size - block)
        fh.seek(start)
        chunk = fh.read(size - start)
        lines = chunk.rstrip(b"\n").split(b"\n")
        if len(lines) > 1 or start == 0:
            try:
                rec = json.loads(lines[-1].decode("utf-8"))
            except ValueError:
                return None
            ok = isinstance(rec, dict) and isinstance(rec.get("seq"), int) and isinstance(rec.get("turn"), int)
            return rec if ok else None
        block *= 4


def append(session_id, record, new_turn=False):
    """Append one record; fills seq, ts and turn. Returns the record written.

    seq and turn come from the last line: every record carries the turn it was written in,
    and seq only grows under the lock. A damaged last line falls back to a full read.
    """
    path = session_path(session_id)
    if not path:
        return None
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a+b") as fh:
        if fcntl:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            last = _last_record(fh, size) if size else None
            if last is not None:
                seq, turn = last["seq"], last["turn"]
            elif size:
                fh.seek(0)
                records = _parse(line.decode("utf-8", "replace") for line in fh)
                seq = max([int(r.get("seq") or 0) for r in records] + [0])
                turn = current_turn(records)
            else:
                seq, turn = 0, 0
            rec = {"seq": seq + 1, "ts": round(time.time(), 3), "turn": turn + (1 if new_turn else 0)}
            rec.update(record)
            line = (json.dumps(rec, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
            if size:
                fh.seek(size - 1)
                if fh.read(1) != b"\n":  # a crashed writer left half a line; start a fresh one
                    line = b"\n" + line
            fh.seek(0, os.SEEK_END)
            fh.write(line)
            fh.flush()
        finally:
            if fcntl:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    return rec


def first_session(path):
    """First session record in the file, without parsing the other lines."""
    if not path or not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if '"kind":"session"' in line:
                recs = _parse([line])
                if recs and recs[0].get("cwd"):
                    return recs[0]
    return None


def log_error(where, exc):
    """One line per failure. Never includes payload content."""
    base = data_dir()
    if not base:
        return
    try:
        os.makedirs(base, exist_ok=True)
        tb = traceback.extract_tb(exc.__traceback__)
        loc = "%s:%s" % (os.path.basename(tb[-1].filename), tb[-1].lineno) if tb else "?"
        msg = str(exc).replace("\n", " ")[:160]
        line = "%s %s %s %s: %s\n" % (
            time.strftime("%Y-%m-%dT%H:%M:%S"), where, loc, type(exc).__name__, msg)
        with open(os.path.join(base, "errors.log"), "a", encoding="utf-8") as fh:
            fh.write(line)
    except Exception:
        pass
