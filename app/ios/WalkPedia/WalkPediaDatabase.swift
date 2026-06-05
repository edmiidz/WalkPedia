import Foundation
import SQLite3

/// One geotagged Wikipedia article from the bundled WalkPedia dataset.
struct Article: Identifiable, Equatable {
    let id: Int64            // Wikipedia page_id
    let title: String
    let lat: Double
    let lon: Double
    let type: String?        // landmark | city | mountain | ...
    let summary: String      // TTS-ready plain-text lead
}

/// Read-only access to the bundled `walkpedia.sqlite` (built by the data pipeline).
/// Implements the core "N closest within R metres" query using the R-tree index
/// for a cheap bounding-box pre-filter, then haversine for metre-accurate ranking.
final class WalkPediaDatabase {
    private var db: OpaquePointer?

    init?(bundledName: String = "walkpedia", ext: String = "sqlite") {
        guard let url = Bundle.main.url(forResource: bundledName, withExtension: ext) else {
            print("WalkPedia: \(bundledName).\(ext) missing from app bundle")
            return nil
        }
        if sqlite3_open_v2(url.path, &db, SQLITE_OPEN_READONLY, nil) != SQLITE_OK {
            print("WalkPedia: could not open database")
            return nil
        }
    }

    deinit { sqlite3_close(db) }

    /// The `limit` closest articles within `radiusMeters` of (lat, lon), nearest first.
    func nearest(lat: Double, lon: Double, radiusMeters: Double, limit: Int) -> [Article] {
        let dLat = radiusMeters / 111_320.0
        let dLon = radiusMeters / (111_320.0 * max(cos(lat * .pi / 180), 1e-6))
        let sql = """
            SELECT a.page_id, a.title, a.lat, a.lon, a.type, a.summary
            FROM article_rtree r JOIN article a ON a.page_id = r.page_id
            WHERE r.max_lat >= ? AND r.min_lat <= ?
              AND r.max_lon >= ? AND r.min_lon <= ?
            """
        var stmt: OpaquePointer?
        guard sqlite3_prepare_v2(db, sql, -1, &stmt, nil) == SQLITE_OK else { return [] }
        defer { sqlite3_finalize(stmt) }
        sqlite3_bind_double(stmt, 1, lat - dLat)
        sqlite3_bind_double(stmt, 2, lat + dLat)
        sqlite3_bind_double(stmt, 3, lon - dLon)
        sqlite3_bind_double(stmt, 4, lon + dLon)

        var scored: [(Double, Article)] = []
        while sqlite3_step(stmt) == SQLITE_ROW {
            let title = sqlite3_column_text(stmt, 1).map { String(cString: $0) } ?? "(untitled)"
            let alat = sqlite3_column_double(stmt, 2)
            let alon = sqlite3_column_double(stmt, 3)
            let d = WalkPediaDatabase.haversine(lat, lon, alat, alon)
            guard d <= radiusMeters else { continue }
            let article = Article(
                id: sqlite3_column_int64(stmt, 0),
                title: title,
                lat: alat, lon: alon,
                type: sqlite3_column_text(stmt, 4).map { String(cString: $0) },
                summary: sqlite3_column_text(stmt, 5).map { String(cString: $0) } ?? ""
            )
            scored.append((d, article))
        }
        return scored.sorted { $0.0 < $1.0 }.prefix(limit).map { $0.1 }
    }

    /// Great-circle distance in metres.
    static func haversine(_ lat1: Double, _ lon1: Double, _ lat2: Double, _ lon2: Double) -> Double {
        let R = 6_371_000.0
        let p1 = lat1 * .pi / 180, p2 = lat2 * .pi / 180
        let dp = (lat2 - lat1) * .pi / 180, dl = (lon2 - lon1) * .pi / 180
        let a = sin(dp / 2) * sin(dp / 2) + cos(p1) * cos(p2) * sin(dl / 2) * sin(dl / 2)
        return 2 * R * asin(min(1, sqrt(a)))
    }
}
