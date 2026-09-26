"""Run the benchmark: fixtures x conditions x reps (SPEC "Protocolo de corrida").

    python -m bench.run --fixtures fixtures --conditions original,stripped,rewritten \
        --reps 3 --max-turns 40 [--model m] [--judge-model m] \
        [--mock noop|root_fix|patch_extend] [--only <fixture-id>] [--no-judge] --out results/
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import platform
import shutil
import sys
import tempfile
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from . import __version__
from .agent import MOCK_MODES, claude_version, run_agent
from .fixture import CONDITIONS, Fixture, discover
from .grade import diff_metrics, judge, run_hidden, run_visible
from .workspace import (build_condition, git_baseline, git_diff, inherited_claude_md,
                        remove_claude_config, save_tree)

_lock = threading.Lock()


def log(msg: str) -> None:
    with _lock:
        print(msg, file=sys.stderr, flush=True)


def run_one(fx: Fixture, condition: str, rep: int, args, run_dir: Path, meta: dict) -> dict:
    rdir = run_dir / "runs" / fx.id / condition / f"rep{rep}"
    rdir.mkdir(parents=True, exist_ok=True)
    rec: dict = {
        "run_id": meta["run_id"], "fixture": fx.id, "lang": fx.lang, "condition": condition, "rep": rep,
        "model": args.model, "judge_model": None if (args.no_judge or args.mock) else args.judge_model,
        "claude_version": meta["claude_version"], "harness_version": __version__,
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "mock": args.mock, "max_turns": args.max_turns, "run_dir": str(rdir.relative_to(run_dir)),
        "error": None,
    }
    tmp_root = Path(tempfile.mkdtemp(prefix=f"cdb-{fx.id}-{condition}-{rep}-", dir=args.workdir))
    ws = tmp_root / "ws"
    ws.mkdir()
    try:
        build_condition(fx, condition, ws)
        removed = remove_claude_config(ws)
        if removed:
            rec["removed_claude_config"] = removed
        inherited = inherited_claude_md(ws)
        if inherited:
            rec["inherited_claude_md"] = inherited
        baseline = git_baseline(ws)
        rec["baseline_sha"] = baseline

        # 3. subject
        ar = run_agent(ws, fx.task, max_turns=args.max_turns, model=args.model,
                       timeout=args.agent_timeout, mock=args.mock, fixture=fx, condition=condition)
        (rdir / "agent_stdout.json").write_text(ar.stdout or "", encoding="utf-8")
        (rdir / "agent_stderr.txt").write_text(ar.stderr or "", encoding="utf-8")
        rec.update({
            "agent_result": (ar.result or "")[:4000] if isinstance(ar.result, str) else ar.result,
            "total_cost_usd": ar.total_cost_usd, "num_turns": ar.num_turns,
            "duration_ms": ar.duration_ms, "session_id": ar.session_id,
            "is_error": ar.is_error, "agent_returncode": ar.returncode,
            "agent_timed_out": ar.timed_out, "agent_wall_s": ar.wall_s,
            "agent_parse_error": ar.parse_error, "mock_apply": ar.mock_apply,
        })

        # 4. diff (before hidden tests are copied) + final tree
        diff = git_diff(ws, baseline)
        (rdir / "diff.patch").write_text(diff, encoding="utf-8")
        if not args.no_save_tree:
            save_tree(ws, rdir / "final")

        # 7. deterministic metrics (on the agent's final state)
        rec.update(diff_metrics(diff, fx, ws, baseline))

        # 5. visible tests
        vis = run_visible(fx, ws, timeout=args.test_timeout)
        (rdir / "test_visible.txt").write_text(f"$ {vis.cmd}\n(rc={vis.returncode})\n{vis.output}",
                                               encoding="utf-8")
        rec["visible_pass"] = vis.ok

        # 6. hidden tests, per file
        hr = run_hidden(fx, ws, timeout=args.test_timeout)
        rec["root_cause_pass"] = hr.passed("root_cause")
        rec["protected_pass"] = hr.passed("protected")
        rec["cleanup_pass"] = hr.passed("cleanup")  # None when the fixture has no cleanup tier
        rec["hidden_results"] = hr.per_file
        rec["full_suite_with_hidden_pass"] = hr.full.ok if hr.full else None
        with open(rdir / "test_hidden.txt", "w", encoding="utf-8") as fh:
            for rel, out in hr.outputs.items():
                fh.write(f"===== {rel} [{hr.kinds[rel]}] pass={hr.per_file[rel]}\n{out}\n")
            if hr.full:
                fh.write(f"===== full suite\n$ {hr.full.cmd}\n(rc={hr.full.returncode})\n{hr.full.output}\n")

        # 8. judge
        if args.no_judge or args.mock:
            rec["judge"] = None
        else:
            v = judge(diff, fx.task, model=args.judge_model, fx=fx, timeout=args.judge_timeout)
            rec["judge"] = v
            (rdir / "judge.json").write_text(json.dumps(v, indent=2), encoding="utf-8")
        _flatten_judge(rec)
    except Exception as exc:  # keep going; record the failure
        rec["error"] = f"{exc.__class__.__name__}: {exc}"
        (rdir / "harness_error.txt").write_text(traceback.format_exc(), encoding="utf-8")
        log(f"[run] ERROR {fx.id}/{condition}/rep{rep}: {rec['error']}")
    finally:
        if args.keep_workspaces:
            rec["workspace"] = str(ws)
        else:
            shutil.rmtree(tmp_root, ignore_errors=True)
    return rec


def _flatten_judge(rec: dict) -> None:
    j = rec.get("judge")
    if not j or j.get("error"):
        rec["judge_strategy"] = None
        rec["judge_broke_protected_why"] = None
        rec["judge_what_comments_added"] = None
        rec["judge_comments_by_kind"] = None
        return
    kinds: dict[str, int] = {}
    for c in j.get("added_comments", []):
        kinds[c.get("kind", "unknown")] = kinds.get(c.get("kind", "unknown"), 0) + 1
    rec["judge_strategy"] = j.get("strategy")
    rec["judge_broke_protected_why"] = j.get("broke_protected_why")
    rec["judge_what_comments_added"] = kinds.get("what", 0)
    rec["judge_comments_by_kind"] = kinds


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fixtures", default="fixtures", help="fixtures directory (or one fixture dir)")
    ap.add_argument("--conditions", default=",".join(CONDITIONS))
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--max-turns", type=int, default=40)
    ap.add_argument("--model", default=None, help="subject model (claude --model)")
    ap.add_argument("--judge-model", default=None, help="judge model (default: claude's default)")
    ap.add_argument("--mock", choices=MOCK_MODES, default=None,
                    help="apply probes/<name>.patch instead of calling claude (judge skipped)")
    ap.add_argument("--only", action="append", default=None,
                    help="fixture id to run (repeatable or comma-separated)")
    ap.add_argument("--no-judge", action="store_true")
    ap.add_argument("--out", default="results")
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--jobs", type=int, default=1, help="parallel runs (default 1)")
    ap.add_argument("--agent-timeout", type=float, default=1800)
    ap.add_argument("--judge-timeout", type=float, default=600)
    ap.add_argument("--test-timeout", type=float, default=600)
    ap.add_argument("--workdir", default=None, help="parent dir for temp workspaces (default: system tmp)")
    ap.add_argument("--keep-workspaces", action="store_true")
    ap.add_argument("--no-save-tree", action="store_true", help="do not copy the final tree into the run dir")
    args = ap.parse_args(argv)
    if args.only:
        args.only = [x for o in args.only for x in o.split(",") if x]
    args.conditions = [c.strip() for c in args.conditions.split(",") if c.strip()]
    bad = [c for c in args.conditions if c not in CONDITIONS]
    if bad:
        ap.error(f"unknown condition(s) {bad}; choose from {CONDITIONS}")
    return args


def main(argv=None) -> int:
    args = parse_args(argv)
    fixtures, errors = discover(args.fixtures, args.only)
    for e in errors:
        log(f"[run] warning: skipping fixture: {e}")
    if not fixtures:
        log("[run] no fixtures to run")
        return 2

    now = dt.datetime.now(dt.timezone.utc)
    run_id = args.run_id or now.strftime("%Y%m%d-%H%M%S") + (f"-mock-{args.mock}" if args.mock else "")
    run_dir = Path(args.out) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "run_id": run_id,
        "timestamp": now.isoformat(timespec="seconds"),
        "claude_version": "mock" if args.mock else claude_version(),
        "model": args.model, "judge_model": args.judge_model,
        "mock": args.mock, "reps": args.reps, "max_turns": args.max_turns,
        "conditions": args.conditions, "fixtures": [f.id for f in fixtures],
        "python": sys.version.split()[0], "platform": platform.platform(),
        "harness_version": __version__, "argv": sys.argv[1:] if argv is None else list(argv),
    }
    if args.mock:
        meta["claude_version_installed"] = claude_version()
    (run_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    log(f"[run] {run_id}: claude={meta['claude_version']} model={args.model} -> {run_dir}")

    jobs = []
    for fx in fixtures:
        for cond in args.conditions:
            if cond == "rewritten" and not fx.has_rewritten:
                log(f"[run] warning: {fx.id} has no rewritten/; skipping condition rewritten")
                continue
            for k in range(1, args.reps + 1):
                jobs.append((fx, cond, k))

    results_path = run_dir / "results.jsonl"
    n_done = 0

    def record(rec: dict) -> None:
        nonlocal n_done
        with _lock:
            with open(results_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, default=str) + "\n")
            n_done += 1
            print(f"[{n_done}/{len(jobs)}] {rec['fixture']:<28} {rec['condition']:<10} rep{rec['rep']} "
                  f"visible={rec.get('visible_pass')} root_cause={rec.get('root_cause_pass')} "
                  f"protected={rec.get('protected_pass')} cleanup={rec.get('cleanup_pass')} judge={rec.get('judge_strategy')} "
                  f"cost={rec.get('total_cost_usd')}" + (f" ERROR={rec['error']}" if rec.get("error") else ""),
                  file=sys.stderr, flush=True)

    if args.jobs <= 1:
        for fx, cond, k in jobs:
            record(run_one(fx, cond, k, args, run_dir, meta))
    else:
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futs = [pool.submit(run_one, fx, cond, k, args, run_dir, meta) for fx, cond, k in jobs]
            for f in as_completed(futs):
                record(f.result())
    print(str(results_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
