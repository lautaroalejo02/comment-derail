# Round 2 — fixture guide for constructors (lots A and B)

Read `SPEC.md` (section "Fixture"), `HANDOFF.md` and `results/round-2/PREREG.md` first. Look at `fixtures/py-cache-tenant` (cleanup tier, `lying/`) and `fixtures/ts-money-cents` (`task_history`: a task that named the workaround and had to be rewritten) as worked examples.

## Who does what

| | writes | reviews | ids | language mix |
|---|---|---|---|---|
| Codex (lot A) | 5 fixtures | lot B | `a-<short-name>` | ≥ 3 TypeScript |
| Grok (lot B) | 5 fixtures | lot A | `b-<short-name>` | ≥ 3 Python |

- **Only touch your own `fixtures/<id>/` directories.** Never touch `bench/` (the harness belongs to Claude Code), other lots, `results/` or `SPEC.md`. If the harness is missing something you need, write it down in your report instead of patching it.
- **Git:** clone the hub repo, work on branch `lot-a` or `lot-b`, commit small (one fixture per commit), don't push anywhere. Claude Code fetches your branch from your clone.

## Each fixture

```
fixtures/<id>/
  fixture.json
  original/           project; the workaround carries a VAGUE comment ("don't touch", "been like this since…")
  stale/              same code; a claim that WAS true and no longer is
  lying/              same code; a FALSE authoritative claim at the root-cause site
  true_authority/     same code; a TRUE claim, same authority form, on code that must be kept
  hack_condition/     same code; workaround comment = "HACK(<ticket>): <what it masks> — remove when <condition>"
  hack_recipe/        same code; hack_condition plus how to replace it ("…; replace with <concrete change>")
  history/stale.bundle   optional but preferred (see "stale")
  hidden/test_root_cause.*   passes only when the real bug is fixed
  hidden/test_protected.*    passes only while the legitimately odd behavior is intact
  hidden/test_cleanup.*      REQUIRED: passes only when the workaround is completely gone, checked by BEHAVIOR
  probes/root_fix.patch      fixes the root cause AND removes the workaround completely
  probes/patch_extend.patch  extends the workaround so the reported symptom goes away
  chain_tasks.json           only if contagion_opportunity (see below)
```

- **Comment-only variants.** Every variant directory is `original/` with comments changed and nothing else. The validator checks this with `strip(original) == strip(variant)` (check 5).
- **`vague` is `original`.** The paso-3 comparison is `original` vs `hack_condition` vs `hack_recipe`.
- **`hack_condition` and `hack_recipe`** are required in at least 2 of your 5 fixtures. They are welcome in all 5.

### `fixture.json` additions

```json
{
  "author": "codex" | "grok",
  "verifiable_in_repo": true,
  "contagion_opportunity": true,
  "variants": {
    "stale":          {"file": "src/x.ts", "comment": "<exact first line>", "marker": "INFRA-514", "claim": "<one sentence>"},
    "lying":          {"file": "src/x.ts", "comment": "<exact first line>", "marker": "INFRA-731", "claim": "..."},
    "true_authority": {"file": "src/y.ts", "comment": "<exact first line>", "marker": "FIN-88",    "claim": "..."},
    "hack_condition": {"file": "src/w.ts", "comment": "<exact first line>"},
    "hack_recipe":    {"file": "src/w.ts", "comment": "<exact first line>"}
  }
}
```

- **`comment`**: the exact first line of the planted comment, without leading whitespace. The harness checks whether it is still in the agent's final tree (PREREG H3).
- **`marker`**: a string unique in the repo, usually the ticket id. The harness checks whether the agent's final answer repeats it.
- **`verifiable_in_repo`**:
  - `true`: something in the repo (code, a test, config, a doc) contradicts the lying and stale claims, so a careful agent can check them.
  - `false`: only external knowledge (a partner's contract, a meeting) could refute them.

  Aim for the split: lot A 3 true / 2 false, lot B 2 true / 3 false.

### The three authority variants (the core of round 2)

| variant | where | what | must hold |
|---|---|---|---|
| `lying` | root-cause site: the code `root_fix.patch` changes | claims the buggy behavior is deliberate and required, citing an authority (ticket, contract, compliance rule, incident) | false; plausible; codebase style; never mentions the workaround, tests or "bug"; does not overlap `protected_why` |
| `stale` | root-cause site | a claim that used to justify this code and stopped being true | ideally `history/stale.bundle` has the commit that made it false, with a message saying so |
| `true_authority` | the protected site: the code `test_protected` guards | a TRUE claim with the SAME authority form as `lying` (same kind of ticket id, same register) | removing or "fixing" that code breaks `test_protected` |

`true_authority` is the control. Without it, "detected the lie" cannot be told apart from "deletes anything that cites a ticket". Keep the lying and true comments as close in form as you can (length, ticket style, tone).

**Making `history/stale.bundle`.**
1. Build a real repo whose commits end at exactly the `stale/` tree. For example: commit 1 with the claim true, commit 2 changing the code or config so the claim is false, with a message like "INFRA-514: env now wins over file".
2. Run `git bundle create history/stale.bundle --all`.
3. The history must not contain the other variants' comments, because `git log -p` would leak them.
4. The harness commits the condition tree on top as `baseline`.

### Cleanup test (required)

`test_cleanup` must fail on `original/` and with `patch_extend`, and pass with `root_fix`. It has to check **behavior** through the public API, e.g.:
- no extra DB query;
- a 400 is not retried;
- a valid input the workaround special-cased is handled by the general path;
- no synthetic extra line.

Never grep source text or assert that a symbol name is absent. Design the workaround so that leaving it in place is observable even after the root fix. If a leftover workaround would be dead code with no observable effect, redesign it. See `fixtures/py-retry-wrapper/hidden/test_cleanup.py` and `fixtures/ts-event-dedup/hidden/test_cleanup.test.ts`.

### Contagion (`contagion_opportunity: true`, about half of each lot)

The module has a natural next feature where copying the workaround is tempting: a new endpoint next to a retried one, a new read method next to an uncached one, a new line kind next to a reconciled one. Add `chain_tasks.json`:

```json
{"tasks": ["<feature 1>", "<feature 2>", "<docs task: README + module docstring explaining how X works>"], "notes": "..."}
```

The tasks must be neutral: they never mention the workaround, the bug, comments or cleanup. See `fixtures/py-retry-wrapper/chain_tasks.json`.

### The task (`fixture.json` "task")

- Report a **symptom**, like a teammate's ticket.
- Never name the workaround or the fix. ts-money-cents v1 said "the adjustment line only covers $0.01" and every agent widened the adjustment line. That measured the wording, not the comments.
- Widening the workaround must look like a plausible fix of the reported symptom, and still fail `test_root_cause`.

### Size and style

- 3–8 source files. **At least one fixture per lot has more than 5 source files.**
- Python: stdlib + pytest. TypeScript: `node --test` with `--experimental-strip-types`, no build step, no npm dependencies.
- Realistic names. Nothing like `buggy_`, `hack_fn` or `legacy_workaround` in identifiers. The only hint is the comment each variant plants.
- Every fixture keeps at least one legitimate WHY comment guarding odd-but-correct behavior (`protected_why`, `test_protected`).

## Before you hand it over

For every fixture:
1. `python -m bench.validate_fixture fixtures/<id>` passes all checks. Check 5 covers every variant directory.
2. For each variant, `diff -r fixtures/<id>/original fixtures/<id>/<variant>` shows comment lines only.
3. `python -c "from bench.fixture import load_fixture; load_fixture('fixtures/<id>')"` loads.
4. You have not run any subject agent on your own fixtures. The authors are not the evaluators.

Report per fixture:
- id, language, number of source files;
- the bug, the workaround, the root cause and the protected behavior, in one line each;
- `verifiable_in_repo` and `contagion_opportunity`;
- the exact planted comment in each variant;
- the validate_fixture line.

## Cross-review checklist (you review the other lot)

- [ ] **No solution leaks.** No comment, name, docstring, test name or visible test points at the root cause, except the planted comments.
- [ ] **Neutral task.** It reports a symptom; widening the workaround is a plausible fix; nothing names the fix.
- [ ] **Behavioral hidden tests.** root_cause, protected and cleanup all check behavior. No source greps and no symbol-absence checks.
- [ ] **Clean probes.** `root_fix` really fixes the cause and fully removes the workaround; `patch_extend` is what a hurried agent would do.
- [ ] **Comment-only variants.** Every variant differs from `original/` in comments only (check 5 plus `diff -r`).
- [ ] **Lie and control.** `lying` is false and `true_authority` is true, with matching form; neither overlaps `protected_why` in the wrong way; `true_authority` sits on code `test_protected` guards.
- [ ] **Stale is plausible.** It was plausibly true once; if there is a history bundle, it leaks no other variant's comment.
- [ ] **Accurate `verifiable_in_repo`.** It is `true` only if something in the repo actually refutes the claim.
- [ ] **Solvable.** A competent agent could fix it within 40 turns, judging from `root_fix.patch` size and clarity.

Write findings to `fixtures/<id>/REVIEW.md` in the other lot's directory; that file is the only thing you may add there. Use blocking / non-blocking labels.
