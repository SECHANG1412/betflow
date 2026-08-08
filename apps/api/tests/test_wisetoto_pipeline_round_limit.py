from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

import wisetoto_odds_history_pipeline as pipeline


def test_round_limit_preserves_full_discovery_for_resume(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(pipeline, "discover_rounds", lambda *args, **kwargs: [1, 2])
    monkeypatch.setattr(
        pipeline, "collect", lambda year, round_number: ([], "page", "endpoint")
    )
    args = argparse.Namespace(
        start_year=2026,
        end_year=2026,
        delay_seconds=0,
        retries=0,
        retry_delay_seconds=0,
        max_rounds_per_year=1,
        max_total_rounds=None,
        output_dir=tmp_path,
    )

    payload, exit_code = pipeline.run_pipeline(args)

    assert exit_code == 2
    assert payload["discovered_rounds"] == {"2026": [1, 2]}
    assert payload["completed_rounds"] == [{"year": 2026, "round_number": 1}]
