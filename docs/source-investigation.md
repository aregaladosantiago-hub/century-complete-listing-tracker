# Century website investigation

Investigation date: 2026-10-04.

The [national home search](https://www.centurycommunities.com/find-your-new-home/) uses `/api/search/findcommunities`. Its brand parameter is `brand=Century Complete`; the page's `nd` parameter is not the API brand filter. `mapShown=true` returns the complete unpaginated national community directory. The tested response returned 163 unique communities, total=163, showLoadMore=false and relaxedMatch=false. Default responses returned only 12 records; startIndex and pageNumber probes did not enumerate further records. The collector rejects such partial responses rather than assuming pagination succeeded.

Each community's ordinary HTTP response includes all home cards and embedded `data-ga-onload-event` commerce JSON. On 163 tested pages, all 915 cards matched 915 structured items. Client code sorts existing cards; no separate home pagination was found. No state or market filter is applied. Empty, sold-out and coming-soon communities are still retrieved.

Commerce items provide `item_id`, `item_brand`, address/lot name, community, advertised price and `location_id`. The ID is a stable-looking commerce SKU such as `00011062_10503_CMP`, also used by Buy Now URLs. Leading zeroes matter. A lot URL may retain an old address slug (for example, 100 Summit Creek Dr has a URL containing 1982-caboose-trail); the displayed address and SKU take priority. Longitudinal provider-ID stability remains to be established through future observations.

`/api/maps/geojson?brand=CMP` is the public map status feed. The map's public request key is discovered from `data-map-key` on a community page. Its 12,461 features included 12,174 lot geometries and 280 community geometries. Repeated geometries collapsed to 11,686 unique lot SKUs with no conflicting status, price, publication, address or URL fields. The feed includes historical Closed homes, Pending, Sold, SpecModel, Model, Unreleased, Unavailable and Available HomeSite statuses.

The map alone is insufficient: only 510 Buy Now cards matched SpecModel map lots, 3 matched Model, and 326 available cards were absent from the map. It is therefore supplemental evidence, not an inventory enumeration source. All 839 available homes are collected from community cards. The remaining 76 cards were Pending; 47 matched Pending map lots and 29 were absent from the map.

Detail-page JSON-LD is also insufficient for availability. Three sampled Pending pages still declared `https://schema.org/InStock` and retained a numeric offer price while visibly showing Pending, Call for Available Homes and no Buy Now link. The collector uses the visible status, validates public advertised prices and never uses JSON-LD InStock as availability evidence.

The production collector uses direct HTTP with JSON parsing and narrow static HTML parsing. Browser execution is unnecessary. The map feed can take about a minute; requests have bounded retries and timeout limits. The website is not an official inventory census: unpublished homes, unsupported/new directory structures, short-lived intraday changes and off-site inventory cannot be guaranteed. National coverage means all communities returned by the tested public directory, not all physical homes Century owns.
## Century Communities brand expansion

Investigated the traditional Century Communities brand separately on 2026-10-12. The national directory accepts `brand=Century Communities`; the tested response returned 268 unique Century Communities entries with `total=268`, `showLoadMore=false` and `relaxedMatch=false`. Community pages use the same quick-move-in card and embedded commerce structures, with `item_brand=Century Communities` and stable-looking commerce SKUs ending in `_CCS`.

The corresponding `brand=CCS` public map feed returned 39,293 lot features (36,789 unique lot SKUs in the accepted validation capture) and uses the same known status vocabulary. Traditional listings also exposed two supported patterns not present in the Complete fixtures: whole-dollar customer prices backed by source values containing cents, and an identity-bound `Submit An Offer` action. The collector accepts only mathematically consistent whole-dollar rounding and validates offer links against the exact SKU. A stale contracted map status must be resolved by the exact home's detail page.

Historical, unreleased, model and homesite records remain supplemental evidence rather than available-inventory enumeration. The traditional brand is therefore collected as a separate series with independent state and reports. Its baseline does not imply historical additions or removals, and its public listings do not guarantee capture of offline, personalized or pre-listing sales.

On 2026-10-13 the Century Complete directory added a `Labelle 2` entry marked `quickMoveInAvailable=false` while its linked page consistently returned HTTP 404. The entry was absent from the prior accepted directory and had no prior cards. The collector now records 404/410 evidence for such explicitly empty shells, while rejecting the capture if the page was previously populated or the directory advertises quick-move-in inventory.

22a855c4667a07cc7702b9e4b06e1105c4d2bd74
