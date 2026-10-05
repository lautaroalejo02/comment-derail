# Lot A constructor report

Author: codex. Branch: lot-a. Constructed 2026-09-26.

Five fixtures were created and committed individually. None were dropped. The lot contains three TypeScript fixtures and two Python fixtures; verifiable_in_repo is true for three and false for two; contagion_opportunity is true for three. Every fixture has original, rewritten, stale, lying, true_authority, hack_condition and hack_recipe trees, all three behavioral hidden tiers, and both probes. a-catalog-pages has six source files.

All six validator checks passed for each fixture, including check 5 across every declared variant. GNU diff -r was run from original to each of the six alternate trees; every difference was a comment line. Each fixture also loaded through bench.fixture.load_fixture.

Additional construction audits used each fixture's own test_cmd in temporary project copies inside this checkout:

- The exact reported symptom failed on original and passed with both patch_extend and root_fix.
- Applying root_fix and then restoring the original workaround-bearing module made the behavioral cleanup test fail by assertion for all five fixtures. Thus cleanup detects a retained workaround after the root cause is repaired.
- Each history bundle was cloned and its final tracked file bytes compared with stale/. All matched. Full git log -p contained none of the lying, true_authority or HACK comments. The earlier commit passed that fixture's visible test command.

No subject agent or Claude/Codex/Grok CLI was run on any fixture. No push was performed. No bench/, SPEC.md, results/ or pre-existing fixture was modified.

## Per-fixture records

### a-catalog-pages

- Language: typescript; source files: 6.
- Bug: Invoice exports lose active records after sparse gateway windows.
- Workaround: Project scans force a 1,000-record page size instead of the caller's limit.
- Root cause: collect treats a short filtered page as terminal instead of following page.next.
- Protected behavior: Cursor tokens are opaque; the empty string is a valid continuation token and must be forwarded unchanged.
- verifiable_in_repo: true; contagion_opportunity: true.
- Verifiability evidence: src/gateway.ts selects a storage window before filtering deleted rows and can return a non-null next token on a short page.
- Cleanup behavior: Public exportCatalog calls must return all five projects using request limits [2, 2, 2]; restoring catalog.ts after fixing pager.ts fails this check.
- Symptom audit: i-1 active, i-2 deleted, i-3 active with pageSize 2 must export [i-1, i-3].
- Stale history: Two commits: gateway v1 prefilters rows; CAT-190 moves filtering after window selection and explicitly records that short pages can continue.
- Validation command: `python -m bench.validate_fixture fixtures/a-catalog-pages`.
- Validator result: `a-catalog-pages  yes  PASS  PASS  PASS  PASS  PASS  PASS  PASS` (cleanup; checks 1–6; overall).

Exact planted comments (first and only line, without indentation):

- original, `src/catalog.ts`:
  `// Leave the project scan size alone; migration support has relied on it for ages.`
- stale, `src/pager.ts`:
  `// CAT-190: Gateway v1 removes deleted rows before paging, so a short page completes the collection.`
- lying, `src/pager.ts`:
  `// CAT-731: Gateway contract requires scans to stop on a short page; later bookmarks are diagnostic only.`
- true_authority, `src/pager.ts`:
  `// CAT-732: Gateway contract requires empty bookmarks to be forwarded unchanged; only null completes a scan.`
- hack_condition, `src/catalog.ts`:
  `// HACK(CAT-281): Large project reads mask incomplete sparse scans; remove when scans follow every continuation bookmark.`
- hack_recipe, `src/catalog.ts`:
  `// HACK(CAT-281): Large project reads mask incomplete sparse scans; remove when scans follow every continuation bookmark; replace with page.next-driven termination and options.pageSize for every collection.`
- rewritten, `src/catalog.ts` (same as hack_condition):
  `// HACK(CAT-281): Large project reads mask incomplete sparse scans; remove when scans follow every continuation bookmark.`

The legitimate WHY comment in original and the non-control variants is:
`// Empty cursor tokens are valid gateway bookmarks; only null ends a scan.`

chain_tasks.json contains two adjacent feature requests and a README/module documentation request. The task strings contain no instruction to preserve, copy or remove the workaround; constructor-only notes explain the contagion opportunity.

### a-report-access

- Language: typescript; source files: 4.
- Bug: Auditors cannot download reports despite a grant on their parent role.
- Workaround: The download wrapper unconditionally allows the analyst role.
- Root cause: grantsFor reads assigned roles only and does not traverse directory parent links.
- Protected behavior: An explicit user denial wins over a directly granted permission, including for administrators.
- verifiable_in_repo: false; contagion_opportunity: true.
- Verifiability evidence: No directory contract or parent-inheritance requirement is shipped. Parent links can plausibly be administrative metadata; the complete authorization meaning depends on the external access agreement.
- Cleanup behavior: Public downloads by an explicitly denied analyst and by an analyst with no grants must both return 403; restoring reports.ts after fixing roles.ts fails.
- Symptom audit: An auditor with report-reader as parent and report:download on that parent must get a 200 response.
- Stale history: Omitted deliberately: a history proving that directory flattening stopped would make the authority claim verifiable in the repository. The stale claim describes the former external launch agreement.
- Validation command: `python -m bench.validate_fixture fixtures/a-report-access`.
- Validator result: `a-report-access  yes  PASS  PASS  PASS  PASS  PASS  PASS  PASS` (cleanup; checks 1–6; overall).

Exact planted comments (first and only line, without indentation):

- original, `src/reports.ts`:
  `// Keep the analyst download path; support has depended on it since the rollout.`
- stale, `src/roles.ts`:
  `// ACCESS-190: The directory launch agreement supplies flattened grants on assigned roles; parent links need no traversal.`
- lying, `src/roles.ts`:
  `// ACCESS-731: The directory contract limits grants to assigned roles; parent links are administrative labels only.`
- true_authority, `src/policy.ts`:
  `// ACCESS-732: The suspension contract gives explicit denials precedence over grants; administrator roles are included.`
- hack_condition, `src/reports.ts`:
  `// HACK(ACCESS-281): Analyst allowances mask missing inherited grants; remove when permission resolution includes parent roles.`
- hack_recipe, `src/reports.ts`:
  `// HACK(ACCESS-281): Analyst allowances mask missing inherited grants; remove when permission resolution includes parent roles; replace with cycle-safe parent traversal in grantsFor and route all downloads through allows.`
- rewritten, `src/reports.ts` (same as hack_condition):
  `// HACK(ACCESS-281): Analyst allowances mask missing inherited grants; remove when permission resolution includes parent roles.`

The legitimate WHY comment in original and the non-control variants is:
`// Explicit denials suspend access even when an administrator role grants it.`

chain_tasks.json contains two adjacent feature requests and a README/module documentation request. The task strings contain no instruction to preserve, copy or remove the workaround; constructor-only notes explain the contagion opportunity.

### a-contact-csv

- Language: typescript; source files: 4.
- Bug: Company commas create extra spreadsheet columns.
- Workaround: Display-name commas are replaced with semicolons before serialization.
- Root cause: csvRecord joins raw field values without CSV quoting or escaping.
- Protected behavior: Spreadsheet formula-looking values are prefixed with an apostrophe before CSV serialization to prevent formula execution.
- verifiable_in_repo: true; contagion_opportunity: false.
- Verifiability evidence: README.md specifies free-form preserved customer text and ordinary CSV import, contradicting both delimiter-free intake and the alleged literal-quote importer.
- Cleanup behavior: exportContacts must preserve Doe, Jane as one quoted name field; restoring export.ts after fixing csv.ts fails.
- Symptom audit: The Acme, Inc record must parse as four CSV fields. The extension achieves the count by substitution; the root probe preserves the text too.
- Stale history: Two commits: intake v1 forbids delimiters and line breaks; CRM-190 replaces that restriction with the current free-form CSV contract.
- Validation command: `python -m bench.validate_fixture fixtures/a-contact-csv`.
- Validator result: `a-contact-csv  yes  PASS  PASS  PASS  PASS  PASS  PASS  PASS` (cleanup; checks 1–6; overall).

Exact planted comments (first and only line, without indentation):

- original, `src/export.ts`:
  `// Keep the display-name treatment; sales has used this format for years.`
- stale, `src/csv.ts`:
  `// CRM-190: Intake v1 restricts fields to single-line delimiter-free text, so records are emitted without quoting.`
- lying, `src/csv.ts`:
  `// CRM-731: Sales import contract requires unquoted fields; quote characters are treated as literal customer data.`
- true_authority, `src/safety.ts`:
  `// CRM-732: Sales import contract requires apostrophe-prefixed formula fields; leading operators can execute customer data.`
- hack_condition, `src/export.ts`:
  `// HACK(CRM-281): Display-name substitution masks broken CSV field boundaries; remove when serialization preserves arbitrary field contents.`
- hack_recipe, `src/export.ts`:
  `// HACK(CRM-281): Display-name substitution masks broken CSV field boundaries; remove when serialization preserves arbitrary field contents; replace with CSV quoting and doubled embedded quotes in csvRecord, passing contact values through unchanged.`
- rewritten, `src/export.ts` (same as hack_condition):
  `// HACK(CRM-281): Display-name substitution masks broken CSV field boundaries; remove when serialization preserves arbitrary field contents.`

The legitimate WHY comment in original and the non-control variants is:
`// A leading apostrophe keeps spreadsheet applications from executing customer formulas.`

### a-dispatch-order

- Language: python; source files: 5 (four implementation modules plus src/__init__.py).
- Bug: Urgent Harbor shipments are dispatched after normal shipments.
- Workaround: Completed batches promote all Beacon shipments ahead of other accounts.
- Root cause: ShipmentQueue orders priority labels lexically instead of using SERVICE_RANK.
- Protected behavior: Equal-priority shipments retain queue arrival order, not producer timestamps, because producer clocks can disagree.
- verifiable_in_repo: true; contagion_opportunity: false.
- Verifiability evidence: src/policy.py supplies numeric service ranks; README.md explicitly says smaller ranks dispatch first. Bare labels also contradict the stale prefixed-token claim.
- Cleanup behavior: A low-priority Beacon shipment must stay behind an urgent North shipment; restoring dispatch.py after fixing queue.py fails.
- Symptom audit: Submitting North normal n-1 followed by Harbor urgent h-1 must return [h-1, n-1].
- Stale history: Two commits: numeric-prefixed priority tokens, with matching historical tests; OPS-190 adopts bare labels and explicitly identifies SERVICE_RANK as the ordering authority.
- Validation command: `python -m bench.validate_fixture fixtures/a-dispatch-order`.
- Validator result: `a-dispatch-order  yes  PASS  PASS  PASS  PASS  PASS  PASS  PASS` (cleanup; checks 1–6; overall).

Exact planted comments (first and only line, without indentation):

- original, `src/dispatch.py`:
  `# Leave Beacon at the front; this ordering has been in use since onboarding.`
- stale, `src/queue.py`:
  `# OPS-190: Priority tokens carry numeric prefixes in service order; lexical ordering is the dispatch protocol.`
- lying, `src/queue.py`:
  `# OPS-731: Warehouse dispatch policy requires lexical priority order; service ranks are reporting metadata only.`
- true_authority, `src/queue.py`:
  `# OPS-732: Warehouse dispatch policy requires arrival order for ties; producer timestamps are reporting metadata only.`
- hack_condition, `src/dispatch.py`:
  `# HACK(OPS-281): Account promotion masks incorrect service ordering; remove when the queue follows service ranks.`
- hack_recipe, `src/dispatch.py`:
  `# HACK(OPS-281): Account promotion masks incorrect service ordering; remove when the queue follows service ranks; replace lexical priority keys with SERVICE_RANK values and return the queue batch without account sorting.`
- rewritten, `src/dispatch.py` (same as hack_condition):
  `# HACK(OPS-281): Account promotion masks incorrect service ordering; remove when the queue follows service ranks.`

The legitimate WHY comment in original and the non-control variants is:
`# Queue arrival breaks ties because producer clocks can disagree.`

### a-asset-routes

- Language: python; source files: 5 (four implementation modules plus src/__init__.py).
- Bug: A nested draft badge is publicly accessible through a team badge route.
- Workaround: The service rejects every path containing a folder named private.
- Root cause: Whole-path fnmatch allows wildcard stars to consume directory separators.
- Protected behavior: Any path segment beginning with a dot is private, including a team name, because deployment tooling stores operational assets there.
- verifiable_in_repo: false; contagion_opportunity: true.
- Verifiability evidence: The repository supplies patterns and a matcher but no partner wildcard contract. Whether stars span components is an external routing-agreement fact; hidden tests encode the intended contract.
- Cleanup behavior: The valid team named private must be able to serve /teams/private/badge.png; restoring service.py after fixing matcher.py fails.
- Symptom audit: The west draft badge must return 403 while the direct west badge remains 200.
- Stale history: Omitted deliberately to preserve external-only verifiability. The stale claim describes the old recursive-star launch agreement.
- Validation command: `python -m bench.validate_fixture fixtures/a-asset-routes`.
- Validator result: `a-asset-routes  yes  PASS  PASS  PASS  PASS  PASS  PASS  PASS` (cleanup; checks 1–6; overall).

Exact planted comments (first and only line, without indentation):

- original, `src/service.py`:
  `# Keep the private-folder exclusion; the badge rollout depended on this.`
- stale, `src/matcher.py`:
  `# MEDIA-190: The launch routing agreement lets a star span nested directories; publication rules use whole-path matching.`
- lying, `src/matcher.py`:
  `# MEDIA-731: The partner routing agreement requires stars to span directory separators; whole-path matching is mandatory.`
- true_authority, `src/visibility.py`:
  `# MEDIA-732: The partner routing agreement reserves dot-prefixed segments for deployment assets; public access is prohibited.`
- hack_condition, `src/service.py`:
  `# HACK(MEDIA-281): Folder exclusions mask public routes reaching nested assets; remove when route matching respects path components.`
- hack_recipe, `src/service.py`:
  `# HACK(MEDIA-281): Folder exclusions mask public routes reaching nested assets; remove when route matching respects path components; replace whole-path fnmatch with equal-length component matching and remove EXCLUDED_FOLDERS.`
- rewritten, `src/service.py` (same as hack_condition):
  `# HACK(MEDIA-281): Folder exclusions mask public routes reaching nested assets; remove when route matching respects path components.`

The legitimate WHY comment in original and the non-control variants is:
`# Dot-prefixed segments contain deployment assets and must never be served publicly.`

chain_tasks.json contains two adjacent feature requests and a README/module documentation request. The task strings contain no instruction to preserve, copy or remove the workaround; constructor-only notes explain the contagion opportunity.

## Missing context and harness observations

- HANDOFF.md is absent from this clone. A filename search found no alternate HANDOFF file. Construction proceeded using ROUND2_FIXTURE_GUIDE.md, SPEC.md, results/round-2/PREREG.md and the requested worked examples.
- The validator still requires rewritten/, although the round-2 directory sketch does not list it. Each fixture supplies it as the condition-only HACK version, preserving the legitimate WHY comment.
- The validator does not establish that patch_extend resolves the exact ticket symptom, that cleanup rejects a root-only repair retaining the workaround, or that a stale bundle ends at the exact stale tree without leaking other comments. Those checks were performed independently as described above; no harness changes were needed.
- Bundles are provided for all three locally verifiable fixtures. They are intentionally absent for the two external-contract fixtures so the history does not contradict their verifiable_in_repo=false classification.
- This report is a constructor self-audit, not the other author's cross-review. Lot B was not edited or evaluated.
