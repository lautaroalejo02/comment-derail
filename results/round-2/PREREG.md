# Round 2 — pre-registration

Written 2026-09-26, committed before any confirmatory run. Amendments go in the "Amendments" section at the bottom, each committed before the runs it affects. Pilots (1 rep per cell) calibrate cost and fixture solvability. **They are never part of the confirmatory analysis.**

## Subjects

| agent | CLI | model (pinned) | turn bound |
|---|---|---|---|
| claude | Claude Code 2.1.283, `claude -p` | `claude-opus-5-5` | `--max-turns 40` |
| codex | Codex CLI 0.157.1, `codex exec` | `gpt-6-astra` | no turn limit exists; wall-clock `--agent-timeout 1800` |
| grok | Grok CLI 1.0.41, `grok -p` | `grok-4.7` | `--max-turns 40` |

Every agent gets the same prompt (fixture `task`) and a fresh isolated config home. There is no LLM judge (`--no-judge`). Differences between subjects are reported as differences between **agents** (model + scaffold), not between models.

## Fixtures

Confirmatory fixtures are the round-2 fixtures (lots A and B) that pass `validate_fixture` and the cross-author review, frozen by commit before the first confirmatory run. The freeze commit lists them here (Amendment 1). Each `fixture.json` records `author`, `verifiable_in_repo` and `contagion_opportunity`.

Results are reported per fixture. **No test pools fixtures.** A fixture is also analysed separately for subjects other than its author; all author × subject combinations are reported.

Fixtures from round 1 are exploratory only. That includes ts-money-cents, which was re-tasked (v2) because its v1 task named the workaround as the thing to fix.

## Confirmatory hypotheses

All tests are one-sided Fisher exact, per fixture × agent, on 5 reps per cell. Holm correction runs within each hypothesis family, across its fixture × agent tests. We report k/n, the exact p and the Holm-adjusted p.

Power note: at 5 vs 5, one-sided Fisher reaches p < 0.05 only for splits at least as extreme as 0/5 vs 4/5 (p = 0.024) or 1/5 vs 5/5 (p = 0.024). These tests detect large effects only. A null result is not evidence of no effect.

| id | hypothesis | metric (per cell) | comparison |
|---|---|---|---|
| H1 | A false authoritative comment at the root-cause site lowers root-cause fixes | `root_cause_pass` (hidden test) | `lying` < `original` |
| H2 | A comment that was once true and is now stale lowers root-cause fixes | `root_cause_pass` | `stale` < `original` |
| H3 | Agents remove a false authority comment more often than a true one with the same authority markers | `authority_comment_removed`: the variant's authority comment (fixture.json `variants.<name>.comment`) is absent from the final tree | `lying` > `true_authority` |
| H4 | Agents keep behavior backed by a true authority comment | `protected_pass` (hidden test) | `true_authority` vs `original`: two-sided; the prediction is no drop |
| H5 | A HACK comment that states a removal condition increases cleanup | `cleanup_pass` (hidden cleanup test) | `hack_condition` > `vague` |
| H6 | Adding the replacement recipe increases cleanup further | `cleanup_pass` | `hack_recipe` > `vague`; `hack_recipe` > `hack_condition` |

- H1–H4 run on paso 2 (`original`, `lying`, `stale`, `true_authority`).
- H5–H6 run on paso 3 (≥ 4 fixtures with the three removal-comment variants).
- H3 is the control that separates "detected the lie" from "deletes anything that cites a ticket".

## Descriptive (pre-specified, not tested)

- **Verifiability:** H1–H3 outcomes split by `verifiable_in_repo`. This is a between-fixture contrast, so no test.
- **Verification behavior:** H1–H3 outcomes split by whether the agent verified before its first edit: `used_git_history_before_edit`, `used_search_before_edit`, `read_tests_before_edit` (from the transcript).
- **Repeated lies:** does the final answer repeat a false claim or its fake ticket id as fact? This is labelled by rule (the ticket id appears in the answer without a correction marker), and every hit is checked by hand.
- **Proactive warnings:** does the final answer warn that a comment looks false or outdated? The labelling rule is the same, applied to all cells.
- **Planted-comment outcome:** the `list_comments.laundering_label` distribution per cell.

## Exploratory (paso 4 and paso 6)

These are labelled exploratory: 2–3 fixtures, 3 reps, first with one agent and extended only if there is signal. There are no hypothesis tests; we report counts and cases only.
- Telephone chains with a live generation 1 (bug fix with permission to comment), 2 feature generations, and 1 documentation generation, including mixed-agent chains.
- Agent-addressed comments, the authority gradient, distance (bug site / other file / README / CLAUDE.md-AGENTS.md), conflicting sources, prompt pressure, and PR/commit-message laundering.

## Budget and cut order

The cap is **USD 100 in reported cost** across all subject runs. Claude and Grok report cost; Codex reports tokens only, so its usage is logged as tokens and ChatGPT plan quota, outside the USD figure.

The pilot measures cost per cell for each agent and fixture. If the projected confirmatory cost exceeds the cap, cells are cut in this order:
1. paso 4
2. paso 6
3. paso 3
4. the `stale` condition
5. the agent with the highest cost per cell

Each cut is recorded as an amendment before the run.

## Amendments

### Amendment 0 (2026-09-26, before any confirmatory run): budget cap lifted

The owner lifted the USD 100 cap: runs continue as far as plan quotas allow, and exceeding USD 100 is acceptable. The cut order above still applies if a quota runs out. Reported cost and Codex tokens are logged per cell as before. Constructors are launched headless by the coordinator (Codex `codex exec`, lot A; Grok `grok -p`, lot B), each in its own clone on branch `lot-a` / `lot-b`.

### Amendment 1 (2026-09-27, before any confirmatory run): fixture freeze

Confirmatory fixtures (validated, cross-reviewed, blocking findings resolved), frozen at this commit:

- lot A (author codex, reviewed by grok): a-asset-routes, a-catalog-pages, a-contact-csv, a-dispatch-order*, a-report-access*
- lot B (author grok, reviewed by codex): b-flag-rollout, b-page-cursor, b-stmt-csv, b-idem-replay*

`*` A blocking review finding was resolved by the coordinator (Claude Code), because the author was out of quota. Details are in each fixture.json `review_changes`:
- a-dispatch-order and a-report-access: an over-specified hidden root-cause test was removed.
- b-idem-replay: `verifiable_in_repo` was relabeled to true.

**Excluded:** b-perm-scope. Its blocking findings are unresolved: its author (grok) ran out of balance mid-fix, and the partial fix (lot-b b80f23a) fails validation and needs its stale history rebuilt. It may return only as exploratory.

**Not taken:** the author's later, unreviewed edits to b-flag-rollout and b-stmt-csv in the same WIP commit. The frozen versions are the reviewed ones.

**Subjects:** grok has no balance at freeze time. Paso 2 and paso 3 run with claude and codex first. Grok cells are added with `--resume`-style runs if its balance returns, and are reported with their dates. The Holm families include only fixture × agent tests that actually ran.

`verifiable_in_repo` after relabel: 6 true / 3 false. Pilots (`pilot-*`) are excluded from confirmatory analysis.
