# WalkPedia data pipeline

Builds `walkpedia.sqlite` — the offline, spatially-indexed dataset of geotagged
Wikipedia articles that the app bundles.

## Requirements
- Python 3.10+
- `pip install -r requirements.txt`  (`mwparserfromhell` for wikitext cleaning)
- `bzip2` / `bzcat` (for the streaming fast path)

## Inputs
Download the two latest English-Wikipedia dumps:

```bash
curl -O https://dumps.wikimedia.org/enwiki/latest/enwiki-latest-geo_tags.sql.gz
curl -O https://dumps.wikimedia.org/enwiki/latest/enwiki-latest-pages-articles.xml.bz2
```

| File | ~Size | What it is |
|---|---|---|
| `enwiki-latest-geo_tags.sql.gz` | 50 MB | `page_id → lat/lon/type` for geotagged pages |
| `enwiki-latest-pages-articles.xml.bz2` | 24 GB | article wikitext (current revision) |

## Build

```bash
bzcat enwiki-latest-pages-articles.xml.bz2 \
  | python build_walkpedia_db.py \
      --geotags  enwiki-latest-geo_tags.sql.gz \
      --articles - \
      --out      walkpedia.sqlite \
      --max-summary-chars 1500
```

`--articles -` streams the decompressed XML from stdin (recommended). You can
also pass a `.bz2`/`.xml` path directly to `--articles`.

> Tip: don't run the build against a dump file that is still downloading — let
> the download finish first (decompressing a growing file stalls).

## Output
A single `walkpedia.sqlite` containing:
- `article(page_id, title, lat, lon, type, summary, summary_chars)`
- `article_rtree` — R-tree spatial index for nearest-neighbour queries
- `meta(key, value)` — build provenance (counts, dump date, settings)

## Nearest-articles query (reference)
See `docs/REQUIREMENTS.md` §4 for the R-tree bounding-box pre-filter + haversine
re-rank that powers "the 10 closest articles within 50 m."

## Tuning knobs
- `--max-summary-chars` — length of the TTS-read lead (default 1500).
- Filter by `type` or coordinate region to shrink the dataset for mobile delivery.
