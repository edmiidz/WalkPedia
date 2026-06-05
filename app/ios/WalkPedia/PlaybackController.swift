import Foundation
import CoreLocation

/// The brain: on each GPS fix, finds the nearest articles, maintains a
/// proximity-ordered queue, and reads them aloud one at a time. A cooldown
/// prevents the same article from repeating while you linger nearby.
@MainActor
final class PlaybackController: ObservableObject {
    @Published var nowPlaying: Article?
    @Published var queue: [Article] = []

    /// v1 spec: 10 closest within 50 m.
    let radiusMeters: Double = 50
    let maxQueue: Int = 10
    private let cooldown: TimeInterval = 30 * 60   // don't repeat for 30 min

    private let db: WalkPediaDatabase?
    private let speech: SpeechManager
    private var recentlyPlayed: [Int64: Date] = [:]

    init(db: WalkPediaDatabase? = WalkPediaDatabase(), speech: SpeechManager = SpeechManager()) {
        self.db = db
        self.speech = speech
        self.speech.onFinish = { [weak self] in
            Task { @MainActor in self?.advance() }
        }
    }

    /// Call on every location update.
    func updateLocation(_ location: CLLocation) {
        guard let db else { return }
        let now = Date()
        let found = db.nearest(lat: location.coordinate.latitude,
                               lon: location.coordinate.longitude,
                               radiusMeters: radiusMeters, limit: maxQueue)
        queue = found.filter { article in
            if let last = recentlyPlayed[article.id], now.timeIntervalSince(last) < cooldown {
                return false
            }
            return true
        }
        if nowPlaying == nil && !speech.isSpeaking { advance() }
    }

    private func advance() {
        guard !queue.isEmpty else { nowPlaying = nil; return }
        let next = queue.removeFirst()
        recentlyPlayed[next.id] = Date()
        nowPlaying = next
        speech.speak("\(next.title). \(next.summary)")
    }

    func skip() { speech.stop(); advance() }
}
