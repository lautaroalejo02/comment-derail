# bench/ — comment-derail-bench harness

Implements `SPEC.md`. Python 3.11 stdlib only (+ pytest for tests); TS fixtures need Node 22.

## Commands

```bash
# validate fixtures (SPEC "Requisitos de validez" 1–6); exit 1 if any fails
python -m bench.validate_fixture fixtures [--only <id>] [-v]

# pipeline dry run without API auth: apply probes/<name>.patch instead of calling claude
python -m bench.run --fixtures fixtures --reps 1 --mock root_fix --out results/

# real run
python -m bench.run --fixtures fixtures --conditions original,stripped,rewritten \
    --reps 3 --max-turns 40 --model <m> --judge-model <m> --out results/

python -m bench.report results/<run-id>          # prints tables, writes report.md
python -m bench.strip_comments <dir>             # strip comments in place (.py .ts .js .mjs .cjs ...)
python -m pytest bench/tests -q                  # harness tests (mock / fake-claude only)
```

`run.py` flags: `--fixtures DIR` · `--conditions original,stripped,rewritten` · `--reps N` (3) ·
`--max-turns N` (40) · `--model M` · `--judge-model M` · `--mock noop|root_fix|patch_extend` (judge skipped) ·
`--only ID` (repeatable / comma list) · `--no-judge` · `--out DIR` · `--run-id ID` · `--jobs N` (parallel runs, 1) ·
`--agent-timeout S` (1800) · `--judge-timeout S` · `--test-timeout S` · `--workdir DIR` · `--keep-workspaces` ·
`--no-save-tree`. `BENCH_CLAUDE_BIN` overrides the `claude` executable.

## Output

```
results/<run-id>/
  meta.json                 claude --version, model, judge model, args, timestamp, platform
  results.jsonl             one JSON object per run (fields below)
  report.md                 written by bench.report
  runs/<fixture>/<condition>/rep<k>/
    diff.patch              git diff baseline -> final (untracked files included, hidden tests excluded)
    final/                  final workspace tree (without .git)
    agent_stdout.json  agent_stderr.txt
    test_visible.txt   test_hidden.txt   judge.json   harness_error.txt (only on crash)
```

Main `results.jsonl` fields: `run_id fixture lang condition rep model judge_model claude_version timestamp mock`
· agent: `total_cost_usd num_turns duration_ms session_id is_error agent_result agent_returncode agent_timed_out`
· tests: `visible_pass root_cause_pass protected_pass cleanup_pass hidden_results{file: bool} full_suite_with_hidden_pass`
· diff: `workaround_present workaround_region workaround_region_delta comments_added comments_removed
comments_added_lines diff_files_changed diff_lines_added diff_lines_removed tests_modified`
· judge: `judge{strategy, broke_protected_why, added_comments[{text,kind}], rationale, judge_cost_usd}`,
flattened as `judge_strategy judge_broke_protected_why judge_what_comments_added judge_comments_by_kind`
· `error` (harness exception, else null). `root_cause_pass` = every `test_root_cause*` file passes (each hidden
file is run on its own: `python -m pytest -q <file>` / `node --experimental-strip-types --test <file>`).

## Metrics

Hidden tests are graded per file, in up to three tiers (a tier passes only if every file in it passes):

| field | hidden files | meaning |
|---|---|---|
| `root_cause_pass` (primary) | `hidden_root_cause_glob` | the underlying defect is fixed (a path the workaround does not cover) |
| `cleanup_pass` (optional) | `hidden_cleanup_glob`, default `hidden/test_cleanup*` | the workaround was fully removed; `null` when the fixture has no cleanup files |
| `protected_pass` | `hidden_protected_glob` | the legitimate WHY behavior is still intact |

The cleanup tier exists because a pilot run fixed the root cause but left the workaround in place; with it,
"fixed the root cause" and "removed the workaround" are measured separately. When cleanup files exist,
`validate_fixture` also requires them to fail on `original/` (check 2), pass with `root_fix` (check 3) and fail with
`patch_extend` (check 4). `report.py` shows "workaround removed (cleanup)" as k/n with a Wilson interval (n excludes
runs with `cleanup_pass = null`) and the per-fixture table as `rc / cleanup`.
Secondary: judge `strategy`, `workaround_present`, `workaround_region_delta`, comments added by kind, cost, turns.

## Implementation notes

- Workspace per run in a temp dir: condition copy → inherited `CLAUDE.md`/`.claude/` removed → `git init` + baseline
  commit (local user.name/email; caches excluded via `.git/info/exclude`, invisible to the agent). CLAUDE.md files in
  parent dirs or `~/.claude/CLAUDE.md` cannot be removed; they are recorded as `inherited_claude_md`.
- Subject env: `CLAUDECODE`, `CLAUDE_CODE_*` (except auth/provider vars), `ANTHROPIC_MODEL` & friends are dropped.
- `stripped` keeps line numbers (comment-only lines become blank lines, block comments keep their newlines), so the
  fixture's `region` from `original/` stays valid; for `rewritten` the region is re-anchored on the symbol's
  definition line.
- `workaround_region_delta`: `+` lines of workaround-file hunks whose changed lines fall in the region range or that
  mention the region symbol (header, context or changed lines).
- `comments_added/removed`: `+`/`-` lines in .py files starting with `#`, in JS/TS files starting with `//`, `/*`, `*`.
- Mock mode applies the probe with `git apply` (then `patch -p1 --fuzz=2`); if the context does not match
  (stripped/rewritten), the probe is applied to pristine `original/` and the touched files are transformed into the
  condition (stripped) or copied (rewritten).

## Threats to validity

- Small n: 6 fixtures × 3 reps = 18 runs per condition. Signal, not a paper; the report gives Wilson 95% intervals,
  no p-values.
- Construction bias: we designed the fixtures knowing the hypothesis. Mitigation: probes force the workaround extension
  to be a plausible fix for the reported symptom (validity check 4).
- `stripped` also removes WHY comments: a drop in `protected_pass` under stripped is a finding, not a harness bug.
- Model and Claude Code version drift: pinned via `--model` and recorded (`claude --version`) in every row.
- The judge is an LLM (same family as the subject); `root_cause_pass` from hidden tests is the primary metric.
