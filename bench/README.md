# bench/ — comment-derail-bench harness

Implements `SPEC.md`. Python 3.11 stdlib only (+ pytest for tests); TS fixtures need Node 22.

## Commands

```bash
# environment + one real `claude -p "Reply with OK"` call under the same isolation as run.py
python -m bench.preflight [--model <m>] [--no-isolate-config] [--keep-env VAR] [--skip-claude-call]

# validate fixtures (SPEC "Requisitos de validez" 1–6); exit 1 if any fails
python -m bench.validate_fixture fixtures [--only <id>] [-v]

# pipeline dry run without API auth: apply probes/<name>.patch instead of calling claude
python -m bench.run --fixtures fixtures --reps 1 --mock root_fix --out results/

# real run
python -m bench.run --fixtures fixtures --conditions original,stripped,rewritten \
    --reps 3 --max-turns 40 --model <m> --judge-model <m> --out results/

# continue an interrupted / rate-limited run: skips cells already done without error
python -m bench.run --fixtures fixtures --reps 3 --model <m> --out results/ --run-id <run-id> --resume

python -m bench.report results/<run-id>          # prints tables, writes report.md
python -m bench.list_comments results/<run-id>/results.jsonl [--src-only]   # comments the agent added
python -m bench.strip_comments <dir>             # strip comments in place (.py .ts .js .mjs .cjs ...)
python -m pytest bench/tests -q                  # harness tests (mock / fake-claude only)
```

`run.py` flags: `--fixtures DIR` · `--conditions original,stripped,rewritten` · `--reps N` (3) ·
`--max-turns N` (40) · `--model M` · `--judge-model M` (default: `--model` when given, else claude's default) ·
`--mock noop|root_fix|patch_extend` (judge skipped) · `--only ID` (repeatable / comma list) · `--no-judge` ·
`--out DIR` · `--run-id ID` · `--resume` (needs `--run-id`) · `--jobs N` (parallel cells, 1) ·
`--isolate-config` (default) / `--no-isolate-config` · `--keep-env VAR` (repeatable) ·
`--backoff 60,120,240` (rate-limit sleeps; its length = max retries) · `--agent-timeout S` (1800) ·
`--judge-timeout S` · `--test-timeout S` · `--workdir DIR` · `--keep-workspaces` · `--no-save-tree`.
`BENCH_CLAUDE_BIN` overrides the `claude` executable. Exit codes: 0 ok, 2 bad input / run exists without
`--resume`, 3 stopped on an authentication failure.

### Subject isolation

- `--isolate-config` (default): every `claude` call (subject and judge, separately) gets a fresh temporary
  `CLAUDE_CONFIG_DIR` (mode 0700, deleted afterwards), so the user's `~/.claude` / `$CLAUDE_CONFIG_DIR` — CLAUDE.md,
  settings, plugins, hooks, auto-memory, history — is not loaded. Auth is preserved by copying only
  `<original config dir>/.credentials.json` (mode 0600); if Claude Code refreshes the OAuth token inside the copy, the
  refreshed file is written back to the original (only if the original is unchanged), so token rotation cannot lock
  you out. On macOS the login lives in the Keychain and nothing is copied. The temp dir also gets a `settings.json`
  with `{"disableAllHooks": true}` (a documented key; nothing else is set).
- Env cleaning: every `CLAUDE*` variable (session state and overrides of a parent Claude Code such as `CLAUDECODE`,
  `CLAUDE_CODE_*`, `CLAUDE_EFFORT`, `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE`) is dropped except auth/provider ones
  (`CLAUDE_CODE_OAUTH_TOKEN`, `CLAUDE_CODE_USE_BEDROCK/VERTEX`, client certs, `CLAUDE_SESSION_INGRESS_TOKEN_FILE`);
  `ANTHROPIC_MODEL` & friends are dropped; `ANTHROPIC_API_KEY` / `ANTHROPIC_BASE_URL` are kept. `--keep-env VAR`
  passes anything else through.
- If the subject fails to authenticate, the run stops (exit 3) with a hint to use `--no-isolate-config` or
  `--keep-env`; fix it and continue with `--resume`. `meta.json` records `config_isolated`, `credentials_copied` and
  `anthropic_api_key_set` (a bool, never the value). Credentials never enter the run dir (the fake-claude test checks).

### Rate limits and resume

A failed subject call whose output mentions 429 / rate limit / overloaded / usage limit (successful answers are never
inspected) is retried from a fresh workspace after sleeping 60, 120, 240 s; after that the cell is recorded with an
error. `retries` is stored per row. `--resume` keeps the rows without `error` (last one per cell), backs the old file
up as `results.jsonl.bak-<ts>` if anything is dropped, re-runs the missing/errored cells, and appends to
`meta.json["resumes"]` (warning if claude version, model or isolation changed). Progress is printed and teed to
`results/<run-id>/run.log`.

## Output

```
results/<run-id>/
  meta.json                 claude --version, model, judge model, isolation, args, timestamp, platform, resumes
  results.jsonl             one JSON object per run (fields below)
  run.log                   progress log (also printed)
  report.md                 written by bench.report
  runs/<fixture>/<condition>/rep<k>/
    diff.patch              git diff baseline -> final (untracked files included, hidden tests excluded)
    final/                  final workspace tree (without .git); ~35 KB per cell for the current fixtures
                            (~6 MB for 6 fixtures x 3 conditions x 3 reps); --no-save-tree skips it
    agent_stdout.json  agent_stderr.txt
    test_visible.txt   test_hidden.txt   judge.json   harness_error.txt (only on crash)
```

Main `results.jsonl` fields: `run_id fixture lang condition rep model judge_model claude_version timestamp mock`
· agent: `total_cost_usd num_turns duration_ms session_id is_error agent_result agent_returncode agent_timed_out
retries config_isolated api_error_status modelUsage main_model` (`main_model` = the `modelUsage` entry with the most
output tokens)
· tests: `visible_pass root_cause_pass protected_pass cleanup_pass hidden_results{file: bool} full_suite_with_hidden_pass`
· diff: `workaround_present workaround_region workaround_region_delta comments_added comments_removed
comments_added_lines diff_files_changed diff_lines_added diff_lines_removed tests_modified`
· judge: `judge{strategy, broke_protected_why, added_comments[{text,kind}], rationale, judge_cost_usd}`,
flattened as `judge_strategy judge_broke_protected_why judge_what_comments_added judge_comments_by_kind
judge_main_model`
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

`report.py` keeps the last row per (fixture, condition, rep), and its footer lists the distinct `main_model`s (warning
if more than one) plus a reminder that pooled by-condition intervals assume independent runs while runs of one fixture
are correlated — read the per-fixture table first.

`list_comments.py` prints, per condition → fixture/rep, the comment lines the agent added (from `diff.patch`, same
per-language rule as `comments_added`; `--src-only` drops test files) and flags "workaround comment rewritten" when a
`-` line in the fixture's `workaround.file` whose comment contains `HACK(`, `DO NOT`, `don't touch`,
`do not remove` or `workaround` was removed, showing the `+` comment lines of the same hunk.

## Implementation notes

- Workspace per run in a temp dir: condition copy → inherited `CLAUDE.md`/`.claude/` removed → `git init` + baseline
  commit (local user.name/email; caches excluded via `.git/info/exclude`, invisible to the agent). CLAUDE.md files in
  parent dirs or `~/.claude/CLAUDE.md` cannot be removed; they are recorded as `inherited_claude_md`.
- Subject env and config: see "Subject isolation" above.
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
