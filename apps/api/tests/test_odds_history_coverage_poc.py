import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

import odds_history_coverage_poc as coverage


def test_extracts_rounds_from_selector_and_links() -> None:
    page = """
    <select name="" onchange="location.href='?game_round='+this.value">
      <option value="3">3회차</option>
      <option value="1">1회차</option>
    </select>
    <a href="?game_round=2">2회차</a>
    """

    assert coverage.extract_available_rounds(page) == [1, 2, 3]


def test_inspects_changed_unchanged_and_unknown_rows() -> None:
    changed = _match_block("100", "홈승", transition=True)
    unchanged = _match_block("101", "", transition=False)

    result = coverage.inspect_round(changed + unchanged, 2026, 80)

    assert result.total_matches == 2
    assert result.matches_without_changes == 1
    assert result.matches_with_one_change == 1
    assert result.matches_with_multiple_changes == 0
    assert result.unknown_results == 1
    assert result.malformed_matches == 0
    assert result.total_snapshots == 3


def test_scan_checkpoints_and_resumes(tmp_path: Path, monkeypatch) -> None:
    calls: list[tuple[int, int]] = []

    monkeypatch.setattr(coverage, "discover_rounds", lambda *args, **kwargs: [1, 2])

    def fake_collect(year: int, round_number: int, **kwargs) -> coverage.RoundCoverage:
        calls.append((year, round_number))
        match = coverage.MatchCoverage(str(round_number), "HOME", 2, 1)
        return coverage.RoundCoverage(year, round_number, 1, 0, 1, 0, 0, 0, 2, [match])

    monkeypatch.setattr(coverage, "collect_round_coverage", fake_collect)
    monkeypatch.setattr(coverage.time, "sleep", lambda _: None)
    args = argparse.Namespace(
        start_year=2026,
        end_year=2026,
        delay_seconds=0,
        retries=0,
        retry_delay_seconds=0,
        max_rounds_per_year=None,
        max_total_rounds=1,
        output_dir=tmp_path,
    )

    first_payload, first_exit = coverage.run_scan(args)
    assert first_exit == 2
    assert first_payload["summary"]["rounds_scanned"] == 1

    args.max_total_rounds = None
    second_payload, second_exit = coverage.run_scan(args)

    assert second_exit == 0
    assert calls == [(2026, 1), (2026, 2)]
    assert second_payload["metadata"]["completed"] is True
    assert second_payload["summary"] == {
        "rounds_scanned": 2,
        "rounds_failed": 0,
        "total_matches": 2,
        "matches_without_changes": 0,
        "matches_with_one_change": 2,
        "matches_with_multiple_changes": 0,
        "unknown_results": 0,
        "malformed_matches": 0,
        "total_snapshots": 4,
    }
    checkpoint = json.loads(
        (tmp_path / "wisetoto_coverage_checkpoint.json").read_text(encoding="utf-8")
    )
    assert len(checkpoint["rounds"]) == 2


def _match_block(match_id: str, result: str, *, transition: bool) -> str:
    tooltip = ""
    if transition:
        tooltip = """
        <li><span onMouseOver="msgset_list('승 (기존) 1.49 배 → (변경) 1.48 배<br/>
        무 (기존) 3.70 배 → (변경) 3.85 배<br/>
        패 (기존) 5.90 배 → (변경) 5.70 배');"></span></li>
        """
    result_tag = f'<li><span class="tag x_medium type04">{result}</span></li>'
    return f"""
    <ul>
      <li><span onclick="tr('1','2','2026-07-10 05:00:00','h')">홈팀</span></li>
      <li><span onclick="tr('1','2','2026-07-10 05:00:00','a')">원정팀</span></li>
      <li><span onclick="rs('2026','80','{match_id}','sc','w','w','n', 'n')" class="pt">1.48</span></li>
      <li><span onclick="rs('2026','80','{match_id}','sc','d','w','n', 'n')" class="pt">3.85</span></li>
      <li><span onclick="rs('2026','80','{match_id}','sc','l','w','n', 'n')" class="pt">5.70</span></li>
      {result_tag}
      {tooltip}
      <li id="db476710_{match_id}" onclick="get_gameinfo_detail('476710','{match_id}','pt1', 'proto', '2026', '80', event, '30', 'n');"></li>
    </ul>
    """
