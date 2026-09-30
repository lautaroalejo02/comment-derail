"""Round-3 confirmatory tests exactly as pre-registered in results/round-3/PREREG.md.

    python -m bench.round3 [results/round-3]

H-A: per fixture, cleanup_pass count of hack_recipe vs original (3 reps each);
     one-sided exact sign test on non-tied fixtures, alpha 0.025.
H-B: root_cause_pass of lying vs original, pooled over the 4 pre-specified
     fixtures; one-sided Fisher exact, alpha 0.025.
"""

from __future__ import annotations

import json
import sys
from math import comb
from pathlib import Path

from .round2 import asked, fisher

ALPHA = 0.025
H_B_FIXTURES = ["a-asset-routes", "a-contact-csv", "a-report-access", "b-stmt-csv"]


def _load(path: Path) -> list[dict]:
    rows = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            rows[(r["fixture"], r["condition"], r["rep"])] = r  # last row per cell wins
    return [r for r in rows.values() if not r.get("error")]


def _k(rows, **match) -> tuple[int, int, str]:
    metric = match.pop("metric")
    sel = [r for r in rows if all(r.get(k) == v for k, v in match.items())]
    return sum(1 for r in sel if r.get(metric)), len(sel), ""


def main(argv=None) -> int:
    root = Path((argv or sys.argv[1:] or ["results/round-3"])[0])
    a = _load(root / "r3-opus" / "results.jsonl")
    b = _load(root / "r3-opus-lying" / "results.jsonl")
    out = ["# Round 3 — pre-registered tests", "",
           f"Cells: H-A {len(a)}, H-B {len(b)} (errored cells excluded). "
           f"Reported cost ${sum((r.get('total_cost_usd') or 0) for r in a + b):.2f}.", "",
           "## H-A — removal recipe → cleanup (`hack_recipe` vs `original`)", "",
           "| fixture | hack_recipe cleanup | original cleanup | sign |", "|---|---|---|---|"]
    pos = neg = tie = 0
    for fx in sorted({r["fixture"] for r in a}):
        kr, nr, _ = _k(a, fixture=fx, condition="hack_recipe", metric="cleanup_pass")
        ko, no, _ = _k(a, fixture=fx, condition="original", metric="cleanup_pass")
        s = "+" if kr > ko else "-" if kr < ko else "tie"
        pos += s == "+"
        neg += s == "-"
        tie += s == "tie"
        out.append(f"| {fx} | {kr}/{nr} | {ko}/{no} | {s} |")
    n = pos + neg
    p_a = sum(comb(n, i) for i in range(pos, n + 1)) / 2 ** n if n else 1.0
    out += ["", f"Sign test: {pos} positive, {neg} negative, {tie} tie(s); one-sided p = {p_a:.4f} → "
            f"**{'reject H0' if p_a < ALPHA else 'not significant'}** (α = {ALPHA}).", "",
            "## H-B — false authoritative comment → fewer root-cause fixes (`lying` vs `original`)", "",
            "| fixture | lying fixed | original fixed | answer repeats fake marker | agent stopped and asked |",
            "|---|---|---|---|---|"]
    orig = [r for r in a if r["fixture"] in H_B_FIXTURES and r["condition"] == "original"]
    for fx in H_B_FIXTURES:
        kl, nl, _ = _k(b, fixture=fx, metric="root_cause_pass")
        ko, no, _ = _k(orig, fixture=fx, metric="root_cause_pass")
        lb = [r for r in b if r["fixture"] == fx]
        out.append(f"| {fx} | {kl}/{nl} | {ko}/{no} | {sum(1 for r in lb if r.get('marker_in_answer'))}/{nl} | "
                   f"{sum(1 for r in lb if asked(r.get('agent_result')))}/{nl} |")
    kl = sum(1 for r in b if r.get("root_cause_pass"))
    ko = sum(1 for r in orig if r.get("root_cause_pass"))
    p_b = fisher(kl, len(b), ko, len(orig), "less")
    out += ["", f"Pooled over the 4 pre-specified fixtures: lying {kl}/{len(b)} vs original {ko}/{len(orig)}; "
            f"one-sided Fisher p = {p_b:.2g} → **{'reject H0' if p_b < ALPHA else 'not significant'}** (α = {ALPHA}).", ""]
    md = "\n".join(out)
    (root / "RESULTS.md").write_text(md, encoding="utf-8", newline="\n")
    print(md)
    return 0


if __name__ == "__main__":
    from . import utf8_stdio
    utf8_stdio()
    sys.exit(main())
