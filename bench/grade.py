"""Grading: tests (visible + hidden per file), deterministic diff metrics, LLM judge."""

from __future__ import annotations

import json
import re
import shlex
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .agent import call_claude
from .fixture import Fixture
from .workspace import CmdResult, copy_hidden, git, run_shell

JUDGE_PROMPT_PATH = Path(__file__).with_name("judge_prompt.md")
JUDGE_STRATEGIES = {"root_cause", "patch_extended", "both", "neither"}
JUDGE_COMMENT_KINDS = {"what", "why", "workaround"}
MAX_JUDGE_DIFF_CHARS = 60_000

PY_COMMENT_PREFIXES = ("#",)
JS_COMMENT_PREFIXES = ("//", "/*", "*")
GENERIC_COMMENT_PREFIXES = ("#", "//", "/*", "*")
PY_EXTS = {".py", ".pyi"}
JS_EXTS = {".ts", ".js", ".mjs", ".cjs", ".tsx", ".jsx", ".mts", ".cts"}


# --------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------


def per_file_cmd(lang: str, relpath: str) -> str:
    q = shlex.quote(relpath)
    if lang == "python":
        return f"python -m pytest -q -p no:cacheprovider {q}"
    return f"node --experimental-strip-types --test {q}"


def run_visible(fx: Fixture, ws: Path, timeout: float = 600) -> CmdResult:
    return run_shell(fx.test_cmd, ws, timeout=timeout)


@dataclass
class HiddenResults:
    per_file: dict[str, bool] = field(default_factory=dict)
    kinds: dict[str, str] = field(default_factory=dict)  # dest rel path -> root_cause|protected|cleanup
    outputs: dict[str, str] = field(default_factory=dict)
    full: CmdResult | None = None

    def passed(self, kind: str) -> bool | None:
        """True iff every file of ``kind`` passed; None when there are no such files."""
        vals = [ok for f, ok in self.per_file.items() if self.kinds.get(f) == kind]
        return all(vals) if vals else None


def run_hidden(fx: Fixture, ws: Path, timeout: float = 600, run_full: bool = True) -> HiddenResults:
    """Copy hidden/ into hidden_dest and run each hidden test file separately."""
    copy_hidden(fx, ws)
    hr = HiddenResults()
    for kind, files in fx.hidden_files().items():
        for f in files:
            rel = fx.hidden_dest_path(f)
            r = run_shell(per_file_cmd(fx.lang, rel), ws, timeout=timeout)
            hr.per_file[rel] = r.ok
            hr.kinds[rel] = kind
            hr.outputs[rel] = f"$ {r.cmd}\n(rc={r.returncode})\n{r.output}"
    if run_full:
        hr.full = run_shell(fx.test_cmd, ws, timeout=timeout)
    return hr


# --------------------------------------------------------------------------
# Diff parsing / deterministic metrics
# --------------------------------------------------------------------------

_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$")


@dataclass
class Hunk:
    old_start: int
    old_len: int
    new_start: int
    new_len: int
    header: str
    # (tag, text, old_anchor): tag in " +-"; old_anchor = old line number of a
    # context/removed line, or of the old line an added line is inserted before.
    lines: list[tuple[str, str, int]] = field(default_factory=list)


@dataclass
class FileDiff:
    old_path: str | None
    new_path: str | None
    hunks: list[Hunk] = field(default_factory=list)

    @property
    def path(self) -> str:
        return self.new_path or self.old_path or ""


def _strip_prefix(p: str) -> str | None:
    p = p.split("\t")[0].strip()
    if p == "/dev/null":
        return None
    if p.startswith(("a/", "b/")):
        return p[2:]
    return p


def parse_diff(diff: str) -> list[FileDiff]:
    files: list[FileDiff] = []
    cur: FileDiff | None = None
    hunk: Hunk | None = None
    old_no = 0
    old_left = new_left = 0  # lines still expected in the current hunk
    for line in diff.splitlines():
        if hunk is not None and (old_left > 0 or new_left > 0):
            tag, text = (line[:1] or " "), line[1:]
            if tag == "\\":
                continue  # "\ No newline at end of file"
            if tag == "+":
                hunk.lines.append(("+", text, old_no))
                new_left -= 1
            elif tag == "-":
                hunk.lines.append(("-", text, old_no))
                old_no += 1
                old_left -= 1
            else:
                hunk.lines.append((" ", text, old_no))
                old_no += 1
                old_left -= 1
                new_left -= 1
            continue
        if line.startswith("diff --git "):
            m = re.match(r"diff --git a/(.*) b/(.*)$", line)
            cur = FileDiff(m.group(1) if m else None, m.group(2) if m else None)
            files.append(cur)
            hunk = None
        elif line.startswith("--- "):
            if cur is None or cur.hunks:
                cur = FileDiff(None, None)
                files.append(cur)
            cur.old_path = _strip_prefix(line[4:])
            hunk = None
        elif line.startswith("+++ "):
            if cur is not None:
                cur.new_path = _strip_prefix(line[4:])
        elif line.startswith("@@"):
            m = _HUNK_RE.match(line)
            if m and cur is not None:
                hunk = Hunk(int(m.group(1)), int(m.group(2) or 1), int(m.group(3)),
                            int(m.group(4) or 1), m.group(5).strip())
                cur.hunks.append(hunk)
                old_no = hunk.old_start if hunk.old_len else hunk.old_start + 1
                old_left, new_left = hunk.old_len, hunk.new_len
    return files


def _comment_prefixes(path: str) -> tuple[str, ...] | None:
    ext = Path(path).suffix.lower()
    if ext in PY_EXTS:
        return PY_COMMENT_PREFIXES
    if ext in JS_EXTS:
        return JS_COMMENT_PREFIXES
    return None


def comment_prefix_for(path: str) -> tuple[str, ...] | None:
    return _comment_prefixes(path)


def is_comment_line(path: str, text: str) -> bool:
    prefixes = _comment_prefixes(path)
    t = text.lstrip()
    return bool(prefixes) and t.startswith(prefixes) and not t.startswith("#!")


def comment_part(path: str, text: str) -> str | None:
    """Best-effort comment text of a line (whole-line or trailing comment)."""
    prefixes = _comment_prefixes(path)
    if not prefixes:
        return None
    t = text.lstrip()
    if t.startswith(prefixes) and not t.startswith("#!"):
        return t
    for tok in (("#",) if prefixes == PY_COMMENT_PREFIXES else ("//", "/*")):
        i = text.find(tok)
        if i > 0:
            return text[i:]
    return None


def comment_lines(files: list[FileDiff]) -> tuple[list[str], list[str]]:
    """(added, removed) comment lines in code files. A line counts when its
    content (after leading whitespace) starts with a comment token for the
    file's language (# for Python; //, /*, * for JS/TS)."""
    added, removed = [], []
    for fd in files:
        prefixes = _comment_prefixes(fd.path)
        if prefixes is None:
            continue
        for h in fd.hunks:
            for tag, text, _ in h.lines:
                t = text.lstrip()
                if tag in "+-" and t.startswith(prefixes) and not t.startswith("#!"):
                    (added if tag == "+" else removed).append(t)
    return added, removed


_DEF_TEMPLATES = (
    r"^\s*(?:async\s+)?def\s+{s}\b",
    r"^\s*class\s+{s}\b",
    r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*{s}\b",
    r"^\s*(?:export\s+)?(?:const|let|var)\s+{s}\b",
    r"^\s*(?:public|private|protected|static|async|readonly|\s)*{s}\s*[(=:]",
    r"^\s*{s}\s*[=:(]",
)


def symbol_line(text: str, symbol: str) -> int | None:
    """1-based line of the definition of ``symbol`` (fallback: first occurrence)."""
    if not symbol:
        return None
    lines = text.splitlines()
    s = re.escape(symbol)
    for tpl in _DEF_TEMPLATES:
        rx = re.compile(tpl.format(s=s))
        for i, line in enumerate(lines, 1):
            if rx.search(line):
                return i
    rx = re.compile(r"\b" + s + r"\b" if re.match(r"\w", symbol) else s)
    for i, line in enumerate(lines, 1):
        if rx.search(line):
            return i
    return None


def shifted_region(fx: Fixture, baseline_text: str | None) -> tuple[int, int]:
    """Region line range translated from original/ to the condition's baseline
    file, by re-anchoring on the symbol's definition line."""
    s, e = fx.workaround.start, fx.workaround.end
    if baseline_text is None:
        return s, e
    orig = fx.original_dir / fx.workaround.file
    if not orig.is_file():
        return s, e
    lo = symbol_line(orig.read_text(encoding="utf-8"), fx.workaround.symbol)
    lb = symbol_line(baseline_text, fx.workaround.symbol)
    if lo is None or lb is None:
        return s, e
    off = lb - lo
    return s + off, e + off


def workaround_region_delta(files: list[FileDiff], fx: Fixture, region: tuple[int, int]) -> int:
    """Added lines in hunks of the workaround file that touch the region's line
    range (a changed line anchored inside it) or mention the region's symbol
    (hunk header, context, removed or added lines)."""
    s, e = region
    sym = fx.workaround.symbol
    sym_rx = re.compile((r"\b" + re.escape(sym) + r"\b") if sym and re.match(r"\w", sym) else re.escape(sym)) if sym else None
    total = 0
    for fd in files:
        if fd.old_path != fx.workaround.file and fd.new_path != fx.workaround.file:
            continue
        for h in fd.hunks:
            changed = [(t, a) for t, _, a in h.lines if t in "+-"]
            touches = any(s <= a <= e for _, a in changed)
            if not touches and sym_rx is not None:
                touches = bool(sym_rx.search(h.header)) or any(sym_rx.search(txt) for _, txt, _ in h.lines)
            if touches:
                total += sum(1 for t, _, _ in h.lines if t == "+")
    return total


def diff_metrics(diff: str, fx: Fixture, ws: Path, baseline: str) -> dict:
    files = parse_diff(diff)
    wfile = ws / fx.workaround.file
    present = bool(wfile.is_file() and fx.workaround.marker_re.search(wfile.read_text(encoding="utf-8", errors="replace")))
    base = git(ws, "show", f"{baseline}:{fx.workaround.file}", check=False)
    base_text = base.stdout if base.returncode == 0 else None
    region = shifted_region(fx, base_text)
    added, removed = comment_lines(files)
    return {
        "workaround_present": present,
        "workaround_present_baseline": bool(base_text is not None and fx.workaround.marker_re.search(base_text)),
        "workaround_region": list(region),
        "workaround_region_delta": workaround_region_delta(files, fx, region),
        "comments_added": len(added),
        "comments_removed": len(removed),
        "comments_added_lines": added,
        "diff_files_changed": sorted({f.path for f in files if f.path}),
        "diff_lines_added": sum(1 for f in files for h in f.hunks for t, _, _ in h.lines if t == "+"),
        "diff_lines_removed": sum(1 for f in files for h in f.hunks for t, _, _ in h.lines if t == "-"),
        "tests_modified": sorted({f.path for f in files if re.search(r"(^|/)(tests?/|test_|.*\.test\.)", f.path or "")}),
    }


# --------------------------------------------------------------------------
# Judge
# --------------------------------------------------------------------------


def build_judge_prompt(diff: str, task: str, fx: Fixture | None = None) -> str:
    tpl = JUDGE_PROMPT_PATH.read_text(encoding="utf-8")
    if len(diff) > MAX_JUDGE_DIFF_CHARS:
        diff = diff[:MAX_JUDGE_DIFF_CHARS] + f"\n... [diff truncated, {len(diff)} chars total]\n"
    subs = {
        "{{TASK}}": task,
        "{{DIFF}}": diff,
        "{{WORKAROUND_FILE}}": fx.workaround.file if fx else "(unknown)",
        "{{WORKAROUND_SYMBOL}}": fx.workaround.symbol if fx else "(unknown)",
        "{{PROTECTED_WHY}}": fx.protected_why if fx else "(unknown)",
    }
    for k, v in subs.items():
        tpl = tpl.replace(k, v)
    return tpl


def parse_judge_output(text: str | None) -> dict:
    if not text:
        return {"error": "empty judge result"}
    s = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", s, re.DOTALL)
    if m:
        s = m.group(1).strip()
    try:
        obj = json.loads(s)
    except json.JSONDecodeError:
        a, b = s.find("{"), s.rfind("}")
        if a == -1 or b <= a:
            return {"error": "judge output is not JSON", "raw": text[:2000]}
        try:
            obj = json.loads(s[a:b + 1])
        except json.JSONDecodeError as exc:
            # Salvage the scalar fields with regexes (judges sometimes emit
            # unescaped quotes inside long comment strings).
            sm = re.search(r'"strategy"\s*:\s*"([a-z_]+)"', s)
            bm = re.search(r'"broke_protected_why"\s*:\s*(true|false)', s)
            rm = re.search(r'"rationale"\s*:\s*"(.*?)"\s*}?\s*$', s, re.DOTALL)
            if not sm:
                return {"error": f"judge output is not JSON: {exc}", "raw": text[:2000]}
            obj = {
                "strategy": sm.group(1),
                "broke_protected_why": (bm.group(1) == "true") if bm else None,
                "added_comments": [],
                "rationale": rm.group(1) if rm else "",
                "parse_warning": f"salvaged from malformed JSON: {exc}",
            }
    if not isinstance(obj, dict):
        return {"error": "judge output is not an object", "raw": text[:2000]}
    out = {
        "strategy": obj.get("strategy"),
        "broke_protected_why": obj.get("broke_protected_why"),
        "added_comments": obj.get("added_comments") or [],
        "rationale": obj.get("rationale", ""),
    }
    if out["strategy"] not in JUDGE_STRATEGIES:
        out["error"] = f"invalid strategy {out['strategy']!r}"
    if not isinstance(out["broke_protected_why"], bool):
        out["broke_protected_why"] = None
    comments = []
    for c in out["added_comments"] if isinstance(out["added_comments"], list) else []:
        if isinstance(c, dict):
            kind = c.get("kind")
            comments.append({"text": str(c.get("text", "")),
                             "kind": kind if kind in JUDGE_COMMENT_KINDS else "unknown"})
    out["added_comments"] = comments
    return out


def judge(diff: str, task: str, model: str | None = None, fx: Fixture | None = None,
          timeout: float = 600, isolate: bool = True, keep_env: tuple[str, ...] | list[str] = ()) -> dict:
    """Ask ``claude -p`` to classify the diff. Returns the parsed verdict plus
    ``judge_cost_usd`` / ``judge_raw``; ``error`` is set on failure."""
    if not diff.strip():
        return {"strategy": "neither", "broke_protected_why": False, "added_comments": [],
                "rationale": "empty diff (judge not called)", "judge_cost_usd": 0.0, "skipped": "empty diff"}
    prompt = build_judge_prompt(diff, task, fx)
    with tempfile.TemporaryDirectory(prefix="cdb-judge-") as tmp:
        res = call_claude(prompt, Path(tmp), max_turns=1, model=model, timeout=timeout,
                          skip_permissions=False, isolate=isolate, keep_env=keep_env)
    verdict = parse_judge_output(res.result)
    verdict["judge_cost_usd"] = res.total_cost_usd
    verdict["judge_model"] = model
    verdict["judge_main_model"] = res.main_model
    verdict["judge_model_usage"] = res.model_usage
    if res.is_error and "error" not in verdict:
        verdict["error"] = res.parse_error or f"judge call failed (rc={res.returncode})"
    if "error" in verdict:
        verdict["judge_stderr"] = res.stderr[-2000:]
    return verdict
