---
name: Bounded geometry precedence
description: Semantic boundary evidence must win over route-shaped parser fallbacks while ordinary route and reference wording stays non-area.
---

Explicit bounded-area wording and implicit bounded-coordinate wording such as `ROUTES BOUNDED BY FOLLOWING COORDINATES` are Area evidence. This evidence must be resolved before numbered-section, sublabel, single-point, and trackline fallbacks.

**Why:** The same operational notices can contain words such as `ROUTE` or `PIPELINE` while publishing a closed boundary. Letting those words win produced a Line, independent Points, or one fallback Point instead of the intended Area.

**How to apply:** Require both bounded grammar and sufficient boundary coordinates before emitting an Area. Do not classify ordinary `ROUTE`, `PIPELINE`, `IN`, `BETWEEN THE POINTS`, or reference-coordinate text as an Area without bounded-boundary evidence; preserve invalid/self-intersecting boundaries as explicit diagnostics rather than silently falling back to a Line.