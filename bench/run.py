"""Run the benchmark: fixtures x conditions x reps (SPEC "Protocolo de corrida").

    python -m bench.run --fixtures fixtures --conditions original,stripped,rewritten \
        --reps 3 --max-turns 40 [--model m] [--judge-model m] \
        [--mock noop|root_fix|patch_extend] [--only <fixture-id>] [--no-judge] --out results/
        [--run-id ID [--resume]] [--no-isolate-config] [--keep-env VAR]

Each cell (fixture, condition, rep) runs in a fresh temp workspace; the subject
and the judge run with a fresh temporary CLAUDE_CONFIG_DIR (--isolate-config,
default on). Progress goes to stdout and results/<run-id>/run.log.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import platform
import re
import shutil
import sys
import tempfile
import os
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from . import __version__
from .agent import MOCK_MODES, claude_version, credentials_available, run_agent
from .fixture import CONDITIONS, Fixture, discover
from .grade import diff_metrics, judge, run_hidden, run_visible
from .subjects import AGENTS, INSTRUCTION_FILE, behavior_flags
from .workspace import (build_condition, git_baseline, git_diff, inherited_claude_md,
                        normalize_instruction_files, remove_claude_config, save_tree)

_lock = threading.Lock()
_log_fh = None  # results/<run-id>/run.log while a run is active

AUTH_HINT = ("the subject failed to authenticate under config isolation. If you log in with "
             "~/.claude credentials that live elsewhere (e.g. macOS Keychain, an apiKeyHelper or "
             "env-provided session token), rerun with --no-isolate-config or pass the needed variable "
             "with --keep-env VAR; `python -m bench.preflight` reproduces the check.")


def log(msg: str) -> None:
    """Print to stdout and append to run.log (tee)."""
    with _lock:
        print(msg, flush=True)
        if _log_fh is not None:
            _log_fh.write(msg + "\n")
            _log_fh.flush()


def cell_key(rec_or_tuple) -> tuple[str, str, int]:
    if isinstance(rec_or_tuple, dict):
        return (rec_or_tuple.get("fixture"), rec_or_tuple.get("condition"), int(rec_or_tuple.get("rep", 0)))
    fx, cond, rep = rec_or_tuple
    return (fx.id if hasattr(fx, "id") else fx, cond, int(rep))


def run_cell(fx: Fixture, condition: str, rep: int, args, run_dir: Path, meta: dict) -> dict:
    """run_one with rate-limit retries (sleep args.backoff[i] before retry i+1)."""
    retries = 0
    while True:
        rec = run_one(fx, condition, rep, args, run_dir, meta)
        if not rec.get("rate_limited"):
            break
        if retries >= len(args.backoff):
            rec["error"] = f"rate limited; gave up after {retries} retries"
            break
        wait = args.backoff[retries]
        retries += 1
        log(f"[run] rate limited on {fx.id}/{condition}/rep{rep}; retry {retries}/{len(args.backoff)} "
            f"in {wait:g}s")
        time.sleep(wait)
    rec["retries"] = retries
    return rec


def _norm_ws(s: str) -> str:
    return " ".join(s.split())


def variant_metrics(fx: Fixture, condition: str, ws: Path, answer) -> dict:
    """For a variant condition with a planted authority comment (fixture.json
    variants.<condition>: file, comment, optional marker): is the comment still in
    the final tree (PREREG H3), and does the final answer repeat the marker (e.g. a
    fake ticket id)? Empty for conditions without that metadata."""
    v = fx.variants.get(condition) if condition in fx.variants else None
    if not v or not v.get("comment") or not v.get("file"):
        return {}
    names = [v["file"]]
    if v["file"] in ("CLAUDE.md", "AGENTS.md"):  # renamed per agent by normalize_instruction_files
        names = ["CLAUDE.md", "AGENTS.md"]
    text = "\n".join((ws / n).read_text(encoding="utf-8", errors="replace") for n in names if (ws / n).is_file())
    out = {"authority_comment_present": _norm_ws(v["comment"]) in _norm_ws(text)}
    out["authority_comment_removed"] = not out["authority_comment_present"]
    if v.get("marker"):
        out["marker_in_answer"] = isinstance(answer, str) and v["marker"] in answer
    return out


def _task(fx: Fixture, args) -> str:
    return fx.task + ("\n\n" + args.task_suffix_text if getattr(args, "task_suffix_text", None) else "")


def run_one(fx: Fixture, condition: str, rep: int, args, run_dir: Path, meta: dict) -> dict:
    rdir = run_dir / "runs" / fx.id / condition / f"rep{rep}"
    rdir.mkdir(parents=True, exist_ok=True)
    rec: dict = {
        "run_id": meta["run_id"], "fixture": fx.id, "lang": fx.lang, "condition": condition, "rep": rep,
        "model": args.model, "judge_model": None if (args.no_judge or args.mock) else args.judge_model,
        "config_isolated": None if args.mock else args.isolate_config,
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
        # A fixture's own CLAUDE.md / AGENTS.md is part of the condition: give it the
        # name this agent reads natively.
        moved = normalize_instruction_files(ws, args.agent)
        if moved:
            rec["instruction_file_renamed"] = moved
        if args.claude_md_text is not None:
            (ws / INSTRUCTION_FILE[args.agent]).write_text(args.claude_md_text, encoding="utf-8", newline="\n")
            rec["claude_md"] = True
        inherited = inherited_claude_md(ws)
        if inherited:
            rec["inherited_claude_md"] = inherited
        baseline = git_baseline(ws, history=fx.history_bundle(condition))
        rec["baseline_sha"] = baseline

        # 3. subject
        ar = run_agent(ws, _task(fx, args), max_turns=args.max_turns, model=args.model,
                       timeout=args.agent_timeout, mock=args.mock, fixture=fx, condition=condition,
                       isolate=args.isolate_config, keep_env=args.keep_env, agent=args.agent)
        (rdir / "agent_stdout.json").write_text(ar.stdout or "", encoding="utf-8", newline="\n")
        (rdir / "agent_stderr.txt").write_text(ar.stderr or "", encoding="utf-8", newline="\n")
        (rdir / "tool_events.json").write_text(json.dumps(ar.events, indent=1), encoding="utf-8", newline="\n")
        rec.update({"agent": args.agent, "turn_limit": ar.turn_limit, **behavior_flags(ar.events)})
        rec.update({
            "agent_result": (ar.result or "")[:4000] if isinstance(ar.result, str) else ar.result,
            "total_cost_usd": ar.total_cost_usd, "num_turns": ar.num_turns,
            "duration_ms": ar.duration_ms, "session_id": ar.session_id,
            "is_error": ar.is_error, "agent_returncode": ar.returncode,
            "agent_timed_out": ar.timed_out, "agent_wall_s": ar.wall_s,
            "agent_parse_error": ar.parse_error, "mock_apply": ar.mock_apply,
            "api_error_status": ar.api_error_status,
            "main_model": ar.main_model, "modelUsage": ar.model_usage,
        })
        if ar.usage_limited:
            rec["error_kind"] = "usage_limit"
            rec["error"] = "usage limit reached"
            return rec
        if ar.rate_limited:
            rec["rate_limited"] = True
            rec["error"] = "rate limited"
            return rec
        if ar.auth_failed:
            rec["error_kind"] = "auth"
            rec["error"] = "authentication failed" + (" (config isolated)" if args.isolate_config else "")
            return rec

        # 4. diff (before hidden tests are copied) + final tree
        diff = git_diff(ws, baseline)
        (rdir / "diff.patch").write_text(diff, encoding="utf-8", newline="\n")
        if not args.no_save_tree:
            save_tree(ws, rdir / "final")

        # 7. deterministic metrics (on the agent's final state)
        rec.update(diff_metrics(diff, fx, ws, baseline))
        rec.update(variant_metrics(fx, condition, ws, rec.get("agent_result")))

        # 5. visible tests
        vis = run_visible(fx, ws, timeout=args.test_timeout)
        (rdir / "test_visible.txt").write_text(f"$ {vis.cmd}\n(rc={vis.returncode})\n{vis.output}",
                                               encoding="utf-8", newline="\n")
        rec["visible_pass"] = vis.ok

        # 6. hidden tests, per file
        hr = run_hidden(fx, ws, timeout=args.test_timeout)
        rec["root_cause_pass"] = hr.passed("root_cause")
        rec["protected_pass"] = hr.passed("protected")
        rec["cleanup_pass"] = hr.passed("cleanup")  # None when the fixture has no cleanup tier
        rec["hidden_results"] = hr.per_file
        rec["full_suite_with_hidden_pass"] = hr.full.ok if hr.full else None
        with open(rdir / "test_hidden.txt", "w", encoding="utf-8", newline="\n") as fh:
            for rel, out in hr.outputs.items():
                fh.write(f"===== {rel} [{hr.kinds[rel]}] pass={hr.per_file[rel]}\n{out}\n")
            if hr.full:
                fh.write(f"===== full suite\n$ {hr.full.cmd}\n(rc={hr.full.returncode})\n{hr.full.output}\n")

        # 8. judge
        if args.no_judge or args.mock:
            rec["judge"] = None
        else:
            v = judge(diff, fx.task, model=args.judge_model, fx=fx, timeout=args.judge_timeout,
                      isolate=args.isolate_config, keep_env=args.keep_env)
            rec["judge"] = v
            (rdir / "judge.json").write_text(json.dumps(v, indent=2), encoding="utf-8", newline="\n")
            if v.get("error_kind") in ("usage_limit", "auth"):
                # Mark the whole cell failed so the run stops and --resume re-runs it.
                rec["error_kind"] = v["error_kind"]
                rec["error"] = f"judge: {v.get('error')}"
        _flatten_judge(rec)
    except Exception as exc:  # keep going; record the failure
        rec["error"] = f"{exc.__class__.__name__}: {exc}"
        (rdir / "harness_error.txt").write_text(traceback.format_exc(), encoding="utf-8", newline="\n")
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
        rec["judge_main_model"] = j.get("judge_main_model") if j else None
        rec["judge_strategy"] = None
        rec["judge_broke_protected_why"] = None
        rec["judge_what_comments_added"] = None
        rec["judge_comments_by_kind"] = None
        return
    kinds: dict[str, int] = {}
    for c in j.get("added_comments", []):
        kinds[c.get("kind", "unknown")] = kinds.get(c.get("kind", "unknown"), 0) + 1
    rec["judge_main_model"] = j.get("judge_main_model")
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
    ap.add_argument("--agent", choices=AGENTS, default="claude",
                    help="subject agent CLI (default claude); one agent per run id")
    ap.add_argument("--model", default=None, help="subject model (the agent CLI's --model / -m)")
    ap.add_argument("--task-suffix", default=None,
                    help="file whose text is appended to every fixture task (prompt-pressure / PR-text variants)")
    ap.add_argument("--judge-model", default=None,
                    help="judge model (default: --model if given, else claude's default)")
    ap.add_argument("--mock", choices=MOCK_MODES, default=None,
                    help="apply probes/<name>.patch instead of calling claude (judge skipped)")
    ap.add_argument("--only", action="append", default=None,
                    help="fixture id to run (repeatable or comma-separated)")
    ap.add_argument("--no-judge", action="store_true")
    ap.add_argument("--out", default="results")
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--resume", action="store_true",
                    help="with --run-id of an existing run: skip cells already done without error")
    ap.add_argument("--jobs", type=int, default=1, help="parallel runs (default 1)")
    ap.add_argument("--agent-timeout", type=float, default=1800)
    ap.add_argument("--judge-timeout", type=float, default=600)
    ap.add_argument("--test-timeout", type=float, default=600)
    ap.add_argument("--backoff", default="60,120,240",
                    help="seconds to sleep before each rate-limit retry (comma list; its length = max retries)")
    ap.add_argument("--isolate-config", dest="isolate_config", action="store_true", default=True,
                    help="fresh temp CLAUDE_CONFIG_DIR per claude call (default)")
    ap.add_argument("--no-isolate-config", dest="isolate_config", action="store_false",
                    help="use the user's normal Claude Code config dir")
    ap.add_argument("--keep-env", action="append", default=[],
                    help="env var to pass through to claude although it would be cleaned (repeatable)")
    ap.add_argument("--claude-md", default=None,
                    help="file whose content is written to CLAUDE.md at the workspace root before the "
                         "baseline commit (project instructions for the subject)")
    ap.add_argument("--workdir", default=None, help="parent dir for temp workspaces (default: system tmp)")
    ap.add_argument("--keep-workspaces", action="store_true")
    ap.add_argument("--no-save-tree", action="store_true", help="do not copy the final tree into the run dir")
    args = ap.parse_args(argv)
    if args.only:
        args.only = [x for o in args.only for x in o.split(",") if x]
    args.conditions = [c.strip() for c in args.conditions.split(",") if c.strip()]
    bad = [c for c in args.conditions if c not in CONDITIONS and not re.fullmatch(r"[a-z][a-z0-9_-]*", c)]
    if bad:
        ap.error(f"bad condition name(s) {bad}; use {CONDITIONS} or a fixture variant name")
    args.task_suffix_text = None
    if args.task_suffix:
        try:
            args.task_suffix_text = Path(args.task_suffix).read_text(encoding="utf-8").strip()
        except OSError as exc:
            ap.error(f"--task-suffix: {exc}")
    if args.claude_md:
        try:
            args.claude_md_text = Path(args.claude_md).read_text(encoding="utf-8")
        except OSError as exc:
            ap.error(f"--claude-md: {exc}")
    else:
        args.claude_md_text = None
    try:
        args.backoff = [float(x) for x in args.backoff.split(",") if x.strip()]
    except ValueError:
        ap.error("--backoff must be a comma list of seconds")
    if args.resume and not args.run_id:
        ap.error("--resume needs --run-id of the run to continue")
    if args.judge_model is None and args.model:
        args.judge_model = args.model
    args.keep_env = [x for k in args.keep_env for x in k.split(",") if x]
    return args


def _load_rows(path: Path) -> list[dict]:
    rows = []
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return rows


def _prepare_resume(results_path: Path) -> set[tuple[str, str, int]]:
    """Keep only successful rows (last one per cell); back up the old file if
    anything is dropped. Returns the set of completed cells."""
    rows = _load_rows(results_path)
    good: dict[tuple, dict] = {}
    for r in rows:
        if not r.get("error"):
            good[cell_key(r)] = r
    if len(good) != len(rows):
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
        shutil.copy2(results_path, results_path.with_name(f"results.jsonl.bak-{stamp}"))
        with open(results_path, "w", encoding="utf-8", newline="\n") as fh:
            for r in good.values():
                fh.write(json.dumps(r, default=str) + "\n")
    return set(good)


def main(argv=None) -> int:
    global _log_fh
    args = parse_args(argv)
    fixtures, errors = discover(args.fixtures, args.only)
    if not fixtures:
        for e in errors:
            print(f"[run] warning: skipping fixture: {e}", file=sys.stderr)
        print("[run] no fixtures to run", file=sys.stderr)
        return 2

    now = dt.datetime.now(dt.timezone.utc)
    run_id = args.run_id or now.strftime("%Y%m%d-%H%M%S") + (f"-mock-{args.mock}" if args.mock else "")
    run_dir = Path(args.out) / run_id
    results_path = run_dir / "results.jsonl"
    meta_path = run_dir / "meta.json"
    if args.resume and not results_path.is_file():
        print(f"[run] --resume: {results_path} does not exist; starting a new run", file=sys.stderr)
    elif not args.resume and results_path.is_file() and results_path.stat().st_size:
        print(f"[run] {results_path} already exists; use --resume or another --run-id", file=sys.stderr)
        return 2
    run_dir.mkdir(parents=True, exist_ok=True)
    _log_fh = open(run_dir / "run.log", "a", encoding="utf-8", newline="\n")
    try:
        return _main(args, fixtures, errors, now, run_id, run_dir, results_path, meta_path, argv)
    finally:
        _log_fh.close()
        _log_fh = None


def _main(args, fixtures, errors, now, run_id, run_dir, results_path, meta_path, argv) -> int:
    for e in errors:
        log(f"[run] warning: skipping fixture: {e}")
    version = "mock" if args.mock else claude_version()
    meta = {
        "run_id": run_id,
        "timestamp": now.isoformat(timespec="seconds"),
        "claude_version": version,
        "model": args.model, "judge_model": None if (args.no_judge or args.mock) else args.judge_model,
        "agent": args.agent, "task_suffix": args.task_suffix_text,
        "mock": args.mock, "reps": args.reps, "max_turns": args.max_turns,
        "conditions": args.conditions, "fixtures": [f.id for f in fixtures],
        "config_isolated": bool(args.isolate_config and not args.mock),
        "credentials_copied": bool(args.isolate_config and not args.mock and credentials_available()),
        "anthropic_api_key_set": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "keep_env": args.keep_env, "backoff_s": args.backoff, "claude_md": args.claude_md_text,
        "python": sys.version.split()[0], "platform": platform.platform(),
        "harness_version": __version__, "argv": sys.argv[1:] if argv is None else list(argv),
    }
    if args.mock:
        meta["claude_version_installed"] = claude_version()

    done: set = set()
    if args.resume and results_path.is_file():
        old = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else {}
        for k in ("claude_version", "model", "judge_model", "max_turns", "config_isolated"):
            if old and old.get(k) != meta.get(k):
                log(f"[run] WARNING resume: {k} changed ({old.get(k)!r} -> {meta.get(k)!r})")
        done = _prepare_resume(results_path)
        resumes = old.get("resumes", [])
        resumes.append({k: meta[k] for k in ("timestamp", "claude_version", "model", "judge_model",
                                             "config_isolated", "credentials_copied", "argv")})
        meta = {**old, "resumes": resumes} if old else {**meta, "resumes": resumes}
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8", newline="\n")
    log(f"[run] {run_id}: claude={version} model={args.model} judge={meta.get('judge_model')} "
        f"isolated_config={_isolation_label(meta, args)} -> {run_dir}")

    missing = [c for c in args.conditions if not any(fx.has_condition(c) for fx in fixtures)]
    if missing:
        log(f"[run] no fixture has condition(s) {missing}")
        return 2
    jobs = []
    for fx in fixtures:
        for cond in args.conditions:
            if not fx.has_condition(cond):
                log(f"[run] warning: {fx.id} has no {cond}/; skipping condition {cond}")
                continue
            for k in range(1, args.reps + 1):
                if (fx.id, cond, k) in done:
                    continue
                jobs.append((fx, cond, k))
    if done:
        log(f"[run] resume: {len(done)} cell(s) already done, {len(jobs)} to run")

    n_done = 0
    stop = threading.Event()
    stop_kind: dict = {}
    main_models: set = set()

    def record(rec: dict) -> None:
        nonlocal n_done
        with _lock:
            with open(results_path, "a", encoding="utf-8", newline="\n") as fh:
                fh.write(json.dumps(rec, default=str) + "\n")
            n_done += 1
        if rec.get("main_model"):
            main_models.add(rec["main_model"])
        log(f"[{n_done}/{len(jobs)}] {rec['fixture']:<28} {rec['condition']:<10} rep{rec['rep']} "
            f"visible={rec.get('visible_pass')} root_cause={rec.get('root_cause_pass')} "
            f"protected={rec.get('protected_pass')} cleanup={rec.get('cleanup_pass')} "
            f"judge={rec.get('judge_strategy')} model={rec.get('main_model')} "
            f"cost={rec.get('total_cost_usd')} retries={rec.get('retries')}"
            + (f" ERROR={rec['error']}" if rec.get("error") else ""))
        if rec.get("error_kind") in ("auth", "usage_limit"):
            stop_kind.setdefault("kind", rec["error_kind"])
            stop.set()

    def guarded(fx, cond, k):
        if stop.is_set():
            return None
        return run_cell(fx, cond, k, args, run_dir, meta)

    if args.jobs <= 1:
        for fx, cond, k in jobs:
            rec = guarded(fx, cond, k)
            if rec is None:
                break
            record(rec)
    else:
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            futs = [pool.submit(guarded, fx, cond, k) for fx, cond, k in jobs]
            for f in as_completed(futs):
                rec = f.result()
                if rec is not None:
                    record(rec)
    if stop.is_set() and stop_kind.get("kind") == "usage_limit":
        log("[run] STOPPED: usage limit reached (plan window or API credit); the limited cell "
            "and the cells not started are not counted as done.")
        log(f"[run] continue after the reset with --run-id {run_id} --resume")
        return 4
    if stop.is_set():
        log(f"[run] FATAL: {AUTH_HINT}" if args.isolate_config else
            "[run] FATAL: the subject failed to authenticate; check `claude` login / ANTHROPIC_API_KEY.")
        log(f"[run] stopped early; rerun with --run-id {run_id} --resume after fixing auth")
        return 3
    if main_models:
        log(f"[run] main model(s) seen: {', '.join(sorted(main_models))}")
        if len(main_models) > 1:
            log("[run] WARNING: more than one main model across cells")
    log(str(results_path))
    return 0


def _isolation_label(meta: dict, args) -> str:
    if not meta.get("config_isolated"):
        return "no"
    return "yes (credentials copied)" if meta.get("credentials_copied") else "yes (no credentials file to copy)"


if __name__ == "__main__":
    from . import utf8_stdio
    utf8_stdio()
    sys.exit(main())
