# Round 3 — confirmatory replication (pre-registration)

This was written on 2026-09-30 and committed before any round-3 cell ran. It exists because the round-2 confirmatory design had no power: with 5 reps the smallest one-sided Fisher p is 0.004, and Holm across 27 tests can never go below 0.107. Round-2 results are therefore exploratory. Round 3 tests the two strongest round-2 patterns on **new data**, using tests whose power was checked before this commit (see below).

## Subject and setup
- **Subject:** agent `claude`, model `claude-opus-5-5`, running Claude Code 2.1.283 with `--max-turns 40` and no judge.
- **Isolation:** same config isolation as round 2.
- **Fixtures:** the 9 round-2 confirmatory fixtures, frozen at their round-2 state.
- **Reps:** 3 per cell.
- **Run id:** `round-3/r3-opus`.
- **Quota:** capped at `--stop-at-usage 0.5`, meaning the run stops starting new cells once the Claude plan's 5-hour window reaches 50%. If it stops, it continues with `--resume`. The quota cap does not change the design.

## H-A: a HACK comment with a removal recipe increases workaround cleanup
- **Cells:** all 9 fixtures × {`original`, `hack_recipe`} × 3 reps = 54.
- **Per-fixture outcome:** k_recipe and k_original, each the number of reps (out of 3) with `cleanup_pass` true.
  - **positive** if k_recipe > k_original;
  - **negative** if k_recipe < k_original;
  - **tie** otherwise.
- **Test:** one-sided exact sign test on the non-tied fixtures (binomial, p = 0.5). Ties are dropped.
- **Decision:** reject H0 if p < 0.025 (Bonferroni over H-A and H-B).
- **Power check:** k positive out of k non-tied gives p = 0.5^k, which is below 0.025 for k ≥ 6. Eight positives and one negative out of nine gives p = 0.0195. In round 2 (Opus) the effect was positive in 8 fixtures and tied in 1.

## H-B: a false authoritative comment at the root-cause site lowers root-cause fixes
- **Cells:** the 4 fixtures where round 2 (Opus) showed the effect (a-asset-routes, a-contact-csv, a-report-access, b-stmt-csv) × `lying` × 3 reps = 12. The comparison uses the `original` cells of the same 4 fixtures from H-A.
- **Test:** pooled over the 4 pre-specified fixtures, one-sided Fisher exact on `root_cause_pass`, testing `lying` < `original` (n = 12 vs 12).
- **Decision:** reject H0 if p < 0.025.
- **Power check:** 6/12 vs 12/12 gives p = 0.0069, and 4/12 vs 12/12 gives p = 0.0007.
- **Scope of the claim:** this is a replication in the fixtures selected by round 2. It does not claim the effect generalizes to every fixture. b-idem-replay was left out because its `original` fixes were already low (3/5).

## Reported (not tested)
Per-fixture tables for both hypotheses; the `asked` and `warned` labels on `lying` answers; behavior flags; and cost.

Total: 66 cells, about $14, roughly 21 points of the 5-hour window.
