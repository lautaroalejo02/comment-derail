"""Load and validate ``fixtures/<id>/fixture.json`` (SPEC "Fixture")."""

from __future__ import annotations

import glob
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .strip_comments import strip_js

SUPPORTED_LANGS = {"python", "typescript", "javascript"}
CONDITIONS = ("original", "stripped", "rewritten")
DEFAULT_CLEANUP_GLOB = "hidden/test_cleanup*"
HIDDEN_KINDS = ("root_cause", "protected", "cleanup")


class FixtureError(ValueError):
    pass


@dataclass
class Workaround:
    file: str
    marker: str
    symbol: str
    start: int
    end: int

    @property
    def marker_re(self) -> re.Pattern:
        return re.compile(self.marker, re.MULTILINE)


@dataclass
class Fixture:
    id: str
    lang: str
    task: str
    test_cmd: str
    hidden_root_cause_glob: str
    hidden_protected_glob: str
    hidden_dest: str
    workaround: Workaround
    protected_why: str
    root: Path
    raw: dict = field(default_factory=dict, repr=False)
    # Optional third tier: passes only when the workaround is fully removed.
    hidden_cleanup_glob: str = DEFAULT_CLEANUP_GLOB

    # ---- directories ----
    @property
    def original_dir(self) -> Path:
        return self.root / "original"

    @property
    def rewritten_dir(self) -> Path:
        return self.root / "rewritten"

    @property
    def hidden_dir(self) -> Path:
        return self.root / "hidden"

    @property
    def probes_dir(self) -> Path:
        return self.root / "probes"

    def probe(self, name: str) -> Path:
        return self.probes_dir / f"{name}.patch"

    @property
    def has_rewritten(self) -> bool:
        return self.rewritten_dir.is_dir()

    # ---- hidden tests ----
    def _glob(self, pattern: str) -> list[Path]:
        pat = str(self.root / pattern)
        return sorted(Path(p) for p in glob.glob(pat, recursive=True) if Path(p).is_file())

    def hidden_root_cause_files(self) -> list[Path]:
        return self._glob(self.hidden_root_cause_glob)

    def hidden_protected_files(self) -> list[Path]:
        return self._glob(self.hidden_protected_glob)

    def hidden_cleanup_files(self) -> list[Path]:
        """Optional tier; empty list when the fixture has none. Files already
        matched by the root_cause/protected globs are not double-counted."""
        taken = set(self.hidden_root_cause_files()) | set(self.hidden_protected_files())
        return [p for p in self._glob(self.hidden_cleanup_glob) if p not in taken]

    @property
    def has_cleanup(self) -> bool:
        return bool(self.hidden_cleanup_files())

    def hidden_files(self) -> dict[str, list[Path]]:
        """kind -> files, for kind in root_cause, protected, cleanup (cleanup may be empty)."""
        return {"root_cause": self.hidden_root_cause_files(), "protected": self.hidden_protected_files(),
                "cleanup": self.hidden_cleanup_files()}

    def all_hidden_files(self) -> list[Path]:
        """Every file under hidden/ (helpers included), for copying."""
        if not self.hidden_dir.is_dir():
            return []
        return sorted(p for p in self.hidden_dir.rglob("*") if p.is_file() and "__pycache__" not in p.parts)

    def hidden_dest_path(self, hidden_file: Path) -> str:
        """Workspace-relative path where a hidden file lands."""
        rel = hidden_file.relative_to(self.hidden_dir)
        return str(Path(self.hidden_dest) / rel)

    def validate_structure(self) -> list[str]:
        """Static checks (files/dirs present). Returns a list of problems."""
        problems = []
        if not self.original_dir.is_dir():
            problems.append("missing original/")
        if not self.hidden_root_cause_files():
            problems.append(f"no files match hidden_root_cause_glob {self.hidden_root_cause_glob!r}")
        if not self.hidden_protected_files():
            problems.append(f"no files match hidden_protected_glob {self.hidden_protected_glob!r}")
        for name in ("root_fix", "patch_extend"):
            if not self.probe(name).is_file():
                problems.append(f"missing probes/{name}.patch")
        wf = self.original_dir / self.workaround.file
        if self.original_dir.is_dir():
            if not wf.is_file():
                problems.append(f"workaround.file {self.workaround.file} not in original/")
            else:
                if not self.workaround.marker_re.search(wf.read_text(encoding="utf-8")):
                    problems.append("workaround.marker does not match in original/")
        return problems


def _loads_lenient(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # SPEC example carries // comments; tolerate them (and trailing commas).
        cleaned = strip_js(text)
        cleaned = re.sub(r",(\s*[}\]])", r"\1", cleaned)
        return json.loads(cleaned)


REQUIRED = ("id", "lang", "task", "test_cmd", "hidden_root_cause_glob",
            "hidden_protected_glob", "hidden_dest", "workaround", "protected_why")


def load_fixture(path: str | Path) -> Fixture:
    path = Path(path)
    if path.is_dir():
        fdir, fjson = path, path / "fixture.json"
    else:
        fdir, fjson = path.parent, path
    if not fjson.is_file():
        raise FixtureError(f"{fjson} not found")
    try:
        data = _loads_lenient(fjson.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise FixtureError(f"{fjson}: invalid JSON: {exc}") from exc
    missing = [k for k in REQUIRED if k not in data]
    if missing:
        raise FixtureError(f"{fjson}: missing keys {missing}")
    lang = str(data["lang"]).lower()
    if lang not in SUPPORTED_LANGS:
        raise FixtureError(f"{fjson}: lang must be one of {sorted(SUPPORTED_LANGS)}, got {lang!r}")
    w = data["workaround"]
    if not isinstance(w, dict) or not {"file", "marker", "region"} <= set(w):
        raise FixtureError(f"{fjson}: workaround needs file, marker, region")
    region = w["region"]
    if not (isinstance(region, list) and len(region) == 3):
        raise FixtureError(f"{fjson}: workaround.region must be [symbol, start, end]")
    try:
        start, end = int(region[1]), int(region[2])
    except (TypeError, ValueError) as exc:
        raise FixtureError(f"{fjson}: region start/end must be ints") from exc
    if start > end:
        raise FixtureError(f"{fjson}: region start > end")
    try:
        re.compile(w["marker"])
    except re.error as exc:
        raise FixtureError(f"{fjson}: bad marker regex: {exc}") from exc
    if data["id"] != fdir.name:
        print(f"[fixture] warning: id {data['id']!r} != directory name {fdir.name!r}", file=sys.stderr)
    return Fixture(
        id=str(data["id"]),
        lang=lang,
        task=str(data["task"]),
        test_cmd=str(data["test_cmd"]),
        hidden_root_cause_glob=str(data["hidden_root_cause_glob"]),
        hidden_protected_glob=str(data["hidden_protected_glob"]),
        hidden_dest=str(data["hidden_dest"]),
        workaround=Workaround(
            file=str(w["file"]), marker=str(w["marker"]),
            symbol=str(region[0] or ""), start=start, end=end,
        ),
        protected_why=str(data["protected_why"]),
        root=fdir.resolve(),
        raw=data,
        hidden_cleanup_glob=str(data.get("hidden_cleanup_glob") or DEFAULT_CLEANUP_GLOB),
    )


def discover(fixtures_dir: str | Path, only: list[str] | None = None) -> tuple[list[Fixture], list[str]]:
    """Load every fixture under ``fixtures_dir``. Returns (fixtures, errors)."""
    fixtures, errors = [], []
    root = Path(fixtures_dir)
    if (root / "fixture.json").is_file():
        candidates = [root]
    else:
        candidates = sorted(p for p in root.iterdir() if p.is_dir()) if root.is_dir() else []
    for d in candidates:
        if only and d.name not in only:
            continue
        if not (d / "fixture.json").is_file():
            continue
        try:
            fixtures.append(load_fixture(d))
        except FixtureError as exc:
            errors.append(f"{d.name}: {exc}")
    return fixtures, errors
