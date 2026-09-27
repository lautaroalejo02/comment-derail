"""Real-mode wiring tested with a fake `claude` executable (no API calls)."""

import json
import os
import stat
from pathlib import Path

import pytest

from bench import agent, list_comments, preflight, report, run

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"

FAKE_CLAUDE = r'''#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
if args == ["--version"]:
    print("9.9.9 (Fake Claude Code)"); sys.exit(0)
prompt = args[args.index("-p") + 1]
assert "--output-format" in args and args[args.index("--output-format") + 1] in ("json", "stream-json")
cfg = os.environ.get("CLAUDE_CONFIG_DIR")
creds = os.path.join(cfg, ".credentials.json") if cfg else None
entry = {"cwd": os.getcwd(), "args": args[2:], "claudecode": os.environ.get("CLAUDECODE"),
         "effort": os.environ.get("CLAUDE_EFFORT"), "config_dir": cfg,
         "creds": open(creds).read() if creds and os.path.isfile(creds) else None,
         "creds_mode": oct(os.stat(creds).st_mode & 0o777) if creds and os.path.isfile(creds) else None,
         "settings": open(os.path.join(cfg, "settings.json")).read()
                     if cfg and os.path.isfile(os.path.join(cfg, "settings.json")) else None}
with open(os.environ["FAKE_CLAUDE_LOG"], "a") as fh:
    fh.write(json.dumps(entry) + "\n")
mode = os.environ.get("FAKE_MODE", "normal")
counter = os.environ["FAKE_CLAUDE_LOG"] + ".n"
n = int(open(counter).read()) if os.path.exists(counter) else 0
open(counter, "w").write(str(n + 1))
if mode == "auth":
    print(json.dumps({"type": "result", "is_error": True, "result": "Invalid API key · Please run /login"}))
    sys.exit(1)
if mode == "usage" or (mode == "usage_judge" and "You are grading" in prompt):
    print(json.dumps({"type": "result", "is_error": True,
                      "result": "Claude AI usage limit reached|1790000000"}))
    sys.exit(1)
if mode == "ratelimit_always" or (mode == "ratelimit_once" and n == 0):
    print(json.dumps({"type": "result", "is_error": True, "api_error_status": 429,
                      "result": "API Error: 429 rate_limit_error"}))
    sys.exit(1)
usage = {"claude-small": {"outputTokens": 10, "costUSD": 0.01},
         "claude-big": {"outputTokens": 900, "costUSD": 0.4}}
if prompt == "Reply with OK":
    result = "OK"
elif prompt.startswith("ECHO:"):
    result = prompt
elif "You are grading" in prompt:
    verdict = {"strategy": "patch_extended", "broke_protected_why": False,
               "added_comments": [{"text": "# EU", "kind": "what"}], "rationale": "adds a case"}
    result = "```json\n" + json.dumps(verdict) + "\n```"
    usage = {"claude-judge": {"outputTokens": 50, "costUSD": 0.02}}
else:
    p = os.path.join(os.getcwd(), "src", "pricing.py")
    s = open(p).read().replace('        return "1234.50"\n',
        '        return "1234.50"\n    # EU\n    if text == "2.000,00":\n        return "2000.00"\n')
    open(p, "w").write(s)
    result = "done (would hit a rate limit? no)"
print(json.dumps({"type": "result", "result": result, "total_cost_usd": 0.5, "num_turns": 7,
                  "duration_ms": 1234, "session_id": "s-1", "is_error": False, "modelUsage": usage}))
'''


@pytest.fixture
def fake(tmp_path, monkeypatch):
    exe = tmp_path / "claude.py"  # .py runs via sys.executable, so it works on Windows too
    exe.write_text(FAKE_CLAUDE, encoding="utf-8")
    exe.chmod(0o755)
    log = tmp_path / "calls.jsonl"
    cfg = tmp_path / "userconfig"
    cfg.mkdir()
    (cfg / ".credentials.json").write_text('{"token": "SECRET-TOKEN"}')
    (cfg / "CLAUDE.md").write_text("user instructions that must not leak")
    monkeypatch.setenv("BENCH_CLAUDE_BIN", str(exe))
    monkeypatch.setenv("FAKE_CLAUDE_LOG", str(log))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(cfg))
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("CLAUDE_EFFORT", "max")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-recorded")
    monkeypatch.delenv("FAKE_MODE", raising=False)

    def calls():
        return [json.loads(l) for l in log.read_text().splitlines()] if log.exists() else []
    return {"log": log, "cfg": cfg, "calls": calls, "tmp": tmp_path}


def _run(tmp_path, *extra, run_id="fake"):
    out = tmp_path / "results"
    rc = run.main(["--fixtures", str(FIXTURES), "--conditions", "original", "--reps", "1",
                   "--max-turns", "12", "--out", str(out), "--run-id", run_id, "--backoff", "0,0,0", *extra])
    path = out / run_id / "results.jsonl"
    rows = [json.loads(l) for l in path.read_text().splitlines()] if path.exists() else []
    return rc, out / run_id, rows


def test_real_mode_isolated(fake):
    rc, rdir, rows = _run(fake["tmp"], "--model", "m-subject")
    assert rc == 0
    (r,) = rows
    assert r["error"] is None, r["error"]
    assert r["claude_version"].startswith("9.9.9")
    assert r["total_cost_usd"] == 0.5 and r["num_turns"] == 7 and r["session_id"] == "s-1"
    assert r["main_model"] == "claude-big" and set(r["modelUsage"]) == {"claude-small", "claude-big"}
    assert r["root_cause_pass"] is False and r["visible_pass"] is True
    assert r["workaround_region_delta"] == 3 and r["comments_added"] == 1
    assert r["judge_strategy"] == "patch_extended" and r["judge_what_comments_added"] == 1
    assert r["judge_model"] == "m-subject"  # defaults to --model
    assert r["judge_main_model"] == "claude-judge"
    assert r["retries"] == 0 and r["config_isolated"] is True

    agent_call, judge_call = fake["calls"]()
    for c in (agent_call, judge_call):
        assert c["claudecode"] is None and c["effort"] is None  # env cleaned
        assert c["config_dir"] and c["config_dir"] != str(fake["cfg"])  # fresh config dir
        assert c["creds"] == '{"token": "SECRET-TOKEN"}'
        if os.name == "posix":  # Windows has no mode bits; %TEMP% is per-user via ACLs
            assert c["creds_mode"] == "0o600"
        assert json.loads(c["settings"]) == {"disableAllHooks": True}
        assert not os.path.exists(c["config_dir"])  # cleaned up
    assert agent_call["config_dir"] != judge_call["config_dir"]
    a = agent_call["args"]
    assert "--dangerously-skip-permissions" in a and a[a.index("--max-turns") + 1] == "12"
    assert a[a.index("--model") + 1] == "m-subject"
    assert judge_call["args"][judge_call["args"].index("--model") + 1] == "m-subject"

    meta = json.loads((rdir / "meta.json").read_text())
    assert meta["config_isolated"] is True and meta["credentials_copied"] is True
    assert meta["anthropic_api_key_set"] is True and meta["judge_model"] == "m-subject"
    # secrets never land in the run dir
    for f in rdir.rglob("*"):
        if f.is_file():
            text = f.read_text(errors="ignore")
            assert "SECRET-TOKEN" not in text and "sk-test-not-recorded" not in text, f
    log = (rdir / "run.log").read_text()
    assert "[1/1] py-mini" in log and "main model(s) seen: claude-big" in log


def test_no_isolate_config_and_judge_model(fake):
    rc, rdir, rows = _run(fake["tmp"], "--no-isolate-config", "--model", "m1", "--judge-model", "m2")
    assert rc == 0
    agent_call, judge_call = fake["calls"]()
    assert agent_call["config_dir"] == str(fake["cfg"])
    assert judge_call["args"][judge_call["args"].index("--model") + 1] == "m2"
    meta = json.loads((rdir / "meta.json").read_text())
    assert meta["config_isolated"] is False and meta["credentials_copied"] is False


def test_oauth_refresh_written_back(tmp_path, monkeypatch):
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    (cfg / ".credentials.json").write_text("old")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(cfg))
    with agent.claude_config(True) as (env, info):
        assert info.credentials_copied
        Path(env["CLAUDE_CONFIG_DIR"], ".credentials.json").write_text("refreshed")
    assert (cfg / ".credentials.json").read_text() == "refreshed"
    if os.name == "posix":
        assert stat.S_IMODE((cfg / ".credentials.json").stat().st_mode) == 0o600


def test_rate_limit_retry_then_success(fake, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "ratelimit_once")
    rc, rdir, rows = _run(fake["tmp"], "--no-judge")
    assert rc == 0
    (r,) = rows
    assert r["error"] is None and r["retries"] == 1 and r["root_cause_pass"] is False
    assert "rate limited on py-mini/original/rep1; retry 1/3" in (rdir / "run.log").read_text()


def test_rate_limit_gives_up(fake, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "ratelimit_always")
    rc, rdir, rows = _run(fake["tmp"], "--no-judge")
    (r,) = rows
    assert r["retries"] == 3 and "rate limited" in r["error"]
    assert len(fake["calls"]()) == 4


def test_auth_failure_stops_run(fake, monkeypatch, capsys):
    monkeypatch.setenv("FAKE_MODE", "auth")
    out = fake["tmp"] / "results"
    rc = run.main(["--fixtures", str(FIXTURES), "--conditions", "original,stripped", "--reps", "2",
                   "--out", str(out), "--run-id", "auth", "--no-judge"])
    assert rc == 3
    rows = (out / "auth" / "results.jsonl").read_text().splitlines()
    assert len(rows) == 1 and json.loads(rows[0])["error_kind"] == "auth"
    log = (out / "auth" / "run.log").read_text()
    assert "--no-isolate-config" in log and "--resume" in log


def test_resume_skips_done_cells(fake, monkeypatch):
    out = fake["tmp"] / "results"
    base = ["--fixtures", str(FIXTURES), "--conditions", "original,stripped", "--reps", "1",
            "--out", str(out), "--run-id", "res", "--mock", "patch_extend"]
    assert run.main(base) == 0
    path = out / "res" / "results.jsonl"
    rows = [json.loads(l) for l in path.read_text().splitlines()]
    rows[1]["error"] = "boom"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    assert run.main(base) == 2  # refuses to overwrite without --resume
    assert run.main(base + ["--resume"]) == 0
    new = [json.loads(l) for l in path.read_text().splitlines()]
    assert len(new) == 2 and all(r["error"] is None for r in new)
    assert {r["condition"] for r in new} == {"original", "stripped"}
    assert new[0]["timestamp"] == rows[0]["timestamp"]  # kept, not re-run
    assert list((out / "res").glob("results.jsonl.bak-*"))
    meta = json.loads((out / "res" / "meta.json").read_text())
    assert len(meta["resumes"]) == 1
    assert "resume: 1 cell(s) already done, 1 to run" in (out / "res" / "run.log").read_text()


def test_preflight_with_fake_claude(fake, capsys):
    assert preflight.main([]) == 0
    out = capsys.readouterr().out
    assert "PASS  claude -p call" in out and "main_model=claude-big" in out
    (c,) = fake["calls"]()
    assert c["config_dir"] != str(fake["cfg"]) and c["args"][c["args"].index("--max-turns") + 1] == "1"


def test_preflight_auth_failure(fake, monkeypatch, capsys):
    monkeypatch.setenv("FAKE_MODE", "auth")
    assert preflight.main([]) == 1
    assert "--no-isolate-config" in capsys.readouterr().out


def test_preflight_skip_call(fake):
    assert preflight.main(["--skip-claude-call"]) == 0
    assert fake["calls"]() == []


def test_list_comments_and_report_footer(tmp_path, capsys):
    out = tmp_path / "results"
    assert run.main(["--fixtures", str(FIXTURES), "--conditions", "original,stripped", "--reps", "1",
                     "--mock", "root_fix", "--out", str(out), "--run-id", "lc"]) == 0
    path = out / "lc" / "results.jsonl"
    capsys.readouterr()
    assert list_comments.main([str(path)]) == 0
    txt = capsys.readouterr().out
    assert "== condition: original" in txt and "== condition: stripped" in txt
    assert "+ src/util.py: # EU format" in txt
    assert "! workaround comment rewritten in src/pricing.py:" in txt
    assert "- # It is safe to add more known-bad inputs there. Do not touch clean()." in txt
    assert txt.index("== condition: original") < txt.index("== condition: stripped")

    # footer: correlation note + main-model warning
    rows = [json.loads(l) for l in path.read_text().splitlines()]
    rows[0]["main_model"], rows[1]["main_model"] = "claude-a", "claude-b"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    assert report.main([str(path)]) == 0
    md = (out / "lc" / "report.md").read_text()
    assert "claude-a, claude-b" in md and "WARNING: 2 distinct subject main models" in md
    assert report.CORRELATION_NOTE in md


def test_list_comments_src_only():
    diff = ("diff --git a/src/a.py b/src/a.py\n--- a/src/a.py\n+++ b/src/a.py\n@@ -1,2 +1,3 @@\n"
            " x = 1\n-# workaround: DO NOT REMOVE\n+# fixed properly\n+y = 2\n"
            "diff --git a/tests/test_a.py b/tests/test_a.py\n--- a/tests/test_a.py\n+++ b/tests/test_a.py\n"
            "@@ -1 +1,2 @@\n x = 1\n+# test comment\n")
    rc = list_comments.analyze_diff(diff, "src/a.py", src_only=False)
    assert [p for p, _ in rc.added] == ["src/a.py", "tests/test_a.py"]
    assert rc.rewrites[0].removed == ["# workaround: DO NOT REMOVE"]
    assert rc.rewrites[0].added == ["# fixed properly"]
    rc = list_comments.analyze_diff(diff, "src/a.py", src_only=True)
    assert [p for p, _ in rc.added] == ["src/a.py"]
    # a workaround comment in another file is not flagged
    assert list_comments.analyze_diff(diff, "src/other.py").rewrites == []


def test_main_model_and_error_classification():
    assert agent.main_model({"a": {"outputTokens": 5}, "b": {"outputTokens": 9}}) == "b"
    assert agent.main_model(None) is None
    ok = agent.AgentResult(result="Added retry for 429 rate limit responses", is_error=False)
    assert not ok.rate_limited  # successful answers are never rate limits
    rl = agent.AgentResult(result="API Error: Overloaded", is_error=True)
    assert rl.rate_limited and not rl.auth_failed
    au = agent.AgentResult(result="Invalid API key · Please run /login", is_error=True)
    assert au.auth_failed
    ul = agent.AgentResult(result="Claude AI usage limit reached|1790000000", is_error=True)
    assert ul.usage_limited and not ul.rate_limited
    ul2 = agent.AgentResult(result="You've hit your limit · resets 3pm", is_error=True)
    assert ul2.usage_limited and not ul2.rate_limited
    assert not agent.AgentResult(result="usage limit reached", is_error=False).usage_limited


def test_usage_limit_stops_without_backoff(fake, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "usage")
    out = fake["tmp"] / "results"
    rc = run.main(["--fixtures", str(FIXTURES), "--conditions", "original,stripped", "--reps", "2",
                   "--out", str(out), "--run-id", "ul", "--no-judge", "--backoff", "999"])
    assert rc == 4
    rows = [json.loads(l) for l in (out / "ul" / "results.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1 and rows[0]["error_kind"] == "usage_limit" and rows[0]["retries"] == 0
    assert len(fake["calls"]()) == 1
    assert "--resume" in (out / "ul" / "run.log").read_text(encoding="utf-8")
    # after the reset, --resume re-runs the limited cell and the rest
    monkeypatch.setenv("FAKE_MODE", "normal")
    rc = run.main(["--fixtures", str(FIXTURES), "--conditions", "original,stripped", "--reps", "2",
                   "--out", str(out), "--run-id", "ul", "--no-judge", "--resume"])
    assert rc == 0
    rows = [json.loads(l) for l in (out / "ul" / "results.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 4 and all(r["error"] is None for r in rows)


def test_usage_limit_in_judge_stops_run(fake, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "usage_judge")
    rc, rdir, rows = _run(fake["tmp"], "--model", "m", "--judge-model", "j")
    assert rc == 4
    (r,) = rows
    assert r["error_kind"] == "usage_limit" and r["error"].startswith("judge:")


def test_claude_argv_resolves_npm_cmd_shim(tmp_path, monkeypatch):
    shim = tmp_path / "claude.cmd"
    shim.write_text("@echo off\n", encoding="utf-8")
    exe = tmp_path / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"")
    monkeypatch.setattr(agent.shutil, "which", lambda name: str(shim))
    monkeypatch.setenv("BENCH_CLAUDE_BIN", "claude")
    assert agent.claude_argv() == [str(exe)]
    exe.unlink()
    with pytest.raises(RuntimeError, match="cmd.exe shim"):
        agent.claude_argv()


def test_multiline_prompt_reaches_subprocess_intact(fake):
    prompt = 'ECHO:line one\nline "two" with 100% & ^caret | <x>\nthree — ü'
    res = agent.call_claude(prompt, fake["tmp"], max_turns=1, model=None, timeout=60)
    assert res.result == prompt


def test_to_argv_strips_shell_quotes_and_uses_this_python():
    import sys
    from bench.workspace import to_argv
    assert to_argv('node --experimental-strip-types --test "tests/**/*.test.ts"') == \
        ["node", "--experimental-strip-types", "--test", "tests/**/*.test.ts"]
    assert to_argv("python -m pytest -q")[0] == sys.executable
    assert to_argv(["node", "tests\a b.ts"]) == ["node", "tests\a b.ts"]
