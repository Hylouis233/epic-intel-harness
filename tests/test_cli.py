from __future__ import annotations

import pytest

from epic_intel.cli import main


def test_cli_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert "0.1.0" in capsys.readouterr().out


def test_results_without_ledger(capsys: pytest.CaptureFixture[str], tmp_path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\nversion='0'\n", encoding="utf-8")
    (tmp_path / "benchmarks").mkdir()
    with pytest.raises(SystemExit) as exc:
        main(["--root", str(tmp_path), "results"])
    assert exc.value.code == 0
    assert "No research experiments" in capsys.readouterr().out

