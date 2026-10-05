# Century Complete Listing Flow Tracker

Tracks publicly visible Century Complete home inventory through daily observations and fixed weekly listing flow. Traditional Century Communities inventory is excluded.

| Metric | Definition |
|---|---|
| Active | Homes advertised as available, plus homes awaiting a second successful absence confirmation. |
| Added | A home entering available inventory since the prior successful observation, including reappearances. The initial baseline is not an addition. |
| Removed | An available home explicitly becoming Pending, Reserved, Under Contract, Already Taken, Sold or Closed; or absent in two successive successful observations. |
| Net Change | Added minus Removed. |
| Removal ASP | Average last publicly advertised price before each removal, excluding removals with no observed price. |

Removals are a sell-through/order proxy, not confirmed official contracts. Removal ASP is an advertised-price proxy, not realized sale price. Century's reported ASP reflects delivered homes and may include economics absent from advertised prices.

Weeks are fixed seven-day periods anchored to the first successful observation, matching the reference tracker. Closed rows remain frozen. Failed captures do not advance listing comparisons or manufacture daily observations; the next successful comparison spans the gap. Blank flow values mean no comparable data. Movements are counted as events, so two removal cycles for one home remain two auditable events.

## Outputs

- `reports/weekly_report.md` — headline weekly table and current week.
- `reports/weekly_history.csv` — frozen history and current week, with completeness status.
- `reports/daily_movement.csv` — daily observations and failed-run status.
- `reports/current_added.csv`, `reports/current_removed.csv` — current fixed week's events.
- `reports/qtd_pricing.csv` — event-weighted QTD Removal ASP, priced count and Advertised Removed Value; not revenue.
- `data/snapshots/` — dated home observations and advertised prices.
- `data/state.json` — lifecycle records and immutable events, including reappearance links.
- `data/raw/`, `data/coverage/`, `data/runs/` — compressed source evidence, coverage checks and run receipts.

CSV files use UTF-8 with a byte-order mark and ordinary numeric dollar values for Excel.

## Run

Requires Python 3.12 and curl.

```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m century_tracker.run
```

The **Daily listing flow** GitHub Actions workflow runs at **12:30 UTC daily** (07:30 Central daylight time / 06:30 Central standard time) and supports **Run workflow** manual dispatch. Dates use America/Chicago. Runs are serialized; the first accepted observation each day is immutable. Updated data and reports are committed only when changed. Rejected runs commit failure evidence and report failure in Actions, preserving the previous accepted inventory.

See [implementation handoff](docs/handoff.md), [source investigation](docs/source-investigation.md), [methodology](docs/methodology.md), and [live validation](docs/live-validation.md) for scope and limitations.
