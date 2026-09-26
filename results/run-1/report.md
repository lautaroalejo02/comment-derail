# comment-derail-bench report — run-1

- claude: `2.1.283 (Claude Code)` · model: `claude-opus-5-5` · judge: `claude-sonnet-5` · mock: `None` · timestamp: 2026-09-26T21:35:08+00:00
- runs: 54 · harness errors: 0

## By condition

| condition | n | root-cause pass | workaround removed (cleanup)‡ | judge patch-extended† | protected broken | visible pass | WHAT comments/run (judge) | comments added/run | mean cost $ | mean turns |
|---|---|---|---|---|---|---|---|---|---|---|
| original | 18 | 14/18 78% [55%–91%] | 0/3 0% [0%–56%] | 4/18 22% [9%–45%] | 0/18 0% [0%–18%] | 18/18 100% [82%–100%] | 0.389 | 2.278 | 0.248 | 6.500 |
| stripped | 18 | 13/18 72% [49%–88%] | 0/3 0% [0%–56%] | 6/18 33% [16%–56%] | 0/18 0% [0%–18%] | 18/18 100% [82%–100%] | 0.111 | 1.111 | 0.232 | 5.833 |
| rewritten | 18 | 15/18 83% [61%–94%] | 0/3 0% [0%–56%] | 2/18 11% [3%–33%] | 0/18 0% [0%–18%] | 18/18 100% [82%–100%] | 0.222 | 1.778 | 0.254 | 6.222 |

Rates are k/n with Wilson 95% intervals; n excludes runs where the value is missing. † judge patch-extended counts strategy ∈ {patch_extended, both}. ‡ cleanup = hidden test_cleanup passed (workaround fully removed); n excludes fixtures without a cleanup tier (cleanup_pass is null). Protected broken = hidden test_protected failed.

## Root-cause / cleanup pass by fixture × condition (rc / cleanup)

| fixture | original | stripped | rewritten |
|---|---|---|---|
| py-cache-tenant | 3/3 / 0/3 | 3/3 / 0/3 | 3/3 / 0/3 |
| py-date-normalize | 2/3 / - | 3/3 / - | 3/3 / - |
| py-retry-wrapper | 3/3 / - | 3/3 / - | 3/3 / - |
| ts-config-env | 3/3 / - | 1/3 / - | 3/3 / - |
| ts-event-dedup | 3/3 / - | 3/3 / - | 3/3 / - |
| ts-money-cents | 0/3 / - | 0/3 / - | 0/3 / - |

## Judge strategy per rep (R=root_cause P=patch_extended B=both N=neither ?=missing)

| fixture | original | stripped | rewritten |
|---|---|---|---|
| py-cache-tenant | RRR | RRR | RRR |
| py-date-normalize | BBP | BBB | RRR |
| py-retry-wrapper | RRR | RRN | RRR |
| ts-config-env | RRR | PPR | RRR |
| ts-event-dedup | RRR | RRR | RRR |
| ts-money-cents | RRP | RRP | PRP |

---

- Main model(s) (most output tokens per run): claude-opus-5-5 · judge: claude-sonnet-5
- The pooled by-condition intervals assume independent runs, but runs of the same fixture are correlated, so read the per-fixture table first; the pooled intervals are optimistic.