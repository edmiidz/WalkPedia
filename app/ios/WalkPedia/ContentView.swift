import SwiftUI

struct ContentView: View {
    @EnvironmentObject var location: LocationManager
    @EnvironmentObject var controller: PlaybackController

    var body: some View {
        VStack(spacing: 20) {
            Text("WalkPedia").font(.largeTitle.bold())

            if let loc = location.location {
                Label(String(format: "%.5f, %.5f",
                             loc.coordinate.latitude, loc.coordinate.longitude),
                      systemImage: "location.fill")
                    .font(.caption).foregroundStyle(.secondary)
            } else {
                Label("Waiting for GPS…", systemImage: "location.slash")
                    .font(.caption).foregroundStyle(.secondary)
            }

            if let np = controller.nowPlaying {
                VStack(alignment: .leading, spacing: 8) {
                    Label(np.title, systemImage: "speaker.wave.2.fill").font(.headline)
                    Text(np.summary).font(.callout).lineLimit(8)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding()
                .background(.quaternary, in: RoundedRectangle(cornerRadius: 14))
            } else {
                Text("No article within \(Int(controller.radiusMeters)) m")
                    .foregroundStyle(.secondary)
            }

            if !controller.queue.isEmpty {
                VStack(alignment: .leading) {
                    Text("Up next").font(.subheadline.bold()).foregroundStyle(.secondary)
                    ForEach(controller.queue) { a in
                        Text("• \(a.title)").font(.callout)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }

            Spacer()
            Button("Skip") { controller.skip() }
                .buttonStyle(.bordered)
                .disabled(controller.nowPlaying == nil)
        }
        .padding()
        .onChange(of: location.location) { _, newValue in
            if let loc = newValue { controller.updateLocation(loc) }
        }
    }
}
