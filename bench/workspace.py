"""Workspace helpers: build condition workspaces, git baseline/diff, patches, shell."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .fixture import Fixture
from .strip_comments import strip, strip_tree

IGNORE_NAMES = {".git", "node_modules", "__pycache__", ".pytest_cache", ".DS_Store"}
GIT_EXCLUDES = ["__pycache__/", "*.pyc", ".pytest_cache/", "node_modules/", ".DS_Store"]


def _ignore(_dir, names):
    return {n for n in names if n in IGNORE_NAMES}


def copytree(src: Path, dst: Path) -> None:
    shutil.copytree(src, dst, ignore=_ignore, dirs_exist_ok=True, symlinks=True)


@dataclass
class CmdResult:
    cmd: str
    returncode: int
    output: str
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out


_SHIM_DIR: str | None = None


def test_env() -> dict:
    """Environment for running fixture test commands."""
    global _SHIM_DIR
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.setdefault("NODE_NO_WARNINGS", "1")
    env.pop("PYTEST_ADDOPTS", None)
    env.pop("PYTEST_CURRENT_TEST", None)
    if shutil.which("python") is None:
        # test_cmd says `python`; provide a shim pointing at this interpreter.
        if _SHIM_DIR is None:
            _SHIM_DIR = tempfile.mkdtemp(prefix="cdb-shim-")
            os.symlink(sys.executable, os.path.join(_SHIM_DIR, "python"))
        env["PATH"] = _SHIM_DIR + os.pathsep + env.get("PATH", "")
    return env


def run_shell(cmd: str, cwd: Path, timeout: float = 600, env: dict | None = None) -> CmdResult:
    try:
        p = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True,
                           timeout=timeout, env=env if env is not None else test_env(),
                           stdin=subprocess.DEVNULL)
        return CmdResult(cmd, p.returncode, p.stdout + p.stderr)
    except subprocess.TimeoutExpired as exc:
        out = (exc.stdout or b"")
        err = (exc.stderr or b"")
        if isinstance(out, bytes):
            out = out.decode("utf-8", "replace")
        if isinstance(err, bytes):
            err = err.decode("utf-8", "replace")
        return CmdResult(cmd, -9, out + err + f"\n[timeout after {timeout}s]", timed_out=True)


def git(ws: Path, *args: str, check: bool = True, input: str | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    for k in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        env.pop(k, None)
    env.update({
        "GIT_AUTHOR_NAME": "bench", "GIT_AUTHOR_EMAIL": "bench@localhost",
        "GIT_COMMITTER_NAME": "bench", "GIT_COMMITTER_EMAIL": "bench@localhost",
        "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0",
    })
    p = subprocess.run(["git", "-c", "core.autocrlf=false", "-c", "commit.gpgsign=false",
                        "-c", "core.hooksPath=/dev/null", *args],
                       cwd=ws, capture_output=True, text=True, env=env, input=input)
    if check and p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed in {ws}: {p.stderr.strip()}")
    return p


def git_baseline(ws: Path) -> str:
    """git init + commit everything. Returns baseline sha."""
    git(ws, "init", "-q")
    git(ws, "config", "user.name", "bench")
    git(ws, "config", "user.email", "bench@localhost")
    git(ws, "config", "commit.gpgsign", "false")
    info = ws / ".git" / "info"
    info.mkdir(parents=True, exist_ok=True)
    with open(info / "exclude", "a", encoding="utf-8") as fh:
        fh.write("\n".join(GIT_EXCLUDES) + "\n")
    git(ws, "add", "-A")
    git(ws, "commit", "-q", "--allow-empty", "--no-verify", "-m", "baseline")
    return git(ws, "rev-parse", "HEAD").stdout.strip()


def git_diff(ws: Path, baseline: str) -> str:
    """Diff baseline -> current worktree, including untracked files."""
    if not (ws / ".git").exists():
        return ""
    git(ws, "add", "-A", check=False)
    return git(ws, "diff", "--cached", "--no-color", "--no-ext-diff", baseline, "--", check=False).stdout


def remove_claude_config(ws: Path) -> list[str]:
    """Remove inherited CLAUDE.md / .claude/ from the workspace tree."""
    removed = []
    for p in list(ws.rglob("CLAUDE.md")) + list(ws.rglob("CLAUDE.local.md")):
        if ".git" in p.parts:
            continue
        p.unlink()
        removed.append(str(p.relative_to(ws)))
    for p in list(ws.rglob(".claude")):
        if p.is_dir() and ".git" not in p.parts:
            shutil.rmtree(p)
            removed.append(str(p.relative_to(ws)) + "/")
    return removed


def inherited_claude_md(ws: Path) -> list[str]:
    """CLAUDE.md files in parent dirs / home that Claude Code would still load."""
    found = []
    for parent in ws.resolve().parents:
        for name in ("CLAUDE.md", "CLAUDE.local.md", ".claude/CLAUDE.md"):
            if (parent / name).is_file():
                found.append(str(parent / name))
    home = Path.home() / ".claude" / "CLAUDE.md"
    if home.is_file():
        found.append(str(home))
    return found


def build_condition(fx: Fixture, condition: str, dest: Path) -> Path:
    """Populate ``dest`` with the project as seen under ``condition``."""
    if condition == "original":
        copytree(fx.original_dir, dest)
    elif condition == "stripped":
        copytree(fx.original_dir, dest)
        strip_tree(dest)
    elif condition == "rewritten":
        if not fx.has_rewritten:
            raise FileNotFoundError(f"{fx.id}: rewritten/ missing")
        copytree(fx.rewritten_dir, dest)
    else:
        raise ValueError(f"unknown condition {condition!r}")
    return dest


def apply_patch(ws: Path, patch: Path) -> tuple[bool, str]:
    """Apply a patch with git apply, falling back to patch -p1."""
    patch = Path(patch).resolve()
    attempts = [
        ["git", "apply", "--whitespace=nowarn", str(patch)],
        ["git", "apply", "--whitespace=nowarn", "--recount", "-C1", str(patch)],
    ]
    log = []
    # Never let git discover an enclosing repository above the workspace.
    env = dict(os.environ, GIT_CEILING_DIRECTORIES=str(Path(ws).resolve().parent))
    for k in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        env.pop(k, None)
    for cmd in attempts:
        p = subprocess.run(cmd, cwd=ws, capture_output=True, text=True, env=env)
        log.append(f"$ {' '.join(cmd)}\n{p.stdout}{p.stderr}")
        if p.returncode == 0:
            return True, "git apply"
    if shutil.which("patch"):
        dry = subprocess.run(["patch", "-p1", "--dry-run", "--batch", "--fuzz=2", "-i", str(patch)],
                             cwd=ws, capture_output=True, text=True)
        log.append(f"$ patch --dry-run\n{dry.stdout}{dry.stderr}")
        if dry.returncode == 0:
            p = subprocess.run(["patch", "-p1", "--batch", "--fuzz=2", "--no-backup-if-mismatch",
                                "-i", str(patch)], cwd=ws, capture_output=True, text=True)
            log.append(f"$ patch -p1\n{p.stdout}{p.stderr}")
            if p.returncode == 0:
                return True, "patch -p1"
    return False, "\n".join(log)


def patched_files(patch: Path) -> list[str]:
    """Workspace-relative paths touched by a unified diff (new side, or old side if deleted)."""
    files = []
    old = None
    for line in Path(patch).read_text(encoding="utf-8").splitlines():
        if line.startswith("--- "):
            old = line[4:].split("\t")[0].strip()
        elif line.startswith("+++ "):
            new = line[4:].split("\t")[0].strip()
            name = new if new != "/dev/null" else old
            if name and name != "/dev/null":
                if name.startswith(("a/", "b/")):
                    name = name[2:]
                if name not in files:
                    files.append(name)
    return files


def apply_patch_for_condition(fx: Fixture, condition: str, ws: Path, patch: Path) -> tuple[bool, str]:
    """Apply a probe patch (written against original/) to a condition workspace.

    Tries the patch directly; if the context does not match (stripped / rewritten
    comments), applies it to a pristine copy of original/, transforms the touched
    files into the condition (strip for ``stripped``) and copies them over.
    """
    ok, how = apply_patch(ws, patch)
    if ok or condition == "original":
        return ok, how
    with tempfile.TemporaryDirectory(prefix="cdb-probe-") as tmp:
        tmp = Path(tmp)
        copytree(fx.original_dir, tmp)
        ok2, how2 = apply_patch(tmp, patch)
        if not ok2:
            return False, how + "\n" + how2
        for rel in patched_files(patch):
            src, dst = tmp / rel, ws / rel
            if not src.exists():
                if dst.exists():
                    dst.unlink()
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            if condition == "stripped":
                from .strip_comments import lang_for_path
                lang = lang_for_path(src)
                text = src.read_text(encoding="utf-8")
                dst.write_text(strip(text, lang) if lang else text, encoding="utf-8")
            else:
                shutil.copy2(src, dst)
    return True, "applied to original then transformed"


def copy_hidden(fx: Fixture, ws: Path) -> list[str]:
    """Copy every hidden/ file into hidden_dest. Returns workspace-relative dest paths."""
    dests = []
    for f in fx.all_hidden_files():
        rel = fx.hidden_dest_path(f)
        dst = ws / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dst)
        dests.append(rel)
    return dests


def save_tree(ws: Path, dest: Path) -> None:
    copytree(ws, dest)
