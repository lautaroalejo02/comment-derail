"""Preflight checks before a real run.

    python -m bench.preflight [--model M] [--no-isolate-config] [--keep-env VAR] [--skip-claude-call]

Checks python>=3.11, node>=22, pytest importable, git and patch on PATH,
`claude --version`, then runs one
`claude -p "Reply with OK" --output-format json --max-turns 1` under the same
config isolation and env cleaning as bench.run, and prints the main model,
cost and whether it succeeded. Exits non-zero on any failure.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .agent import call_claude, claude_bin, claude_version, credentials_available


def _version_tuple(s: str) -> tuple[int, ...]:
    m = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", s)
    return tuple(int(x) for x in m.groups() if x is not None) if m else ()


def check_python() -> tuple[bool, str]:
    v = sys.version_info
    return v >= (3, 11), f"{v.major}.{v.minor}.{v.micro}"


def check_node() -> tuple[bool, str]:
    if not shutil.which("node"):
        return False, "node not on PATH"
    out = subprocess.run(["node", "--version"], capture_output=True, text=True).stdout.strip()
    vt = _version_tuple(out)
    return bool(vt) and vt[0] >= 22, out or "unknown"


def check_pytest() -> tuple[bool, str]:
    spec = importlib.util.find_spec("pytest")
    if spec is None:
        return False, "not importable"
    import pytest  # noqa: F401
    return True, pytest.__version__


def check_bin(name: str) -> tuple[bool, str]:
    p = shutil.which(name)
    return bool(p), p or "not on PATH"


def check_claude_version() -> tuple[bool, str]:
    v = claude_version()
    return not v.startswith(("unavailable", "unknown")), v


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default=None)
    ap.add_argument("--isolate-config", dest="isolate_config", action="store_true", default=True)
    ap.add_argument("--no-isolate-config", dest="isolate_config", action="store_false")
    ap.add_argument("--keep-env", action="append", default=[])
    ap.add_argument("--timeout", type=float, default=180)
    ap.add_argument("--skip-claude-call", action="store_true", help="only local checks (no API call)")
    args = ap.parse_args(argv)
    keep_env = [x for k in args.keep_env for x in k.split(",") if x]

    checks = [
        ("python >= 3.11", check_python),
        ("node >= 22", check_node),
        ("pytest importable", check_pytest),
        ("git on PATH", lambda: check_bin("git")),
        ("patch on PATH", lambda: check_bin("patch")),
        (f"{claude_bin()} --version", check_claude_version),
    ]
    ok_all = True
    rows = []
    for name, fn in checks:
        try:
            ok, detail = fn()
        except Exception as exc:  # a crashing check is a failing check
            ok, detail = False, f"{exc.__class__.__name__}: {exc}"
        ok_all &= ok
        rows.append((name, ok, detail))

    w = max([len(r[0]) for r in rows] + [len("ANTHROPIC_API_KEY set")]) + 2
    for name, ok, detail in rows:
        print(f"{'PASS' if ok else 'FAIL'}  {name:<{w}}{detail}")

    print(f"info  {'config isolation':<{w}}{'on' if args.isolate_config else 'off'}"
          + (f" (credentials file {'found, will be copied' if credentials_available() else 'not found'})"
             if args.isolate_config else ""))
    print(f"info  {'ANTHROPIC_API_KEY set':<{w}}{bool(os.environ.get('ANTHROPIC_API_KEY'))}")

    if args.skip_claude_call:
        return 0 if ok_all else 1

    with tempfile.TemporaryDirectory(prefix="cdb-preflight-") as tmp:
        res = call_claude("Reply with OK", Path(tmp), max_turns=1, model=args.model, timeout=args.timeout,
                          skip_permissions=False, isolate=args.isolate_config, keep_env=keep_env)
    text = (res.result or "").strip()
    call_ok = not res.is_error and "OK" in text.upper()
    ok_all &= call_ok
    print(f"{'PASS' if call_ok else 'FAIL'}  {'claude -p call':<{w}}"
          f"result={text[:60]!r} main_model={res.main_model} cost_usd={res.total_cost_usd} "
          f"turns={res.num_turns} wall_s={res.wall_s}")
    if not call_ok:
        err = (res.stderr or res.parse_error or "").strip()
        if err:
            print("      stderr: " + err[-800:].replace("\n", "\n      "))
        if res.auth_failed and args.isolate_config:
            print("      authentication failed under config isolation: rerun with --no-isolate-config "
                  "(and pass it to bench.run too), or pass the needed auth variable with --keep-env VAR.")
        elif res.rate_limited:
            print("      rate limited / overloaded: wait and retry.")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
