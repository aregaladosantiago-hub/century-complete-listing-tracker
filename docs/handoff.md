# Implementation handoff

The tracker is operational in [century-complete-listing-tracker](https://github.com/aregaladosantiago-hub/century-complete-listing-tracker). The repository initially created as century-complete-tracker was renamed to the requested name; it is the same repository. The GRBK repository was inspected and left unchanged.

## Collection and accounting

1. **Source:** Century's national community JSON API plus embedded commerce JSON and static home cards. The public map API supplements contracted statuses. Browser execution is not required.
2. **Coverage:** 163 communities, 915 cards: **839 available homes and 76 Pending** on the first test and GitHub baseline. All ten active states were sampled. Full coverage is relative to the public directory, not an official inventory census.
3. **Identity:** Century commerce SKU, such as `00011062_10503_CMP`, preserving community and lot leading zeroes. URLs and addresses are retained as attributes.
4. **Added:** Home enters accepted available inventory relative to the previous successful comparable observation. Initial baseline homes are not Adds. Reappearances are Adds with a link to the previous removal.
5. **Removed:** Previously active home explicitly becomes Pending, Reserved, Under Contract, Already Taken, Sold or Closed; or is absent in two successive successful observations. Removal is dated when confirmed. Failed observations do not advance this rule.
6. **Contracted homes:** May remain online with a Pending flag and no Buy Now link. They are excluded from Active even when their URL survives. Initially observed contracted homes create no removal event.
7. **Reappearances:** Retain the same SKU; append a linked reappearance event without rewriting a past removal, price or closed week. Subsequent removals remain distinct events.
8. **Price:** Current displayed advertised home price, cross-checked against embedded commerce price and card data-price. Pending hidden prices do not refresh the last available price.
9. **Removal ASP:** Sum of last previously observed advertised available prices divided by priced removal events. Missing prices are excluded from the denominator, never treated as zero. QTD uses individual events, with a priced-removal count and Advertised Removed Value.
10. **Failure protection:** Complete directory/count checks, all-community retrieval, brand/SKU/card reconciliation, duplicate and price checks, national/market/community decline gates, and two-successful-observation absence confirmation. Unknown schemas/statuses fail closed. Only completed output publication is eligible for a GitHub commit.

## Repository layout

```text
century_tracker/         collector, accounting engine and daily command
.github/workflows/      daily collection and regression tests
tests/                  synthetic accounting tests and live-derived parser fixtures
docs/                   methodology, source investigation, validation and handoff
data/snapshots/         immutable observed daily homes and prices
data/state.json         lifecycle state, events and frozen weekly history
data/raw/               compressed source evidence and response receipts
data/coverage/          accepted coverage manifests
data/runs/              successful/rejected run records
reports/                weekly report and five support CSVs
```

The **Daily listing flow** workflow runs at **12:30 UTC daily**, equivalent to 07:30 CDT / 06:30 CST. Manual dispatch works. Dates use America/Chicago. No local machine or separate scheduled service is required.

## Baseline output

| Week | Period | Active | Added | Removed | Net Change | Removal ASP |
|---|---|---:|---:|---:|---:|---:|
| Week 1 | 2026-10-04 to 2026-10-10 | 839 | — | — | — | — |

The baseline has no prior comparable observation; blanks are intentional. Its 839 homes are not presented as newly added inventory. Weeks follow the reference's seven-day anchor from the first accepted day, rather than forcing a Monday start.

Actual daily CSV:

```csv
date,active,added,removed,net_change,removal_asp,scrape_status
2026-10-04,839,,,,,baseline
```

Actual weekly CSV:

```csv
week,period_start,period_end,active,added,removed,net_change,removal_asp,status
Week 1,2026-10-04,2026-10-10,839,,,,,current
```

Current added/removed files correctly contain headers only until movements are observed:

```csv
date,address,lot,community,advertised_price,url
```

```csv
date,address,lot,community,last_advertised_price,url
```

## Verification and limitations

- **34 automated tests passed**, locally and on GitHub's runner.
- **13 individual live home pages checked:** ten active, one per state, plus three Pending. Addresses and advertised prices matched; Pending pages suppressed public price and Buy Now.
- [Initial manual collection](https://github.com/aregaladosantiago-hub/century-complete-listing-tracker/actions/runs/37254756947) succeeded, collecting and committing the baseline.
- [Second manual run](https://github.com/aregaladosantiago-hub/century-complete-listing-tracker/actions/runs/37255193527) succeeded on the final implementation, passed all 34 tests and preserved today's snapshot. SHA-256 before and after: `1176e48a383e8671b2d2491754ec7e61d81e5d4d3af438f5d1a2aeeee5feb04f`.
- The scheduled trigger is configured; its first future scheduled execution has not yet occurred.

The map alone misses many available homes. JSON-LD can falsely label Pending homes InStock. The implementation avoids both assumptions. Century's endpoints remain undocumented; true broad source changes can require manual review and temporarily stop collection. Public removals are not official contracts, and Removal ASP is not delivered ASP or realized sale price. Two-observation absence confirmation delays ambiguous removals and provisionally retains such homes in Active. Gaps cannot reveal exact event dates or intraday cycles. SKU persistence is supported by current source structure and tested identity handling, but future provider reassignment cannot be ruled out. Frozen raw event history enables future adjusted analysis without claiming that every removal represents a completed order.
