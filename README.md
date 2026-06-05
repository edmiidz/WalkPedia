# WalkPedia 🚶📖🔊

**An open-source, fully-offline mobile app that reads nearby Wikipedia articles
aloud as you walk** — using your phone's GPS and on-device text-to-speech.
No network. No accounts. No AI. Just the world around you, narrated.

> Put in your earbuds and walk. When you come within ~50 m of a place with a
> Wikipedia article — a landmark, a bridge, a historic building — WalkPedia
> quietly reads you the opening of that article. Works in airplane mode.

## How it works
1. A **preprocessed dataset** of ~1.26M *geotagged* Wikipedia articles is bundled
   as a spatially-indexed SQLite database (R-tree).
2. The app watches your **GPS** and continuously finds the **10 closest articles
   within 50 m**.
3. It reads the nearest one aloud with **on-device TTS**, in order of proximity.

Everything runs locally — no API, no network at runtime.

## Repository layout
| Path | What |
|---|---|
| [`docs/REQUIREMENTS.md`](docs/REQUIREMENTS.md) | Full requirements & architecture |
| [`data-pipeline/`](data-pipeline/) | Wikipedia dumps → `walkpedia.sqlite` |
| [`app/`](app/) | The mobile app (Android + iOS) |

## Status
v1 prototype. See [`docs/REQUIREMENTS.md`](docs/REQUIREMENTS.md) for scope and
open decisions (app framework, dataset delivery).

## Licensing
- **Code:** MIT.
- **Data:** Wikipedia article text is **CC BY-SA 4.0** — the bundled dataset
  inherits that license, and the app attributes Wikipedia per its terms.

## Roadmap (post-v1)
Keyword/interest articles · guided routes · region packs · multiple languages.
