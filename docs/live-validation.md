# Live validation

2026-10-04: inspected 13 individual home pages independently of their community cards: one available home in each of ten states, plus three Pending homes. All ten advertised prices and addresses matched. All three Pending pages retained their URLs and suppressed Buy Now and the visible numeric price.

| Home SKU | Address | Status | Advertised price | Result |
|---|---|---|---:|---|
| [00011150_0009_CMP](https://www.centurycommunities.com/find-your-new-home/alabama/birmingham-metro/childersburg/griffin-creek/lots/0009-135-griffin-dr/) | 135 Griffin Dr | Available | $195,888 | Match |
| [00010657_0307_CMP](https://www.centurycommunities.com/find-your-new-home/arizona/phoenix-metro/arizona-city/arizona-city/lots/0307-11070-w-penasco-dr/) | 11070 W Penasco Dr | Available | $229,990 | Match |
| [00010135_H005_CMP](https://www.centurycommunities.com/find-your-new-home/florida/treasure-coast-metro/vero-beach/vero-lake-estates/lots/h005-8245-101st-ct/) | 8245 101St Ct | Available | $343,990 | Match |
| [00010655_0376_CMP](https://www.centurycommunities.com/find-your-new-home/georgia/macon-metro/lizella/arrowhead-by-the-lake/lots/0376-119-sundance-court/) | 119 Sundance Court | Available | $238,888 | Match |
| [00011225_0101_CMP](https://www.centurycommunities.com/find-your-new-home/indiana/louisville-metro-in/lanesville/woods-of-heritage-hills/lots/0101-6565-calla-lilly-court/) | 6565 Calla Lilly Court | Available | $286,990 | Match |
| [00011035_0029_CMP](https://www.centurycommunities.com/find-your-new-home/kentucky/louisville-metro-ky/elizabethtown/summit-creek/lots/0029-1982-caboose-trail-470dd382/) | 100 Summit Creek Dr | Available | $279,990 | Match |
| [00011242_0037_CMP](https://www.centurycommunities.com/find-your-new-home/michigan/grand-rapids-metro/coopersville/reserve-of-coopersville/lots/0037-702-norway-lane/) | 702 NORWAY LANE | Available | $354,990 | Match |
| [00010476_0067_CMP](https://www.centurycommunities.com/find-your-new-home/north-carolina/greensboro-high-point-metro/liberty/ferguson-creek-village/lots/0067-6106-patrum-trace/) | 6106 Patrum Trace | Available | $313,990 | Match |
| [00011261_0141_CMP](https://www.centurycommunities.com/find-your-new-home/nevada/pahrump-metro/pahrump/lca---ishani-ridge/lots/0141-668-s-dyani-dr/) | 668 S Dyani Dr | Available | $329,990 | Match |
| [00010835_0101_CMP](https://www.centurycommunities.com/find-your-new-home/south-carolina/upstate-south-carolina-metro/anderson/shockley-bend/lots/0101---31b6425a/) | 103 Bunter Trail | Available | $258,990 | Match |
| [00010132_18110_CMP](https://www.centurycommunities.com/find-your-new-home/florida/treasure-coast-metro/fort-pierce/lakewood-park/lots/18110-7201-palomar-pkwy/) | 7201 Palomar Pkwy | Pending | Call for Available Homes | Match |
| [00010593_568507_CMP](https://www.centurycommunities.com/find-your-new-home/florida/gulf-coast-metro/cape-coral/cape-coral-classic/lots/568507-3913-andalusia-blvd/) | 3913 Andalusia Blvd | Pending | Call for Available Homes | Match |
| [00010655_0388_CMP](https://www.centurycommunities.com/find-your-new-home/georgia/macon-metro/lizella/arrowhead-by-the-lake/lots/0388-111-dream-catcher-drive/) | 111 Dream Catcher Drive | Pending | Call for Available Homes | Match |

Nationwide community-card cross-check: 163/163 pages; 915/915 cards matched structured commerce items; 839 unique active SKUs and 76 Pending; all 839 active prices valid. No active duplicates. The map feed had duplicate geometries but no contradictory home fields.

Automated regression suite: 34 tests passed locally. Tests cover baseline treatment, identity continuity, additions, explicit removals, disappearance confirmation, failed/partial captures, reappearances and repeated cycles, frozen history, missing weeks, malformed/missing prices, last available prices, weighted QTD pricing, CSV formatting, national directory completeness, brand isolation, card counts, and map/card conflicts.

Longitudinal SKU stability and future source coverage remain observational limitations. A synthetic test proves URL/address changes do not change identity; it does not prove Century will never reassign SKUs.

GitHub Actions: initial Validate tracker run passed; manual Daily listing flow run [37254756947](https://github.com/aregaladosantiago-hub/century-complete-listing-tracker/actions/runs/37254756947) completed successfully and committed the 2026-10-04 baseline (839 active).
