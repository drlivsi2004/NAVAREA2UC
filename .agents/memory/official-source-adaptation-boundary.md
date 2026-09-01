---
name: Official source adaptation boundary
description: Future NAVAREA/MSI ingestion must separate official source intake from the website's normalized notice presentation.
---

Official NAVAREA and MSI pages are input sources, not the final product message. The website should display a consistent, readable NAVAREA2UC adaptation with structured metadata, geometry, validity, safety classification, and clear provenance.

The source registry is a candidate catalog, not a guarantee that every URL is
ready for automated fetching. Verify each endpoint before enabling ingestion,
follow canonical redirects, and classify browser-only or unavailable sources
separately. Known current alternatives include Argentina's `hidro.gov.ar`
radio-warning page, Peru's `/portal/navarea/radioavisos` page, and Canada's
e-Navigation notices portal.

**Why:** Official services publish different languages, layouts, encodings, and message formats, so exposing source text directly would produce an inconsistent and difficult-to-review experience.

**How to apply:** Preserve the original source reference and raw evidence for traceability, but normalize every imported notice before it reaches the public website. Treat the candidate endpoints in `corpus_manifests/official_navarea_sources.txt` as ingestion inputs only, with a connectivity check and source-specific adapter before production use.