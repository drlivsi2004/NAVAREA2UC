---
name: Recommended route ECDIS semantics
description: Confirmed Furuno UserChart presentation for recommended routes.
---

The confirmed Furuno presentation for an exact `RECOMMENDED ROUTE` line is `NINFO` with `lineType=1` and `checkDanger=0`.

**Why:** The visual proof export was imported on Furuno ECDIS in both day and night modes, and this combination gave the desired distinct route rendering.

**How to apply:** Apply this rule only when the current line semantic explicitly says `RECOMMENDED ROUTE`. Keep unrelated routes, tracklines, channels, and other line semantics on their existing presentation.