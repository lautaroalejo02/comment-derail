"""Run the subject under test: Claude Code headless (``claude -p``), or a mock.

Real mode::

    claude -p "<task>" --output-format json --dangerously-skip-permissions \
        --max-turns N [--model M]

run with cwd=workspace and an environment cleaned of Claude Code overrides.
With config isolation (default in run.py) CLAUDE_CONFIG_DIR points at a fresh
temporary directory per call, so the user's ~/.claude (CLAUDE.md, settings,
plugins, hooks, auto-memory, history) is not loaded. Only the credentials file
is copied in (0600) so auth keeps working.

Mock mode (``mock=noop|root_fix|patch_extend``) applies
``probes/<name>.patch`` instead of calling claude, so the whole pipeline can be
exercised without API auth.
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
from dataclasses import asdict, dataclass, field
from pathlib import Path

MOCK_MODES = ("noop", "root_fix", "patch_extend")

# Every CLAUDE*/CLAUDECODE variable is dropped (they are session state or
# behavior overrides of the parent Claude Code, e.g. CLAUDE_EFFORT,
# CLAUDE_AUTOCOMPACT_PCT_OVERRIDE, CLAUDE_CODE_*), except these auth/provider
# ones. Model overrides are dropped too. ``keep`` adds exceptions (--keep-env).
_KEEP_CLAUDE_VARS = {
    "CLAUDE_CODE_OAUTH_TOKEN", "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX",
    "CLAUDE_CODE_SKIP_BEDROCK_AUTH", "CLAUDE_CODE_SKIP_VERTEX_AUTH", "CLAUDE_CONFIG_DIR",
    "CLAUDE_CODE_API_KEY_HELPER_TTL_MS", "CLAUDE_CODE_CLIENT_CERT", "CLAUDE_CODE_CLIENT_KEY",
    "CLAUDE_CODE_CLIENT_KEY_PASSPHRASE", "CLAUDE_SESSION_INGRESS_TOKEN_FILE",
}
_DROP_EXACT = {
    "ANTHROPIC_MODEL", "ANTHROPIC_SMALL_FAST_MODEL",
    "ANTHROPIC_DEFAULT_OPUS_MODEL", "ANTHROPIC_DEFAULT_SONNET_MODEL", "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    "ANTHROPIC_CUSTOM_HEADERS", "MAX_THINKING_TOKENS", "DISABLE_PROMPT_CACHING",
}


def clean_env(base: dict | None = None, keep: tuple[str, ...] | list[str] = (),
              overrides: dict | None = None) -> dict:
    env = dict(os.environ if base is None else base)
    keep_set = _KEEP_CLAUDE_VARS | set(keep)
    for k in list(env):
        if k in keep_set:
            continue
        if k in _DROP_EXACT or k.startswith("CLAUDE"):
            env.pop(k)
    env["CI"] = env.get("CI", "1")
    if overrides:
        env.update(overrides)
    return env


# --------------------------------------------------------------------------
# Config isolation
# --------------------------------------------------------------------------

# Only keys documented in the Claude Code settings reference.
ISOLATED_SETTINGS = {"disableAllHooks": True}
_CREDS = ".credentials.json"
_creds_lock = threading.Lock()


def original_config_dir() -> Path:
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or (Path.home() / ".claude"))


def _write_private(path: Path, data: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)
    os.chmod(path, 0o600)


@dataclass
class ConfigInfo:
    config_isolated: bool
    credentials_copied: bool = False
    config_dir: str | None = None


@contextmanager
def claude_config(isolate: bool = True):
    """Yield (env_overrides, ConfigInfo). With ``isolate`` a fresh temporary
    CLAUDE_CONFIG_DIR is created (0700) holding only a copy of the credentials
    file and a minimal settings.json; it is deleted afterwards. If Claude Code
    refreshed the OAuth token inside the copy, the refreshed file is written
    back to the original location (only if the original is unchanged), so a
    rotated refresh token does not lock the user out."""
    if not isolate:
        yield {}, ConfigInfo(config_isolated=False)
        return
    tmp = Path(tempfile.mkdtemp(prefix="cdb-claude-config-"))
    src = original_config_dir() / _CREDS
    original_bytes = None
    info = ConfigInfo(config_isolated=True, config_dir=str(tmp))
    try:
        if src.is_file():
            original_bytes = src.read_bytes()
            _write_private(tmp / _CREDS, original_bytes)
            info.credentials_copied = True
        (tmp / "settings.json").write_text(json.dumps(ISOLATED_SETTINGS), encoding="utf-8")
        yield {"CLAUDE_CONFIG_DIR": str(tmp)}, info
    finally:
        try:
            copy = tmp / _CREDS
            if original_bytes is not None and copy.is_file():
                new = copy.read_bytes()
                if new != original_bytes:
                    with _creds_lock:
                        if src.is_file() and src.read_bytes() == original_bytes:
                            _write_private(src, new)
        except OSError:
            pass
        shutil.rmtree(tmp, ignore_errors=True)


def credentials_available() -> bool:
    return (original_config_dir() / _CREDS).is_file()


# --------------------------------------------------------------------------
# Error classification
# --------------------------------------------------------------------------

RATE_LIMIT_RX = re.compile(r"\b429\b|rate[ _-]?limit|overloaded|usage limit", re.IGNORECASE)
AUTH_RX = re.compile(r"invalid api key|/login\b|not logged in|authentication[ _]?(error|failed)|"
                     r"\b401\b|unauthori[sz]ed|oauth token (has )?expired|"
                     r"could not resolve authentication|missing api key", re.IGNORECASE)


def main_model(model_usage: dict | None) -> str | None:
    """Model with the most output tokens in ``modelUsage`` (ties: higher cost)."""
    if not isinstance(model_usage, dict) or not model_usage:
        return None
    def key(item):
        _, u = item
        u = u if isinstance(u, dict) else {}
        return (u.get("outputTokens") or 0, u.get("costUSD") or 0)
    return max(model_usage.items(), key=key)[0]


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
    model_usage: dict | None = None
    main_model: str | None = None
    api_error_status: int | str | None = None
    config_isolated: bool | None = None

    def _error_text(self) -> str:
        return "\n".join(str(x) for x in (self.stderr, self.result, self.parse_error,
                                          self.api_error_status, self.stdout[-4000:] if self.stdout else "")
                         if x)

    @property
    def rate_limited(self) -> bool:
        """Only failed calls are inspected: a successful answer that merely
        talks about rate limits (e.g. a retry fixture) is not a rate limit."""
        if not self.is_error or self.timed_out or self.mock:
            return False
        if str(self.api_error_status) in ("429", "529"):
            return True
        return bool(RATE_LIMIT_RX.search(self._error_text()))

    @property
    def auth_failed(self) -> bool:
        if not self.is_error or self.timed_out or self.mock:
            return False
        if str(self.api_error_status) in ("401", "403"):
            return True
        return bool(AUTH_RX.search(self._error_text()))

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
                           env=clean_env(keep=("CLAUDE_CONFIG_DIR",)), stdin=subprocess.DEVNULL)
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
                extra: list[str] | None = None, isolate: bool = True,
                keep_env: tuple[str, ...] | list[str] = ()) -> AgentResult:
    with claude_config(isolate) as (overrides, info):
        res = _call_claude(prompt, cwd, max_turns, model, timeout, skip_permissions, extra,
                           clean_env(keep=keep_env, overrides=overrides))
    res.config_isolated = info.config_isolated
    return res


def _call_claude(prompt, cwd, max_turns, model, timeout, skip_permissions, extra, env) -> AgentResult:
    cmd = build_command(prompt, max_turns, model, skip_permissions, extra)
    res = AgentResult(command=["<prompt>" if i == 2 else c for i, c in enumerate(cmd)])
    t0 = time.monotonic()
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout,
                           env=env, stdin=subprocess.DEVNULL)
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
    res.api_error_status = obj.get("api_error_status")
    mu = obj.get("modelUsage")
    res.model_usage = mu if isinstance(mu, dict) else None
    res.main_model = main_model(res.model_usage)
    res.is_error = bool(obj.get("is_error", False)) or res.returncode not in (0, None)
    return res


def run_agent(workspace: Path, task: str, max_turns: int = 40, model: str | None = None,
              timeout: float = 1800, mock: str | None = None, fixture=None,
              condition: str = "original", isolate: bool = True,
              keep_env: tuple[str, ...] | list[str] = ()) -> AgentResult:
    """Run the subject in ``workspace``. With ``mock`` set, apply a probe patch instead."""
    workspace = Path(workspace)
    if mock:
        return run_mock(workspace, mock, fixture, condition)
    return call_claude(task, workspace, max_turns, model, timeout, isolate=isolate, keep_env=keep_env)


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
