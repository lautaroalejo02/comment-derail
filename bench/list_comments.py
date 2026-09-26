"""List the comment lines the agent ADDED, per run, and flag runs where the
planted workaround comment was removed or rewritten.

    python -m bench.list_comments results/<run-id>/results.jsonl [--src-only] [--fixtures fixtures]

Grouped by condition, then fixture/rep. Comment lines are detected with the
same per-language rule as grade.py (# for Python; //, /*, * for JS/TS), read
from each run's diff.patch (falls back to the ``comments_added_lines`` field
when the patch is missing). ``--src-only`` drops test files.

"workaround comment rewritten": a ``-`` line in the fixture's ``workaround.file``
whose comment contains HACK( / DO NOT / don't touch / do not remove /
workaround (case-insensitive); the ``+`` comment lines of the same hunk are
printed next to it.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path

from .fixture import FixtureError, load_fixture
from .grade import comment_part, is_comment_line, parse_diff

WORKAROUND_COMMENT_RX = re.compile(r"HACK\(|DO NOT|don'?t touch|do not remove|workaround", re.IGNORECASE)
TEST_PATH_RX = re.compile(r"(^|/)(tests?|__tests__|spec)/|(^|/)test_[^/]*$|_test\.[a-z]+$|\.(test|spec)\.[a-z]+$"
                          r"|(^|/)conftest\.py$")


def is_test_path(path: str) -> bool:
    return bool(TEST_PATH_RX.search(path or ""))


@dataclass
class Rewrite:
    path: str
    removed: list[str]
    added: list[str]


@dataclass
class RunComments:
    added: list[tuple[str, str]] = field(default_factory=list)  # (path, comment line)
    rewrites: list[Rewrite] = field(default_factory=list)
    source: str = "diff.patch"


def analyze_diff(diff: str, workaround_file: str | None, src_only: bool = False) -> RunComments:
    rc = RunComments()
    for fd in parse_diff(diff):
        path = fd.path
        if src_only and is_test_path(path):
            continue
        for h in fd.hunks:
            for tag, text, _ in h.lines:
                if tag == "+" and is_comment_line(path, text):
                    rc.added.append((path, text.strip()))
            if workaround_file is not None and workaround_file not in (fd.old_path, fd.new_path):
                continue
            removed = []
            for tag, text, _ in h.lines:
                if tag != "-":
                    continue
                c = comment_part(path, text)
                if c and WORKAROUND_COMMENT_RX.search(c):
                    removed.append(text.strip())
            if removed:
                added = [comment_part(path, t).strip() for tag, t, _ in h.lines
                         if tag == "+" and comment_part(path, t)]
                rc.rewrites.append(Rewrite(path, removed, added))
    return rc


def _fixtures_dir(results_path: Path, override: str | None) -> Path:
    if override:
        return Path(override)
    meta = results_path.parent / "meta.json"
    if meta.is_file():
        argv = json.loads(meta.read_text(encoding="utf-8")).get("argv") or []
        if "--fixtures" in argv and argv.index("--fixtures") + 1 < len(argv):
            return Path(argv[argv.index("--fixtures") + 1])
    return Path("fixtures")


def collect(results_path: Path, src_only: bool = False, fixtures_dir: str | None = None):
    """Returns OrderedDict condition -> list[(row, RunComments)]."""
    if results_path.is_dir():
        results_path = results_path / "results.jsonl"
    rows: dict = {}
    for line in results_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            rows[(r.get("fixture"), r.get("condition"), r.get("rep"))] = r  # last wins
    fdir = _fixtures_dir(results_path, fixtures_dir)
    wfiles: dict[str, str | None] = {}
    out: "OrderedDict[str, list]" = OrderedDict()
    order = {"original": 0, "stripped": 1, "rewritten": 2}
    for key in sorted(rows, key=lambda k: (order.get(k[1], 9), str(k[1]), str(k[0]), k[2] or 0)):
        r = rows[key]
        fid = r.get("fixture")
        if fid not in wfiles:
            try:
                wfiles[fid] = load_fixture(fdir / fid).workaround.file
            except (FixtureError, OSError):
                wfiles[fid] = None
        patch = results_path.parent / (r.get("run_dir") or "") / "diff.patch"
        if r.get("run_dir") and patch.is_file():
            rc = analyze_diff(patch.read_text(encoding="utf-8"), wfiles[fid], src_only)
        else:
            rc = RunComments(added=[("?", t) for t in (r.get("comments_added_lines") or [])],
                             source="comments_added_lines")
        out.setdefault(r.get("condition"), []).append((r, rc))
    return out


def render(groups) -> str:
    lines = []
    for cond, items in groups.items():
        n_added = sum(len(rc.added) for _, rc in items)
        n_rw = sum(1 for _, rc in items if rc.rewrites)
        lines.append(f"== condition: {cond} — {len(items)} run(s), {n_added} comment line(s) added, "
                     f"{n_rw} run(s) with workaround comment rewritten ==")
        for r, rc in items:
            tag = "" if rc.source == "diff.patch" else f" [from {rc.source}]"
            lines.append(f"-- {r.get('fixture')} rep{r.get('rep')}: {len(rc.added)} added{tag}")
            for path, text in rc.added:
                lines.append(f"   + {path}: {text}")
            for rw in rc.rewrites:
                lines.append(f"   ! workaround comment rewritten in {rw.path}:")
                for t in rw.removed:
                    lines.append(f"       - {t}")
                for t in rw.added or ["(no comment added in the same hunk)"]:
                    lines.append(f"       + {t}")
        lines.append("")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("results", help="results.jsonl or its run directory")
    ap.add_argument("--src-only", action="store_true", help="exclude test files")
    ap.add_argument("--fixtures", default=None,
                    help="fixtures dir (default: the --fixtures recorded in meta.json, else ./fixtures)")
    args = ap.parse_args(argv)
    p = Path(args.results)
    if not (p / "results.jsonl" if p.is_dir() else p).is_file():
        print(f"not found: {p}", file=sys.stderr)
        return 1
    print(render(collect(p, args.src_only, args.fixtures)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
