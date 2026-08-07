"""Audit WiseToto 1X2 odds-history coverage across years and rounds.

This PoC deliberately stores coverage metadata instead of every odds row. It
supports throttling, retries, checkpoints, and resume so a long public-source
scan can be stopped safely without restarting from the beginning.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import sys
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TypeVar
from urllib.error import HTTPError, URLError

from odds_history_poc import (
    extract_master_id,
    fetch_text,
    parse_match_block,
    round_list_url,
    round_page_url,
)

T = TypeVar("T")


@dataclass(frozen=True)
class MatchCoverage:
    source_match_id: str
    result: str
    snapshot_count: int
    change_count: int


@dataclass(frozen=True)
class RoundCoverage:
    year: int
    round_number: int
    total_matches: int
    matches_without_changes: int
    matches_with_one_change: int
    matches_with_multiple_changes: int
    unknown_results: int
    malformed_matches: int
    total_snapshots: int
    matches: list[MatchCoverage]


def extract_available_rounds(page: str) -> list[int]:
    """Return round numbers exposed in the round selector or page links."""
    decoded = html.unescape(page)
    values: set[int] = set()

    for attributes, select in re.findall(
        r"<select\b(?P<attributes>[^>]*)>(?P<body>.*?)</select>",
        decoded,
        re.IGNORECASE | re.DOTALL,
    ):
        if "game_round" not in attributes:
            continue
        values.update(
            int(value)
            for value in re.findall(
                r"<option\b[^>]*value=[\"']?(\d+)", select, re.IGNORECASE
            )
        )

    values.update(int(value) for value in re.findall(r"game_round=(\d+)", decoded))
    values.update(
        int(value)
        for value in re.findall(
            r"get_gameinfo_body\('proto','pt1','\d+','(\d+)'", decoded
        )
    )
    return sorted(values)


def inspect_round(page: str, year: int, round_number: int) -> RoundCoverage:
    matches: list[MatchCoverage] = []
    malformed = 0

    for block in re.findall(r"<ul\b[^>]*>.*?</ul>", page, re.DOTALL | re.IGNORECASE):
        if "get_gameinfo_detail" not in block or "'pt1'" not in block:
            continue
        try:
            match = parse_match_block(block, year, round_number)
        except (IndexError, KeyError, ValueError):
            # Count only football normal 1X2-looking rows as malformed.
            if "'sc'" in block and len(re.findall(r'class="pt">\d', block)) >= 3:
                malformed += 1
            continue
        if match is None:
            continue
        snapshot_count = len(match.snapshots)
        matches.append(
            MatchCoverage(
                source_match_id=match.source_match_id,
                result=match.result,
                snapshot_count=snapshot_count,
                change_count=max(0, snapshot_count - 1),
            )
        )

    return RoundCoverage(
        year=year,
        round_number=round_number,
        total_matches=len(matches),
        matches_without_changes=sum(item.change_count == 0 for item in matches),
        matches_with_one_change=sum(item.change_count == 1 for item in matches),
        matches_with_multiple_changes=sum(item.change_count > 1 for item in matches),
        unknown_results=sum(item.result == "UNKNOWN" for item in matches),
        malformed_matches=malformed,
        total_snapshots=sum(item.snapshot_count for item in matches),
        matches=matches,
    )


def with_retries[T](
    operation: Callable[[], T], *, retries: int, retry_delay_seconds: float
) -> T:
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return operation()
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(retry_delay_seconds * (attempt + 1))
    assert last_error is not None
    raise last_error


def discover_rounds(
    year: int, *, retries: int, retry_delay_seconds: float
) -> list[int]:
    page = with_retries(
        lambda: fetch_text(round_page_url(year, 1)),
        retries=retries,
        retry_delay_seconds=retry_delay_seconds,
    )
    rounds = extract_available_rounds(page)
    if not rounds:
        raise ValueError(f"round selector not found for {year}")
    return rounds


def collect_round_coverage(
    year: int, round_number: int, *, retries: int, retry_delay_seconds: float
) -> RoundCoverage:
    page_url = round_page_url(year, round_number)
    page = with_retries(
        lambda: fetch_text(page_url),
        retries=retries,
        retry_delay_seconds=retry_delay_seconds,
    )
    master_id = extract_master_id(page, year, round_number)
    list_url = round_list_url(year, round_number, master_id)
    list_page = with_retries(
        lambda: fetch_text(list_url, referer=page_url),
        retries=retries,
        retry_delay_seconds=retry_delay_seconds,
    )
    return inspect_round(list_page, year, round_number)


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
        "rounds": [],
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


def save_checkpoint(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    metadata = payload["metadata"]
    assert isinstance(metadata, dict)
    metadata["updated_at"] = datetime.now(UTC).isoformat()
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def build_summary(payload: dict[str, object]) -> dict[str, object]:
    rows = payload["rounds"]
    failures = payload["failures"]
    assert isinstance(rows, list)
    assert isinstance(failures, list)
    return {
        "rounds_scanned": len(rows),
        "rounds_failed": len(failures),
        "total_matches": sum(int(row["total_matches"]) for row in rows),
        "matches_without_changes": sum(
            int(row["matches_without_changes"]) for row in rows
        ),
        "matches_with_one_change": sum(
            int(row["matches_with_one_change"]) for row in rows
        ),
        "matches_with_multiple_changes": sum(
            int(row["matches_with_multiple_changes"]) for row in rows
        ),
        "unknown_results": sum(int(row["unknown_results"]) for row in rows),
        "malformed_matches": sum(int(row["malformed_matches"]) for row in rows),
        "total_snapshots": sum(int(row["total_snapshots"]) for row in rows),
    }


def write_round_csv(path: Path, payload: dict[str, object]) -> None:
    rows = payload["rounds"]
    assert isinstance(rows, list)
    fields = [
        "year",
        "round_number",
        "total_matches",
        "matches_without_changes",
        "matches_with_one_change",
        "matches_with_multiple_changes",
        "unknown_results",
        "malformed_matches",
        "total_snapshots",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row[field] for field in fields})


def run_scan(args: argparse.Namespace) -> tuple[dict[str, object], int]:
    checkpoint_path = args.output_dir / "wisetoto_coverage_checkpoint.json"
    payload = load_checkpoint(checkpoint_path, args.start_year, args.end_year)
    discovered = payload["discovered_rounds"]
    rows = payload["rounds"]
    failures = payload["failures"]
    assert isinstance(discovered, dict)
    assert isinstance(rows, list)
    assert isinstance(failures, list)
    completed = {(int(row["year"]), int(row["round_number"])) for row in rows}
    failed = {(int(row["year"]), int(row.get("round_number", 0))) for row in failures}

    stop_requested = False
    for year in range(args.start_year, args.end_year + 1):
        year_key = str(year)
        if year_key not in discovered:
            try:
                year_rounds = discover_rounds(
                    year,
                    retries=args.retries,
                    retry_delay_seconds=args.retry_delay_seconds,
                )
                if args.max_rounds_per_year:
                    year_rounds = year_rounds[: args.max_rounds_per_year]
                discovered[year_key] = year_rounds
                save_checkpoint(checkpoint_path, payload)
            except (HTTPError, URLError, TimeoutError, ValueError) as exc:
                failures.append({"year": year, "round_number": 0, "error": str(exc)})
                save_checkpoint(checkpoint_path, payload)
                continue

        for round_number in discovered[year_key]:
            key = (year, int(round_number))
            if key in completed or key in failed:
                continue
            try:
                coverage = collect_round_coverage(
                    year,
                    int(round_number),
                    retries=args.retries,
                    retry_delay_seconds=args.retry_delay_seconds,
                )
                rows.append(asdict(coverage))
                completed.add(key)
            except (HTTPError, URLError, TimeoutError, ValueError) as exc:
                failures.append(
                    {"year": year, "round_number": int(round_number), "error": str(exc)}
                )
                failed.add(key)
            save_checkpoint(checkpoint_path, payload)
            if args.max_total_rounds and len(rows) >= args.max_total_rounds:
                stop_requested = True
                break
            time.sleep(args.delay_seconds)
        if stop_requested:
            break

    expected = sum(len(value) for value in discovered.values())
    metadata = payload["metadata"]
    assert isinstance(metadata, dict)
    metadata["completed"] = len(rows) + len(failures) >= expected and not stop_requested
    payload["summary"] = build_summary(payload)
    save_checkpoint(checkpoint_path, payload)
    write_round_csv(args.output_dir / "wisetoto_coverage_rounds.csv", payload)
    return payload, 0 if metadata["completed"] and not failures else 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-year", type=int, default=2010)
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument("--delay-seconds", type=float, default=1.0)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--retry-delay-seconds", type=float, default=2.0)
    parser.add_argument("--max-rounds-per-year", type=int)
    parser.add_argument("--max-total-rounds", type=int)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/odds-history-coverage"),
    )
    args = parser.parse_args()
    if args.start_year > args.end_year:
        parser.error("--start-year must be less than or equal to --end-year")
    if args.delay_seconds < 0 or args.retries < 0 or args.retry_delay_seconds < 0:
        parser.error("delay and retry values must not be negative")

    try:
        payload, exit_code = run_scan(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"coverage scan failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
