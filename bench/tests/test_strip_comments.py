import ast
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from bench.strip_comments import strip, strip_tree


def d(s: str) -> str:
    return textwrap.dedent(s).lstrip("\n")


# ---------------------------------------------------------------- python


def test_py_removes_comments_keeps_strings_with_hash():
    src = d('''
        x = "a # not a comment"  # trailing
        # full line
        y = 'b // also not'
        z = f"{x} # inside fstring"
        ''')
    out = strip(src, "python")
    assert "trailing" not in out and "full line" not in out
    assert '"a # not a comment"' in out
    assert "'b // also not'" in out
    assert 'f"{x} # inside fstring"' in out
    assert out.splitlines()[0] == 'x = "a # not a comment"'
    assert out.splitlines()[1] == ""


def test_py_docstrings_preserved():
    src = d('''
        def f():
            """Docstring # with hash."""
            # comment
            return 1
        ''')
    out = strip(src, "python")
    assert '"""Docstring # with hash."""' in out
    assert "# comment" not in out


def test_py_shebang_preserved_coding_dropped():
    src = "#!/usr/bin/env python3\n# -*- coding: utf-8 -*-\nprint(1)  # hi\n"
    out = strip(src, "python")
    assert out.startswith("#!/usr/bin/env python3\n")
    assert "coding" not in out
    assert out.endswith("print(1)\n")


def test_py_indentation_intact_and_line_count_kept():
    src = d('''
        class A:
            # comment in class
            def m(self, x):
                if x:
                    # only a comment here before code
                    return 1  # one
                # dedented comment
                    # weirdly indented comment
                return 2
        ''')
    out = strip(src, "python")
    ast.parse(out)
    assert len(out.splitlines()) == len(src.splitlines())
    ns = {}
    exec(out, ns)
    assert ns["A"]().m(True) == 1 and ns["A"]().m(False) == 2
    for line in out.splitlines():
        assert line == line.rstrip()


def test_py_idempotent():
    src = d('''
        #!/usr/bin/env python
        import os  # os
        # x
        S = "# keep"
        def f():
            """doc"""  # c
            return S
        ''')
    once = strip(src, "python")
    assert strip(once, "python") == once


def test_py_no_trailing_newline():
    assert strip("x = 1  # c", "python") == "x = 1"


def test_py_multiline_string_with_hash_kept():
    src = 's = """\n# not a comment\n"""\n# real\n'
    out = strip(src, "python")
    assert "# not a comment" in out and "real" not in out


# ---------------------------------------------------------------- js / ts


def test_js_strings_containing_comment_tokens():
    src = d('''
        const a = "http://example.com"; // url
        const b = 'a /* not */ b'; /* block */
        const c = "#hash";
        ''')
    out = strip(src, "typescript")
    assert '"http://example.com";' in out
    assert "'a /* not */ b';" in out
    assert '"#hash"' in out
    assert "url" not in out and "block" not in out


def test_js_template_literals_with_nesting():
    src = d('''
        const t = `line // not comment ${ x /* real */ + `inner // nope ${y}` } tail /* no */`;
        const u = `${ {a: 1}.a } // still template`; // real2
        ''')
    out = strip(src, "typescript")
    assert "line // not comment" in out
    assert "inner // nope ${y}" in out
    assert "tail /* no */" in out
    assert "real" not in out
    assert "${ {a: 1}.a } // still template`;" in out
    assert "real2" not in out


def test_js_regex_with_slashes():
    src = d('''
        const re = /https?:\\/\\/[^/]+/g; // strip host
        const r2 = x.replace(/\\/\\//, "");
        const r3 = [/a\\/*b/, /[/*]/];
        function f() { return /\\/\\/+/.test(s); }
        const div = a / b / c; // division
        ''')
    out = strip(src, "typescript")
    assert r"/https?:\/\/[^/]+/g;" in out
    assert r"x.replace(/\/\//, " in out
    assert r"[/a\/*b/, /[/*]/]" in out
    assert r"return /\/\/+/.test(s);" in out
    assert "const div = a / b / c;" in out
    assert "strip host" not in out and "division" not in out


def test_js_block_comment_keeps_lines_and_tokens():
    src = "let a/**/= 1;\n/*\n * doc\n */\nlet b = 2; /* x */ let c = 3;\n"
    out = strip(src, "typescript")
    assert len(out.split("\n")) == len(src.split("\n"))
    assert out.split("\n")[0] in ("let a = 1;", "let a= 1;")
    assert out.split("\n")[1:4] == ["", "", ""]
    assert "let b = 2;" in out and "let c = 3;" in out and "x" not in out.split("\n")[4].replace("let", "")


def test_js_shebang_preserved():
    src = "#!/usr/bin/env node\n// comment\nconsole.log('//');\n"
    out = strip(src, "javascript")
    assert out == "#!/usr/bin/env node\n\nconsole.log('//');\n"


def test_js_indentation_intact():
    src = d('''
        function f(x) {
            // leading
            if (x) {
                return 1; // one
            }
            /* block */ return 2;
        }
        ''')
    out = strip(src, "typescript")
    lines = out.splitlines()
    assert lines[1] == ""
    assert lines[2] == "    if (x) {"
    assert lines[3] == "        return 1;"
    assert lines[5] == "    return 2;"


def test_js_idempotent():
    src = d('''
        #!/usr/bin/env node
        const u = "a//b"; // c
        const r = /\\/\\//; /* d */
        const t = `x ${ y /* e */ } // z`;
        /**
         * JSDoc
         */
        export function g() { return 1 }
        ''')
    once = strip(src, "typescript")
    assert strip(once, "typescript") == once


def test_js_output_still_runs(tmp_path):
    src = d('''
        const re = /\\/\\//g; // regex with slashes
        const s = "a//b" + `c ${ "d//e" /* x */ } f`; // concat
        /* multi
           line */
        console.log(JSON.stringify([s.replace(re, "|"), 10 / 2 / 5]));
        ''')
    out = strip(src, "javascript")
    f = tmp_path / "a.mjs"
    f.write_text(out)
    p = subprocess.run(["node", str(f)], capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    assert p.stdout.strip() == '["a|bc d|e f",1]'


# ---------------------------------------------------------------- tree / api


def test_strip_accepts_path_and_tree(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "a.py").write_text("x = 1  # c\n")
    (tmp_path / "pkg" / "b.ts").write_text("let y = 2; // c\n")
    (tmp_path / "pkg" / "README.md").write_text("# title\n")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "m.js").write_text("// keep\n")
    assert strip(tmp_path / "pkg" / "a.py") == "x = 1\n"
    assert strip(str(tmp_path / "pkg" / "b.ts")) == "let y = 2;\n"
    changed = strip_tree(tmp_path)
    assert len(changed) == 2
    assert (tmp_path / "pkg" / "README.md").read_text() == "# title\n"
    assert (tmp_path / "node_modules" / "m.js").read_text() == "// keep\n"


def test_cli_strips_directory(tmp_path):
    (tmp_path / "a.py").write_text("#!/usr/bin/env python\nx = 1  # c\n")
    root = Path(__file__).resolve().parents[2]
    p = subprocess.run([sys.executable, "-m", "bench.strip_comments", str(tmp_path)],
                       cwd=root, capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    assert (tmp_path / "a.py").read_text() == "#!/usr/bin/env python\nx = 1\n"


def test_unknown_lang():
    with pytest.raises(ValueError):
        strip("x", "cobol")
