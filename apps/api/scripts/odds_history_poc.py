"""PoC collector for public WiseToto Proto 1X2 odds-change history.

The source exposes ordered ``(previous) -> (changed)`` transitions without
timestamps.  This script reconstructs the snapshot order, writes JSON/CSV,
and intentionally ignores handicap, totals, first-half, and non-football rows.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE_URL = "https://www.wisetoto.com"
USER_AGENT = "BetFlow public-data feasibility PoC/0.1"


@dataclass(frozen=True)
class Snapshot:
    sequence: int
    observed_at: None
    home: float
    draw: float
    away: float


@dataclass(frozen=True)
class MatchHistory:
    source: str
    source_year: int
    source_round: int
    source_match_id: str
    source_schedule_id: str
    starts_at: str
    home_team: str
    away_team: str
    result: str
    timestamps_available: bool
    snapshots: list[Snapshot]


def fetch_text(url: str, *, referer: str | None = None) -> str:
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,*/*;q=0.8"}
    if referer:
        headers["Referer"] = referer
        headers["X-Requested-With"] = "XMLHttpRequest"
    request = Request(url, headers=headers)
    with urlopen(request, timeout=30) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def round_page_url(year: int, round_number: int) -> str:
    query = urlencode(
        {
            "game_category": "pt1",
            "game_round": round_number,
            "game_type": "pt",
            "game_year": year,
            "tab_type": "proto",
        }
    )
    return f"{BASE_URL}/index.htm?{query}"


def extract_master_id(page: str, year: int, round_number: int) -> str:
    pattern = re.compile(
        rf"get_gameinfo_body\('proto','pt1','{year}','{round_number}',"
        rf"'','','(?P<id>\d+)'"
    )
    match = pattern.search(page)
    if not match:
        raise ValueError(f"round master id not found for {year}/{round_number}")
    return match.group("id")


def round_list_url(year: int, round_number: int, master_id: str) -> str:
    query = urlencode(
        {
            "game_category": "pt1",
            "game_year": year,
            "game_round": round_number,
            "game_month": "",
            "game_day": "",
            "game_info_master_seq": master_id,
            "sports": "sc",
            "sort": "game_no_asc",
            "tab_type": "proto",
        }
    )
    return f"{BASE_URL}/util/gameinfo/get_proto_list.htm?{query}"


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", value))).strip()


def parse_current_odds(block: str) -> dict[str, float]:
    odds: dict[str, float] = {}
    pattern = re.compile(
        r"rs\('[^']+','[^']+','[^']+','sc','(?P<side>[wdl])',"
        r"\s*'[^']+','n',\s*'n'\).*?class=\"pt\">(?P<odd>\d+(?:\.\d+)?)",
        re.DOTALL,
    )
    side_names = {"w": "home", "d": "draw", "l": "away"}
    for match in pattern.finditer(block):
        odds[side_names[match.group("side")]] = float(match.group("odd"))
    return odds


def parse_transitions(block: str) -> dict[str, list[tuple[float, float]]]:
    decoded = html.unescape(block)
    transitions: dict[str, list[tuple[float, float]]] = {
        "home": [],
        "draw": [],
        "away": [],
    }
    pattern = re.compile(
        r"(?P<side>승|무|패)\s*\(기존\)\s*(?P<old>\d+(?:\.\d+)?)\s*배\s*"
        r"→\s*\(변경\)\s*(?P<new>\d+(?:\.\d+)?)\s*배"
    )
    side_names = {"승": "home", "무": "draw", "패": "away"}
    for match in pattern.finditer(decoded):
        transitions[side_names[match.group("side")]].append(
            (float(match.group("old")), float(match.group("new")))
        )
    return transitions


def reconstruct_snapshots(
    current: dict[str, float], transitions: dict[str, list[tuple[float, float]]]
) -> list[Snapshot]:
    counts = {len(values) for values in transitions.values()}
    if counts == {0}:
        return [Snapshot(0, None, current["home"], current["draw"], current["away"])]
    if len(counts) != 1:
        raise ValueError(f"unaligned transition counts: {transitions}")

    count = counts.pop()
    snapshots = [
        Snapshot(
            0,
            None,
            transitions["home"][0][0],
            transitions["draw"][0][0],
            transitions["away"][0][0],
        )
    ]
    for index in range(count):
        snapshots.append(
            Snapshot(
                index + 1,
                None,
                transitions["home"][index][1],
                transitions["draw"][index][1],
                transitions["away"][index][1],
            )
        )

    final = snapshots[-1]
    if (final.home, final.draw, final.away) != (
        current["home"],
        current["draw"],
        current["away"],
    ):
        raise ValueError("transition chain does not end at current/final odds")
    return snapshots


def parse_match_block(block: str, year: int, round_number: int) -> MatchHistory | None:
    identity = re.search(
        r"id=\"db(?P<schedule>\d+)_(?P<match>\d+)\".*?"
        r"get_gameinfo_detail\('[^']+','[^']+','pt1',\s*'proto'",
        block,
        re.DOTALL,
    )
    if not identity or "'sc'" not in block or "'n', 'n'" not in block:
        return None

    current = parse_current_odds(block)
    if set(current) != {"home", "draw", "away"}:
        return None

    team_matches = re.findall(
        r"onclick=\"tr\('[^']+','[^']+','(?P<date>[^']+)','[ha]'\)\">(?P<team>[^<]+)</span>",
        block,
    )
    if len(team_matches) < 2:
        return None

    result_match = re.search(r'class="tag[^\"]*">([^<]+)</span>', block)
    result_names = {"홈승": "HOME", "무승부": "DRAW", "홈패": "AWAY"}
    result = result_names.get(clean_text(result_match.group(1)) if result_match else "", "UNKNOWN")
    transitions = parse_transitions(block)
    snapshots = reconstruct_snapshots(current, transitions)

    return MatchHistory(
        source="wisetoto",
        source_year=year,
        source_round=round_number,
        source_match_id=identity.group("match"),
        source_schedule_id=identity.group("schedule"),
        starts_at=team_matches[0][0],
        home_team=clean_text(team_matches[0][1]),
        away_team=clean_text(team_matches[1][1]),
        result=result,
        timestamps_available=False,
        snapshots=snapshots,
    )


def parse_round(page: str, year: int, round_number: int) -> list[MatchHistory]:
    matches: list[MatchHistory] = []
    for block in re.findall(r"<ul\b[^>]*>.*?</ul>", page, re.DOTALL | re.IGNORECASE):
        try:
            parsed = parse_match_block(block, year, round_number)
        except ValueError as exc:
            print(f"skip malformed row: {exc}", file=sys.stderr)
            continue
        if parsed and len(parsed.snapshots) > 1:
            matches.append(parsed)
    return matches


def collect(year: int, round_number: int) -> tuple[list[MatchHistory], str, str]:
    page_url = round_page_url(year, round_number)
    page = fetch_text(page_url)
    master_id = extract_master_id(page, year, round_number)
    list_url = round_list_url(year, round_number, master_id)
    return parse_round(fetch_text(list_url, referer=page_url), year, round_number), page_url, list_url


def write_outputs(matches: list[MatchHistory], output_dir: Path, metadata: dict[str, object]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {"metadata": metadata, "matches": [asdict(match) for match in matches]}
    (output_dir / "wisetoto_odds_history.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    with (output_dir / "wisetoto_odds_history.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        fields = [
            "source_year",
            "source_round",
            "source_match_id",
            "source_schedule_id",
            "starts_at",
            "home_team",
            "away_team",
            "result",
            "sequence",
            "observed_at",
            "home",
            "draw",
            "away",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for match in matches:
            common = {
                key: value
                for key, value in asdict(match).items()
                if key not in {"source", "timestamps_available", "snapshots"}
            }
            for snapshot in match.snapshots:
                writer.writerow(common | asdict(snapshot))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--round", dest="round_number", type=int, default=80)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument(
        "--output-dir", type=Path, default=Path("artifacts/odds-history-poc")
    )
    args = parser.parse_args()

    try:
        matches, page_url, list_url = collect(args.year, args.round_number)
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        print(f"collection failed: {exc}", file=sys.stderr)
        return 1

    selected = matches[: args.limit]
    metadata = {
        "collected_at": datetime.now(UTC).isoformat(),
        "source_page": page_url,
        "source_endpoint": list_url,
        "requested_limit": args.limit,
        "matches_with_history_found": len(matches),
        "matches_written": len(selected),
        "timestamps_available": False,
        "history_semantics": "ordered transitions exposed by source; exact change times absent",
    }
    write_outputs(selected, args.output_dir, metadata)
    print(json.dumps(metadata, ensure_ascii=False, indent=2))
    return 0 if len(selected) >= args.limit else 2


if __name__ == "__main__":
    raise SystemExit(main())
