# WalkPedia — Android (Kotlin / Jetpack Compose)

Native Android scaffold implementing the v1 core: read-only access to the bundled
`walkpedia.sqlite` (with an **R-tree-or-fallback** nearest query), GPS via the
framework LocationManager, on-device TTS, and the proximity playback queue.

## Files
| File | Role |
|---|---|
| `MainActivity.kt` | Entry point, permission flow, Compose UI, wiring |
| `WalkPediaDatabase.kt` | SQLite access; R-tree query with plain-index fallback |
| `ProximityEngine.kt` | `Article` model + haversine |
| `LocationProvider.kt` | GPS via `LocationManager` (no Play Services) |
| `SpeechManager.kt` | `TextToSpeech` wrapper |
| `PlaybackController.kt` | Proximity queue, cooldown, advance logic |

## Setup
1. Create a standard Android Studio project (Empty Compose Activity), package
   `app.walkpedia`, then drop these files in (replacing the generated ones).
   The provided `app/build.gradle.kts` and `AndroidManifest.xml` show the needed
   config — merge them with the Studio-generated Gradle wrapper / settings.
2. **Bundle the dataset:** put `walkpedia.sqlite` in `app/src/main/assets/`.
   The build is configured with `noCompress += "sqlite"` so it isn't gzip'd
   inside the APK; on first launch it's copied to internal storage for SQLite.
3. Run on a device. Use Android Studio's *Extended Controls → Location → Routes*
   to simulate walking for testing.

## R-tree note
Some Android system SQLite builds omit the R-tree module. `WalkPediaDatabase`
probes for `article_rtree` once and, if absent, falls back to a bounding-box
query on the `idx_article_lat` / `idx_article_lon` indexes that the data pipeline
also creates. Either way the nearest-N result is identical.

## Background playback (next step)
This scaffold drives playback from the foreground Activity. For true
pocket/screen-off narration, move location + TTS into a **foreground service**
(`FOREGROUND_SERVICE_LOCATION`, an ongoing notification). Permissions are already
declared in the manifest.

## Dataset delivery
The ~1.5–2 GB dataset exceeds the Play Store base-APK limit. For production use
**Play Asset Delivery** (asset pack) or a first-run download — see
`docs/REQUIREMENTS.md` §6.
