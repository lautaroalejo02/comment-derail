"""Telephone-game chains: each generation's agent gets the previous final tree
and a new task from fixtures/<id>/chain_tasks.json.

    python -m bench.chain --fixtures fixtures --seed-run results/run-1 \
        [--seed-condition original] [--reps 3] [--model M] [--max-turns 40] \
        [--jobs 4] --out results/ --run-id chain-1

Generation 1 is the seed: results/<seed-run>/runs/<id>/<seed-condition>/rep<k>/final
(an earlier agent's answer to the fixture's bug task). Generations 2.. run the
tasks in chain_tasks.json in order, sequentially within a chain; chains run in
parallel. Per generation it records the diff, the final tree, the comment lines
around the workaround, the planted-comment outcome (bench.list_comments), and
visible/hidden test results. Hidden tests run on a copy, so they never leak
into the next generation. Writes results/<run-id>/chains.jsonl and chains.md.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import sys
import tempfile
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .agent import claude_version, run_agent
from .fixture import Fixture, discover
from .grade import diff_metrics, is_comment_line, run_hidden, run_visible
from .list_comments import analyze_diff, laundering_label
from .subjects import AGENTS, behavior_flags
from .workspace import (build_condition, copytree, git_baseline, git_diff, normalize_instruction_files,
                        remove_claude_config, save_tree)

_lock = threading.Lock()
_log_fh = None


def log(msg: str) -> None:
    print(msg, flush=True)
    if _log_fh is not None:
        with _lock:
            _log_fh.write(msg + "\n")
            _log_fh.flush()


def load_tasks(fx: Fixture) -> list[str] | None:
    p = fx.root / "chain_tasks.json"
    if not p.is_file():
        return None
    return list(json.loads(p.read_text(encoding="utf-8"))["tasks"])


def workaround_comments(fx: Fixture, tree: Path, window: int = 8) -> list[str]:
    """Comment lines of the workaround file within ``window`` lines of a marker match."""
    f = tree / fx.workaround.file
    if not f.is_file():
        return []
    lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
    hits = [i for i, l in enumerate(lines) if fx.workaround.marker_re.search(l)]
    if not hits:
        return []
    keep = set()
    for i in hits:
        keep.update(range(max(0, i - window), min(len(lines), i + window + 1)))
    return [lines[i].strip() for i in sorted(keep) if is_comment_line(fx.workaround.file, lines[i])]


def _grade_copy(fx: Fixture, tree: Path, timeout: float) -> dict:
    """Visible + hidden tests on a throwaway copy of ``tree``."""
    with tempfile.TemporaryDirectory(prefix="cdb-chain-grade-") as tmp:
        ws = Path(tmp) / "ws"
        copytree(tree, ws)
        vis = run_visible(fx, ws, timeout=timeout)
        hr = run_hidden(fx, ws, timeout=timeout, run_full=False)
        return {"visible_pass": vis.ok, "root_cause_pass": hr.passed("root_cause"),
                "protected_pass": hr.passed("protected"), "cleanup_pass": hr.passed("cleanup")}


def agent_for_gen(args, gen: int) -> str:
    """--agents a,b,c assigns agents to generations 1, 2, 3, ... cyclically."""
    return args.agents[(gen - 1) % len(args.agents)]


def run_chain(fx: Fixture, rep: int, tasks: list[str], seed: Path | None, args, run_dir: Path, record) -> None:
    cdir = run_dir / "runs" / fx.id / f"rep{rep}"
    base = {"run_id": args.run_id, "fixture": fx.id, "rep": rep, "seed": str(seed) if seed else None}
    if seed is not None:
        # generation 1: the seed tree as an earlier agent left it
        prev = seed
        rec = {**base, "gen": 1, "task": fx.task, "seeded": True,
               "workaround_present": bool(fx.workaround.marker_re.search(
                   (seed / fx.workaround.file).read_text(encoding="utf-8", errors="replace"))
                   if (seed / fx.workaround.file).is_file() else False),
               "workaround_comments": workaround_comments(fx, seed)}
        rec.update(_grade_copy(fx, seed, args.test_timeout))
        record(rec)
        gens = list(enumerate(tasks, start=2))
    else:
        # generation 1 runs live: the fixture's bug task on --start-condition
        start = run_dir / "_start" / fx.id / f"rep{rep}"
        if start.exists():
            shutil.rmtree(start)
        start.mkdir(parents=True)
        build_condition(fx, args.start_condition, start)
        prev = start
        gens = [(1, fx.task + ("\n\n" + args.gen1_suffix_text if args.gen1_suffix_text else ""))]
        gens += list(enumerate(tasks, start=2))
    for gen, task in gens:
        agent = agent_for_gen(args, gen)
        gdir = cdir / f"gen{gen}"
        gdir.mkdir(parents=True, exist_ok=True)
        rec = {**base, "gen": gen, "task": task, "agent": agent, "error": None, "retries": 0}
        tmp_root = Path(tempfile.mkdtemp(prefix=f"cdb-chain-{fx.id}-{rep}-{gen}-", dir=args.workdir))
        ws = tmp_root / "ws"
        try:
            copytree(prev, ws)
            shutil.rmtree(ws / ".git", ignore_errors=True)
            remove_claude_config(ws)
            normalize_instruction_files(ws, agent)
            baseline = git_baseline(ws)
            while True:
                ar = run_agent(ws, task, max_turns=args.max_turns, model=args.models.get(agent),
                               timeout=args.agent_timeout, isolate=args.isolate_config, agent=agent)
                if ar.rate_limited and rec["retries"] < len(args.backoff):
                    time.sleep(args.backoff[rec["retries"]])
                    rec["retries"] += 1
                    continue
                break
            (gdir / "agent_stdout.json").write_text(ar.stdout or "", encoding="utf-8", newline="\n")
            (gdir / "tool_events.json").write_text(json.dumps(ar.events, indent=1), encoding="utf-8", newline="\n")
            rec.update(behavior_flags(ar.events))
            rec.update({"total_cost_usd": ar.total_cost_usd, "num_turns": ar.num_turns,
                        "agent_returncode": ar.returncode, "agent_timed_out": ar.timed_out,
                        "main_model": ar.main_model,
                        "agent_result": (ar.result or "")[:2000] if isinstance(ar.result, str) else None})
            if ar.usage_limited or ar.auth_failed or ar.rate_limited or ar.is_error:
                rec["error_kind"] = ("usage_limit" if ar.usage_limited else "auth" if ar.auth_failed
                                     else "rate_limit" if ar.rate_limited else "agent_error")
                rec["error"] = rec["error_kind"]
                record(rec)
                return  # a broken generation ends the chain
            diff = git_diff(ws, baseline)
            (gdir / "diff.patch").write_text(diff, encoding="utf-8", newline="\n")
            save_tree(ws, gdir / "final")
            m = diff_metrics(diff, fx, ws, baseline)
            rc = analyze_diff(diff, fx.workaround.file, src_only=True)
            rec.update({
                "workaround_present": m["workaround_present"],
                "comments_added_lines": m.get("comments_added_lines"),
                "planted_comment_outcome": laundering_label(
                    {"condition": "original", "workaround_present": m["workaround_present"],
                     "root_cause_pass": None}, rc),
                "workaround_comments": workaround_comments(fx, ws),
            })
            rec.update(_grade_copy(fx, ws, args.test_timeout))
            prev = gdir / "final"
        except Exception as exc:  # record and end this chain
            rec["error"] = f"{exc.__class__.__name__}: {exc}"
            (gdir / "harness_error.txt").write_text(traceback.format_exc(), encoding="utf-8", newline="\n")
            record(rec)
            return
        finally:
            shutil.rmtree(tmp_root, ignore_errors=True)
        record(rec)


def render_md(rows: list[dict]) -> str:
    out = ["# Telephone chains", ""]
    gens = sorted({r["gen"] for r in rows})
    fixtures = sorted({r["fixture"] for r in rows})
    out += ["| fixture | " + " | ".join(f"gen{g} workaround / cleanup / root cause" for g in gens) + " |",
            "|---|" + "---|" * len(gens)]
    for f in fixtures:
        cells = []
        for g in gens:
            rs = [r for r in rows if r["fixture"] == f and r["gen"] == g and not r.get("error")]
            n = len(rs)
            wp = sum(1 for r in rs if r.get("workaround_present"))
            cl = sum(1 for r in rs if r.get("cleanup_pass"))
            rc = sum(1 for r in rs if r.get("root_cause_pass"))
            cells.append(f"{wp}/{n} / {cl}/{n} / {rc}/{n}" if n else "-")
        out.append(f"| {f} | " + " | ".join(cells) + " |")
    out += ["", "Cleanup counts only fixtures with a cleanup tier (else 0).", ""]
    for f in fixtures:
        for rep in sorted({r["rep"] for r in rows if r["fixture"] == f}):
            out += [f"## {f} rep{rep}", ""]
            for r in sorted((r for r in rows if r["fixture"] == f and r["rep"] == rep), key=lambda r: r["gen"]):
                tag = r.get("planted_comment_outcome") or ""
                err = f" ERROR {r['error']}" if r.get("error") else ""
                out.append(f"**gen{r['gen']}** workaround={r.get('workaround_present')} "
                           f"root_cause={r.get('root_cause_pass')} cleanup={r.get('cleanup_pass')} "
                           f"protected={r.get('protected_pass')} {tag}{err}")
                out += ["```"] + (r.get("workaround_comments") or ["(no comment near the workaround)"]) + ["```", ""]
    return "\n".join(out)


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fixtures", default="fixtures")
    ap.add_argument("--only", default=None, help="comma-separated fixture ids")
    ap.add_argument("--seed-run", default=None,
                    help="results/<run-id> whose final trees seed generation 1; without it generation 1 "
                         "runs live on --start-condition")
    ap.add_argument("--seed-condition", default="original")
    ap.add_argument("--start-condition", default="stripped", help="condition for a live generation 1")
    ap.add_argument("--gen1-suffix", default=None, help="file appended to the generation-1 task (live mode)")
    ap.add_argument("--agents", default="claude",
                    help="comma list of subject agents assigned to generations 1,2,3.. cyclically")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--model", action="append", default=[],
                    help="agent=model (repeatable), or a bare model for every agent")
    ap.add_argument("--max-turns", type=int, default=40)
    ap.add_argument("--jobs", type=int, default=1)
    ap.add_argument("--out", default="results")
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--agent-timeout", type=float, default=1800)
    ap.add_argument("--test-timeout", type=float, default=600)
    ap.add_argument("--backoff", default="60,120,240")
    ap.add_argument("--no-isolate-config", dest="isolate_config", action="store_false", default=True)
    ap.add_argument("--workdir", default=None)
    args = ap.parse_args(argv)
    args.backoff = [float(x) for x in args.backoff.split(",") if x.strip()]
    args.agents = [a.strip() for a in args.agents.split(",") if a.strip()]
    bad = [a for a in args.agents if a not in AGENTS]
    if bad:
        ap.error(f"unknown agent(s) {bad}; choose from {AGENTS}")
    args.models = {}
    for m in args.model:
        if "=" in m:
            a, v = m.split("=", 1)
            args.models[a.strip()] = v.strip()
        else:
            args.models = {a: m for a in AGENTS} | args.models
    args.gen1_suffix_text = Path(args.gen1_suffix).read_text(encoding="utf-8").strip() if args.gen1_suffix else None
    return args


def main(argv=None) -> int:
    global _log_fh
    args = parse_args(argv)
    only = [x for x in (args.only or "").split(",") if x] or None
    fixtures, errors = discover(args.fixtures, only)
    for e in errors:
        print(f"[chain] warning: {e}", file=sys.stderr)
    jobs = []
    for fx in fixtures:
        tasks = load_tasks(fx)
        if not tasks:
            continue
        for k in range(1, args.reps + 1):
            seed = None
            if args.seed_run:
                seed = Path(args.seed_run) / "runs" / fx.id / args.seed_condition / f"rep{k}" / "final"
                if not seed.is_dir():
                    print(f"[chain] missing seed {seed}; skipping", file=sys.stderr)
                    continue
            elif not fx.has_condition(args.start_condition):
                print(f"[chain] {fx.id} has no {args.start_condition}/; skipping", file=sys.stderr)
                continue
            jobs.append((fx, k, tasks, seed))
    if not jobs:
        print("[chain] nothing to run (no chain_tasks.json or seeds)", file=sys.stderr)
        return 2
    run_dir = Path(args.out) / args.run_id
    out = run_dir / "chains.jsonl"
    if out.is_file() and out.stat().st_size:
        print(f"[chain] {out} exists; use another --run-id", file=sys.stderr)
        return 2
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "meta.json").write_text(json.dumps({
        "run_id": args.run_id, "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "claude_version": claude_version(), "models": args.models, "agents": args.agents, "max_turns": args.max_turns,
        "start_condition": None if args.seed_run else args.start_condition, "gen1_suffix": args.gen1_suffix_text,
        "seed_run": args.seed_run, "seed_condition": args.seed_condition, "reps": args.reps,
        "fixtures": sorted({fx.id for fx, *_ in jobs}), "config_isolated": args.isolate_config,
        "argv": sys.argv[1:] if argv is None else list(argv)}, indent=2), encoding="utf-8", newline="\n")
    _log_fh = open(run_dir / "run.log", "a", encoding="utf-8", newline="\n")
    rows: list[dict] = []
    stop_kinds: set = set()

    def record(rec: dict) -> None:
        with _lock:
            rows.append(rec)
            with open(out, "a", encoding="utf-8", newline="\n") as fh:
                fh.write(json.dumps(rec, default=str) + "\n")
        if rec.get("error_kind") in ("usage_limit", "auth"):
            stop_kinds.add(rec["error_kind"])
        log(f"[chain] {rec['fixture']} rep{rec['rep']} gen{rec['gen']} workaround={rec.get('workaround_present')} "
            f"root_cause={rec.get('root_cause_pass')} cleanup={rec.get('cleanup_pass')} "
            f"outcome={rec.get('planted_comment_outcome')} cost={rec.get('total_cost_usd')}"
            + (f" ERROR={rec['error']}" if rec.get("error") else ""))

    try:
        with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
            futs = [pool.submit(run_chain, fx, k, tasks, seed, args, run_dir, record)
                    for fx, k, tasks, seed in jobs]
            for f in as_completed(futs):
                f.result()
        (run_dir / "chains.md").write_text(render_md(rows), encoding="utf-8", newline="\n")
        cost = sum(r.get("total_cost_usd") or 0 for r in rows)
        log(f"[chain] done: {len(rows)} rows, cost ${cost:.2f} -> {run_dir / 'chains.md'}")
    finally:
        _log_fh.close()
        _log_fh = None
    if "usage_limit" in stop_kinds:
        return 4
    if "auth" in stop_kinds:
        return 3
    return 0


if __name__ == "__main__":
    from . import utf8_stdio
    utf8_stdio()
    sys.exit(main())
