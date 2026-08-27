---
name: GitHub CI workspace synchronization
description: A local Replit checkout can contain release workflow commits that are not present on the connected GitHub default branch.
---

When release confirmation depends on GitHub Actions, verify that the workflow and its inputs exist on the GitHub ref being dispatched; a successful run on an older default-branch workflow does not validate newer local jobs.

**Why:** Replit task work can be ahead of the connected GitHub repository, while direct Git pushes may lack credentials and large REST blob uploads may be rejected by the proxy.

**How to apply:** Compare the local HEAD with the GitHub workflow ref before dispatching. If they differ, report the remote run separately from local validation instead of treating it as proof of the current workflow.