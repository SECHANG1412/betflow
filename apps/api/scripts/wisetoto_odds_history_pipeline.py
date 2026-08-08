"""Resumable WiseToto odds-history collection pipeline."""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError

from odds_history_coverage_poc import discover_rounds, with_retries
from odds_history_poc import MatchHistory, Snapshot, collect, write_outputs

COLLECTION_ERRORS = (HTTPError, URLError, TimeoutError, ValueError)
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def empty_checkpoint(start_year: int, end_year: int) -> dict[str, object]:
    return {
        "metadata": {
            "source": "wisetoto",
            "start_year": start_year,
            "end_year": end_year,
            "started_at": datetime.now(UTC).isoformat(),
            "updated_at": None,
            "completed": False,
        },
        "discovered_rounds": {},
        "completed_rounds": [],
        "failures": [],
    }


def load_checkpoint(path: Path, start_year: int, end_year: int) -> dict[str, object]:
    if not path.exists():
        return empty_checkpoint(start_year, end_year)
    payload = json.loads(path.read_text(encoding="utf-8"))
    metadata = payload.get("metadata", {})
    if metadata.get("start_year") != start_year or metadata.get("end_year") != end_year:
        raise ValueError("checkpoint year range does not match the requested range")
    return payload


def save_json_atomic(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    for attempt in range(5):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == 4:
                raise
            time.sleep(0.1 * (attempt + 1))


def save_checkpoint(path: Path, payload: dict[str, object]) -> None:
    metadata = payload["metadata"]
    assert isinstance(metadata, dict)
    metadata["updated_at"] = datetime.now(UTC).isoformat()
    save_json_atomic(path, payload)


def round_fragment_path(output_dir: Path, year: int, round_number: int) -> Path:
    return output_dir / ".rounds" / str(year) / f"{round_number:03d}.json"


def write_round_fragment(path: Path, matches: list[MatchHistory]) -> None:
    save_json_atomic(path, [asdict(match) for match in matches])


def match_from_dict(value: dict[str, object]) -> MatchHistory:
    raw_snapshots = value["snapshots"]
    assert isinstance(raw_snapshots, list)
    snapshots = [Snapshot(**snapshot) for snapshot in raw_snapshots]
    return MatchHistory(**(value | {"snapshots": snapshots}))


def load_year_matches(
    output_dir: Path, year: int, round_numbers: list[int]
) -> list[MatchHistory]:
    matches: list[MatchHistory] = []
    for round_number in sorted(round_numbers):
        path = round_fragment_path(output_dir, year, round_number)
        rows = json.loads(path.read_text(encoding="utf-8"))
        matches.extend(match_from_dict(row) for row in rows)
    return matches


def write_year_outputs(
    output_dir: Path, year: int, round_numbers: list[int]
) -> None:
    matches = load_year_matches(output_dir, year, round_numbers)
    metadata = {
        "collected_at": datetime.now(UTC).isoformat(),
        "source": "wisetoto",
        "source_year": year,
        "rounds_completed": len(round_numbers),
        "matches_written": len(matches),
        "snapshots_written": sum(len(match.snapshots) for match in matches),
        "timestamps_available": False,
        "history_semantics": "ordered transitions exposed by source; exact change times absent",
    }
    write_outputs(matches, output_dir / str(year), metadata)


def failure_key(value: dict[str, object]) -> tuple[int, int]:
    return int(value["year"]), int(value["round_number"])


def record_failure(
    failures: list[dict[str, object]], year: int, round_number: int, error: Exception
) -> None:
    failures[:] = [row for row in failures if failure_key(row) != (year, round_number)]
    failures.append(
        {
            "year": year,
            "round_number": round_number,
            "error_type": type(error).__name__,
            "error": str(error),
            "failed_at": datetime.now(UTC).isoformat(),
        }
    )


def run_pipeline(args: argparse.Namespace) -> tuple[dict[str, object], int]:
    checkpoint_path = args.output_dir / "wisetoto_history_checkpoint.json"
    payload = load_checkpoint(checkpoint_path, args.start_year, args.end_year)
    discovered = payload["discovered_rounds"]
    completed_rows = payload["completed_rounds"]
    failures = payload["failures"]
    assert isinstance(discovered, dict)
    assert isinstance(completed_rows, list)
    assert isinstance(failures, list)
    completed = {
        (int(row["year"]), int(row["round_number"])) for row in completed_rows
    }
    attempts = 0
    stopped_early = False

    for year in range(args.start_year, args.end_year + 1):
        year_key = str(year)
        if year_key not in discovered:
            try:
                rounds = discover_rounds(
                    year,
                    retries=args.retries,
                    retry_delay_seconds=args.retry_delay_seconds,
                )
                discovered[year_key] = rounds
                failures[:] = [row for row in failures if failure_key(row) != (year, 0)]
                save_checkpoint(checkpoint_path, payload)
            except COLLECTION_ERRORS as exc:
                record_failure(failures, year, 0, exc)
                save_checkpoint(checkpoint_path, payload)
                continue

        rounds_to_process = discovered[year_key]
        if args.max_rounds_per_year is not None:
            rounds_to_process = rounds_to_process[: args.max_rounds_per_year]
        for round_value in rounds_to_process:
            round_number = int(round_value)
            key = (year, round_number)
            if key in completed:
                continue
            if args.max_total_rounds is not None and attempts >= args.max_total_rounds:
                stopped_early = True
                break
            attempts += 1
            try:
                matches, _, _ = with_retries(
                    lambda year=year, round_number=round_number: collect(year, round_number),
                    retries=args.retries,
                    retry_delay_seconds=args.retry_delay_seconds,
                )
                write_round_fragment(
                    round_fragment_path(args.output_dir, year, round_number), matches
                )
                completed_rows.append({"year": year, "round_number": round_number})
                completed.add(key)
                failures[:] = [row for row in failures if failure_key(row) != key]
            except (*COLLECTION_ERRORS, OSError, json.JSONDecodeError) as exc:
                record_failure(failures, year, round_number, exc)
            save_checkpoint(checkpoint_path, payload)
            if args.delay_seconds:
                time.sleep(args.delay_seconds)

        completed_for_year = sorted(
            round_number for item_year, round_number in completed if item_year == year
        )
        if completed_for_year:
            write_year_outputs(args.output_dir, year, completed_for_year)
        if stopped_early:
            break

    expected = {
        (int(year), int(round_number))
        for year, rounds in discovered.items()
        for round_number in rounds
    }
    metadata = payload["metadata"]
    assert isinstance(metadata, dict)
    metadata["completed"] = (
        not stopped_early
        and expected.issubset(completed)
        and not failures
        and len(discovered) == args.end_year - args.start_year + 1
    )
    payload["summary"] = {
        "rounds_discovered": len(expected),
        "rounds_completed": len(completed),
        "rounds_failed": len(failures),
        "stopped_early": stopped_early,
    }
    save_checkpoint(checkpoint_path, payload)
    return payload, 0 if metadata["completed"] else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-year", type=int, default=2010)
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument("--delay-seconds", type=float, default=1.0)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--retry-delay-seconds", type=float, default=2.0)
    parser.add_argument("--max-rounds-per-year", type=int)
    parser.add_argument("--max-total-rounds", type=int)
    parser.add_argument(
        "--output-dir", type=Path,
        default=PROJECT_ROOT / "artifacts" / "wisetoto-history",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.start_year > args.end_year:
        parser.error("--start-year must be less than or equal to --end-year")
    if args.delay_seconds < 0 or args.retries < 0 or args.retry_delay_seconds < 0:
        parser.error("delay and retry values must not be negative")
    if args.max_rounds_per_year is not None and args.max_rounds_per_year < 1:
        parser.error("--max-rounds-per-year must be positive")
    if args.max_total_rounds is not None and args.max_total_rounds < 1:
        parser.error("--max-total-rounds must be positive")
    try:
        payload, exit_code = run_pipeline(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"collection pipeline failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
