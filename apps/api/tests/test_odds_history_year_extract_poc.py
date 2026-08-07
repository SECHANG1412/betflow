import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

import odds_history_year_extract_poc as extractor
from odds_history_poc import MatchHistory, Snapshot


def test_extracts_all_rounds_and_summarizes_sequences(monkeypatch) -> None:
    calls: list[tuple[int, int]] = []

    def fake_collect(year: int, round_number: int):
        calls.append((year, round_number))
        match = MatchHistory(
            "wisetoto",
            year,
            round_number,
            str(round_number),
            "1",
            "2026-01-01 12:00:00",
            "Home",
            "Away",
            "HOME",
            False,
            [Snapshot(0, None, 2.0, 3.0, 4.0), Snapshot(1, None, 1.9, 3.1, 4.2)],
        )
        return [match], "page", "endpoint"

    monkeypatch.setattr(extractor, "collect", fake_collect)
    monkeypatch.setattr(extractor.time, "sleep", lambda _: None)

    matches, metadata = extractor.extract_year(2026, [1, 2], delay_seconds=1)

    assert calls == [(2026, 1), (2026, 2)]
    assert len(matches) == 2
    assert metadata["matches_written"] == 2
    assert metadata["snapshots_written"] == 4
    assert metadata["rounds_failed"] == {}
