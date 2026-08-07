from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from odds_history_coverage_report import build_year_summaries, write_report


def sample_payload() -> dict[str, object]:
    return {
        "metadata": {"start_year": 2025, "end_year": 2026, "completed": True},
        "summary": {"rounds_scanned": 3, "rounds_failed": 1},
        "rounds": [
            {
                "year": 2025,
                "round_number": 1,
                "total_matches": 10,
                "matches_without_changes": 2,
                "matches_with_one_change": 5,
                "matches_with_multiple_changes": 3,
                "unknown_results": 0,
                "malformed_matches": 0,
                "total_snapshots": 21,
            },
            {
                "year": 2025,
                "round_number": 2,
                "total_matches": 12,
                "matches_without_changes": 4,
                "matches_with_one_change": 6,
                "matches_with_multiple_changes": 2,
                "unknown_results": 1,
                "malformed_matches": 0,
                "total_snapshots": 23,
            },
            {
                "year": 2026,
                "round_number": 1,
                "total_matches": 8,
                "matches_without_changes": 1,
                "matches_with_one_change": 5,
                "matches_with_multiple_changes": 2,
                "unknown_results": 0,
                "malformed_matches": 1,
                "total_snapshots": 17,
            },
        ],
        "failures": [{"year": 2026, "round_number": 2, "error": "timeout"}],
    }


def test_build_year_summaries_aggregates_rounds_and_failures() -> None:
    summaries = build_year_summaries(sample_payload())

    assert summaries[0] == {
        "year": 2025,
        "rounds_scanned": 2,
        "rounds_failed": 0,
        "total_matches": 22,
        "matches_without_changes": 6,
        "matches_with_one_change": 11,
        "matches_with_multiple_changes": 5,
        "unknown_results": 1,
        "malformed_matches": 0,
        "total_snapshots": 44,
    }
    assert summaries[1]["year"] == 2026
    assert summaries[1]["rounds_failed"] == 1


def test_write_report_creates_json_and_csv(tmp_path: Path) -> None:
    checkpoint = tmp_path / "checkpoint.json"
    checkpoint.write_text(json.dumps(sample_payload()), encoding="utf-8")

    write_report(checkpoint, tmp_path)

    report = json.loads(
        (tmp_path / "wisetoto_coverage_summary.json").read_text(encoding="utf-8")
    )
    assert report["years"][0]["total_matches"] == 22
    assert (tmp_path / "wisetoto_coverage_years.csv").read_bytes().startswith(
        b"\xef\xbb\xbf"
    )
