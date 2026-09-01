---
name: Bounded geometry precedence
description: Semantic boundary evidence must win over route-shaped parser fallbacks while ordinary route and reference wording stays non-area.
---

Explicit bounded-area wording and implicit bounded-coordinate wording such as `ROUTES BOUNDED BY FOLLOWING COORDINATES` are Area evidence. This evidence must be resolved before numbered-section, sublabel, single-point, and trackline fallbacks.

**Why:** The same operational notices can contain words such as `ROUTE` or `PIPELINE` while publishing a closed boundary. Letting those words win produced a Line, independent Points, or one fallback Point instead of the intended Area.

**How to apply:** Require both bounded grammar and sufficient boundary coordinates before emitting an Area. Do not classify ordinary `ROUTE`, `PIPELINE`, `IN`, `BETWEEN THE POINTS`, or reference-coordinate text as an Area without bounded-boundary evidence; preserve invalid/self-intersecting boundaries as explicit diagnostics rather than silently falling back to a Line.

An undivided operational coordinate list may qualify as an implicit Area when
it has at least three coordinates and a reviewed evidence profile combines
regional context such as `VICINITY OF`, an operational activity, and explicit
clearance wording such as `WIDE BERTH REQUESTED`. This is semantic boundary
evidence, not a geometry-only inference.

**Why:** `NAVAREA VIII 895/26` describes hydrographic survey activity in the
vicinity of four positions and requests wide berth. The ordered coordinates
form a valid non-self-intersecting ring, while an open Line would misrepresent
the operation and a single Point would discard its spatial extent.

**How to apply:** Resolve extensible implicit-area profiles before numbered
section and trackline fallbacks, require the profile's negative conditions
(no explicit line grammar, endpoint-object package, or separate point list),
and send the resulting ring through the common Area validation path.

Physical Furuno verification confirmed restored Area geometry for NAVAREA IX 94/2024, IX 289/2024, and IX 254/2026.

**Why:** These repaired self-intersecting boundary cases now have target-ECDIS evidence in addition to parser and XML validation.

**How to apply:** Treat the three IX cases as closed physical regression cases; use new complex Areas as separate evidence requests rather than generalizing their repair outcome.