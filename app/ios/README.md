# WalkPedia — iOS (Swift / SwiftUI)

Native iOS scaffold. The Swift files implement the full v1 core: read-only access
to the bundled `walkpedia.sqlite` with the R-tree nearest-query, GPS, on-device
TTS, and the proximity playback queue with cooldown.

## Files
| File | Role |
|---|---|
| `WalkPediaApp.swift` | App entry; wires LocationManager + PlaybackController |
| `ContentView.swift` | Minimal SwiftUI UI (now playing, queue, skip) |
| `LocationManager.swift` | CoreLocation GPS (background-capable) |
| `WalkPediaDatabase.swift` | SQLite + R-tree nearest-N query, haversine |
| `PlaybackController.swift` | Proximity queue, cooldown, advance logic |
| `SpeechManager.swift` | AVSpeechSynthesizer on-device TTS |

## Setup
1. **Create an Xcode project** (App, SwiftUI, iOS 17+) named `WalkPedia` and add
   the `.swift` files from this folder to the target.
2. **Bundle the dataset:** drag `walkpedia.sqlite` (from the data pipeline) into
   the project, "Copy items if needed," and ensure it's in *Target → Build Phases
   → Copy Bundle Resources*.
3. **Info.plist keys** (required — the app crashes/permissions fail without them):
   ```xml
   <key>NSLocationWhenInUseUsageDescription</key>
   <string>WalkPedia reads you Wikipedia articles about places as you walk near them.</string>
   <key>NSLocationAlwaysAndWhenInUseUsageDescription</key>
   <string>WalkPedia keeps narrating nearby places while the app is in your pocket.</string>
   <key>UIBackgroundModes</key>
   <array>
     <string>location</string>
     <string>audio</string>
   </array>
   ```
4. **Capabilities:** enable *Background Modes → Location updates* and *Audio*.
5. Run on a device (GPS + TTS need real hardware). Use Xcode's *Features →
   Location → Freeway Drive* in the simulator to fake movement for testing.

## Notes
- iOS system SQLite ships with the R-tree module, so the R-tree query works as-is.
- The dataset is ~1.5–2 GB — see `docs/REQUIREMENTS.md` §6 for delivery options
  (On-Demand Resources / first-run download) instead of shipping it in the binary.
