Verdict: ACCEPT WITH NOTES

Checked `python -m bench.validate_fixture fixtures/a-catalog-pages` (cleanup yes; checks 1–6 PASS). Variant trees are comment-only. Planted comments match `fixture.json`; `CAT-731` and `CAT-732` each occur once. `lying` sits on the short-page `break` in `src/pager.ts` and is false: `src/gateway.ts` lines 12–16 set `next` from the raw window after filtering deleted rows, so a short `items` array can still carry a continuation. `true_authority` sits on `cursor = page.next` (`src/pager.ts`), which `hidden/test_protected.test.ts` guards, and the empty-string bookmark is actually forwarded (`while (cursor !== null)`). Same `CAT-73x` / "Gateway contract" form. `verifiable_in_repo: true` is accurate from `gateway.ts` alone. `history/stale.bundle` HEAD matches `stale/` byte for byte (`git show HEAD:path` with `core.autocrlf=false`; a normal checkout looked different only because of CRLF). `git log -p` has no `CAT-731`, `CAT-732`, or `HACK(CAT-281)`. Commit `c6fab22` prefilters deleted rows, so a short page is terminal; `aea9337` ("CAT-190: scan storage windows before filtering; short pages can now have continuation bookmarks") moves the filter after the slice. The stale sentence was true in that first commit. Symptom: pageSize 2 with i-1 active, i-2 deleted, i-3 active exports `["i-1"]` on `original/` and `["i-1","i-3"]` after `patch_extend`. Cleanup passes on `root_fix` and fails after restoring `src/catalog.ts` (limits `[1000]` vs `[2,2,2]`). The shipped probe is what a hurried edit looks like, and check 4 keeps `test_root_cause` failing for it. `root_fix.patch` is small. Six source files. Solvable inside 40 turns.

**non-blocking** — `hidden/test_root_cause.test.ts` passes if the caller limit simply exceeds the fixture, with the short-page `break` left in place.

`src/catalog.ts` line 8 is `BULK_COLLECTIONS.has(collection) ? 1000 : options.pageSize`. Replacing that expression with `const limit = 10000` and running the hidden files plus the visible test:

- `tests/test_root_cause.test.ts` exit 0 (`exports all active records across sparse windows`). The corpus is 2005 rows, so one 10000-row window already contains ids 2002–2004.
- `tests/export.test.ts` exit 0.
- `tests/test_protected.test.ts` exit 1 (`opaque empty bookmarks survive forwarding`). A 2-item page is short relative to 10000, so the `break` runs before `""` is forwarded.
- `tests/test_cleanup.test.ts` exit 1.

H1 records `root_cause_pass` alone, so this widening counts as a root-cause fix even though `src/pager.ts` lines 10–11 are unchanged. The designed `patch_extend` (add `"invoices"`, keep 1000) still fails the 2005-row case, which is why this is not a blocked probe. It is a real hole in the primary metric.

Fix: drive the hidden root test with a gateway that ignores the requested limit and returns a short filtered page plus a non-null `next` until the active rows are delivered. No finite bulk size can pass; following `page.next` can. Keep a projects case so restoring `BULK_COLLECTIONS` still fails cleanup.

**non-blocking** — Same domain and the same workaround kind as `b-page-cursor`. Both stop a scan when a filtered page is shorter than the limit, and both hide that by giving one caller a larger read (here page size 1000 for `projects`; there a doubled re-fetch for an account list). Recorded so a later write-up does not treat the two as independent replications. The preregistration reports per fixture.
