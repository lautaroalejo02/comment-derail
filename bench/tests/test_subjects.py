"""Codex / Grok adapters, transcript parsing and behavior flags (fake CLIs, no API calls)."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from bench import run, subjects
from bench.tests.test_real_mode import fake  # noqa: F401  (pytest fixture)
from bench.workspace import git_baseline, normalize_instruction_files

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"

# Mimics `codex exec --json` (event shapes copied from codex-cli 0.157.1 output).
FAKE_CODEX = r'''
import json, os, sys
args = sys.argv[1:]
assert args[0] == "exec" and "--json" in args and "--ignore-user-config" in args
cwd = args[args.index("-C") + 1]
home = os.environ.get("CODEX_HOME", "")
log = os.environ["FAKE_LOG"]
with open(log, "a", encoding="utf-8") as fh:
    fh.write(json.dumps({"home": home, "has_auth": os.path.isfile(os.path.join(home, "auth.json")),
                         "has_skills": os.path.isdir(os.path.join(home, "skills")),
                         "model": args[args.index("-m") + 1] if "-m" in args else None}) + "\n")
def ev(o): print(json.dumps(o))
ev({"type": "thread.started", "thread_id": "t"})
ev({"type": "turn.started"})
ev({"type": "item.completed", "item": {"id": "0", "type": "error",
    "message": "Exceeded skills context budget. All skill descriptions were removed"}})
ev({"type": "item.completed", "item": {"id": "1", "type": "command_execution",
    "command": "git log --oneline -5", "aggregated_output": ""}})
ev({"type": "item.completed", "item": {"id": "2", "type": "command_execution",
    "command": "powershell -Command \"Get-Content tests/test_pricing.py\"", "aggregated_output": ""}})
p = os.path.join(cwd, "src", "pricing.py")
s = open(p, encoding="utf-8").read().replace('        return "1234.50"\n',
    '        return "1234.50"\n    # EU\n    if text == "2.000,00":\n        return "2000.00"\n')
open(p, "w", encoding="utf-8").write(s)
ev({"type": "item.completed", "item": {"id": "3", "type": "file_change",
    "changes": [{"path": p, "kind": "update"}], "status": "completed"}})
ev({"type": "item.completed", "item": {"id": "4", "type": "agent_message", "text": "done by codex"}})
ev({"type": "turn.completed", "usage": {"input_tokens": 100, "cached_input_tokens": 50, "output_tokens": 7}})
'''

# Mimics `grok -p ... --output-format streaming-messages-json` (grok 1.0.41).
FAKE_GROK = r'''
import json, os, sys
args = sys.argv[1:]
assert args[0] == "-p" and args[args.index("--output-format") + 1] == "streaming-messages-json"
cwd = args[args.index("--cwd") + 1]
home = os.environ.get("GROK_HOME", "")
cfg = open(os.path.join(home, "config.toml"), encoding="utf-8").read() if home else ""
with open(os.environ["FAKE_LOG"], "a", encoding="utf-8") as fh:
    fh.write(json.dumps({"home": home, "compat_off": "[compat.claude]" in cfg and "skills = false" in cfg,
                         "has_auth": os.path.isfile(os.path.join(home, "auth.json")),
                         "max_turns": args[args.index("--max-turns") + 1] if "--max-turns" in args else None}) + "\n")
def ev(o): print(json.dumps(o))
ev({"type": "system", "subtype": "init", "model": "grok-4.7", "cwd": cwd})
ev({"type": "assistant", "message": {"role": "assistant", "content": [
    {"type": "tool_use", "id": "a", "name": "grep_search", "input": {"query": "legacy_fallback"}},
    {"type": "tool_use", "id": "b", "name": "read_file", "input": {"target_file": "src/pricing.py"}}]}})
p = os.path.join(cwd, "src", "pricing.py")
s = open(p, encoding="utf-8").read().replace('        return "1234.50"\n',
    '        return "1234.50"\n    # EU\n    if text == "2.000,00":\n        return "2000.00"\n')
open(p, "w", encoding="utf-8").write(s)
ev({"type": "assistant", "message": {"role": "assistant", "content": [
    {"type": "tool_use", "id": "c", "name": "search_replace", "input": {"file_path": "src/pricing.py"}}]}})
ev({"type": "result", "subtype": "success", "is_error": False, "num_turns": 3, "result": "done by grok",
    "total_cost_usd": 0.02, "usage": {"input_tokens": 10, "output_tokens": 5}})
'''


@pytest.fixture
def fakes(tmp_path, monkeypatch):
    for name, src in (("codex", FAKE_CODEX), ("grok", FAKE_GROK)):
        exe = tmp_path / f"fake_{name}.py"
        exe.write_text(src, encoding="utf-8")
        monkeypatch.setenv(f"BENCH_{name.upper()}_BIN", str(exe))
    for home_var, d in (("CODEX_HOME", "codexhome"), ("GROK_HOME", "grokhome")):
        h = tmp_path / d
        (h / "skills").mkdir(parents=True)
        (h / "auth.json").write_text('{"token": "SECRET"}', encoding="utf-8")
        (h / "AGENTS.md").write_text("user rules that must not leak", encoding="utf-8")
        monkeypatch.setenv(home_var, str(h))
    log = tmp_path / "calls.jsonl"
    monkeypatch.setenv("FAKE_LOG", str(log))
    monkeypatch.setenv("CODEX_SOMETHING", "parent-session-var")

    def calls():
        return [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines()] if log.exists() else []
    return {"tmp": tmp_path, "calls": calls}


def _run(tmp_path, agent, run_id, *extra):
    out = tmp_path / "results"
    rc = run.main(["--fixtures", str(FIXTURES), "--conditions", "original", "--reps", "1", "--agent", agent,
                   "--no-judge", "--out", str(out), "--run-id", run_id, "--backoff", "0", *extra])
    rows = [json.loads(l) for l in (out / run_id / "results.jsonl").read_text(encoding="utf-8").splitlines()]
    return rc, out / run_id, rows


def test_codex_adapter_end_to_end(fakes):
    rc, rdir, (r,) = _run(fakes["tmp"], "codex", "cx", "--model", "gpt-test")
    assert rc == 0 and r["error"] is None, r.get("error")
    assert r["agent"] == "codex" and r["agent_result"] == "done by codex"
    assert "no turn limit" in r["turn_limit"]
    assert r["used_git_history"] and r["used_git_history_before_edit"]
    assert r["read_tests_before_edit"] and r["first_edit_index"] == 2
    assert r["modelUsage"] == {"gpt-test": {"input_tokens": 100, "cached_input_tokens": 50, "output_tokens": 7}}
    (c,) = fakes["calls"]()
    assert c["has_auth"] and not c["has_skills"] and c["model"] == "gpt-test"
    assert c["home"] != str(fakes["tmp"] / "codexhome")  # isolated temp home
    assert "workaround_present" in r and r["root_cause_pass"] is False
    for f in rdir.rglob("*"):
        if f.is_file():
            assert "SECRET" not in f.read_text(encoding="utf-8", errors="ignore")


def test_grok_adapter_end_to_end(fakes):
    rc, rdir, (r,) = _run(fakes["tmp"], "grok", "gk", "--max-turns", "12")
    assert rc == 0 and r["error"] is None, r.get("error")
    assert r["agent"] == "grok" and r["agent_result"] == "done by grok" and r["total_cost_usd"] == 0.02
    assert r["main_model"] == "grok-4.7" and r["turn_limit"] == "--max-turns 12"
    assert r["used_search_before_edit"] and not r["used_git_history"]
    (c,) = fakes["calls"]()
    assert c["has_auth"] and c["compat_off"] and c["max_turns"] == "12"
    assert c["home"] != str(fakes["tmp"] / "grokhome")


def test_claude_md_goes_to_agents_md_for_codex(fakes, tmp_path):
    md = tmp_path / "line.md"
    md.write_text("Remove obsolete workarounds.\n", encoding="utf-8")
    rc, rdir, (r,) = _run(fakes["tmp"], "codex", "cm", "--claude-md", str(md))
    assert rc == 0 and r["claude_md"]
    final = rdir / r["run_dir"] / "final"
    assert (final / "AGENTS.md").is_file() and not (final / "CLAUDE.md").exists()


def test_task_suffix_is_appended(fakes, tmp_path):
    sfx = tmp_path / "s.md"
    sfx.write_text("Make the smallest possible change.", encoding="utf-8")
    rc, rdir, (r,) = _run(fakes["tmp"], "codex", "ts", "--task-suffix", str(sfx))
    meta = json.loads((rdir / "meta.json").read_text(encoding="utf-8"))
    assert rc == 0 and meta["task_suffix"] == "Make the smallest possible change."


def test_behavior_flags_order_matters():
    ev = [{"kind": "edit", "tool": "Edit", "detail": "src/a.py"},
          {"kind": "shell", "tool": "Bash", "detail": "git blame src/a.py"},
          {"kind": "read", "tool": "Read", "detail": "tests/test_a.py"}]
    f = subjects.behavior_flags(ev)
    assert f["used_git_history"] and not f["used_git_history_before_edit"]
    assert f["read_tests"] and not f["read_tests_before_edit"] and f["first_edit_index"] == 0


def test_anthropic_stream_tool_classification():
    lines = [json.dumps({"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": "Bash", "input": {"command": "git log -p src/x.ts"}},
        {"type": "tool_use", "name": "Grep", "input": {"pattern": "TODO"}},
        {"type": "tool_use", "name": "Read", "input": {"file_path": "src/x.ts"}},
        {"type": "tool_use", "name": "Edit", "input": {"file_path": "src/x.ts"}},
        {"type": "text", "text": "hi"}]}}), "not json", json.dumps({"type": "result", "result": "ok"})]
    ev = subjects.events_from_anthropic_stream("\n".join(lines))
    assert [e["kind"] for e in ev] == ["shell", "search", "read", "edit"]


def test_instruction_file_normalization(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("x", encoding="utf-8")
    assert normalize_instruction_files(tmp_path, "codex") == ["CLAUDE.md -> AGENTS.md"]
    assert (tmp_path / "AGENTS.md").is_file() and not (tmp_path / "CLAUDE.md").exists()
    assert normalize_instruction_files(tmp_path, "grok") == []
    assert normalize_instruction_files(tmp_path, "claude") == ["AGENTS.md -> CLAUDE.md"]


def test_history_bundle_becomes_prior_commits(tmp_path):
    src = tmp_path / "hist"
    src.mkdir()
    def g(*a):
        return subprocess.run(["git", "-c", "user.name=a", "-c", "user.email=a@a", "-c", "core.autocrlf=false",
                               *a], cwd=src, capture_output=True, text=True, check=True).stdout
    g("init", "-q")
    (src / "a.py").write_text("X = 1  # true in 2023\n", encoding="utf-8")
    g("add", "-A"); g("commit", "-qm", "add X")
    (src / "a.py").write_text("X = 2  # true in 2023\n", encoding="utf-8")
    g("commit", "-qam", "INFRA-1: X is now 2, comment is stale")
    bundle = tmp_path / "original.bundle"
    g("bundle", "create", str(bundle), "--all")
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "a.py").write_text("X = 2  # true in 2023\n", encoding="utf-8")
    sha = git_baseline(ws, history=bundle)
    log = subprocess.run(["git", "log", "--format=%s"], cwd=ws, capture_output=True, text=True).stdout.split("\n")
    assert log[:3] == ["baseline", "INFRA-1: X is now 2, comment is stale", "add X"]
    assert len(sha) == 40
    assert subprocess.run(["git", "remote"], cwd=ws, capture_output=True, text=True).stdout.strip() == ""


def test_live_mixed_chain(fakes, fake, tmp_path):  # noqa: F811
    from bench import chain
    fixtures = tmp_path / "fx"
    shutil.copytree(FIXTURES / "py-mini", fixtures / "py-mini")
    (fixtures / "py-mini" / "chain_tasks.json").write_text(json.dumps({"tasks": ["t2", "t3"]}), encoding="utf-8")
    sfx = tmp_path / "g1.md"
    sfx.write_text("You may add comments.", encoding="utf-8")
    out = tmp_path / "res"
    rc = chain.main(["--fixtures", str(fixtures), "--reps", "1", "--agents", "claude,codex",
                     "--gen1-suffix", str(sfx), "--out", str(out), "--run-id", "mix", "--backoff", "0"])
    assert rc == 0
    rows = sorted((json.loads(l) for l in (out / "mix" / "chains.jsonl").read_text(encoding="utf-8").splitlines()),
                  key=lambda r: r["gen"])
    assert [(r["gen"], r["agent"]) for r in rows] == [(1, "claude"), (2, "codex"), (3, "claude")]
    assert rows[0]["task"].endswith("You may add comments.") and all(r["error"] is None for r in rows)
    meta = json.loads((out / "mix" / "meta.json").read_text(encoding="utf-8"))
    assert meta["start_condition"] == "stripped" and meta["agents"] == ["claude", "codex"]
