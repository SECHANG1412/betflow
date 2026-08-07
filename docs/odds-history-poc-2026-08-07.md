# Odds history feasibility PoC — 2026-08-07

## Decision

The core dataset is technically obtainable from WiseToto without login: its
public Proto round response contains ordered `(previous) -> (changed)` odds
transitions for football 1X2 rows. Exact change timestamps are not included.

This is a promising source, but it is not yet approved as a production data
dependency. Terms of use, redistribution rights, completeness, and structural
stability still require confirmation.

## Verified result

- Reconstructed one match with four ordered snapshots and a result.
- Expanded successfully to ten matches from 2026 round 78.
- Wrote normalized JSON and CSV.
- Verified historical transitions in 2010 round 1.
- The year selector exposes 2009–2026, but sampled 2009 rounds 1 and 50 had no
  football 1X2 rows with change history. Therefore the currently demonstrated
  lower bound is 2010, not 2009.
- No login, cookie, or paid API was required for the successful WiseToto run.

Example (Switzerland vs Algeria, 2026 round 78):

```text
seq 0  1.95 / 3.15 / 3.55
seq 1  1.89 / 3.15 / 3.80
seq 2  1.86 / 3.15 / 3.90
seq 3  1.81 / 3.25 / 4.00
result = HOME
```

## Source assessment

| Source | Full ordered history | Timestamps | Free/no login | PoC assessment |
|---|---:|---:|---:|---|
| WiseToto | Yes, sampled | No | Yes | Technically viable; HTML/AJAX contract is undocumented and can change |
| Betman | Not demonstrated | Not demonstrated | Public page exists | Direct automated request was reset; official page is suited to forward collection, not proven historical reconstruction |
| BetScore | Claimed to track Betman flow | Unknown | No public web/API proof | App description mentions premium analysis; no free public historical export/API found |
| TotalCorner | Page claims odds movement | Unknown | Page is public | Cloudflare challenge blocks unattended collection; unsuitable for stable free automation |
| The Odds API | Yes | Yes | No | Historical endpoint is paid, so excluded by requirement |

## Data caveats

1. WiseToto gives transition order but not transition time.
2. The response is explicitly described by WiseToto as unofficial/provisional;
   official results should be cross-checked.
3. Completeness must be measured across all rounds: a row without a change
   tooltip may mean no change, or missing retained history.
4. The source uses undocumented page and AJAX parameters. Add fixtures,
   schema checks, throttling, retries, and a source-health monitor before any
   bulk backfill.
5. Do not begin model, frontend, or final database design until coverage and
   terms/permission have been audited.

## Reproduction

```powershell
venv\Scripts\python.exe apps\api\scripts\odds_history_poc.py `
  --year 2026 --round 78 --limit 10 `
  --output-dir artifacts\odds-history-poc\round-78
```

Outputs:

- `artifacts/odds-history-poc/round-78/wisetoto_odds_history.json`
- `artifacts/odds-history-poc/round-78/wisetoto_odds_history.csv`

## Next gate

Before approving a full backfill, scan every round from 2010–2026 and report:

- total football 1X2 matches;
- matches with zero, one, or multiple changes;
- broken/misaligned transition chains;
- result completeness;
- per-year coverage and gaps;
- request failure/rate-limit behavior;
- written permission or terms assessment for automated collection and use.
