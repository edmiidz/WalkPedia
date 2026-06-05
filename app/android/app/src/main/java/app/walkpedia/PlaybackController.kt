package app.walkpedia

import android.location.Location

/**
 * On each GPS fix, finds the nearest articles, maintains a proximity-ordered
 * queue, and drives TTS playback. A cooldown stops the same article repeating
 * while you linger nearby. `onState` pushes UI updates.
 */
class PlaybackController(
    private val db: WalkPediaDatabase,
    private val speech: SpeechManager,
    private val onState: (nowPlaying: Article?, queue: List<Article>) -> Unit
) {
    val radiusMeters = 50.0          // v1 spec
    private val maxQueue = 10
    private val cooldownMs = 30 * 60 * 1000L

    private val recentlyPlayed = HashMap<Long, Long>()
    private var queue = mutableListOf<Article>()
    private var nowPlaying: Article? = null

    fun updateLocation(location: Location) {
        val now = System.currentTimeMillis()
        val found = db.nearest(location.latitude, location.longitude, radiusMeters, maxQueue)
        queue = found.filter { a ->
            val last = recentlyPlayed[a.id]
            last == null || now - last >= cooldownMs
        }.toMutableList()
        onState(nowPlaying, queue)
        if (nowPlaying == null && !speech.isSpeaking) advance()
    }

    /** Called when an utterance finishes, or to start the next one. */
    fun advance() {
        if (queue.isEmpty()) {
            nowPlaying = null
            onState(null, queue)
            return
        }
        val next = queue.removeAt(0)
        recentlyPlayed[next.id] = System.currentTimeMillis()
        nowPlaying = next
        onState(nowPlaying, queue)
        speech.speak("${next.title}. ${next.summary}", next.id.toString())
    }

    fun skip() {
        speech.stop()
        advance()
    }
}
