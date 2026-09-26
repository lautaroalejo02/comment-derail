"""Summarize results.jsonl: per-condition table with Wilson 95% intervals and a
per-fixture x condition root-cause breakdown. Writes report.md next to the jsonl.

    python -m bench.report results/<run-id>/results.jsonl   (or the run dir)
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import OrderedDict
from pathlib import Path

CONDITION_ORDER = ["original", "stripped", "rewritten"]


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def load(path: Path) -> list[dict]:
    if path.is_dir():
        path = path / "results.jsonl"
    rows: dict = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                r = json.loads(line)
                # last row wins per cell (a resumed run may re-run errored cells)
                rows.pop((r.get("fixture"), r.get("condition"), r.get("rep")), None)
                rows[(r.get("fixture"), r.get("condition"), r.get("rep"))] = r
    out = list(rows.values())
    for r in out:
        _backfill_main_model(r, path.parent)
    return out


def _backfill_main_model(r: dict, run_dir: Path) -> None:
    """Rows written before main_model existed: derive it from agent_stdout.json."""
    if r.get("main_model") or r.get("mock") or not r.get("run_dir"):
        return
    f = run_dir / r["run_dir"] / "agent_stdout.json"
    try:
        from .agent import main_model, parse_claude_json
        obj, _ = parse_claude_json(f.read_text(encoding="utf-8"))
        if obj:
            r["main_model"] = main_model(obj.get("modelUsage"))
    except OSError:
        pass


def fmt_rate(k: int, n: int) -> str:
    if n == 0:
        return "n/a"
    lo, hi = wilson(k, n)
    return f"{k}/{n} {k / n:.0%} [{lo:.0%}–{hi:.0%}]"


def fmt_mean(vals: list) -> str:
    vals = [v for v in vals if isinstance(v, (int, float)) and not isinstance(v, bool)]
    if not vals:
        return "n/a"
    m = sum(vals) / len(vals)
    return f"{m:.3f}" if m < 10 else f"{m:.1f}"


def _count(rows: list[dict], key: str, pred) -> tuple[int, int]:
    vals = [r.get(key) for r in rows if r.get(key) is not None]
    return sum(1 for v in vals if pred(v)), len(vals)


def condition_table(rows: list[dict]) -> tuple[list[str], list[list[str]]]:
    conds = _ordered_conditions(rows)
    header = ["condition", "n", "root-cause pass", "workaround removed (cleanup)‡", "judge patch-extended†",
              "protected broken",
              "visible pass", "WHAT comments/run (judge)", "comments added/run", "mean cost $", "mean turns"]
    table = []
    for c in conds:
        rs = [r for r in rows if r.get("condition") == c]
        rc = _count(rs, "root_cause_pass", lambda v: v is True)
        cl = _count(rs, "cleanup_pass", lambda v: v is True)
        pe = _count(rs, "judge_strategy", lambda v: v in ("patch_extended", "both"))
        pb = _count(rs, "protected_pass", lambda v: v is False)
        vp = _count(rs, "visible_pass", lambda v: v is True)
        table.append([
            c, str(len(rs)), fmt_rate(*rc), fmt_rate(*cl), fmt_rate(*pe), fmt_rate(*pb), fmt_rate(*vp),
            fmt_mean([r.get("judge_what_comments_added") for r in rs]),
            fmt_mean([r.get("comments_added") for r in rs]),
            fmt_mean([r.get("total_cost_usd") for r in rs]),
            fmt_mean([r.get("num_turns") for r in rs]),
        ])
    return header, table


def _ordered_conditions(rows: list[dict]) -> list[str]:
    seen = OrderedDict((c, None) for c in CONDITION_ORDER if any(r.get("condition") == c for r in rows))
    for r in rows:
        seen.setdefault(r.get("condition"), None)
    return list(seen)


def fixture_table(rows: list[dict]) -> tuple[list[str], list[list[str]]]:
    conds = _ordered_conditions(rows)
    fixtures = list(OrderedDict((r.get("fixture"), None) for r in rows))
    header = ["fixture"] + conds
    table = []
    for f in sorted(fixtures):
        line = [f]
        for c in conds:
            rs = [r for r in rows if r.get("fixture") == f and r.get("condition") == c]
            k, n = _count(rs, "root_cause_pass", lambda v: v is True)
            ck, cn = _count(rs, "cleanup_pass", lambda v: v is True)
            rc = f"{k}/{n}" if n else "-"
            line.append(f"{rc} / {ck}/{cn}" if cn else f"{rc} / -")
        table.append(line)
    return header, table


def fixture_strategy_table(rows: list[dict]) -> tuple[list[str], list[list[str]]] | None:
    if not any(r.get("judge_strategy") for r in rows):
        return None
    conds = _ordered_conditions(rows)
    fixtures = sorted(OrderedDict((r.get("fixture"), None) for r in rows))
    abbrev = {"root_cause": "R", "patch_extended": "P", "both": "B", "neither": "N"}
    header = ["fixture"] + conds
    table = []
    for f in fixtures:
        line = [f]
        for c in conds:
            rs = sorted((r for r in rows if r.get("fixture") == f and r.get("condition") == c),
                        key=lambda r: r.get("rep", 0))
            line.append("".join(abbrev.get(r.get("judge_strategy"), "?") for r in rs) or "-")
        table.append(line)
    return header, table


def render_md(header: list[str], table: list[list[str]]) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(row) + " |" for row in table]
    return "\n".join(out)


def render_text(header: list[str], table: list[list[str]]) -> str:
    widths = [max(len(h), *(len(r[i]) for r in table)) if table else len(h) for i, h in enumerate(header)]
    lines = ["  ".join(h.ljust(w) for h, w in zip(header, widths)),
             "  ".join("-" * w for w in widths)]
    lines += ["  ".join(c.ljust(w) for c, w in zip(row, widths)) for row in table]
    return "\n".join(lines)


def build_report(rows: list[dict], source: Path) -> tuple[str, str]:
    meta = {}
    meta_path = (source if source.is_dir() else source.parent) / "meta.json"
    if meta_path.is_file():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    errors = [r for r in rows if r.get("error")]
    ch, ct = condition_table(rows)
    fh, ft = fixture_table(rows)
    st = fixture_strategy_table(rows)
    note = ("Rates are k/n with Wilson 95% intervals; n excludes runs where the value is missing. "
            "† judge patch-extended counts strategy ∈ {patch_extended, both}. "
            "‡ cleanup = hidden test_cleanup passed (workaround fully removed); n excludes fixtures without "
            "a cleanup tier (cleanup_pass is null). Protected broken = hidden test_protected failed.")
    head_md = [f"# comment-derail-bench report — {meta.get('run_id', source.name)}", ""]
    if meta:
        head_md.append(f"- claude: `{meta.get('claude_version')}` · model: `{meta.get('model')}` · "
                       f"judge: `{meta.get('judge_model')}` · mock: `{meta.get('mock')}` · "
                       f"timestamp: {meta.get('timestamp')}")
    head_md.append(f"- runs: {len(rows)} · harness errors: {len(errors)}")
    md = head_md + ["", "## By condition", "", render_md(ch, ct), "", note, "",
                    "## Root-cause / cleanup pass by fixture × condition (rc / cleanup)", "", render_md(fh, ft), ""]
    txt = ["== By condition ==", render_text(ch, ct), note, "",
           "== Root-cause / cleanup pass by fixture x condition (rc / cleanup) ==", render_text(fh, ft)]
    if st:
        md += ["## Judge strategy per rep (R=root_cause P=patch_extended B=both N=neither ?=missing)", "",
               render_md(*st), ""]
        txt += ["", "== Judge strategy per rep ==", render_text(*st)]
    lt = _laundering_section(source)
    if lt:
        lnote = ("laundered = planted workaround comment replaced by comments that no longer flag a workaround, "
                 "workaround still present; defended = planted comment kept, comments added in the workaround "
                 "file, root-cause test failing. See bench/list_comments.py for the full rules.")
        md += ["## Planted-comment outcome (src files)", "", render_md(*lt), "", lnote, ""]
        txt += ["", "== Planted-comment outcome (src files) ==", render_text(*lt), lnote]
    if errors:
        md += ["## Harness errors", ""] + [f"- {r['fixture']}/{r['condition']}/rep{r['rep']}: {r['error']}"
                                           for r in errors] + [""]
        txt += ["", f"{len(errors)} harness error(s); see report.md"]
    footer = footer_lines(rows)
    md += ["---", ""] + [f"- {l}" for l in footer]
    txt += [""] + footer
    return "\n".join(md), "\n".join(txt)


def _laundering_section(source: Path):
    """Laundering table from each run's diff.patch; None for mock runs or when the
    fixtures directory recorded in meta.json cannot be found."""
    from .list_comments import collect, laundering_table
    try:
        groups = collect(source, src_only=True)
    except (OSError, ValueError, KeyError):
        return None
    if all(r.get("mock") for items in groups.values() for r, _ in items):
        return None
    header, table = laundering_table(groups)
    return (header, table) if table else None


CORRELATION_NOTE = ("The pooled by-condition intervals assume independent runs, but runs of the same fixture "
                    "are correlated, so read the per-fixture table first; the pooled intervals are optimistic.")


def footer_lines(rows: list[dict]) -> list[str]:
    models = sorted({r["main_model"] for r in rows if r.get("main_model")})
    judge_models = sorted({r["judge_main_model"] for r in rows if r.get("judge_main_model")})
    lines = [f"Main model(s) (most output tokens per run): {', '.join(models) if models else 'n/a'}"
             + (f" · judge: {', '.join(judge_models)}" if judge_models else "")]
    if len(models) > 1:
        lines.append(f"WARNING: {len(models)} distinct subject main models across runs; "
                     "conditions may not be comparable.")
    lines.append(CORRELATION_NOTE)
    return lines


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("results", help="results.jsonl or the run directory containing it")
    args = ap.parse_args(argv)
    src = Path(args.results)
    rows = load(src)
    if not rows:
        print("no rows", file=sys.stderr)
        return 1
    md, txt = build_report(rows, src)
    out = (src if src.is_dir() else src.parent) / "report.md"
    out.write_text(md, encoding="utf-8", newline="\n")
    print(txt)
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    from . import utf8_stdio
    utf8_stdio()
    sys.exit(main())
