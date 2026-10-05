# Methodology and operations

## Reference architecture

Reviewed `aregaladosantiago-hub/grbk-tracker` at the commit recorded in source-investigation.md, including scrape.py, scrape_base.py, validate.py, report.py, configuration, snapshots, reports and the daily workflow. The reference repository was not changed.

Retained daily collection, prior-success comparisons, physical-home keys, fixed seven-day periods anchored to the initial observation, simple CSV reports and daily GitHub commits. The existing reference implementation carries brand data forward on failures and rebuilds its weekly CSV; this tracker instead rejects unhealthy captures and stores closed weekly rows explicitly. No incentive, discounting, geographic dashboard or forecast metrics are included.

## Identity and availability

The commerce SKU (`community_lot_CMP`, including leading zeroes) is the physical-home key. URLs and address text are attributes. Changes to them do not create events. Conflicting SKU records or duplicate active addresses within a community reject the capture. A provider SKU reassignment requires manual identity review; no speculative fuzzy merges occur.

Active inventory requires a Century Complete commerce item and its matching home card with a Buy Now link, unless a known contracted flag makes it unavailable. A contradictory available card and contracted map status rejects the run. Model status alone does not override a public Buy Now home card: some saleable homes retain Model in the map feed. Vacant/unreleased homesites, floor plans and unavailable model homes are excluded.

Pending, Reserved, Under Contract, Already Taken, Sold and Closed are explicit removals only when the same home was previously active. A home appearing initially as Pending is not counted as a removal. Pending labels are currently observed live; other contracted labels are supported without claiming they were observed during setup.

A home absent from both current cards and explicit contracted map observations remains provisionally active on its first successful absence. Its second successive successful absence records removal on that second date. Failures do not increment the counter. Returning before confirmation creates no movement. Raw snapshots contain observed homes only: held homes are not fabricated observations. The state retains their original last_seen and missing_count.

Reappearances create an Added event with `reappearance=true` and `prior_removal_id`. The prior removal and its price remain unchanged. A later removal has its own event ID and price. This supports a future adjusted dataset without revising raw history.

## Prices and periods

Prices are integer cents internally. For active cards, displayed current price, card data-price and commerce item price must agree. Malformed or implausible prices reject the run. Zero/absent prices are missing, never zero-dollar removals. Pending pages may retain stale numeric prices while displaying a call-for-availability message; those hidden prices are not used to refresh the pre-removal price.

A removal uses the latest previously observed publicly advertised available price, with its observation date retained. If an intervening available observation lacks a price, the latest known advertised price remains attached and its older date remains visible. No price after removal replaces it.

Daily/weekly ASP = sum of attached prices / priced removal events. Unpriced removals count in Removed but not in that denominator. QTD uses individual removal events within calendar-quarter boundaries, never an unweighted mean of weekly ASPs. Advertised Removed Value sums the same prices. When prices are missing, total Removed multiplied by ASP is not the correct value; use priced removals.

Repeated cycles count as repeated events, including within a week. This deliberately differs from the reference's within-week unique-key unions, preserves Active reconciliation and avoids discarding subsequent removals. The baseline contributes no Adds. Closed periods retain their original metrics even when homes later return. A skipped day is not inserted. A failed scheduled attempt has a failed row with blank inventory/flows, not a zero-movement observation. Events following a gap belong to the successful observation date; their exact intervening occurrence dates are unknown.

`closed_incomplete` identifies closed weeks with fewer than seven comparable daily observations, including the baseline week. Active is the last successful observation inside that week; an entirely unobserved week is blank. Coverage may still be stale within an incomplete period, so inspect daily status before using the headline.

## Health gates

All national directory entries must be captured and verified as Century Complete. The directory's declared total must equal unique records, showLoadMore must be false and relaxedMatch must be false. A second directory read must have the same community IDs. Every community page must be retrieved; every displayed card must match a structured commerce item. Empty pages require a recognizable community schema. Unknown statuses, ambiguous availability, conflicting prices and duplicates reject the candidate.

Baseline minimums: 100 communities, 5,000 unique historical map lots and 300 available homes. Subsequent captures reject declines exceeding 20% in communities, map lots or available homes; exceeding 30% in any market with at least ten prior active homes; or exceeding 50% of cards in a community with at least five. Any disappearing directory community requires review. These conservative rules can reject genuine large changes; they never silently weaken themselves.

If a gate trips, inspect the failed run receipt and compressed evidence, compare the affected source with the website, and correct the parser or documented threshold through a reviewed code change. Do not delete prior history, disable gates wholesale, or fabricate a replacement day. The next successful run compares with the previous accepted state. Failure evidence may contain full responses if processing stopped before evidence reduction.

Receipts preserve response URL, retrieval time, byte length and original SHA-256. Successful raw archives retain the exact relevant card attributes, labels, prices, links and commerce items, plus map fields used in parsing. Marketing text and image payloads are omitted to control repository growth. Snapshots and source receipts remain dated; there is no retention deletion job.

A publication-ready marker is written only after all intended outputs are saved; an unexpected output-writing failure prevents the workflow from committing partial files. GitHub commits are the publication boundary: data, state and reports are committed together. A push rejected by concurrent changes fails visibly; it never force-pushes. Scheduled GitHub execution is best effort, may be delayed, and public-repository schedules can be disabled after inactivity. Monitor Actions status and repository activity. Source APIs are undocumented and may change.
