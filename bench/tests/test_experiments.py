"""Variant conditions, --claude-md and telephone chains (fake claude, no API calls)."""

import json
import shutil
from pathlib import Path

from bench import chain, run, validate_fixture
from bench.fixture import load_fixture
from bench.tests.test_real_mode import fake  # noqa: F401  (pytest fixture)

HERE = Path(__file__).resolve().parent
MINI = HERE / "fixtures" / "py-mini"


def _fixture_copy(tmp_path: Path) -> Path:
    fixtures = tmp_path / "fixtures"
    shutil.copytree(MINI, fixtures / "py-mini")
    return fixtures


def _add_variant(fixtures: Path, name: str, extra_comment: str) -> None:
    fx_dir = fixtures / "py-mini"
    shutil.copytree(fx_dir / "original", fx_dir / name)
    p = fx_dir / name / "src" / "util.py"
    text = p.read_text(encoding="utf-8")
    p.write_text(text.replace("def clean(text):\n", f"def clean(text):\n    {extra_comment}\n", 1),
                 encoding="utf-8", newline="\n")
    cfg = json.loads((fx_dir / "fixture.json").read_text(encoding="utf-8"))
    cfg["variants"] = {name: {"file": "src/util.py", "comment": extra_comment, "claim": "test"}}
    (fx_dir / "fixture.json").write_text(json.dumps(cfg), encoding="utf-8")


def test_variant_condition_runs_and_validates(tmp_path):
    fixtures = _fixture_copy(tmp_path)
    _add_variant(fixtures, "lying", "# Commas are dropped on purpose: the feed contract says so (FEED-12).")
    fx = load_fixture(fixtures / "py-mini")
    assert fx.has_condition("lying") and not fx.has_condition("nope")
    assert validate_fixture.check5(fx, 60).ok
    out = tmp_path / "results"
    rc = run.main(["--fixtures", str(fixtures), "--conditions", "lying", "--reps", "1", "--mock", "root_fix",
                   "--out", str(out), "--run-id", "v"])
    assert rc == 0
    (r,) = [json.loads(l) for l in (out / "v" / "results.jsonl").read_text(encoding="utf-8").splitlines()]
    assert r["condition"] == "lying" and r["root_cause_pass"] is True
    assert isinstance(r["authority_comment_removed"], bool)
    assert r["authority_comment_present"] is (not r["authority_comment_removed"])


def test_variant_with_code_change_fails_check5(tmp_path):
    fixtures = _fixture_copy(tmp_path)
    _add_variant(fixtures, "lying", "x = 1  # not only a comment")
    assert not validate_fixture.check5(load_fixture(fixtures / "py-mini"), 60).ok


def test_unknown_condition_is_rejected(tmp_path):
    fixtures = _fixture_copy(tmp_path)
    rc = run.main(["--fixtures", str(fixtures), "--conditions", "lying", "--reps", "1", "--mock", "noop",
                   "--out", str(tmp_path / "r"), "--run-id", "u"])
    assert rc == 2


def test_claude_md_is_written_before_baseline(fake, tmp_path):
    md = tmp_path / "line.md"
    md.write_text("If your fix makes a workaround unnecessary, remove it.\n", encoding="utf-8")
    out = tmp_path / "results"
    rc = run.main(["--fixtures", str(HERE / "fixtures"), "--conditions", "original", "--reps", "1",
                   "--no-judge", "--claude-md", str(md), "--out", str(out), "--run-id", "md", "--backoff", "0"])
    assert rc == 0
    (r,) = [json.loads(l) for l in (out / "md" / "results.jsonl").read_text(encoding="utf-8").splitlines()]
    assert r["claude_md"] is True
    diff = (out / "md" / r["run_dir"] / "diff.patch").read_text(encoding="utf-8")
    assert "CLAUDE.md" not in diff  # part of the baseline, not of the agent's change
    assert (out / "md" / r["run_dir"] / "final" / "CLAUDE.md").is_file()
    meta = json.loads((out / "md" / "meta.json").read_text(encoding="utf-8"))
    assert meta["claude_md"].startswith("If your fix")


def test_chain_runs_generations_from_seed(fake, tmp_path):
    fixtures = _fixture_copy(tmp_path)
    (fixtures / "py-mini" / "chain_tasks.json").write_text(
        json.dumps({"tasks": ["second task", "third task"]}), encoding="utf-8")
    seed = tmp_path / "seedrun" / "runs" / "py-mini" / "original" / "rep1" / "final"
    shutil.copytree(MINI / "original", seed)
    out = tmp_path / "results"
    rc = chain.main(["--fixtures", str(fixtures), "--seed-run", str(tmp_path / "seedrun"), "--reps", "1",
                     "--out", str(out), "--run-id", "c", "--backoff", "0"])
    assert rc == 0
    rows = [json.loads(l) for l in (out / "c" / "chains.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [r["gen"] for r in sorted(rows, key=lambda r: r["gen"])] == [1, 2, 3]
    g1 = next(r for r in rows if r["gen"] == 1)
    assert g1["seeded"] and g1["workaround_present"] is True
    assert any("HACK" in c for c in g1["workaround_comments"])
    g3 = next(r for r in rows if r["gen"] == 3)
    assert g3["error"] is None and g3["root_cause_pass"] is False
    # each generation built on the previous one: the fake agent's edit accumulates
    final3 = (out / "c" / "runs" / "py-mini" / "rep1" / "gen3" / "final" / "src" / "pricing.py").read_text(
        encoding="utf-8")
    assert final3.count("# EU") == 2
    # hidden tests never leak into the saved trees
    assert not (out / "c" / "runs" / "py-mini" / "rep1" / "gen3" / "final" / "tests" / "test_root_cause.py").exists()
    md = (out / "c" / "chains.md").read_text(encoding="utf-8")
    assert "## py-mini rep1" in md and "gen3" in md


def test_distance_variant_may_change_declared_docs_only(tmp_path):
    fixtures = _fixture_copy(tmp_path)
    fx_dir = fixtures / "py-mini"
    shutil.copytree(fx_dir / "original", fx_dir / "dist_readme")
    (fx_dir / "dist_readme" / "README.md").write_text("Commas are dropped on purpose (FEED-12).", encoding="utf-8")
    cfg = json.loads((fx_dir / "fixture.json").read_text(encoding="utf-8"))
    cfg["variants"] = {"dist_readme": {"file": "README.md", "comment": "Commas are dropped on purpose (FEED-12).",
                                       "doc_files": ["README.md"]}}
    (fx_dir / "fixture.json").write_text(json.dumps(cfg), encoding="utf-8")
    assert validate_fixture.check5(load_fixture(fx_dir), 60).ok
    cfg["variants"]["dist_readme"]["doc_files"] = []
    (fx_dir / "fixture.json").write_text(json.dumps(cfg), encoding="utf-8")
    assert not validate_fixture.check5(load_fixture(fx_dir), 60).ok
