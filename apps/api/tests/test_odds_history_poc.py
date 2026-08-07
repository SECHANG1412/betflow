import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from odds_history_poc import parse_match_block, reconstruct_snapshots


def test_reconstructs_ordered_snapshots() -> None:
    snapshots = reconstruct_snapshots(
        {"home": 1.92, "draw": 3.35, "away": 3.20},
        {
            "home": [(2.10, 2.05), (2.05, 1.98), (1.98, 1.92)],
            "draw": [(3.20, 3.25), (3.25, 3.30), (3.30, 3.35)],
            "away": [(2.85, 2.95), (2.95, 3.10), (3.10, 3.20)],
        },
    )

    assert [(item.home, item.draw, item.away) for item in snapshots] == [
        (2.10, 3.20, 2.85),
        (2.05, 3.25, 2.95),
        (1.98, 3.30, 3.10),
        (1.92, 3.35, 3.20),
    ]


def test_parses_public_wisetoto_row() -> None:
    block = """
    <ul>
      <li class="a6"><span class="tnb" onclick="tr('1','2','2026-07-10 05:00:00','h')">프랑스</span></li>
      <li class="a8"><span class="tn" onclick="tr('1','2','2026-07-10 05:00:00','a')">모로코</span></li>
      <li><span onclick="rs('2026','80','6277','sc','w','w','n', 'n')" class="pt">1.48</span></li>
      <li><span onclick="rs('2026','80','6277','sc','d', 'w','n', 'n')" class="pt">3.85</span></li>
      <li><span onclick="rs('2026','80','6277','sc','l', 'w','n', 'n')" class="pt">5.70</span></li>
      <li><span class="tag x_medium type04">홈승</span></li>
      <li><span onMouseOver="msgset_list('승 (기존) 1.49 배 → (변경) 1.48 배<br/>무 (기존) 3.70 배 → (변경) 3.85 배<br/>패 (기존) 5.90 배 → (변경) 5.70 배');"></span></li>
      <li id="db476710_6277" onclick="get_gameinfo_detail('476710','6277','pt1', 'proto', '2026', '80', event, '30', 'n');"></li>
    </ul>
    """

    match = parse_match_block(block, 2026, 80)

    assert match is not None
    assert match.result == "HOME"
    assert match.home_team == "프랑스"
    assert [(row.home, row.draw, row.away) for row in match.snapshots] == [
        (1.49, 3.70, 5.90),
        (1.48, 3.85, 5.70),
    ]
