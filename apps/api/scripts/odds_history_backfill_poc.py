"""Walk WiseToto rounds backwards and collect a target number of histories."""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError

from odds_history_poc import MatchHistory, collect, write_outputs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--start-round", type=int, required=True)
    parser.add_argument("--max-rounds", type=int, default=20)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument(
        "--output-dir", type=Path, default=Path("artifacts/odds-history-poc/backfill")
    )
    args = parser.parse_args()

    matches: list[MatchHistory] = []
    checked_rounds: list[int] = []
    failed_rounds: dict[int, str] = {}
    source_pages: list[str] = []
    source_endpoints: list[str] = []

    last_round = max(0, args.start_round - args.max_rounds)
    for round_number in range(args.start_round, last_round, -1):
        try:
            found, page_url, list_url = collect(args.year, round_number)
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            failed_rounds[round_number] = str(exc)
            continue
        checked_rounds.append(round_number)
        source_pages.append(page_url)
        source_endpoints.append(list_url)
        matches.extend(found)
        if len(matches) >= args.limit:
            break

    selected = matches[: args.limit]
    metadata: dict[str, object] = {
        "collected_at": datetime.now(UTC).isoformat(),
        "source_pages": source_pages,
        "source_endpoints": source_endpoints,
        "checked_rounds": checked_rounds,
        "failed_rounds": failed_rounds,
        "requested_limit": args.limit,
        "matches_with_history_found": len(matches),
        "matches_written": len(selected),
        "timestamps_available": False,
        "history_semantics": "ordered transitions exposed by source; exact change times absent",
    }
    write_outputs(selected, args.output_dir, metadata)
    print(f"checked rounds: {checked_rounds}")
    print(f"matches written: {len(selected)}")
    if failed_rounds:
        print(f"failed rounds: {failed_rounds}", file=sys.stderr)
    return 0 if len(selected) >= args.limit else 2


if __name__ == "__main__":
    raise SystemExit(main())
