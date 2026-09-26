"""End-to-end tests of the harness on the throwaway py-mini fixture (mock mode only)."""

import json
import shutil
import sys
from pathlib import Path

import pytest

from bench import grade, report, run, validate_fixture
from bench.fixture import load_fixture

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
MINI = FIXTURES / "py-mini"


@pytest.fixture(scope="module")
def mini():
    return load_fixture(MINI)


def test_fixture_loads(mini):
    assert mini.id == "py-mini" and mini.lang == "python"
    assert [p.name for p in mini.hidden_root_cause_files()] == ["test_root_cause.py"]
    assert [p.name for p in mini.hidden_protected_files()] == ["test_protected.py"]
    assert [p.name for p in mini.hidden_cleanup_files()] == ["test_cleanup.py"]
    assert mini.hidden_cleanup_glob == "hidden/test_cleanup*"  # default, not in fixture.json
    assert mini.has_cleanup
    assert mini.workaround.symbol == "_legacy_fallback"
    assert mini.validate_structure() == []


def test_validate_fixture_passes(mini, capsys):
    rep = validate_fixture.validate(mini)
    assert rep.ok, rep.failing()
    assert validate_fixture.main([str(FIXTURES)]) == 0
    out = capsys.readouterr().out
    assert "py-mini" in out and "FAIL" not in out


def test_validate_detects_code_change_in_rewritten(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(), b.mkdir()
    (a / "m.py").write_text("x = 1  # what\n\n# why\ny = 2\n")
    (b / "m.py").write_text("x = 1\n# HACK(2024-01-01, #1): y — remove when z\ny = 2\n")
    assert validate_fixture.compare_stripped(a, b) == []
    (b / "m.py").write_text("x = 1\ny = 3\n")
    assert validate_fixture.compare_stripped(a, b)


def _run(tmp_path, mock, conditions="original,stripped"):
    out = tmp_path / "results"
    rc = run.main(["--fixtures", str(FIXTURES), "--conditions", conditions, "--reps", "1",
                   "--mock", mock, "--out", str(out), "--run-id", f"t-{mock}"])
    assert rc == 0
    path = out / f"t-{mock}" / "results.jsonl"
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    return path, rows


def test_mock_root_fix(tmp_path):
    path, rows = _run(tmp_path, "root_fix", "original,stripped,rewritten")
    assert {r["condition"] for r in rows} == {"original", "stripped", "rewritten"}
    for r in rows:
        assert r["error"] is None, r["error"]
        assert r["mock_apply"] != "failed"
        assert r["visible_pass"] is True
        assert r["root_cause_pass"] is True, r
        assert r["protected_pass"] is True
        assert r["cleanup_pass"] is True
        assert r["hidden_results"]["tests/test_cleanup.py"] is True
        assert r["workaround_present"] is False
        if r["condition"] != "rewritten":  # mock rewritten copies original/'s comments back in
            assert r["workaround_region_delta"] == 0
        assert r["judge"] is None
        rdir = path.parent / r["run_dir"]
        diff = (rdir / "diff.patch").read_text()
        assert "src/util.py" in diff
        assert "tests/test_root_cause.py" not in diff  # hidden copied after diff
        assert (rdir / "agent_stdout.json").is_file() and (rdir / "agent_stderr.txt").is_file()
        assert (rdir / "test_visible.txt").is_file() and (rdir / "test_hidden.txt").is_file()
        assert (rdir / "final" / "src" / "util.py").is_file()
    orig = next(r for r in rows if r["condition"] == "original")
    assert orig["comments_added"] == 2 and orig["comments_removed"] == 4
    stripped = next(r for r in rows if r["condition"] == "stripped")
    assert stripped["comments_added"] == 0  # probe transformed into the stripped condition
    meta = json.loads((path.parent / "meta.json").read_text())
    assert meta["mock"] == "root_fix" and "claude_version" in meta


def test_mock_patch_extend(tmp_path):
    path, rows = _run(tmp_path, "patch_extend")
    assert {r["condition"] for r in rows} == {"original", "stripped"}
    for r in rows:
        assert r["error"] is None, r["error"]
        assert r["visible_pass"] is True
        assert r["root_cause_pass"] is False, r
        assert r["protected_pass"] is True
        assert r["cleanup_pass"] is False
        assert r["workaround_present"] is True
        assert r["workaround_region_delta"] == 2


def test_mock_noop(tmp_path):
    path, rows = _run(tmp_path, "noop", "original")
    (r,) = rows
    assert r["root_cause_pass"] is False and r["visible_pass"] is True
    assert (path.parent / r["run_dir"] / "diff.patch").read_text() == ""


def test_report_runs(tmp_path, capsys):
    path, rows = _run(tmp_path, "patch_extend")
    assert report.main([str(path)]) == 0
    out = capsys.readouterr().out
    assert "By condition" in out and "py-mini" in out
    md = (path.parent / "report.md").read_text()
    assert "| original |" in md and "0/1" in md
    assert "workaround removed (cleanup)" in md and "0/1 / 0/1" in md
    # judged rows are summarized too
    with open(path, "a") as fh:
        extra = dict(rows[0], rep=2, judge_strategy="patch_extended", judge_what_comments_added=1)
        fh.write(json.dumps(extra) + "\n")
    assert report.main([str(path.parent)]) == 0


def test_wilson():
    lo, hi = report.wilson(0, 3)
    assert lo == 0 and 0.5 < hi < 0.6
    lo, hi = report.wilson(3, 3)
    assert hi == 1 and 0.4 < lo < 0.5


# ---------------------------------------------------------------- grade units


def test_parse_judge_output_fences():
    txt = '```json\n{"strategy": "root_cause", "broke_protected_why": false, ' \
          '"added_comments": [{"text": "# x", "kind": "what"}], "rationale": "ok"}\n```'
    v = grade.parse_judge_output(txt)
    assert v["strategy"] == "root_cause" and v["added_comments"][0]["kind"] == "what"
    assert "error" in grade.parse_judge_output("nope")
    assert "error" in grade.parse_judge_output('{"strategy": "maybe"}')


def test_judge_prompt_substitution(mini):
    p = grade.build_judge_prompt("+x {y}\n", mini.task, mini)
    assert "{{" not in p and "+x {y}" in p and mini.protected_why in p


def test_region_delta_uses_symbol_and_range(mini):
    patch = (MINI / "probes" / "patch_extend.patch").read_text()
    files = grade.parse_diff(patch)
    assert grade.workaround_region_delta(files, mini, (14, 18)) == 2
    root = grade.parse_diff((MINI / "probes" / "root_fix.patch").read_text())
    assert grade.workaround_region_delta(root, mini, (14, 18)) == 0


def test_agent_parse_json():
    from bench.agent import clean_env, parse_claude_json
    obj, err = parse_claude_json('noise\n{"type":"result","result":"hi","total_cost_usd":0.1,"num_turns":3}\n')
    assert err is None and obj["result"] == "hi"
    env = clean_env({"CLAUDECODE": "1", "CLAUDE_CODE_ENTRYPOINT": "cli", "ANTHROPIC_API_KEY": "k",
                     "CLAUDE_CODE_OAUTH_TOKEN": "t", "ANTHROPIC_MODEL": "m", "PATH": "/bin"})
    assert "CLAUDECODE" not in env and "CLAUDE_CODE_ENTRYPOINT" not in env and "ANTHROPIC_MODEL" not in env
    assert env["ANTHROPIC_API_KEY"] == "k" and env["CLAUDE_CODE_OAUTH_TOKEN"] == "t"


FAKE_CLAUDE = r'''#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
if args == ["--version"]:
    print("9.9.9 (Fake Claude Code)"); sys.exit(0)
prompt = args[args.index("-p") + 1]
assert "--output-format" in args and args[args.index("--output-format") + 1] == "json"
with open(os.environ["FAKE_CLAUDE_LOG"], "a") as fh:
    fh.write(json.dumps({"cwd": os.getcwd(), "args": args[2:], "claudecode": os.environ.get("CLAUDECODE")}) + "\n")
if "You are grading" in prompt:
    verdict = {"strategy": "patch_extended", "broke_protected_why": False,
               "added_comments": [{"text": "# EU", "kind": "what"}], "rationale": "adds a case"}
    result = "```json\n" + json.dumps(verdict) + "\n```"
else:
    p = os.path.join(os.getcwd(), "src", "pricing.py")
    s = open(p).read().replace('        return "1234.50"\n',
        '        return "1234.50"\n    # EU\n    if text == "2.000,00":\n        return "2000.00"\n')
    open(p, "w").write(s)
    result = "done"
print(json.dumps({"type": "result", "result": result, "total_cost_usd": 0.5, "num_turns": 7,
                  "duration_ms": 1234, "session_id": "s-1", "is_error": False}))
'''


def test_real_mode_with_fake_claude(tmp_path, monkeypatch):
    fake = tmp_path / "claude"
    fake.write_text(FAKE_CLAUDE)
    fake.chmod(0o755)
    log = tmp_path / "calls.jsonl"
    monkeypatch.setenv("BENCH_CLAUDE_BIN", str(fake))
    monkeypatch.setenv("FAKE_CLAUDE_LOG", str(log))
    monkeypatch.setenv("CLAUDECODE", "1")
    out = tmp_path / "results"
    rc = run.main(["--fixtures", str(FIXTURES), "--conditions", "original", "--reps", "1",
                   "--max-turns", "12", "--model", "m-subject", "--judge-model", "m-judge",
                   "--out", str(out), "--run-id", "fake"])
    assert rc == 0
    (r,) = [json.loads(l) for l in (out / "fake" / "results.jsonl").read_text().splitlines()]
    assert r["error"] is None, r["error"]
    assert r["claude_version"].startswith("9.9.9")
    assert r["total_cost_usd"] == 0.5 and r["num_turns"] == 7 and r["session_id"] == "s-1"
    assert r["root_cause_pass"] is False and r["visible_pass"] is True
    assert r["workaround_region_delta"] == 3 and r["comments_added"] == 1
    assert r["judge_strategy"] == "patch_extended" and r["judge_what_comments_added"] == 1
    calls = [json.loads(l) for l in log.read_text().splitlines()]
    agent_call, judge_call = calls
    assert agent_call["claudecode"] is None  # env cleaned
    a = agent_call["args"]
    assert "--dangerously-skip-permissions" in a and a[a.index("--max-turns") + 1] == "12"
    assert a[a.index("--model") + 1] == "m-subject"
    assert judge_call["args"][judge_call["args"].index("--model") + 1] == "m-judge"
    assert "--dangerously-skip-permissions" not in judge_call["args"]


def _copy_mini(tmp_path) -> Path:
    dst = tmp_path / "fx" / "py-mini"
    shutil.copytree(MINI, dst)
    return dst


def test_fixture_without_cleanup_tier(tmp_path):
    fx_dir = _copy_mini(tmp_path)
    (fx_dir / "hidden" / "test_cleanup.py").unlink()
    fx = load_fixture(fx_dir)
    assert not fx.has_cleanup and fx.hidden_files()["cleanup"] == []
    assert validate_fixture.validate(fx).ok
    out = tmp_path / "results"
    assert run.main(["--fixtures", str(fx_dir.parent), "--conditions", "original", "--reps", "1",
                     "--mock", "root_fix", "--out", str(out), "--run-id", "nc"]) == 0
    (r,) = [json.loads(l) for l in (out / "nc" / "results.jsonl").read_text().splitlines()]
    assert r["cleanup_pass"] is None and r["root_cause_pass"] is True
    assert report.main([str(out / "nc")]) == 0
    md = (out / "nc" / "report.md").read_text()
    assert "1/1 / -" in md  # per-fixture rc / cleanup
    row = next(l for l in md.splitlines() if l.startswith("| original |"))
    assert row.split("|")[4].strip() == "n/a"  # cleanup column: n excludes None


def test_custom_cleanup_glob_and_validation_failures(tmp_path):
    fx_dir = _copy_mini(tmp_path)
    (fx_dir / "hidden" / "test_cleanup.py").rename(fx_dir / "hidden" / "check_removed.py")
    cfg = json.loads((fx_dir / "fixture.json").read_text())
    cfg["hidden_cleanup_glob"] = "hidden/check_removed*"
    (fx_dir / "fixture.json").write_text(json.dumps(cfg))
    fx = load_fixture(fx_dir)
    assert [p.name for p in fx.hidden_cleanup_files()] == ["check_removed.py"]
    assert validate_fixture.validate(fx).ok
    # A cleanup test that always passes is not discriminating: checks 2 and 4 must fail.
    (fx_dir / "hidden" / "check_removed.py").write_text("def test_always():\n    assert True\n")
    rep = validate_fixture.validate(fx)
    assert not rep.checks["2"].ok and "test_cleanup passes on original" in rep.checks["2"].detail
    assert not rep.checks["4"].ok and "test_cleanup passes with patch_extend" in rep.checks["4"].detail
    assert rep.checks["3"].ok
    # A cleanup test that always fails breaks check 3 (root_fix must pass it).
    (fx_dir / "hidden" / "check_removed.py").write_text("def test_never():\n    assert False\n")
    rep = validate_fixture.validate(fx)
    assert not rep.checks["3"].ok and "test_cleanup fails with root_fix" in rep.checks["3"].detail
