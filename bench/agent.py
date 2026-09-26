"""Run the subject under test: Claude Code headless (``claude -p``), or a mock.

Real mode::

    claude -p "<task>" --output-format json --dangerously-skip-permissions \
        --max-turns N [--model M]

run with cwd=workspace and an environment cleaned of Claude Code overrides.

Mock mode (``mock=noop|root_fix|patch_extend``) applies
``probes/<name>.patch`` instead of calling claude, so the whole pipeline can be
exercised without API auth.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

MOCK_MODES = ("noop", "root_fix", "patch_extend")

# Env vars that would change what the subject sees or which model it uses.
# Auth-related variables (ANTHROPIC_API_KEY, CLAUDE_CODE_OAUTH_TOKEN,
# CLAUDE_CODE_USE_BEDROCK/VERTEX, CLAUDE_CONFIG_DIR, ...) are kept.
_KEEP_CLAUDE_VARS = {
    "CLAUDE_CODE_OAUTH_TOKEN", "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX",
    "CLAUDE_CODE_SKIP_BEDROCK_AUTH", "CLAUDE_CODE_SKIP_VERTEX_AUTH", "CLAUDE_CONFIG_DIR",
    "CLAUDE_CODE_API_KEY_HELPER_TTL_MS", "CLAUDE_CODE_CLIENT_CERT", "CLAUDE_CODE_CLIENT_KEY",
}
_DROP_EXACT = {
    "CLAUDECODE", "ANTHROPIC_MODEL", "ANTHROPIC_SMALL_FAST_MODEL",
    "ANTHROPIC_DEFAULT_OPUS_MODEL", "ANTHROPIC_DEFAULT_SONNET_MODEL", "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    "ANTHROPIC_CUSTOM_HEADERS", "MAX_THINKING_TOKENS", "DISABLE_PROMPT_CACHING",
}


def clean_env(base: dict | None = None) -> dict:
    env = dict(os.environ if base is None else base)
    for k in list(env):
        if k in _KEEP_CLAUDE_VARS:
            continue
        if k in _DROP_EXACT or k.startswith("CLAUDE_CODE_") or k.startswith("CLAUDE_AGENT_") \
                or k == "CLAUDE_PROJECT_DIR" or k.startswith("CLAUDE_PLUGIN"):
            env.pop(k)
    env["CI"] = env.get("CI", "1")
    return env


@dataclass
class AgentResult:
    result: str | None = None
    total_cost_usd: float | None = None
    num_turns: int | None = None
    duration_ms: int | None = None
    session_id: str | None = None
    is_error: bool | None = None
    returncode: int | None = None
    timed_out: bool = False
    wall_s: float = 0.0
    stdout: str = field(default="", repr=False)
    stderr: str = field(default="", repr=False)
    parse_error: str | None = None
    mock: str | None = None
    mock_apply: str | None = None
    command: list[str] = field(default_factory=list)

    def summary(self) -> dict:
        d = asdict(self)
        d.pop("stdout")
        d.pop("stderr")
        return d


def claude_bin() -> str:
    return os.environ.get("BENCH_CLAUDE_BIN", "claude")


def claude_version() -> str:
    try:
        p = subprocess.run([claude_bin(), "--version"], capture_output=True, text=True, timeout=30,
                           env=clean_env(), stdin=subprocess.DEVNULL)
        return (p.stdout or p.stderr).strip() or f"unknown (rc={p.returncode})"
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"unavailable ({exc.__class__.__name__})"


def parse_claude_json(stdout: str) -> tuple[dict | None, str | None]:
    """Parse ``--output-format json`` stdout. Tolerates leading noise and a
    stream of JSON lines (takes the last object with type=result)."""
    s = stdout.strip()
    if not s:
        return None, "empty stdout"
    try:
        obj = json.loads(s)
        if isinstance(obj, list):  # some versions emit an array of messages
            res = [m for m in obj if isinstance(m, dict) and m.get("type") == "result"]
            obj = res[-1] if res else (obj[-1] if obj else None)
        return (obj if isinstance(obj, dict) else None), None
    except json.JSONDecodeError:
        pass
    last = None
    for line in s.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(o, dict) and (o.get("type") == "result" or last is None):
            last = o
    if last is not None:
        return last, None
    start, end = s.find("{"), s.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(s[start:end + 1]), None
        except json.JSONDecodeError as exc:
            return None, f"cannot parse stdout as JSON: {exc}"
    return None, "no JSON object in stdout"


def build_command(prompt: str, max_turns: int | None, model: str | None,
                  skip_permissions: bool = True, extra: list[str] | None = None) -> list[str]:
    cmd = [claude_bin(), "-p", prompt, "--output-format", "json"]
    if skip_permissions:
        cmd.append("--dangerously-skip-permissions")
    if max_turns:
        cmd += ["--max-turns", str(max_turns)]
    if model:
        cmd += ["--model", model]
    if extra:
        cmd += extra
    return cmd


def call_claude(prompt: str, cwd: Path, max_turns: int | None, model: str | None,
                timeout: float, skip_permissions: bool = True,
                extra: list[str] | None = None) -> AgentResult:
    cmd = build_command(prompt, max_turns, model, skip_permissions, extra)
    res = AgentResult(command=[c if c is not prompt else "<prompt>" for c in cmd])
    t0 = time.monotonic()
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout,
                           env=clean_env(), stdin=subprocess.DEVNULL)
        res.returncode, res.stdout, res.stderr = p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired as exc:
        res.timed_out = True
        res.returncode = -9
        out, err = exc.stdout or "", exc.stderr or ""
        res.stdout = out.decode("utf-8", "replace") if isinstance(out, bytes) else out
        res.stderr = (err.decode("utf-8", "replace") if isinstance(err, bytes) else err) \
            + f"\n[harness] timeout after {timeout}s"
    except OSError as exc:
        res.returncode = -1
        res.stderr = f"[harness] cannot run {cmd[0]}: {exc}"
    res.wall_s = round(time.monotonic() - t0, 3)
    obj, err = parse_claude_json(res.stdout)
    if obj is None:
        res.parse_error = err
        res.is_error = True
        return res
    res.result = obj.get("result")
    res.total_cost_usd = obj.get("total_cost_usd", obj.get("cost_usd"))
    res.num_turns = obj.get("num_turns")
    res.duration_ms = obj.get("duration_ms")
    res.session_id = obj.get("session_id")
    res.is_error = bool(obj.get("is_error", False)) or res.returncode not in (0, None)
    return res


def run_agent(workspace: Path, task: str, max_turns: int = 40, model: str | None = None,
              timeout: float = 1800, mock: str | None = None, fixture=None,
              condition: str = "original") -> AgentResult:
    """Run the subject in ``workspace``. With ``mock`` set, apply a probe patch instead."""
    workspace = Path(workspace)
    if mock:
        return run_mock(workspace, mock, fixture, condition)
    return call_claude(task, workspace, max_turns, model, timeout)


def run_mock(workspace: Path, mock: str, fixture, condition: str) -> AgentResult:
    from .workspace import apply_patch_for_condition

    if mock not in MOCK_MODES:
        raise ValueError(f"mock must be one of {MOCK_MODES}, got {mock!r}")
    t0 = time.monotonic()
    res = AgentResult(mock=mock, total_cost_usd=0.0, num_turns=0, duration_ms=0,
                      session_id=f"mock-{mock}", is_error=False, returncode=0,
                      command=["<mock>", mock])
    if mock == "noop":
        res.result = "mock noop: no changes"
        res.mock_apply = "none"
    else:
        if fixture is None:
            raise ValueError("mock mode needs the fixture to locate probes/")
        patch = fixture.probe(mock)
        ok, how = apply_patch_for_condition(fixture, condition, workspace, patch)
        res.mock_apply = how if ok else "failed"
        res.is_error = not ok
        res.returncode = 0 if ok else 1
        res.result = f"mock {mock}: {'applied' if ok else 'FAILED to apply'} {patch.name}"
        if not ok:
            res.stderr = how
    res.stdout = json.dumps({"type": "result", "subtype": "success", "result": res.result,
                             "total_cost_usd": 0.0, "num_turns": 0, "duration_ms": 0,
                             "session_id": res.session_id, "is_error": res.is_error})
    res.wall_s = round(time.monotonic() - t0, 3)
    return res
