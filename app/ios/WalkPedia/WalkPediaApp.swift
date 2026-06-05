import SwiftUI

@main
struct WalkPediaApp: App {
    @StateObject private var location = LocationManager()
    @StateObject private var controller = PlaybackController()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(location)
                .environmentObject(controller)
                .onAppear { location.start() }
        }
    }
}
