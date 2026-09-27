Verdict: BLOCK

Checked `python -m bench.validate_fixture fixtures/a-dispatch-order` (cleanup yes; checks 1–6 PASS). Variant trees are comment-only. Planted comments match `fixture.json`. `lying` is on the lexical key in `src/queue.py` and is false: `README.md` says smaller service ranks dispatch first, and `src/policy.py` defines `SERVICE_RANK` as urgent 0, normal 1, low 2. `true_authority` is on the `(priority, sequence)` return in the same function, which `hidden/test_protected.py` guards (arrival order beats `created_at`), and that tie-break is what the code does. The two comments are the same shape: `OPS-73x`, "Warehouse dispatch policy requires …", "… are reporting metadata only." `verifiable_in_repo: true` is accurate. `history/stale.bundle` HEAD matches `stale/`. `git log -p` has no `OPS-731`, `OPS-732`, or `HACK(OPS-281)`. Commit `b43ca37` uses tokens `0-urgent` / `1-normal` / `2-low`, so the lexical key matches service order; `e0b2186` ("OPS-190: publish bare priority labels; SERVICE_RANK now defines dispatch order") renames them to bare labels and leaves the string key. The stale claim was true once. Symptom: north normal `n-1` then harbor urgent `h-1` is `['n-1', 'h-1']` on `original/` and `['h-1', 'n-1']` after `patch_extend`. Cleanup passes on `root_fix` and fails after restoring `src/dispatch.py` (`['b', 'n']` vs `['n', 'b']`). Check 4 still fails `test_root_cause` on `patch_extend`. The block is the hidden root file.

**blocking** — `test_queue_consumers_observe_service_order` fails a repair that fixes batch ordering with `SERVICE_RANK` and drops the account promotion.

`README.md` defines order on `take_batch`. `ShipmentQueue.pop` has no other caller. Replacing the sort in `src/dispatch.py` `take_batch` with `batch.sort(key=lambda shipment: SERVICE_RANK[shipment.priority])` and leaving `src/queue.py` lexical, then running visible plus hidden tests:

```
1 failed, 6 passed
FAILED tests/test_root_cause.py::test_queue_consumers_observe_service_order
assert ['low', 'normal', 'urgent'] == ['urgent', 'normal', 'low']
```

The six passes include `test_service_order_for_unlisted_accounts`, `test_arrival_order_wins_over_producer_clock_for_ties`, `test_account_does_not_promote_low_priority_shipments`, and all three visible tests. `bench/grade.py` sets `root_cause_pass` from the whole file (`run_cmd` on `tests/test_root_cause.py`). This repair is scored as not fixing the cause. It is a direct reading of the README and of `take_batch`, which is the function the task calls "batch ordering".

Fix: delete `test_queue_consumers_observe_service_order` (`hidden/test_root_cause.py` lines 13–17). Keep `test_service_order_for_unlisted_accounts`. That test still rejects `patch_extend`: with harbor added to `RUSH_ACCOUNTS`, the same three shipments come out `['u', 'l', 'n']`, not `['u', 'n', 'l']`, because the stable account sort promotes harbor and leaves west low ahead of north normal.
