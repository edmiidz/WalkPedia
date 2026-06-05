#!/usr/bin/env python3
"""
build_walkpedia_db.py  —  WalkPedia offline dataset builder.

Turns two Wikipedia dumps into a single, mobile-ready SQLite database of
geotagged articles with an R-tree spatial index, so the app can answer
"the N closest articles within R metres" instantly and fully offline.

INPUTS
  --geotags   enwiki-latest-geo_tags.sql.gz     (page_id -> lat/lon, ~50 MB)
  --articles  enwiki-latest-pages-articles.xml.bz2 (article wikitext, ~24 GB)

OUTPUT  (--out walkpedia.sqlite)
  article(page_id PK, title, lat, lon, type, summary, summary_chars)
  article_rtree  -- R-tree(page_id, min_lat,max_lat, min_lon,max_lon)
  meta(key, value)

USAGE
  # full build:
  bzcat enwiki-latest-pages-articles.xml.bz2 \
    | ./build_walkpedia_db.py --geotags enwiki-latest-geo_tags.sql.gz \
                              --articles - --out walkpedia.sqlite

  # the --articles - reads the decompressed XML stream from stdin (fast path).
  # Alternatively pass a .bz2 path to --articles and it will decompress itself.

DESIGN NOTES
  * geo_tags is parsed with a positional regex over the INSERT tuples — robust
    because the fields we need (page_id, globe, primary, lat, lon, type) all
    precede the free-text fields that could contain commas/quotes.
  * Only globe='earth' + gt_primary=1 coordinates are kept (one point/article).
  * Article text is reduced to its lead section and stripped to plain prose,
    which is what you actually want a TTS voice to read as you walk past.
  * Truncated input streams are tolerated, so you can test on a partial download.
"""
import argparse, bz2, gzip, re, sqlite3, sys, time
import xml.etree.ElementTree as ET

try:
    import mwparserfromhell
except ImportError:
    mwparserfromhell = None

# --- geo_tags row: (gt_id,gt_page_id,'globe',gt_primary,gt_lat,gt_lon,gt_dim,'type',...)
# capture: 1=page_id 2=globe 3=primary 4=lat 5=lon 6=type(optional)
GEO_ROW = re.compile(
    r"\(\d+,(\d+),'([^']*)',([01]),"
    r"(-?\d+(?:\.\d+)?|NULL),(-?\d+(?:\.\d+)?|NULL),"
    r"(?:-?\d+|NULL),(?:'([^']*)'|NULL)"
)

HEADING = re.compile(r"^==+.*?==+\s*$", re.MULTILINE)


def localname(tag):
    return tag.rsplit('}', 1)[-1]


def load_geotags(path):
    """Return dict page_id -> (lat, lon, type) for earth/primary coordinates."""
    coords = {}
    opener = gzip.open if path.endswith('.gz') else open
    t0 = time.time()
    with opener(path, 'rt', encoding='utf-8', errors='replace') as fh:
        for line in fh:
            if not line.startswith('INSERT INTO'):
                continue
            for m in GEO_ROW.finditer(line):
                pid, globe, primary, lat, lon, gtype = m.groups()
                if globe != 'earth' or primary != '1' or lat == 'NULL' or lon == 'NULL':
                    continue
                # first primary wins; ignore later dup primaries if any
                pid = int(pid)
                if pid not in coords:
                    coords[pid] = (float(lat), float(lon), gtype or None)
    sys.stderr.write(f"[geo] {len(coords):,} geotagged articles "
                     f"({time.time()-t0:.1f}s)\n")
    return coords


def init_db(path):
    db = sqlite3.connect(path)
    db.executescript("""
      PRAGMA journal_mode=OFF;
      PRAGMA synchronous=OFF;
      PRAGMA temp_store=MEMORY;
      DROP TABLE IF EXISTS article;
      CREATE TABLE article (
        page_id       INTEGER PRIMARY KEY,
        title         TEXT,
        lat           REAL NOT NULL,
        lon           REAL NOT NULL,
        type          TEXT,
        summary       TEXT,
        summary_chars INTEGER DEFAULT 0
      );
      DROP TABLE IF EXISTS article_rtree;
      CREATE VIRTUAL TABLE article_rtree USING rtree(
        page_id, min_lat, max_lat, min_lon, max_lon
      );
      DROP TABLE IF EXISTS meta;
      CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
    """)
    return db


def seed_coords(db, coords):
    """Insert every geotagged page with its coordinates (text filled later)."""
    db.executemany(
        "INSERT OR IGNORE INTO article(page_id,lat,lon,type) VALUES (?,?,?,?)",
        ((pid, la, lo, ty) for pid, (la, lo, ty) in coords.items()))
    db.executemany(
        "INSERT INTO article_rtree(page_id,min_lat,max_lat,min_lon,max_lon) "
        "VALUES (?,?,?,?,?)",
        ((pid, la, la, lo, lo) for pid, (la, lo, ty) in coords.items()))
    db.commit()


def lead_plaintext(wikitext, max_chars):
    """First section of an article, stripped to plain prose for TTS."""
    if not wikitext:
        return ""
    # lead = everything before the first == Heading ==
    m = HEADING.search(wikitext)
    lead = wikitext[:m.start()] if m else wikitext
    if mwparserfromhell is not None:
        try:
            lead = mwparserfromhell.parse(lead).strip_code(normalize=True, collapse=True)
        except Exception:
            pass
    lead = re.sub(r"\{\{[^{}]*\}\}", " ", lead)      # any stray templates
    lead = re.sub(r"<[^>]+>", " ", lead)              # stray html/refs
    lead = re.sub(r"\[\[[^\]|]*\|", "", lead).replace("[[", "").replace("]]", "")
    lead = re.sub(r"'''?|''", "", lead)               # bold/italic ticks
    lead = re.sub(r"[ \t]*\n[ \t]*", " ", lead)       # flatten newlines
    # TTS hygiene: drop parentheticals left empty by stripped IPA/respell
    # templates (e.g. "Aarhus (, ; ) is..."), tidy stranded punctuation.
    for _ in range(2):
        lead = re.sub(r"\(\s*[^A-Za-z0-9()]*\s*\)", "", lead)  # parens w/o content
    lead = re.sub(r"\s+([,.;:!?])", r"\1", lead)       # space before punctuation
    lead = re.sub(r"([,;:])(?=[,;:])", "", lead)       # punctuation pileups
    lead = re.sub(r"\s{2,}", " ", lead).strip(" ,;:")
    if max_chars and len(lead) > max_chars:
        cut = lead[:max_chars]
        lead = cut[:cut.rfind('. ') + 1] if '. ' in cut else cut  # end on sentence
    return lead


def stream_articles(db, articles_arg, coords, max_chars, progress_every):
    if articles_arg == '-':
        stream = sys.stdin.buffer
    elif articles_arg.endswith('.bz2'):
        stream = bz2.open(articles_arg, 'rb')
    else:
        stream = open(articles_arg, 'rb')

    pid = title = text = None
    in_rev = False
    seen = matched = filled = 0
    t0 = time.time()
    cur = db.cursor()
    batch = []

    context = ET.iterparse(stream, events=('start', 'end'))
    _, root = next(context)
    try:
        for event, elem in context:
            tag = localname(elem.tag)
            if event == 'start':
                if tag == 'page':
                    pid = title = text = None
                elif tag == 'revision':
                    in_rev = True
                continue
            if tag == 'title':
                title = elem.text
            elif tag == 'id' and pid is None and not in_rev:
                pid = int(elem.text)
            elif tag == 'text':
                text = elem.text
            elif tag == 'revision':
                in_rev = False
            elif tag == 'page':
                seen += 1
                if pid in coords:
                    matched += 1
                    if text and not text[:9].upper().startswith('#REDIRECT'):
                        summary = lead_plaintext(text, max_chars)
                        if summary:
                            filled += 1
                            batch.append((title, summary, len(summary), pid))
                            if len(batch) >= 500:
                                cur.executemany(
                                    "UPDATE article SET title=?,summary=?,"
                                    "summary_chars=? WHERE page_id=?", batch)
                                db.commit(); batch.clear()
                root.clear()
                if seen % progress_every == 0:
                    r = seen / (time.time() - t0)
                    sys.stderr.write(
                        f"\r[art] {seen:>9,} seen | {matched:>8,} geo | "
                        f"{filled:>8,} summarized | {r:6.0f} pg/s "
                        f"| {(title or '')[:34]:<34}")
                    sys.stderr.flush()
    except ET.ParseError as e:
        sys.stderr.write(f"\n[note] stream ended/truncated (ok for partial): {e}\n")
    if batch:
        cur.executemany("UPDATE article SET title=?,summary=?,summary_chars=? "
                        "WHERE page_id=?", batch)
        db.commit()
    sys.stderr.write(f"\n[art] done: {seen:,} pages, {matched:,} geotagged, "
                     f"{filled:,} summarized ({time.time()-t0:.0f}s)\n")
    return seen, matched, filled


def finalize(db, stats):
    db.execute("CREATE INDEX IF NOT EXISTS idx_article_title ON article(title)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_article_type ON article(type)")
    # Fallback for platforms whose bundled SQLite lacks the R-tree module
    # (e.g. some Android system SQLite builds): plain B-tree indexes on the
    # coordinates let the app run the same bounding-box query without R-tree.
    db.execute("CREATE INDEX IF NOT EXISTS idx_article_lat ON article(lat)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_article_lon ON article(lon)")
    for k, v in stats.items():
        db.execute("INSERT OR REPLACE INTO meta(key,value) VALUES (?,?)", (k, str(v)))
    db.commit()
    db.execute("PRAGMA journal_mode=DELETE")
    db.execute("VACUUM")
    db.commit()


def main():
    ap = argparse.ArgumentParser(description="Build the WalkPedia offline SQLite DB")
    ap.add_argument('--geotags', required=True)
    ap.add_argument('--articles', required=True, help="'-' for stdin, or a .bz2/.xml path")
    ap.add_argument('--out', required=True)
    ap.add_argument('--max-summary-chars', type=int, default=1500)
    ap.add_argument('--progress-every', type=int, default=20000)
    args = ap.parse_args()

    if mwparserfromhell is None:
        sys.stderr.write("[warn] mwparserfromhell not installed; using regex-only cleaning\n")

    coords = load_geotags(args.geotags)
    db = init_db(args.out)
    seed_coords(db, coords)
    sys.stderr.write(f"[db] seeded {len(coords):,} coordinate rows + R-tree\n")
    seen, matched, filled = stream_articles(
        db, args.articles, coords, args.max_summary_chars, args.progress_every)
    finalize(db, {
        'geotagged_articles': len(coords),
        'articles_scanned': seen,
        'articles_matched': matched,
        'articles_summarized': filled,
        'max_summary_chars': args.max_summary_chars,
        'built_unix': int(time.time()),
    })
    db.close()
    sys.stderr.write(f"[done] wrote {args.out}\n")


if __name__ == '__main__':
    main()
