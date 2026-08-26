---
name: Cloudflare blocks headless fetch of own replit.dev pages
description: Why fetching a user's own published *.replit.dev / replit.app page via Playwright/headless browser can return a Cloudflare 403 block page instead of real content, and what to use instead.
---

Fetching a Replit-hosted page's public URL (e.g. `https://<repl>.replit.dev/...` or a `replit.app` domain) with Playwright or another headless-browser fetch can be intercepted by Cloudflare's bot protection, returning an HTTP 403 block page rather than the actual rendered HTML — even when the user owns the project and the page is otherwise public.

**Why:** Cloudflare's automated-traffic heuristics flag headless browser fingerprints regardless of ownership; this is unrelated to auth or the app's own logic.

**How to apply:** When asked to clone/import a design from a URL that is the user's own Replit project, first check whether the source lives in the current workspace (e.g. a root `index.html` or an already-registered artifact) and use that file directly instead of trying to re-fetch it externally. Only fall back to reconstructing from a blocked fetch response if no local copy exists, and flag to the user that the visual result may be approximate in that case.
