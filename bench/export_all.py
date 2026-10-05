"""Export every experiment cell into one CSV (and one JSONL with full rows).

    python -m bench.export_all [results] [--out results/ALL_CELLS]

Writes <out>.csv (one row per cell, the columns most analyses need) and
<out>.jsonl (the full original rows, plus "run" and "status"). Errored cells are
kept with their error, so counts can be checked against each run's own log.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

# What each run is, so the file can be read without the repo.
RUN_INFO = {
    "pilot-all": ("round-1", "pilot", "1 rep, original/stripped/rewritten, claude-fable-5-1"),
    "run-1": ("round-1", "main", "3 reps, original/stripped/rewritten, claude-opus-5-5, judge claude-sonnet-5"),
    "exp-claude-md": ("round-1", "experiment", "CLAUDE.md cleanup line, original/stripped"),
    "exp-lying": ("round-1", "experiment", "lying comment v1"),
    "pilot-money-v2": ("round-2", "pilot", "ts-money-cents task v2 solvability"),
    "pilot-claude": ("round-2", "pilot", "1 rep, excluded from analysis"),
    "pilot-claude-idem": ("round-2", "pilot", "1 rep, excluded from analysis"),
    "pilot-codex": ("round-2", "pilot", "gpt-6-astra, excluded"),
    "pilot-codex-idem": ("round-2", "pilot", "gpt-6-astra, excluded"),
    "pilot-codex-luna": ("round-2", "pilot", "gpt-6-luna, excluded"),
    "pilot-sonnet": ("round-2", "pilot", "claude-sonnet-5-5, excluded"),
    "conf-claude": ("round-2", "confirmatory-design (unpowered; exploratory)", "claude-opus-5-5, 5 reps"),
    "conf-sonnet": ("round-2", "confirmatory-design (unpowered; exploratory)", "claude-sonnet-5-5, 5 reps"),
    "conf-codex-luna": ("round-2", "confirmatory-design (unpowered; exploratory)", "gpt-6-luna, 4 core conditions"),
    "conf-codex": ("round-2", "descriptive only", "gpt-6-astra, superseded by luna (amendment 3)"),
    "p6-claude": ("round-2", "exploratory paso 6", "authority/distance/agent-directed variants"),
    "p6-claude-pressure-minimal": ("round-2", "exploratory paso 6", "task suffix: smallest change"),
    "p6-claude-pressure-rootcause": ("round-2", "exploratory paso 6", "task suffix: find the root cause"),
    "p6-claude-prtext": ("round-2", "exploratory paso 6", "task suffix: PR description"),
    "p6-codex": ("round-2", "exploratory paso 6 (partial, quota)", "gpt-6-astra"),
    "p6-grok": ("round-2", "exploratory paso 6 (partial, balance)", "grok-4.7"),
    "r3-opus": ("round-3", "CONFIRMATORY (pre-registered, powered)", "H-A: original vs hack_recipe"),
    "r3-opus-lying": ("round-3", "CONFIRMATORY (pre-registered, powered)", "H-B: lying"),
}

COLUMNS = [
    "round", "run", "run_role", "run_note", "status", "error",
    "agent", "model", "main_model", "fixture", "condition", "rep", "timestamp",
    "root_cause_pass", "protected_pass", "cleanup_pass", "visible_pass",
    "workaround_present", "workaround_region_delta", "comments_added", "comments_removed",
    "authority_comment_removed", "marker_in_answer",
    "judge_strategy", "used_git_history_before_edit", "used_search_before_edit", "read_tests_before_edit",
    "n_tool_calls", "num_turns", "total_cost_usd", "agent_wall_s", "plan_usage_5h",
    "claude_md", "task_suffix", "run_dir", "agent_result",
]


def _rows(results: Path):
    for f in sorted(results.rglob("results.jsonl")):
        run = f.parent.name
        meta = {}
        m = f.parent / "meta.json"
        if m.is_file():
            meta = json.loads(m.read_text(encoding="utf-8"))
        rnd, role, note = RUN_INFO.get(run, ("?", "?", ""))
        seen = {}
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                seen[(r.get("fixture"), r.get("condition"), r.get("rep"))] = r  # last row per cell (resume)
        for r in seen.values():
            yield {**r, "round": rnd, "run": run, "run_role": role, "run_note": note,
                   "status": "error" if r.get("error") else "ok",
                   "agent": r.get("agent") or "claude",
                   "task_suffix": meta.get("task_suffix"),
                   "plan_usage_5h": (r.get("plan_usage") or {}).get("five_hour"),
                   "run_dir": str(f.parent / (r.get("run_dir") or "")).replace("\\", "/")}


def main(argv=None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    out = Path("results/ALL_CELLS")
    if "--out" in args:
        i = args.index("--out")
        out = Path(args[i + 1])
        del args[i:i + 2]
    results = Path(args[0] if args else "results")
    rows = list(_rows(results))
    with open(out.with_suffix(".csv"), "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            r = dict(r)
            if isinstance(r.get("agent_result"), str):
                r["agent_result"] = r["agent_result"][:1500]
            w.writerow(r)
    with open(out.with_suffix(".jsonl"), "w", encoding="utf-8", newline="\n") as fh:
        for r in rows:
            fh.write(json.dumps(r, default=str) + "\n")
    by = {}
    for r in rows:
        by.setdefault(r["run"], [0, 0])[0 if r["status"] == "ok" else 1] += 1
    print(f"{len(rows)} cells -> {out.with_suffix('.csv')} and {out.with_suffix('.jsonl')}")
    for run, (ok, err) in sorted(by.items()):
        print(f"  {run:<30} ok {ok:>4}  error {err:>3}")
    return 0


if __name__ == "__main__":
    from . import utf8_stdio
    utf8_stdio()
    sys.exit(main())
