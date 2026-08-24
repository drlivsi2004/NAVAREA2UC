---
name: S1 nested numbering
description: Full dotted section identities must be captured consistently in both numeric partitioning and route boundary scanning.
---

Nested section markers such as `2.2.2.` require the complete dotted identity in partition metadata; the route branch also scans numeric markers for boundaries, so both scanners must preserve the same identity shape without changing boundary positions.

**Why:** Updating only the ordinary numbered-section branch leaves route-mode residual sections with truncated IDs.

**How to apply:** Change capture shape only; preserve marker positions, partition count, handler routing, and geometry generation.