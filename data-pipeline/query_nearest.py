#!/usr/bin/env python3
"""
query_nearest.py — reference implementation of WalkPedia's core runtime query:
the N closest geotagged articles within R metres of a point, fully offline.

This is the exact logic the mobile app reimplements natively (R-tree bounding-box
pre-filter, then haversine re-rank). Handy for validating a built database.

    python query_nearest.py walkpedia.sqlite --lat 40.7484 --lon -73.9857 \
                            --radius 50 --n 10
"""
import argparse, math, sqlite3, sys

EARTH_R = 6371000.0  # metres


def haversine(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * EARTH_R * math.asin(math.sqrt(a))


def nearest(db, lat, lon, radius_m, n):
    dlat = radius_m / 111320.0
    dlon = radius_m / (111320.0 * max(math.cos(math.radians(lat)), 1e-6))
    rows = db.execute(
        """SELECT a.page_id,a.title,a.lat,a.lon,a.type,a.summary
           FROM article_rtree r JOIN article a ON a.page_id=r.page_id
           WHERE r.max_lat>=? AND r.min_lat<=? AND r.max_lon>=? AND r.min_lon<=?""",
        (lat - dlat, lat + dlat, lon - dlon, lon + dlon)).fetchall()
    out = []
    for pid, title, la, lo, ty, summary in rows:
        d = haversine(lat, lon, la, lo)
        if d <= radius_m:
            out.append((d, pid, title, ty, summary))
    out.sort(key=lambda x: x[0])
    return out[:n]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('db')
    ap.add_argument('--lat', type=float, required=True)
    ap.add_argument('--lon', type=float, required=True)
    ap.add_argument('--radius', type=float, default=50.0, help='metres')
    ap.add_argument('--n', type=int, default=10)
    args = ap.parse_args()
    db = sqlite3.connect(args.db)
    hits = nearest(db, args.lat, args.lon, args.radius, args.n)
    if not hits:
        print(f"No articles within {args.radius:.0f} m of "
              f"({args.lat}, {args.lon}).")
        return
    print(f"{len(hits)} article(s) within {args.radius:.0f} m, nearest first:\n")
    for d, pid, title, ty, summary in hits:
        snip = (summary or '').strip().replace('\n', ' ')
        print(f"  {d:6.0f} m  {title}  [{ty or '-'}]")
        if snip:
            print(f"           {snip[:120]}{'…' if len(snip) > 120 else ''}")


if __name__ == '__main__':
    main()
