#!/usr/bin/env python3
"""
validate_db.py — sanity-check a built walkpedia.sqlite.

Checks: schema/meta, row counts & coverage, R-tree consistency, text quality,
and live proximity spot-checks at well-known landmarks (with an R-tree vs.
brute-force cross-check to prove the spatial index returns no false negatives).

    python validate_db.py walkpedia.sqlite
"""
import sqlite3, sys, time
from query_nearest import nearest, haversine

LANDMARKS = [
    ("Eiffel Tower, Paris",        48.8584,   2.2945),
    ("Times Square, NYC",          40.7580, -73.9855),
    ("Sydney Opera House",        -33.8568, 151.2153),
    ("Colosseum, Rome",            41.8902,  12.4922),
    ("Tokyo Station",             35.6812, 139.7671),
]


def section(t): print(f"\n{'='*60}\n{t}\n{'='*60}")


def brute_nearest(rows, lat, lon, radius, n):
    out = []
    for pid, title, la, lo in rows:
        d = haversine(lat, lon, la, lo)
        if d <= radius:
            out.append((d, pid))
    out.sort()
    return [p for _, p in out[:n]]


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "walkpedia.sqlite"
    db = sqlite3.connect(path)
    ok = True

    section("META / BUILD PROVENANCE")
    for k, v in db.execute("SELECT key,value FROM meta ORDER BY key"):
        print(f"  {k:24} {v}")

    section("COUNTS & COVERAGE")
    total = db.execute("SELECT COUNT(*) FROM article").fetchone()[0]
    summ  = db.execute("SELECT COUNT(*) FROM article WHERE summary_chars>0").fetchone()[0]
    rtree = db.execute("SELECT COUNT(*) FROM article_rtree").fetchone()[0]
    nocoord = db.execute("SELECT COUNT(*) FROM article WHERE lat IS NULL OR lon IS NULL").fetchone()[0]
    print(f"  articles (geotagged):   {total:,}")
    print(f"  with summary text:      {summ:,}  ({100*summ/max(total,1):.1f}%)")
    print(f"  R-tree rows:            {rtree:,}")
    print(f"  rows missing coords:    {nocoord}")
    if rtree != total:
        print(f"  !! R-tree count != article count"); ok = False
    if nocoord:
        print(f"  !! some rows lack coordinates"); ok = False

    section("INTEGRITY")
    ic = db.execute("PRAGMA quick_check").fetchone()[0]
    print(f"  quick_check: {ic}")
    if ic != "ok": ok = False

    section("TEXT QUALITY (random summaries)")
    for title, summary in db.execute(
            "SELECT title,summary FROM article WHERE summary_chars>200 "
            "ORDER BY page_id LIMIT 3"):
        print(f"  • {title}: {summary[:140]}…")

    section("PROXIMITY SPOT-CHECKS (50 m, then 300 m)")
    coords = db.execute("SELECT page_id,title,lat,lon FROM article").fetchall()
    print(f"  (loaded {len(coords):,} points for brute-force cross-check)")
    for name, lat, lon in LANDMARKS:
        hits = nearest(db, lat, lon, 300, 10)
        radius_used = 300
        tag = ""
        near50 = [h for h in nearest(db, lat, lon, 50, 10)]
        if near50:
            hits, radius_used = near50, 50
        # R-tree vs brute force for the same radius
        rtree_ids = [h[1] for h in hits]
        brute_ids = brute_nearest([(c[0], c[1], c[2], c[3]) for c in coords],
                                  lat, lon, radius_used, 10)
        match = set(rtree_ids) == set(brute_ids)
        if not match: ok = False; tag = "  !! RTREE/BRUTE MISMATCH"
        print(f"\n  {name}  ({radius_used} m){tag}")
        if not hits:
            print("    (nothing nearby — plausible if remote)")
        for d, pid, title, ty, summary in hits[:5]:
            has = "✓" if summary else "·"
            print(f"    {d:6.0f} m  {has} {title}  [{ty or '-'}]")

    section("RESULT")
    print("  ✅ PASS — dataset looks good." if ok else "  ❌ FAIL — see !! markers above.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
