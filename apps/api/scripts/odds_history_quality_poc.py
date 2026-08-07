"""Diagnose malformed WiseToto rows found by the coverage scan."""

from __future__ import annotations

import argparse
import csv
import json
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from odds_history_coverage_poc import with_retries
from odds_history_poc import (
    extract_master_id,
    fetch_text,
    parse_match_block,
    round_list_url,
    round_page_url,
)


@dataclass(frozen=True)
class MalformedCandidate:
    year: int
    round_number: int
    source_schedule_id: str | None
    source_match_id: str | None
    reason: str
    raw_block: str


def diagnose_round(page: str, year: int, round_number: int) -> list[MalformedCandidate]:
    candidates: list[MalformedCandidate] = []
    for block in re.findall(r"<ul\b[^>]*>.*?</ul>", page, re.DOTALL | re.IGNORECASE):
        if "get_gameinfo_detail" not in block or "'pt1'" not in block:
            continue
        try:
            parse_match_block(block, year, round_number)
        except (IndexError, KeyError, ValueError) as exc:
            if "'sc'" not in block or len(re.findall(r'class="pt">\d', block)) < 3:
                continue
            identity = re.search(r'id="db(?P<schedule>\d+)_(?P<match>\d+)"', block)
            candidates.append(
                MalformedCandidate(
                    year=year,
                    round_number=round_number,
                    source_schedule_id=identity.group("schedule") if identity else None,
                    source_match_id=identity.group("match") if identity else None,
                    reason=str(exc),
                    raw_block=block,
                )
            )
    return candidates


def collect_diagnostics(year: int, round_number: int) -> list[MalformedCandidate]:
    page_url = round_page_url(year, round_number)
    page = with_retries(lambda: fetch_text(page_url), retries=2, retry_delay_seconds=2)
    master_id = extract_master_id(page, year, round_number)
    list_url = round_list_url(year, round_number, master_id)
    response = with_retries(
        lambda: fetch_text(list_url, referer=page_url), retries=2, retry_delay_seconds=2
    )
    return diagnose_round(response, year, round_number)


def target_rounds(path: Path) -> list[tuple[int, int]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return [
            (int(row["year"]), int(row["round_number"]))
            for row in csv.DictReader(handle)
            if int(row["malformed_matches"]) > 0
        ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--coverage-csv",
        type=Path,
        default=Path("artifacts/odds-history-coverage/wisetoto_coverage_rounds.csv"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/odds-history-quality/malformed_candidates.json"),
    )
    parser.add_argument("--delay-seconds", type=float, default=1.0)
    args = parser.parse_args()

    candidates: list[MalformedCandidate] = []
    for year, round_number in target_rounds(args.coverage_csv):
        candidates.extend(collect_diagnostics(year, round_number))
        time.sleep(args.delay_seconds)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps([asdict(item) for item in candidates], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"malformed_candidates": len(candidates)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
