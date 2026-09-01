---
name: Release and pipeline sequence
description: Project sequencing decision for NAVAREA2UC core stabilization, web UI, and coastal pipeline work.
---

The project sequence is: establish the NAVAREA2UC 1.3.0 scope and baseline, stabilize the core against the main NAVAREA corpus, build the HTML/web UI on the stable normalized-output contract, and only then add coastal or provider-specific pipelines as isolated adapters.

**Why:** Mixing core semantic fixes, UI work, and new source formats makes regressions difficult to attribute and can turn source ambiguity into permanent parser exceptions.

**How to apply:** Do not expand coastal parsing rules while the core has unresolved coordinate-loss, false-line, context-propagation, confidence, or duplicate-control issues. The web UI should consume core output and diagnostics rather than reimplement parsing decisions.