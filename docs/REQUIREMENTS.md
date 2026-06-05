# WalkPedia — Requirements & Architecture

> An open-source, fully-offline mobile app that reads nearby Wikipedia articles
> aloud as you walk, using your phone's GPS and on-device text-to-speech.
> No network. No accounts. No AI. Just the world around you, narrated.

**Status:** v1 design / prototype
**Source call:** spec'd 2026-06-05 (conv_5201ktcrzz6qebt8pzv7de8xpf2x)
**License (code):** MIT (proposed) · **License (data):** CC BY-SA 4.0 (inherited from Wikipedia)

---

## 1. Vision

You put in your earbuds, open WalkPedia, and start walking. As you come within
~50 metres of a place that has a Wikipedia article — a landmark, a historic
building, a park, a bridge — your phone quietly reads you the opening of that
article in a natural voice. It's a passive, ambient audio guide to the real
world, and it works with airplane mode on.

It is a spiritual sibling of the earlier "AutoWiki" experiment, narrowed to one
sharp idea: **proximity → speech**, fully offline.

---

## 2. Scope

### v1 (this document)
- **Fully offline.** No API calls, no network dependency at runtime.
- **Bundled dataset** of *only* geotagged Wikipedia articles (~1.26M articles).
- **GPS-driven playback:** continuously find the **10 closest** articles, play
  the nearest first, in order of proximity.
- **50 m trigger radius** for "you're here, here's the story."
- **On-device TTS** (Apple AVSpeechSynthesizer / Android TextToSpeech). No cloud TTS.
- **Targets:** Android and iOS.

### Deferred to v2+
- **Keyword / interest articles** interspersed with proximity articles. (Dropped
  from v1 because v1's dataset contains *only* geotagged articles — there is no
  non-geotagged content to pull interest-based reads from. Revisit when a second
  content source is added.)
- Routes / guided tours, bookmarking, history, "play full article," downloadable
  region packs, multiple languages, community-contributed audio.

---

## 3. Data pipeline

The dataset is produced offline on a workstation and shipped to the app. It is
**not** built on-device.

### Inputs (English Wikipedia dumps)
| File | Size | Role |
|---|---|---|
| `enwiki-latest-geo_tags.sql.gz` | ~50 MB | `page_id → (lat, lon, type)` for every geotagged page |
| `enwiki-latest-pages-articles.xml.bz2` | ~24 GB | Article wikitext (current revision, main namespace) |

`geo_tags` is the GeoData extension's table. We keep rows where
`gt_globe='earth'` and `gt_primary=1` (one canonical coordinate per article).

### Processing  (`data-pipeline/build_walkpedia_db.py`)
1. **Parse `geo_tags`** → in-memory map `page_id → (lat, lon, type)`.
   *(Measured: 1,255,401 geotagged articles.)*
2. **Seed** the output SQLite `article` table + R-tree with every coordinate.
3. **Stream `pages-articles.xml.bz2`**; for each page whose `page_id` is in the
   map, extract the **lead section**, strip wiki markup to **plain prose**
   (via `mwparserfromhell`), trim to a sentence boundary near
   `--max-summary-chars` (default 1500). Skip redirects and empty pages.
4. **Finalize:** indexes, write `meta`, `VACUUM`.

### Output schema (`walkpedia.sqlite`)
```sql
article(
  page_id       INTEGER PRIMARY KEY,
  title         TEXT,
  lat           REAL,         -- WGS84
  lon           REAL,
  type          TEXT,         -- landmark|city|edu|mountain|waterbody|... (from geo_tags)
  summary       TEXT,         -- plain-text lead, TTS-ready
  summary_chars INTEGER
);

-- spatial index: bounding-box pre-filter for nearest-neighbour queries
article_rtree USING rtree(page_id, min_lat, max_lat, min_lon, max_lon);

meta(key, value);  -- build provenance: counts, dump date, max_summary_chars
```

### Dataset composition (measured)
~1.26M geotagged articles. Top types: landmark (194K), city (149K),
edu (41K), railwaystation (38K), mountain (27K), waterbody (20K).

---

## 4. The proximity engine

The core runtime query — "the N closest articles within R metres of (lat, lon)":

```sql
-- 1) R-tree bounding-box pre-filter (degrees), cheap and indexed.
--    dLat = R/111320 ; dLon = R/(111320*cos(lat))
SELECT a.page_id, a.title, a.lat, a.lon, a.type, a.summary
FROM article_rtree r
JOIN article a ON a.page_id = r.page_id
WHERE r.max_lat >= :lat - :dLat AND r.min_lat <= :lat + :dLat
  AND r.max_lon >= :lon - :dLon AND r.min_lon <= :lon + :dLon;
-- 2) Re-rank the small candidate set by true haversine distance in app code,
--    drop anything > R metres, keep the closest N.
```

The R-tree turns a 1.26M-row scan into a handful of candidates. Haversine on the
shortlist gives metre-accurate ordering. At a 50 m radius the candidate set is
typically 0–dozens of rows even in dense cities.

### Playback logic
- Sample GPS (e.g. every few seconds / on significant movement).
- Recompute the nearest-10-within-50 m queue on each fix.
- Play the nearest unplayed article via TTS; advance through the queue by proximity.
- **Cooldown / dedup:** once an article is read, suppress it for a cooldown
  window (and/or until you leave + re-enter its radius) so it doesn't loop.
- Foreground audio session + background-location handling so playback continues
  with the screen off (this is the main platform-specific work).

---

## 5. App architecture

```
┌──────────────────────────────────────────────────────┐
│                       WalkPedia app                    │
│                                                        │
│  GPS / Location  ──►  Proximity Engine  ──►  Play Queue │
│  (background)         (R-tree + haversine)      │       │
│        ▲                     │                  ▼       │
│        │              walkpedia.sqlite     TTS Engine    │
│        │              (bundled asset)   (on-device voice)│
│   significant-change                                    │
│   location updates                                      │
└──────────────────────────────────────────────────────┘
        no network at runtime — everything above is local
```

| Concern | iOS | Android |
|---|---|---|
| Location (background) | CoreLocation, significant-change / region monitoring | FusedLocationProvider + foreground service |
| TTS | `AVSpeechSynthesizer` | `android.speech.tts.TextToSpeech` |
| SQLite + R-tree | system SQLite (R-tree compiled in) | system SQLite (R-tree compiled in) |
| Audio session | `AVAudioSession` (playback, mix/duck) | `AudioManager` / MediaSession |

### Framework recommendation
For a single-codebase open-source MVP that needs background location + on-device
TTS + bundled SQLite on both platforms, **Flutter** is the recommended default
(`geolocator`, `flutter_tts`, `sqflite`; system SQLite includes R-tree). React
Native is a comparable alternative. Fully-native (Swift + Kotlin) gives the most
control over background audio/location but doubles the work — reasonable later if
the prototype proves out. **This is an open decision — see §8.**

---

## 6. Packaging the dataset (important constraint)

At ~1.26M articles × ~1.5 KB plain-text summaries, `walkpedia.sqlite` is roughly
**1.5–2 GB**. That exceeds app-store binary limits (Play Store: 200 MB base AAB;
App Store: practical limits + cellular-download caps). So "bundled & offline"
needs a delivery strategy that still results in a fully-offline app after setup:

1. **First-run download** of the SQLite from a CDN/GitHub Release, stored
   locally; app is offline forever after. *(Simplest; mild caveat to "offline
   from install.")* — **recommended for v1.**
2. **Platform asset delivery:** Android *asset packs* (Play Asset Delivery) /
   iOS *On-Demand Resources* — ships with the install, no separate server.
3. **Trim to fit:** shorter summaries, drop sparse types, or **region packs**
   (download only the country/area you're in). Best long-term UX.

Knobs that move the size: `--max-summary-chars`, lead-only vs. full text,
type/quality filtering, and per-region splitting.

---

## 7. Open-source plan

```
WalkPedia/
├── README.md
├── LICENSE                 # MIT (code)
├── docs/REQUIREMENTS.md    # this file
├── data-pipeline/          # dump → walkpedia.sqlite (Python)
│   ├── build_walkpedia_db.py
│   ├── requirements.txt
│   └── README.md           # how to (re)build the dataset
└── app/                    # the mobile app (framework TBD)
```

**Attribution / licensing (must-do):** Wikipedia article text is **CC BY-SA 4.0**.
The app must (a) attribute Wikipedia, (b) link each read to its source article /
license, and (c) release the bundled dataset under CC BY-SA. App *code* can be MIT.
Ship a clear NOTICE/attribution screen and document the dataset's provenance
(dump date is recorded in `meta`).

---

## 8. Open decisions
- [ ] **App framework:** Flutter (recommended) vs. React Native vs. native Swift+Kotlin.
- [ ] **Dataset delivery:** first-run download (v1 default) vs. asset packs vs. region packs.
- [ ] **Summary length / content:** lead-only @1500 chars (default) — tune for voice pacing.
- [ ] **Trigger model:** continuous foreground vs. true background geofencing for v1.
- [ ] **Languages:** English-only v1; schema is language-agnostic for later.
