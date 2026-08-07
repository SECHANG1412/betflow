"""Extract every trustworthy odds sequence for one WiseToto year."""

from __future__ import annotations

import argparse
import csv
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError

from odds_history_poc import MatchHistory, collect, write_outputs


def round_numbers_from_coverage(path: Path, year: int) -> list[int]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return sorted(
            int(row["round_number"])
            for row in csv.DictReader(handle)
            if int(row["year"]) == year
        )


def extract_year(
    year: int,
    round_numbers: list[int],
    *,
    delay_seconds: float,
) -> tuple[list[MatchHistory], dict[str, object]]:
    matches: list[MatchHistory] = []
    failed_rounds: dict[int, str] = {}
    for index, round_number in enumerate(round_numbers):
        try:
            found, _, _ = collect(year, round_number)
            matches.extend(found)
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            failed_rounds[round_number] = str(exc)
        if index + 1 < len(round_numbers):
            time.sleep(delay_seconds)

    metadata: dict[str, object] = {
        "collected_at": datetime.now(UTC).isoformat(),
        "source": "wisetoto",
        "source_year": year,
        "rounds_requested": len(round_numbers),
        "rounds_failed": failed_rounds,
        "matches_written": len(matches),
        "snapshots_written": sum(len(match.snapshots) for match in matches),
        "timestamps_available": False,
        "quality_policy": "exclude histories with unaligned transitions or final-odds mismatch",
    }
    return matches, metadata


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument(
        "--coverage-csv",
        type=Path,
        default=Path("artifacts/odds-history-coverage/wisetoto_coverage_rounds.csv"),
    )
    parser.add_argument("--delay-seconds", type=float, default=1.0)
    parser.add_argument("--max-rounds", type=int)
    parser.add_argument(
        "--output-dir", type=Path, default=Path("artifacts/odds-history-year")
    )
    args = parser.parse_args()
    if args.delay_seconds < 0:
        parser.error("--delay-seconds must not be negative")

    rounds = round_numbers_from_coverage(args.coverage_csv, args.year)
    if args.max_rounds is not None:
        rounds = rounds[: args.max_rounds]
    if not rounds:
        parser.error(f"no rounds found for {args.year}")

    matches, metadata = extract_year(
        args.year, rounds, delay_seconds=args.delay_seconds
    )
    write_outputs(matches, args.output_dir, metadata)
    print(json.dumps(metadata, ensure_ascii=False, indent=2))
    return 0 if not metadata["rounds_failed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
