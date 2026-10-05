"""Other subject agents (Codex CLI, Grok CLI) and transcript analysis shared by all.

Each adapter runs the agent headless in the workspace with the same prompt and
returns an ``AgentResult`` (see agent.py) plus a normalized list of tool events
parsed from the agent's own transcript:

    {"kind": "shell" | "read" | "search" | "edit" | "other", "tool": str, "detail": str}

Command lines used (``<model>``/``<N>``/``<ws>`` filled in):

    claude -p <prompt> --output-format stream-json --verbose --max-turns <N> ...
    codex exec --json --skip-git-repo-check --ephemeral --ignore-user-config --ignore-rules
               --dangerously-bypass-approvals-and-sandbox -C <ws> [-m <model>] <prompt>
    grok -p <prompt> --output-format streaming-messages-json --max-turns <N>
         --permission-mode bypassPermissions --cwd <ws> [-m <model>]

Turn limits: Claude Code and Grok take ``--max-turns``. Codex CLI has no turn
limit; the equivalent bound is the wall-clock ``--agent-timeout`` (same value
for every agent), recorded per cell as ``turn_limit``.

Config isolation: every agent gets a fresh temporary home holding only its auth
file (CLAUDE_CONFIG_DIR, CODEX_HOME, GROK_HOME), so user instructions, skills,
MCP servers, hooks and memory are not loaded. Grok additionally gets a
config.toml that turns off its Claude/Cursor compatibility scanning, which
would otherwise read ~/.claude and ~/.cursor.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path

AGENTS = ("claude", "codex", "grok")

# Project instruction file each agent reads natively (for --claude-md / distance variants).
INSTRUCTION_FILE = {"claude": "CLAUDE.md", "codex": "AGENTS.md", "grok": "AGENTS.md"}

_home_lock = threading.Lock()


# --------------------------------------------------------------------------
# Isolated homes
# --------------------------------------------------------------------------

def _private_copy(src: Path, dst: Path) -> None:
    fd = os.open(dst, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, src.read_bytes())
    finally:
        os.close(fd)


@contextmanager
def isolated_home(env_var: str, real_home: Path, auth_files: tuple[str, ...],
                  extra: dict[str, str] | None = None, isolate: bool = True):
    """Yield env overrides pointing ``env_var`` at a temp dir that holds only
    ``auth_files`` copied from ``real_home`` (plus ``extra`` files). A refreshed
    auth file is written back when the original is unchanged, so rotated
    tokens do not log the user out."""
    if not isolate:
        yield {}, False
        return
    tmp = Path(tempfile.mkdtemp(prefix=f"cdb-{env_var.lower()}-"))
    originals: dict[str, bytes] = {}
    try:
        for name in auth_files:
            src = real_home / name
            if src.is_file():
                originals[name] = src.read_bytes()
                _private_copy(src, tmp / name)
        for name, text in (extra or {}).items():
            (tmp / name).write_text(text, encoding="utf-8", newline="\n")
        yield {env_var: str(tmp)}, bool(originals)
    finally:
        for name, before in originals.items():
            try:
                new = (tmp / name).read_bytes()
                if new != before:
                    with _home_lock:
                        src = real_home / name
                        if src.is_file() and src.read_bytes() == before:
                            src.write_bytes(new)
            except OSError:
                pass
        shutil.rmtree(tmp, ignore_errors=True)


GROK_ISOLATED_CONFIG = """\
[memory]
enabled = false

[compat.cursor]
skills = false
rules = false
agents = false
mcps = false
hooks = false

[compat.claude]
skills = false
rules = false
agents = false
mcps = false
hooks = false
"""


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")


def grok_home() -> Path:
    return Path(os.environ.get("GROK_HOME") or Path.home() / ".grok")


def clean_agent_env(agent: str, base: dict | None = None, keep=()) -> dict:
    """Drop the parent session's agent variables (CLAUDE*, CODEX_*, GROK_*) and
    model overrides; the isolation overrides are added by the caller."""
    from .agent import clean_env
    env = clean_env(base, keep=keep)
    for k in list(env):
        if k in keep:
            continue
        if k.startswith(("CODEX_", "GROK_")) or k in ("OPENAI_MODEL", "XAI_MODEL"):
            env.pop(k)
    return env


# --------------------------------------------------------------------------
# Transcript parsing
# --------------------------------------------------------------------------

def _classify_tool(name: str, inp: dict) -> dict:
    n = (name or "").lower()
    inp = inp if isinstance(inp, dict) else {}
    path = str(inp.get("file_path") or inp.get("path") or inp.get("target_file") or inp.get("filePath") or "")
    if n in ("bash", "powershell") or any(k in n for k in ("terminal", "shell", "command", "exec")):
        return {"kind": "shell", "tool": name, "detail": str(inp.get("command") or inp.get("cmd") or "")}
    if any(k in n for k in ("edit", "write", "replace", "patch", "create", "notebook")):
        return {"kind": "edit", "tool": name, "detail": path}
    if n in ("grep", "glob") or any(k in n for k in ("grep", "search", "glob", "find", "list")):
        return {"kind": "search", "tool": name,
                "detail": str(inp.get("pattern") or inp.get("query") or inp.get("regex") or path)}
    if "read" in n or n in ("view", "cat"):
        return {"kind": "read", "tool": name, "detail": path}
    return {"kind": "other", "tool": name, "detail": ""}


def events_from_anthropic_stream(stdout: str) -> list[dict]:
    """Tool calls from an NDJSON stream of Anthropic-format messages
    (claude --output-format stream-json, grok streaming-messages-json)."""
    events = []
    for line in (stdout or "").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        if o.get("type") != "assistant":
            continue
        for block in (o.get("message") or {}).get("content") or []:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                events.append(_classify_tool(block.get("name", ""), block.get("input") or {}))
    return events


def parse_codex_jsonl(stdout: str) -> tuple[dict, list[dict]]:
    """(summary, events) from ``codex exec --json``. Summary: result (last agent
    message), usage (summed over turns), num_turns, error text."""
    events, messages, errors = [], [], []
    usage: dict = {}
    turns = 0
    failed = False
    for line in (stdout or "").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        t = o.get("type")
        if t == "turn.completed":
            turns += 1
            for k, v in (o.get("usage") or {}).items():
                if isinstance(v, (int, float)):
                    usage[k] = usage.get(k, 0) + v
        elif t in ("turn.failed", "error"):
            failed = True
            errors.append(json.dumps(o.get("error") or o)[:1000])
        elif t == "item.completed":
            item = o.get("item") or {}
            it = item.get("type")
            if it == "agent_message":
                messages.append(item.get("text") or "")
            elif it == "command_execution":
                events.append({"kind": "shell", "tool": "command_execution", "detail": item.get("command") or ""})
            elif it == "file_change":
                for ch in item.get("changes") or []:
                    events.append({"kind": "edit", "tool": "file_change", "detail": ch.get("path") or ""})
            elif it in ("mcp_tool_call", "web_search"):
                events.append({"kind": "other", "tool": it, "detail": ""})
            elif it == "error" and "skills context budget" not in (item.get("message") or ""):
                errors.append(item.get("message") or "")
    return ({"result": messages[-1] if messages else None, "usage": usage, "num_turns": turns,
             "failed": failed, "errors": errors}, events)


GIT_HISTORY_RX = re.compile(r"\bgit(\.exe)?\s+(-C\s+\S+\s+)?(log|blame|show|annotate|reflog)\b")
SEARCH_RX = re.compile(r"\b(grep|rg|ag|findstr|Select-String|git\s+grep)\b", re.IGNORECASE)
TEST_PATH_RX = re.compile(r"(^|[\\/\s'\"])(tests?|__tests__|spec)[\\/]|test_[\w-]*\.py|\.(test|spec)\.[jt]sx?")


def behavior_flags(events: list[dict]) -> dict:
    """What the agent looked at, overall and before its first edit."""
    first_edit = next((i for i, e in enumerate(events) if e["kind"] == "edit"), len(events))

    def uses(pred, upto=None):
        return any(pred(e) for e in events[:upto])

    def git_hist(e):
        return e["kind"] == "shell" and bool(GIT_HISTORY_RX.search(e["detail"]))

    def search(e):
        return e["kind"] == "search" or (e["kind"] == "shell" and bool(SEARCH_RX.search(e["detail"])))

    def tests(e):
        return e["kind"] in ("read", "shell", "search") and bool(TEST_PATH_RX.search(e["detail"]))

    return {
        "n_tool_calls": len(events),
        "first_edit_index": first_edit if first_edit < len(events) else None,
        "used_git_history": uses(git_hist),
        "used_git_history_before_edit": uses(git_hist, first_edit),
        "used_search": uses(search),
        "used_search_before_edit": uses(search, first_edit),
        "read_tests": uses(tests),
        "read_tests_before_edit": uses(tests, first_edit),
    }


# --------------------------------------------------------------------------
# Adapters
# --------------------------------------------------------------------------

def _run(cmd, cwd, env, timeout):
    t0 = time.monotonic()
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout, env=env, stdin=subprocess.DEVNULL)
        return p.returncode, p.stdout, p.stderr, False, round(time.monotonic() - t0, 3)
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout.decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        err = exc.stderr.decode("utf-8", "replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        return -9, out, err + f"\n[harness] timeout after {timeout}s", True, round(time.monotonic() - t0, 3)
    except OSError as exc:
        return -1, "", f"[harness] cannot run {cmd[0]}: {exc}", False, round(time.monotonic() - t0, 3)


def _bin(env_name: str, default: str) -> list[str]:
    import sys
    name = os.environ.get(env_name, default)
    if name.endswith(".py"):
        return [sys.executable, name]
    return [shutil.which(name) or name]


def call_codex(prompt: str, cwd: Path, model: str | None, timeout: float, isolate: bool = True,
               keep_env=()):
    from .agent import AgentResult
    cmd = [*_bin("BENCH_CODEX_BIN", "codex"), "exec", "--json", "--skip-git-repo-check", "--ephemeral",
           "--ignore-user-config", "--ignore-rules", "--dangerously-bypass-approvals-and-sandbox",
           "-C", str(cwd)]
    if model:
        cmd += ["-m", model]
    cmd.append(prompt)
    res = AgentResult(command=[c if c != prompt else "<prompt>" for c in cmd])
    res.agent = "codex"
    res.turn_limit = f"wall-clock {timeout:g}s (codex exec has no turn limit)"
    with isolated_home("CODEX_HOME", codex_home(), ("auth.json",), isolate=isolate) as (ov, _):
        env = clean_agent_env("codex", keep=keep_env)
        env.update(ov)
        rc, out, err, timed_out, wall = _run(cmd, cwd, env, timeout)
    res.returncode, res.stdout, res.stderr, res.timed_out, res.wall_s = rc, out, err, timed_out, wall
    res.config_isolated = isolate
    summary, events = parse_codex_jsonl(out)
    res.result = summary["result"]
    res.num_turns = summary["num_turns"]
    res.model_usage = {model or "codex-default": summary["usage"]} if summary["usage"] else None
    res.main_model = model or "codex-default"
    res.total_cost_usd = None  # codex exec reports tokens only
    res.is_error = bool(summary["failed"] or rc != 0 or timed_out or res.result is None)
    if summary["errors"]:
        res.parse_error = "; ".join(summary["errors"])[:2000]
    res.events = events
    return res


def call_grok(prompt: str, cwd: Path, max_turns: int | None, model: str | None, timeout: float,
              isolate: bool = True, keep_env=()):
    from .agent import AgentResult, main_model, parse_claude_json
    cmd = [*_bin("BENCH_GROK_BIN", "grok"), "-p", prompt, "--output-format", "streaming-messages-json",
           "--permission-mode", "bypassPermissions", "--cwd", str(cwd)]
    if max_turns:
        cmd += ["--max-turns", str(max_turns)]
    if model:
        cmd += ["-m", model]
    res = AgentResult(command=[c if c != prompt else "<prompt>" for c in cmd])
    res.agent = "grok"
    res.turn_limit = f"--max-turns {max_turns}"
    with isolated_home("GROK_HOME", grok_home(), ("auth.json",),
                       extra={"config.toml": GROK_ISOLATED_CONFIG}, isolate=isolate) as (ov, _):
        env = clean_agent_env("grok", keep=keep_env)
        env.update(ov)
        env["GROK_DISABLE_AUTOUPDATER"] = "1"
        env["GROK_TELEMETRY_ENABLED"] = "0"
        rc, out, err, timed_out, wall = _run(cmd, cwd, env, timeout)
    res.returncode, res.stdout, res.stderr, res.timed_out, res.wall_s = rc, out, err, timed_out, wall
    res.config_isolated = isolate
    obj, perr = parse_claude_json(out)
    if obj is None:
        res.parse_error, res.is_error = perr, True
    else:
        res.result = obj.get("result")
        res.total_cost_usd = obj.get("total_cost_usd")
        res.num_turns = obj.get("num_turns")
        res.duration_ms = obj.get("duration_ms")
        res.session_id = obj.get("session_id")
        mu = obj.get("modelUsage")
        res.model_usage = mu if isinstance(mu, dict) else ({model or "grok-default": obj.get("usage")}
                                                           if obj.get("usage") else None)
        res.main_model = main_model(mu) if isinstance(mu, dict) else _grok_model(out) or model
        res.is_error = bool(obj.get("is_error", False)) or rc not in (0, None)
    res.events = events_from_anthropic_stream(out)
    return res


def _grok_model(stdout: str) -> str | None:
    for line in (stdout or "").splitlines():
        if '"subtype": "init"' in line or '"subtype":"init"' in line:
            try:
                return json.loads(line).get("model")
            except json.JSONDecodeError:
                return None
    return None
