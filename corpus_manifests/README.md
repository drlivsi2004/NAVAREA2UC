# NAVAREA source scopes

The corpus is intentionally split into two scopes:

- `navarea_primary.txt` — the 21 global NAVAREA source files used by the
  current comparison and release baseline.
- `coastal_future.txt` — the remaining 48 coastal, sub-area, NAVTEX, and
  regional feeds retained for later integration.

The files remain in the project root so their provenance and existing
regression references are preserved. The default runner uses only the primary
manifest. Pass `--include-future-coastal` when explicitly evaluating the full
retained library.