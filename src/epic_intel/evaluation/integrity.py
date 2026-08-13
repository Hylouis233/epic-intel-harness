"""Hash the truth plane before and after candidate execution."""

from __future__ import annotations

import hashlib
from pathlib import Path

from epic_intel.policy import PROTECTED_PATHS


def truth_plane_hash(project_root: Path) -> str:
    digest = hashlib.sha256()
    paths: list[Path] = []
    for relative in PROTECTED_PATHS:
        target = project_root / relative
        if target.is_dir():
            paths.extend(path for path in target.rglob("*") if path.is_file())
        elif target.is_file():
            paths.append(target)
    for path in sorted(paths):
        if "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
            continue
        digest.update(path.relative_to(project_root).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()

