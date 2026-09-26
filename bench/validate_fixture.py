"""Validate fixtures against SPEC "Requisitos de validez" 1-6.

    python -m bench.validate_fixture fixtures            # every fixture
    python -m bench.validate_fixture fixtures/py-foo     # one fixture
    python -m bench.validate_fixture fixtures --only py-foo -v

Checks:
  1. original/: visible tests pass
  2. original/ + hidden: every test_root_cause fails, every test_protected passes
     (+ every test_cleanup fails, when the fixture has the optional cleanup tier)
  3. original/ + probes/root_fix.patch + hidden: visible and all hidden pass (cleanup included)
  4. original/ + probes/patch_extend.patch: visible pass, every test_root_cause still fails
     (+ every test_cleanup fails)
  5. rewritten/ differs from original/ only in comments (strip(original) == strip(rewritten))
  6. stripped: visible tests pass
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .fixture import Fixture, discover, load_fixture
from .grade import run_hidden, run_visible
from .strip_comments import SKIP_DIRS, lang_for_path, strip
from .workspace import apply_patch, build_condition, git_baseline

CHECKS = ("1", "2", "3", "4", "5", "6")


@dataclass
class CheckResult:
    ok: bool
    detail: str = ""


@dataclass
class FixtureReport:
    id: str
    has_cleanup: bool = False
    structure: list[str] = field(default_factory=list)
    checks: dict[str, CheckResult] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.structure and all(c.ok for c in self.checks.values()) and len(self.checks) == len(CHECKS)

    def failing(self) -> list[str]:
        out = []
        if self.structure:
            out.append("structure: " + "; ".join(self.structure))
        out += [f"check {k}: {c.detail}" for k, c in self.checks.items() if not c.ok]
        return out


class _Workspace:
    def __init__(self, fx: Fixture, condition: str = "original"):
        self.fx, self.condition = fx, condition

    def __enter__(self) -> Path:
        self.tmp = Path(tempfile.mkdtemp(prefix=f"cdb-validate-{self.fx.id}-"))
        ws = self.tmp / "ws"
        ws.mkdir()
        build_condition(self.fx, self.condition, ws)
        git_baseline(ws)
        return ws

    def __exit__(self, *exc):
        shutil.rmtree(self.tmp, ignore_errors=True)


def _tail(s: str, n: int = 600) -> str:
    s = s.strip()
    return s if len(s) <= n else "..." + s[-n:]


def _hidden_state(hr, kind: str) -> tuple[list[str], list[str]]:
    passed = [f for f, ok in hr.per_file.items() if hr.kinds[f] == kind and ok]
    failed = [f for f, ok in hr.per_file.items() if hr.kinds[f] == kind and not ok]
    return passed, failed


def check1(fx: Fixture, t: float) -> CheckResult:
    with _Workspace(fx) as ws:
        r = run_visible(fx, ws, t)
        return CheckResult(r.ok, "" if r.ok else f"visible tests fail on original/: {_tail(r.output)}")


def check2(fx: Fixture, t: float) -> CheckResult:
    with _Workspace(fx) as ws:
        hr = run_hidden(fx, ws, t, run_full=False)
        rc_pass, _ = _hidden_state(hr, "root_cause")
        _, pr_fail = _hidden_state(hr, "protected")
        problems = []
        if rc_pass:
            problems.append(f"test_root_cause passes on original/ (must fail): {rc_pass}")
        if pr_fail:
            problems.append(f"test_protected fails on original/: {pr_fail} {_tail(hr.outputs[pr_fail[0]])}")
        cl_pass, _ = _hidden_state(hr, "cleanup")
        if cl_pass:
            problems.append(f"test_cleanup passes on original/ (must fail): {cl_pass}")
        return CheckResult(not problems, "; ".join(problems))


def _patched(fx: Fixture, name: str, ws: Path) -> CheckResult | None:
    ok, how = apply_patch(ws, fx.probe(name))
    return None if ok else CheckResult(False, f"probes/{name}.patch does not apply: {_tail(how)}")


def check3(fx: Fixture, t: float) -> CheckResult:
    with _Workspace(fx) as ws:
        err = _patched(fx, "root_fix", ws)
        if err:
            return err
        vis = run_visible(fx, ws, t)
        hr = run_hidden(fx, ws, t, run_full=False)
        problems = []
        if not vis.ok:
            problems.append(f"visible tests fail with root_fix: {_tail(vis.output)}")
        for kind in ("root_cause", "protected", "cleanup"):
            _, failed = _hidden_state(hr, kind)
            if failed:
                problems.append(f"test_{kind} fails with root_fix (must pass): {failed} "
                                f"{_tail(hr.outputs[failed[0]])}")
        return CheckResult(not problems, "; ".join(problems))


def check4(fx: Fixture, t: float) -> CheckResult:
    with _Workspace(fx) as ws:
        err = _patched(fx, "patch_extend", ws)
        if err:
            return err
        vis = run_visible(fx, ws, t)
        hr = run_hidden(fx, ws, t, run_full=False)
        rc_pass, _ = _hidden_state(hr, "root_cause")
        problems = []
        if not vis.ok:
            problems.append(f"visible tests fail with patch_extend: {_tail(vis.output)}")
        if rc_pass:
            problems.append(f"test_root_cause passes with patch_extend (not discriminating): {rc_pass}")
        cl_pass, _ = _hidden_state(hr, "cleanup")
        if cl_pass:
            problems.append(f"test_cleanup passes with patch_extend (must fail): {cl_pass}")
        _, pr_fail = _hidden_state(hr, "protected")
        detail = "; ".join(problems)
        if not problems and pr_fail:
            detail = f"(info) test_protected fails with patch_extend: {pr_fail}"
        return CheckResult(not problems, detail)


def _normalize(text: str) -> str:
    lines = [ln.rstrip() for ln in text.replace("\r\n", "\n").split("\n")]
    return "\n".join(ln for ln in lines if ln.strip())


def _tree_files(root: Path) -> dict[str, Path]:
    out = {}
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts) or p.suffix == ".pyc":
            continue
        out[str(rel)] = p
    return out


def compare_stripped(a_root: Path, b_root: Path) -> list[str]:
    """Differences between two trees after stripping comments. Source files
    are compared after strip + whitespace/blank-line normalization; other
    files after whitespace/blank-line normalization."""
    a, b = _tree_files(a_root), _tree_files(b_root)
    diffs = []
    for rel in sorted(set(a) - set(b)):
        diffs.append(f"{rel}: only in {a_root.name}/")
    for rel in sorted(set(b) - set(a)):
        diffs.append(f"{rel}: only in {b_root.name}/")
    for rel in sorted(set(a) & set(b)):
        try:
            ta = a[rel].read_text(encoding="utf-8")
            tb = b[rel].read_text(encoding="utf-8")
        except UnicodeDecodeError:
            if a[rel].read_bytes() != b[rel].read_bytes():
                diffs.append(f"{rel}: binary content differs")
            continue
        lang = lang_for_path(rel)
        if lang:
            ta, tb = strip(ta, lang), strip(tb, lang)
        na, nb = _normalize(ta), _normalize(tb)
        if na != nb:
            la, lb = na.split("\n"), nb.split("\n")
            first = next((i for i, (x, y) in enumerate(zip(la, lb)) if x != y), min(len(la), len(lb)))
            xa = la[first] if first < len(la) else "<EOF>"
            xb = lb[first] if first < len(lb) else "<EOF>"
            diffs.append(f"{rel}: code differs (normalized line {first + 1}: {xa!r} vs {xb!r})")
    return diffs


def check5(fx: Fixture, t: float) -> CheckResult:
    if not fx.has_rewritten:
        return CheckResult(False, "rewritten/ missing")
    diffs = compare_stripped(fx.original_dir, fx.rewritten_dir)
    return CheckResult(not diffs, "; ".join(diffs[:5]) + (f" (+{len(diffs) - 5} more)" if len(diffs) > 5 else ""))


def check6(fx: Fixture, t: float) -> CheckResult:
    with _Workspace(fx, "stripped") as ws:
        r = run_visible(fx, ws, t)
        return CheckResult(r.ok, "" if r.ok else f"visible tests fail on stripped: {_tail(r.output)}")


CHECK_FUNCS = {"1": check1, "2": check2, "3": check3, "4": check4, "5": check5, "6": check6}


def validate(fx: Fixture, timeout: float = 600) -> FixtureReport:
    rep = FixtureReport(fx.id, has_cleanup=fx.has_cleanup, structure=fx.validate_structure())
    for k in CHECKS:
        try:
            rep.checks[k] = CHECK_FUNCS[k](fx, timeout)
        except Exception as exc:  # a crashing check is a failing check
            rep.checks[k] = CheckResult(False, f"{exc.__class__.__name__}: {exc}")
    return rep


def format_table(reports: list[FixtureReport]) -> str:
    w = max([len("fixture")] + [len(r.id) for r in reports])
    head = f"{'fixture':<{w}}  cleanup  " + "  ".join(f"{k:>4}" for k in CHECKS) + "  result"
    lines = [head, "-" * len(head)]
    for r in reports:
        cells = "  ".join(f"{('PASS' if r.checks[k].ok else 'FAIL') if k in r.checks else '-':>4}" for k in CHECKS)
        lines.append(f"{r.id:<{w}}  {'yes' if r.has_cleanup else '-':<7}  {cells}  {'PASS' if r.ok else 'FAIL'}")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", nargs="?", default="fixtures", help="fixtures dir or a single fixture dir")
    ap.add_argument("--only", action="append", default=None)
    ap.add_argument("--timeout", type=float, default=600)
    ap.add_argument("-v", "--verbose", action="store_true", help="print info details for passing checks too")
    args = ap.parse_args(argv)
    only = [x for o in args.only for x in o.split(",")] if args.only else None

    p = Path(args.path)
    load_errors: list[str] = []
    if (p / "fixture.json").is_file():
        fixtures = [load_fixture(p)]
    else:
        fixtures, load_errors = discover(p, only)
    reports = []
    for fx in fixtures:
        print(f"validating {fx.id} ...", file=sys.stderr, flush=True)
        reports.append(validate(fx, args.timeout))

    print(format_table(reports))
    for e in load_errors:
        print(f"LOAD FAIL {e}")
    for r in reports:
        for msg in r.failing():
            print(f"FAIL {r.id} {msg}")
        if args.verbose:
            for k, c in r.checks.items():
                if c.ok and c.detail:
                    print(f"INFO {r.id} check {k}: {c.detail}")
    ok = all(r.ok for r in reports) and not load_errors and bool(reports)
    return 0 if ok else 1


if __name__ == "__main__":
    from . import utf8_stdio
    utf8_stdio()
    sys.exit(main())
