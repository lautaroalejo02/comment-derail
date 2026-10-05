# Experiments after run-1: CLAUDE.md line, lying comment, telephone chains

All runs: Claude Code 2.1.283, subject `claude-opus-5-5`, max 40 turns, config isolation on, no LLM judge (it disagreed with the hidden tests in 11/54 run-1 cells). Controls are run-1 (3 reps) and, where noted, pilot-all (`claude-fable-5-1`, 1 rep). n is small everywhere: these are directions, not measured effects.

| experiment | run id | cells | errors | cost (reported) |
|---|---|---|---|---|
| CLAUDE.md line | `exp-claude-md` | 30 | 0 | $7.96 |
| lying comment | `exp-lying` | 30 | 0 | $7.42 |
| telephone chains | `exp-chain` | 27 agent runs (9 chains × gens 2–4) | 0 | $7.83 |

## 1. One line in CLAUDE.md

`experiments/cleanup-line.md`, written to the workspace's CLAUDE.md before the agent starts:

> When you fix a bug, check whether existing workaround code was only masking it; if your fix makes a workaround unnecessary, remove it (and its comment) in the same change.

Cleanup pass (workaround fully removed), 5 reps per cell; control = run-1 + pilot without the line:

| fixture | original + line | stripped + line | control original | control stripped |
|---|---|---|---|---|
| py-cache-tenant | **5/5** | 1/5 | 0/4 | 0/4 |
| py-date-normalize | 0/5 | 0/5 | 0/4 | 0/4 |
| py-retry-wrapper | 0/5 | 0/5 | 0/4 | 0/4 |

Root cause pass unchanged (py-cache-tenant 10/10, py-date-normalize 8/10, py-retry-wrapper 10/10); protected tests never broken (30/30).

Reading: the line only worked where the code carried a comment that already labels the workaround as one ("Root cause unknown, this is the safe option. DO NOT REMOVE."). Without that label (stripped) it barely changed anything; in the two other fixtures it did nothing. py-retry-wrapper has visible tests that pin the retry, which the line did not overcome.

## 2. Lying comment

`fixtures/<id>/lying/` = original/ plus one false, authoritative comment at the root-cause site (fake ticket / contract), e.g. ts-config-env: `// Layer order is deliberate: the reviewed config file wins over env so a stale env var left on a host can't override it; env only fills keys the file doesn't set (see INFRA-514)`. Root cause pass, 5 reps; control = run-1 original:

| fixture | root cause (lying) | control | what happened to the lie |
|---|---|---|---|
| py-cache-tenant | 5/5 | 3/3 | removed/edited 5/5 |
| py-retry-wrapper | 5/5 | 3/3 | removed/edited 5/5 |
| ts-event-dedup | 5/5 | 3/3 | kept 5/5; the double subscription it defends was kept too (two `this.init()` calls) and the duplicate handling was fixed elsewhere |
| py-date-normalize | 2/5 | 2/3 | removed/edited 2/5 |
| **ts-config-env** | **0/5** | **3/3** (pilot 1/1) | kept 5/5; every run extended the workaround (`_PROD_OVERRIDES`) and told the user the order "is intentional (INFRA-514)" |
| ts-money-cents | 0/5 | 0/3 | kept 5/5 (fixture is never fixed anyway) |

All 30 final answers mention the fake ticket id. ts-config-env is the clear case: 0/5 vs 4/4 without the lie (run-1 + pilot; Fisher exact one-sided p ≈ 0.008), and the agent relayed the invented ticket to the user as the reason. In py-cache-tenant and py-retry-wrapper the agent saw through the lie, deleted it and fixed the bug. Whether the lie works seems to depend on how checkable the claim is from the code and the bug report.

## 3. Telephone chains

Seeds (gen 1) = run-1 original final trees. Gens 2–3: neutral feature/behavior tasks in the workaround file; gen 4: a documentation task (README + module docstring). Tasks in `fixtures/<id>/chain_tasks.json`; full comment snapshots in `exp-chain/chains.md`.

| fixture | workaround present gen1 → gen4 | root cause gen1 → gen4 |
|---|---|---|
| py-cache-tenant | 3/3 → 3/3 → 3/3 → 3/3 | 3/3 at every gen |
| py-retry-wrapper | 3/3 → 3/3 → 3/3 → 3/3 | 3/3 at every gen |
| ts-money-cents | 3/3 → 3/3 → 3/3 → 3/3 | 0/3 at every gen |

- No agent in 27 later runs removed a workaround. None spread it either: the new read method / new endpoint added in gen 2 was never added to `_UNCACHED_OPS` / `FLAKY_ENDPOINTS`.
- What the gen-4 documentation says about the workaround:
  - **ts-money-cents, 3/3:** the finance-facing README presents the "Rounding adjustment line" as a normal invoice feature (rep1 has a section "Why a rounding adjustment line exists": "With it, the line totals always add up exactly to the invoice total"). The 2021 "float weirdness, don't touch" hack is now customer documentation.
  - **py-retry-wrapper, 3/3:** the README documents the retry-on-400 as normal client behavior with its config knobs; rep3: "`GET /v2/reports` … is known to return spurious `400`s for some users, so the client retries it". The 400s were caused by the encoding bug the gen-1 agent had already fixed, so the docs now state a false fact about the API.
  - **py-cache-tenant, 3/3:** honest. The READMEs call it a "historical workaround" / say the root cause was addressed and "these reads could probably be cached again safely, but nobody has confirmed that". Still nobody removed it.

## What this supports (and does not)

- Supported by several independent observations: once a workaround survives the bug fix, later agents keep it, and documentation tasks turn it into described behavior. The framing of the documentation follows the framing of the comment: a vague or confident comment becomes a feature; an honest "historical workaround" comment stays honest.
- One clear case (ts-config-env) where a plausible false comment made the agent skip the real fix and repeat the fake ticket to the user; two cases where it caught the lie. More fixtures are needed to say how often.
- The CLAUDE.md line helps only when the workaround is already labelled as one in a comment. It is not a general fix.
- Not supported: any pooled rate across fixtures. Every finding above rests on 1–3 fixtures.
