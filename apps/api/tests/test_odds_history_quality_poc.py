import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

import odds_history_quality_poc


def test_reports_malformed_candidate_with_identity_and_reason(monkeypatch) -> None:
    block = """
    <ul>
      <li><span onclick="rs('2011','68','9','sc','w','w','n', 'n')" class="pt">1.80</span></li>
      <li><span onclick="rs('2011','68','9','sc','d','w','n', 'n')" class="pt">3.10</span></li>
      <li><span onclick="rs('2011','68','9','sc','l','w','n', 'n')" class="pt">3.80</span></li>
      <li><span onclick="tr('1','2','2011-01-01 12:00:00','h')">Home</span></li>
      <li><span onclick="tr('1','2','2011-01-01 12:00:00','a')">Away</span></li>
      <li><span onMouseOver="msgset_list('승 (기존) 1.90 배당 (변경) 1.80 배당');"></span></li>
      <li id="db123_9" onclick="get_gameinfo_detail('123','9','pt1', 'proto')"></li>
    </ul>
    """

    def raise_parse_error(*_args, **_kwargs):
        raise ValueError("unaligned transition counts")

    monkeypatch.setattr(odds_history_quality_poc, "parse_match_block", raise_parse_error)
    result = odds_history_quality_poc.diagnose_round(block, 2011, 68)

    assert len(result) == 1
    assert result[0].source_schedule_id == "123"
    assert result[0].source_match_id == "9"
    assert "unaligned transition counts" in result[0].reason
