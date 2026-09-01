---
name: Offline data-first web UI
description: Architectural boundary between the offline NAVAREA2UC package and the online map visualization service.
---

The offline web package should handle local NAVAREA parsing, validation, classification, data tables, and Furuno UserChart XML generation without maps or network access. Cartographic visualization belongs to the online service.

**Why:** vessels may have unreliable internet access, while map tiles and online visualization are the heaviest and most connectivity-dependent parts. Keeping them out of the offline package improves reliability, privacy, and package size.

**How to apply:** share the strict core and normalized data contract between online and offline builds; make the offline build self-contained with no CDN, telemetry, API, or map-tile dependency. Target a small JavaScript/TypeScript package; accept the larger Pyodide footprint only if preserving Python execution is more valuable than download size.