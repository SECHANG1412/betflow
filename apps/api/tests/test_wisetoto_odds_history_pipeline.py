from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.error import URLError

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

import wisetoto_odds_history_pipeline as pipeline
from odds_history_poc import MatchHistory, Snapshot


def make_args(output_dir: Path, **overrides: object) -> argparse.Namespace:
    values = {
        "start_year": 2026,
        "end_year": 2026,
        "delay_seconds": 0,
        "retries": 1,
        "retry_delay_seconds": 0,
        "max_rounds_per_year": None,
        "max_total_rounds": None,
        "output_dir": output_dir,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def make_match(round_number: int) -> MatchHistory:
    return MatchHistory(
        "wisetoto",
        2026,
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


def test_pipeline_retries_and_writes_year_outputs(tmp_path: Path, monkeypatch) -> None:
    calls: list[int] = []
    sleeps: list[float] = []
    monkeypatch.setattr(pipeline, "discover_rounds", lambda *args, **kwargs: [1, 2])

    def flaky_collect(year: int, round_number: int):
        calls.append(round_number)
        if round_number == 1 and calls.count(1) == 1:
            raise URLError("temporary")
        return [make_match(round_number)], "page", "endpoint"

    monkeypatch.setattr(pipeline, "collect", flaky_collect)
    monkeypatch.setattr(pipeline.time, "sleep", sleeps.append)

    payload, exit_code = pipeline.run_pipeline(make_args(tmp_path, delay_seconds=0.5))

    assert exit_code == 0
    assert calls == [1, 1, 2]
    assert 0.5 in sleeps
    assert payload["summary"]["rounds_completed"] == 2
    year_payload = json.loads(
        (tmp_path / "2026" / "wisetoto_odds_history.json").read_text(encoding="utf-8")
    )
    assert len(year_payload["matches"]) == 2
    assert (tmp_path / "2026" / "wisetoto_odds_history.csv").exists()


def test_pipeline_resumes_without_collecting_completed_round(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(pipeline, "discover_rounds", lambda *args, **kwargs: [1, 2])
    collected: list[int] = []

    def collect_once(year: int, round_number: int):
        collected.append(round_number)
        return [make_match(round_number)], "page", "endpoint"

    monkeypatch.setattr(pipeline, "collect", collect_once)
    first_payload, first_code = pipeline.run_pipeline(
        make_args(tmp_path, max_total_rounds=1)
    )
    second_payload, second_code = pipeline.run_pipeline(make_args(tmp_path))

    assert first_code == 2
    assert first_payload["summary"]["stopped_early"] is True
    assert second_code == 0
    assert collected == [1, 2]
    assert second_payload["summary"]["rounds_completed"] == 2


def test_failed_round_is_separate_and_retried_on_next_run(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(pipeline, "discover_rounds", lambda *args, **kwargs: [1])
    should_fail = True

    def recoverable_collect(year: int, round_number: int):
        if should_fail:
            raise URLError("unavailable")
        return [make_match(round_number)], "page", "endpoint"

    monkeypatch.setattr(pipeline, "collect", recoverable_collect)
    failed_payload, failed_code = pipeline.run_pipeline(make_args(tmp_path, retries=0))
    should_fail = False
    recovered_payload, recovered_code = pipeline.run_pipeline(make_args(tmp_path))

    assert failed_code == 2
    assert failed_payload["failures"][0]["round_number"] == 1
    assert failed_payload["completed_rounds"] == []
    assert recovered_code == 0
    assert recovered_payload["failures"] == []
    assert recovered_payload["completed_rounds"] == [{"year": 2026, "round_number": 1}]


def test_checkpoint_rejects_different_year_range(tmp_path: Path) -> None:
    path = tmp_path / "checkpoint.json"
    pipeline.save_checkpoint(path, pipeline.empty_checkpoint(2025, 2026))

    try:
        pipeline.load_checkpoint(path, 2026, 2026)
    except ValueError as exc:
        assert "year range" in str(exc)
    else:
        raise AssertionError("different checkpoint range must be rejected")
