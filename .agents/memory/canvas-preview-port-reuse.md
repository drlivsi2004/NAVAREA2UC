---
name: Canvas preview port reuse
description: Distinguishes a healthy stale preview process from a failed duplicate workflow launch.
---

A Canvas Vite preview may remain healthy on its assigned port after a workflow restart reports “port already in use.” Verify the existing endpoint before treating the workflow status as an application failure.

**Why:** Restarting the preview while its prior process is still serving can produce a failed workflow record even though the preview returns a successful HTTP response.

**How to apply:** Check the preview port and process first; only stop and relaunch the process if the endpoint is not responding or the preview is visibly stale.