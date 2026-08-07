"""Build compact yearly and overall reports from a coverage checkpoint."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

METRIC_FIELDS = [
    "total_matches",
    "matches_without_changes",
    "matches_with_one_change",
    "matches_with_multiple_changes",
    "unknown_results",
    "malformed_matches",
    "total_snapshots",
]


def build_year_summaries(payload: dict[str, object]) -> list[dict[str, int]]:
    rows = payload["rounds"]
    failures = payload["failures"]
    assert isinstance(rows, list)
    assert isinstance(failures, list)
    years = sorted(
        {int(row["year"]) for row in rows}
        | {int(failure["year"]) for failure in failures}
    )
    summaries: list[dict[str, int]] = []
    for year in years:
        year_rows = [row for row in rows if int(row["year"]) == year]
        year_failures = [
            failure for failure in failures if int(failure["year"]) == year
        ]
        summary = {
            "year": year,
            "rounds_scanned": len(year_rows),
            "rounds_failed": len(year_failures),
        }
        summary.update(
            {
                field: sum(int(row[field]) for row in year_rows)
                for field in METRIC_FIELDS
            }
        )
        summaries.append(summary)
    return summaries


def build_report(payload: dict[str, object]) -> dict[str, object]:
    metadata = payload["metadata"]
    failures = payload["failures"]
    summary = payload.get("summary", {})
    assert isinstance(metadata, dict)
    assert isinstance(failures, list)
    assert isinstance(summary, dict)
    return {
        "metadata": metadata,
        "summary": summary,
        "years": build_year_summaries(payload),
        "failures": failures,
    }


def write_report(checkpoint_path: Path, output_dir: Path) -> None:
    payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    report = build_report(payload)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "wisetoto_coverage_summary.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    fields = ["year", "rounds_scanned", "rounds_failed", *METRIC_FIELDS]
    with (output_dir / "wisetoto_coverage_years.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(report["years"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    output_dir = args.output_dir or args.checkpoint.parent
    try:
        write_report(args.checkpoint, output_dir)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"coverage report failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
