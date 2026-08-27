---
name: Radius-only warning semantics
description: How to classify NAVAREA radius language when no center position is supplied.
---

A radius warning without an explicit center or position is descriptive guidance
for the surrounding warning, not an independent Circle geometry definition.

**Why:** NAVAREA V 470/26 defines a valid bounded Area and then prohibits
navigation within a radius, but supplies no circle center. Inferring a center
from the first boundary coordinate loses the intended semantics and can create
an unsupported chart object.

**How to apply:** Preserve the radius wording in the Area or label description,
classify it as a Circle only when the source explicitly identifies a center or
position, and keep release-audit component expectations aligned with that rule.