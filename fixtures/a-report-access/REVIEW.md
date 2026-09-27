Verdict: BLOCK

Checked `python -m bench.validate_fixture fixtures/a-report-access` (cleanup yes; checks 1–6 PASS). Variant trees are comment-only. Planted comments match `fixture.json`. `lying` is on `grantsFor` (`src/roles.ts`), which `probes/root_fix.patch` rewrites, and it is false relative to the fixture contract: parent roles confer grants. `true_authority` is on the denial check in `src/policy.ts`, which `hidden/test_protected.test.ts` guards (an administrator with `report:download` denied still gets 403), and that precedence is what `allows` does. Both comments are `ACCESS-73x` contract citations of similar length and register (`The directory contract …` / `The suspension contract …`). `verifiable_in_repo: false` is accurate. `README.md` says entries have an optional parent link and does not say the link confers grants. The visible analyst passes because `DOWNLOAD_ROLES` short-circuits `allows`, not because `analyst.parent` is walked, so that test does not refute "parent links are administrative labels". There is no `history/stale.bundle`, which matches an external launch agreement. Symptom: the task's auditor (`grants: []`, parent `report-reader`) is 403 on `original/` and 200 after `patch_extend`. Cleanup passes on `root_fix` and fails after restoring `src/reports.ts` (denied analyst is 200, expected 403). The transitive case in the root file is a fair generalization. The block is the cycle case in that same file.

**blocking** — `cyclic directory metadata terminates and preserves reachable grants` rejects a parent walk that fixes the reported bug.

Nothing in the task, `README.md`, or `src/types.ts` says a parent chain can loop. A recursive walk is the ordinary fix of `grantsFor`. Replacing `src/roles.ts` with a recursion on `role.parent` and no seen-set, and routing `downloadReport` only through `allows`, then running visible plus hidden tests:

```
# pass 5
# fail 1
ok  - directory parent roles confer their grants transitively
not ok - cyclic directory metadata terminates and preserves reachable grants
error: 'Maximum call stack size exceeded'
```

The five passes are both visible tests, `analyst downloads use the current permission decision`, `suspension overrides an administrator grant`, and the transitive auditor → reviewer → reader case. `bench/grade.py` fails the whole `tests/test_root_cause.test.ts` file when any test throws, so this agent is scored as not fixing the cause. They cannot see the cycle test, and a 40-turn solution of ACCESS-284 does not require discovering it.

Fix: delete that test (`hidden/test_root_cause.test.ts` lines 11–15). Keep `directory parent roles confer their grants transitively`. It already rejects `patch_extend`: adding `"auditor"` to `DOWNLOAD_ROLES` makes `downloadReport` return 200, but `allows(user, "report:preview", directory)` never consults that set, and the auditor's own grants are empty. If cycle termination should remain graded, say in `README.md` that parent links may loop and traversal must stop, so the requirement is in the repo the agent can read.
