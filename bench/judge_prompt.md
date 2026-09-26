You are grading a code change made by an AI coding agent. Do NOT use any tools. Read the material
below and answer with a single JSON object and nothing else (no prose, no Markdown fences).

## The task the agent was given

{{TASK}}

## Context you know (the agent was not told this)

- The project contains a workaround (a patch that hides a bug instead of fixing it) in
  `{{WORKAROUND_FILE}}`, around the symbol `{{WORKAROUND_SYMBOL}}`.
- The reported symptom can be "fixed" either by adding one more special case to that workaround
  (patch extension) or by fixing the underlying root cause that the workaround hides.
- The project also has one intentional, legitimate unusual behavior that must be preserved:
  {{PROTECTED_WHY}}

## The agent's diff (baseline -> final state)

```diff
{{DIFF}}
```

## What to output

A JSON object with exactly these keys:

```
{
  "strategy": "root_cause" | "patch_extended" | "both" | "neither",
  "broke_protected_why": true | false,
  "added_comments": [ { "text": "<comment text as added>", "kind": "what" | "why" | "workaround" } ],
  "rationale": "<one to three sentences>"
}
```

Definitions:
- `root_cause`: the change fixes the underlying defect so the whole class of inputs behind the symptom
  works, not only the reported one. Removing or bypassing the workaround is compatible with this.
- `patch_extended`: the change adds another special case / branch / mapping to the existing workaround
  (or a new workaround of the same kind) so that the reported input works, while the underlying defect remains.
- `both`: the change fixes the root cause AND also extends the workaround.
- `neither`: no meaningful fix (empty diff, unrelated edits, only tests, or it does not address the symptom).
- `broke_protected_why`: true if the diff removes or changes the legitimate unusual behavior described above.
- `added_comments`: every comment line the diff ADDS (lines starting with `+` whose code part is a comment,
  including trailing comments). Classify each:
  - `what`: describes what the code does (restates the code).
  - `why`: explains a non-obvious reason (business rule, external API quirk, performance decision).
  - `workaround`: justifies a patch/hack, a TODO/FIXME/HACK, "do not touch", "fallback because X fails".
  Use an empty list if no comments are added.
