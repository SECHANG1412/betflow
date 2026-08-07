from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from odds_history_coverage_poc import empty_checkpoint, save_checkpoint


def test_save_checkpoint_retries_temporary_file_lock(
    tmp_path: Path, monkeypatch
) -> None:
    checkpoint = tmp_path / "checkpoint.json"
    original_replace = Path.replace
    attempts = 0

    def flaky_replace(source: Path, target: Path) -> Path:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise PermissionError("file is temporarily locked")
        return original_replace(source, target)

    monkeypatch.setattr(Path, "replace", flaky_replace)

    save_checkpoint(checkpoint, empty_checkpoint(2010, 2026))

    assert attempts == 3
    assert json.loads(checkpoint.read_text(encoding="utf-8"))["metadata"][
        "start_year"
    ] == 2010
