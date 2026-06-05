package app.walkpedia

import android.content.Context
import android.database.sqlite.SQLiteDatabase
import java.io.File

/**
 * Read-only access to the bundled `walkpedia.sqlite`.
 *
 * On first launch the asset is copied into app storage (SQLiteDatabase needs a
 * real file path). The nearest-N query uses the R-tree index when available, and
 * transparently falls back to a plain-index bounding-box query on devices whose
 * system SQLite was built without the R-tree module.
 */
class WalkPediaDatabase private constructor(private val db: SQLiteDatabase) {

    private val hasRtree: Boolean by lazy {
        try {
            db.rawQuery("SELECT page_id FROM article_rtree LIMIT 1", null).use { it.moveToFirst() }
            true
        } catch (e: Exception) {
            false
        }
    }

    fun nearest(lat: Double, lon: Double, radiusMeters: Double, limit: Int): List<Article> {
        val dLat = radiusMeters / 111_320.0
        val dLon = radiusMeters / (111_320.0 * maxOf(Math.cos(Math.toRadians(lat)), 1e-6))
        val minLat = lat - dLat; val maxLat = lat + dLat
        val minLon = lon - dLon; val maxLon = lon + dLon

        val (sql, args) = if (hasRtree) {
            """
            SELECT a.page_id,a.title,a.lat,a.lon,a.type,a.summary
            FROM article_rtree r JOIN article a ON a.page_id = r.page_id
            WHERE r.max_lat>=? AND r.min_lat<=? AND r.max_lon>=? AND r.min_lon<=?
            """.trimIndent() to arrayOf(maxLat, minLat, maxLon, minLon)
        } else {
            """
            SELECT page_id,title,lat,lon,type,summary FROM article
            WHERE lat BETWEEN ? AND ? AND lon BETWEEN ? AND ?
            """.trimIndent() to arrayOf(minLat, maxLat, minLon, maxLon)
        }

        val scored = ArrayList<Pair<Double, Article>>()
        db.rawQuery(sql, args.map { it.toString() }.toTypedArray()).use { c ->
            while (c.moveToNext()) {
                val alat = c.getDouble(2)
                val alon = c.getDouble(3)
                val d = haversine(lat, lon, alat, alon)
                if (d <= radiusMeters) {
                    scored.add(
                        d to Article(
                            id = c.getLong(0),
                            title = c.getString(1) ?: "(untitled)",
                            lat = alat, lon = alon,
                            type = c.getString(4),
                            summary = c.getString(5) ?: ""
                        )
                    )
                }
            }
        }
        return scored.sortedBy { it.first }.take(limit).map { it.second }
    }

    companion object {
        private const val ASSET = "walkpedia.sqlite"

        fun open(context: Context): WalkPediaDatabase {
            val out = File(context.filesDir, ASSET)
            if (!out.exists()) {
                context.assets.open(ASSET).use { input ->
                    out.outputStream().use { input.copyTo(it) }
                }
            }
            val db = SQLiteDatabase.openDatabase(out.path, null, SQLiteDatabase.OPEN_READONLY)
            return WalkPediaDatabase(db)
        }
    }
}
