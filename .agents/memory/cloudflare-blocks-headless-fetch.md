---
name: Cloudflare blocks headless fetch of own replit.dev pages
description: Why fetching a user's own published *.replit.dev / replit.app page via Playwright/headless browser can return a Cloudflare 403 block page instead of real content, and what to use instead.
---

Fetching a Replit-hosted page's public URL (e.g. `https://<repl>.replit.dev/...` or a `replit.app` domain) with Playwright or another headless-browser fetch can be intercepted by Cloudflare's bot protection, returning an HTTP 403 block page rather than the actual rendered HTML — even when the user owns the project and the page is otherwise public.

**Why:** Cloudflare's automated-traffic heuristics flag headless browser fingerprints regardless of ownership; this is unrelated to auth or the app's own logic.

**How to apply:** When asked to clone/import a design from a URL that is the user's own Replit project, first check whether the source lives in the current workspace (e.g. a root `index.html` or an already-registered artifact) and use that file directly instead of trying to re-fetch it externally. Only fall back to reconstructing from a blocked fetch response if no local copy exists, and flag to the user that the visual result may be approximate in that case.

When synchronizing imported artifacts through a GitHub connector, a saved Cloudflare block page can also be rejected by the connector proxy with HTTP 403 while ordinary files succeed. GitHub GETs may continue working while repeated Git Data write requests are blocked, and an isolated probe can pass before the burst is blocked. Treat this as a transfer-specific failure rather than changing file contents or retrying the whole sync blindly.

**Why:** The proxy's security layer can inspect or reject the same block-page payload that was captured during a headless fetch, even though the GitHub API request and authentication are otherwise valid.

**How to apply:** Continue the sync for unaffected files only when the connector permits it, report the exact blocked paths, and use a separate approved transfer path for blocked writes instead of silently substituting or deleting them.
