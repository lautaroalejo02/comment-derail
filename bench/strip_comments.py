"""Remove every comment from Python / TypeScript / JavaScript sources.

Rules (SPEC "stripped" condition):
  * Python: every ``COMMENT`` token found by :mod:`tokenize` is removed.
    Docstrings are strings, not comments, so they are kept. A shebang on
    line 1 is kept. Encoding cookies are dropped (they are comments).
  * JS/TS (.ts .js .mjs .cjs, plus .tsx/.jsx/.mts/.cts): ``//`` and ``/* */``
    comments are removed by a small state machine that understands string
    literals, template literals (with ``${}`` nesting) and, best effort,
    regex literals. A shebang on line 1 is kept.

Line numbers are preserved: a line that held only a comment becomes an empty
line and a multi-line block comment keeps its newlines. This keeps the
indentation intact and lets the workaround ``region`` line numbers from
``original/`` stay valid in the ``stripped`` condition.

``strip(strip(x)) == strip(x)`` holds.

CLI::

    python -m bench.strip_comments <dir> [<dir> ...]   # strips in place
    python -m bench.strip_comments --stdout <file>     # prints stripped file
"""

from __future__ import annotations

import argparse
import io
import os
import sys
import tokenize
from pathlib import Path

PY_EXTS = {".py", ".pyi"}
JS_EXTS = {".ts", ".js", ".mjs", ".cjs", ".tsx", ".jsx", ".mts", ".cts"}
SKIP_DIRS = {"node_modules", ".git", "__pycache__", ".pytest_cache", ".venv", "venv"}

LANG_ALIASES = {
    "python": "python",
    "py": "python",
    "typescript": "typescript",
    "ts": "typescript",
    "javascript": "typescript",
    "js": "typescript",
}


def lang_for_path(path: str | os.PathLike) -> str | None:
    ext = Path(path).suffix.lower()
    if ext in PY_EXTS:
        return "python"
    if ext in JS_EXTS:
        return "typescript"
    return None


def strip(path_or_text: str | os.PathLike, lang: str | None = None) -> str:
    """Return the source with all comments removed.

    ``path_or_text`` may be a path to an existing file or the source text
    itself. ``lang`` is ``python`` or ``typescript``/``javascript``; when
    omitted it is inferred from the file extension.
    """
    text: str
    if isinstance(path_or_text, os.PathLike) or (
        isinstance(path_or_text, str)
        and "\n" not in path_or_text
        and len(path_or_text) < 4096
        and os.path.isfile(path_or_text)
    ):
        p = Path(path_or_text)
        text = p.read_text(encoding="utf-8")
        if lang is None:
            lang = lang_for_path(p)
    else:
        text = str(path_or_text)
    if lang is None:
        raise ValueError("lang is required when passing source text")
    norm = LANG_ALIASES.get(lang.lower())
    if norm == "python":
        return strip_python(text)
    if norm == "typescript":
        return strip_js(text)
    raise ValueError(f"unsupported lang: {lang!r}")


# --------------------------------------------------------------------------
# Python
# --------------------------------------------------------------------------


def strip_python(text: str) -> str:
    # Same line splitting as tokenize's readline (split on "\n" only).
    lines = io.StringIO(text).readlines()
    cuts: dict[int, int] = {}  # 0-based line index -> column where comment starts
    try:
        toks = tokenize.generate_tokens(io.StringIO(text).readline)
        for tok in toks:
            if tok.type != tokenize.COMMENT:
                continue
            row, col = tok.start
            if row == 1 and col == 0 and tok.string.startswith("#!"):
                continue  # keep shebang
            cuts[row - 1] = col
    except (tokenize.TokenError, IndentationError, SyntaxError) as exc:
        print(f"[strip_comments] warning: cannot tokenize python source ({exc}); left unchanged",
              file=sys.stderr)
        return text

    out = []
    for i, line in enumerate(lines):
        if i in cuts:
            if line.endswith("\r\n"):
                eol = "\r\n"
            elif line.endswith("\n"):
                eol = "\n"
            else:
                eol = ""
            kept = line[: cuts[i]].rstrip(" \t\f")
            if not kept.strip():
                kept = ""
            out.append(kept + eol)
        else:
            out.append(line)
    return "".join(out)


# --------------------------------------------------------------------------
# JavaScript / TypeScript
# --------------------------------------------------------------------------

# A "/" after one of these characters starts a regex literal.
_REGEX_PREV_CHARS = set("(,=:[!&|?{};+-*%<>~^")
# ... or after one of these keywords.
_REGEX_PREV_WORDS = {
    "return", "typeof", "instanceof", "in", "of", "new", "delete", "void",
    "throw", "case", "do", "else", "yield", "await",
}


def _is_ident_char(c: str) -> bool:
    return c.isalnum() or c in "_$"


def _regex_allowed(out: list[str]) -> bool:
    """Decide whether a '/' at the current position starts a regex literal,
    looking back at what has been emitted so far (comments already removed)."""
    i = len(out) - 1
    while i >= 0:
        c = out[i]
        if c == "\n":
            return True  # line start
        if c in " \t\r\f\v":
            i -= 1
            continue
        break
    else:
        return True  # start of file
    c = out[i]
    if c in _REGEX_PREV_CHARS:
        # `a++ / 2` and `a-- / 2` are divisions.
        if c in "+-" and i > 0 and out[i - 1] == c:
            return False
        return True
    if _is_ident_char(c):
        j = i
        while j >= 0 and _is_ident_char(out[j]):
            j -= 1
        word = "".join(out[j + 1 : i + 1])
        if j >= 0 and out[j] == ".":
            return False  # property access like obj.return
        return word in _REGEX_PREV_WORDS
    return False


def strip_js(text: str) -> str:
    n = len(text)
    out: list[str] = []
    touched: set[int] = set()  # output line indexes where a comment was removed
    line_no = 0  # current output line index
    i = 0

    def emit(s: str) -> None:
        nonlocal line_no
        out.extend(s)
        line_no += s.count("\n")

    # Shebang
    if text.startswith("#!"):
        end = text.find("\n")
        end = n if end == -1 else end
        emit(text[:end])
        i = end

    # Stack for template literals: each entry is the brace depth inside the
    # current `${ ... }` expression.
    tmpl_stack: list[int] = []
    in_template = False

    while i < n:
        c = text[i]
        nxt = text[i + 1] if i + 1 < n else ""

        if in_template:
            if c == "\\":
                emit(text[i : i + 2])
                i += 2
                continue
            if c == "`":
                emit(c)
                i += 1
                in_template = False
                continue
            if c == "$" and nxt == "{":
                emit("${")
                i += 2
                tmpl_stack.append(0)
                in_template = False
                continue
            emit(c)
            i += 1
            continue

        # ---- code state ----
        if c == "/" and nxt == "/":
            touched.add(line_no)
            j = text.find("\n", i)
            i = n if j == -1 else j
            continue
        if c == "/" and nxt == "*":
            touched.add(line_no)
            j = text.find("*/", i + 2)
            body = text[i : (n if j == -1 else j + 2)]
            i = n if j == -1 else j + 2
            newlines = body.count("\n")
            if newlines:
                emit("\n" * newlines)
                touched.add(line_no)
            prev = out[-1] if out else "\n"
            follow = text[i] if i < n else "\n"
            if prev in " \t\n":
                # `a /* x */ b` -> `a b`; `    /* x */ return` -> `    return`
                while i < n and text[i] in " \t":
                    i += 1
            elif follow not in " \t\r\n":
                emit(" ")  # keep tokens apart: a/**/b -> a b
            continue
        if c == "/":
            if _regex_allowed(out):
                j = _scan_regex(text, i)
                if j is not None:
                    emit(text[i:j])
                    i = j
                    continue
            emit(c)
            i += 1
            continue
        if c in "'\"":
            j = _scan_string(text, i, c)
            emit(text[i:j])
            i = j
            continue
        if c == "`":
            emit(c)
            i += 1
            in_template = True
            continue
        if c == "{":
            if tmpl_stack:
                tmpl_stack[-1] += 1
            emit(c)
            i += 1
            continue
        if c == "}":
            if tmpl_stack:
                if tmpl_stack[-1] == 0:
                    tmpl_stack.pop()
                    emit(c)
                    i += 1
                    in_template = True
                    continue
                tmpl_stack[-1] -= 1
            emit(c)
            i += 1
            continue
        emit(c)
        i += 1

    result = "".join(out)
    if not touched:
        return result
    lines = result.split("\n")
    for idx in touched:
        if idx < len(lines):
            s = lines[idx]
            cr = s.endswith("\r")
            s = s.rstrip(" \t\r\f\v")
            if not s.strip():
                s = ""
            lines[idx] = s + ("\r" if cr else "")
    return "\n".join(lines)


def _scan_string(text: str, i: int, quote: str) -> int:
    """Return index just past the string literal starting at ``i``."""
    n = len(text)
    j = i + 1
    while j < n:
        c = text[j]
        if c == "\\":
            j += 2
            continue
        if c == quote:
            return j + 1
        if c == "\n":  # unterminated; stop at end of line
            return j
        j += 1
    return n


def _scan_regex(text: str, i: int) -> int | None:
    """Return index just past the regex literal starting at ``i`` (a '/'), or
    None if it does not look like one (hits a newline / EOF)."""
    n = len(text)
    j = i + 1
    in_class = False
    while j < n:
        c = text[j]
        if c == "\n":
            return None
        if c == "\\":
            j += 2
            continue
        if in_class:
            if c == "]":
                in_class = False
        elif c == "[":
            in_class = True
        elif c == "/":
            j += 1
            while j < n and _is_ident_char(text[j]):
                j += 1  # flags
            return j
        j += 1
    return None


# --------------------------------------------------------------------------
# Tree / CLI
# --------------------------------------------------------------------------


def iter_source_files(root: str | os.PathLike):
    root = Path(root)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for fn in sorted(filenames):
            p = Path(dirpath) / fn
            if lang_for_path(p) and not p.is_symlink():
                yield p


def strip_tree(root: str | os.PathLike) -> list[Path]:
    """Strip every supported source file under ``root`` in place.
    Returns the list of files that changed."""
    changed = []
    for p in iter_source_files(root):
        try:
            src = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        new = strip(src, lang_for_path(p))
        if new != src:
            p.write_text(new, encoding="utf-8", newline="")
            changed.append(p)
    return changed


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+", help="directories to strip in place (or files with --stdout)")
    ap.add_argument("--stdout", action="store_true", help="print stripped file(s) instead of writing")
    args = ap.parse_args(argv)
    for path in args.paths:
        p = Path(path)
        if args.stdout:
            files = [p] if p.is_file() else list(iter_source_files(p))
            for f in files:
                sys.stdout.write(strip(f))
            continue
        if p.is_file():
            lang = lang_for_path(p)
            if lang:
                p.write_text(strip(p, lang), encoding="utf-8", newline="")
                print(f"stripped {p}")
            continue
        if not p.is_dir():
            print(f"not found: {p}", file=sys.stderr)
            return 2
        changed = strip_tree(p)
        print(f"stripped {len(changed)} file(s) under {p}")
    return 0


if __name__ == "__main__":
    from . import utf8_stdio
    utf8_stdio()
    sys.exit(main())
