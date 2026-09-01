---
name: S1 nested numbering
description: Full dotted section identities must be captured consistently in both numeric partitioning and route boundary scanning.
---

Nested section markers such as `2.2.2.` require the complete dotted identity in partition metadata; the route branch also scans numeric markers for boundaries, so both scanners must preserve the same identity shape without changing boundary positions. Numeric section parsers must also require whitespace after the delimiter, because wrapped coordinates such as `38.21 S` otherwise look like a new section and can split or discard preceding positions.

**Why:** Updating only the ordinary numbered-section branch leaves route-mode residual sections with truncated IDs.

**How to apply:** Change capture shape only; preserve marker positions, partition count, handler routing, and geometry generation. Treat `N.` followed immediately by digits as coordinate text, not a section marker.