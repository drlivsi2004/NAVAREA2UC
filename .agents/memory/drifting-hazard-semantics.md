---
name: Drifting and aground hazard semantics
description: Map drifting-vessel and aground hazard wording to dangerous Wreck points without inventing geometry.
---

`DRIFTING HAZARDS`, `ADRIFT`, and `AGROUND` describe dangerous reported positions. They should produce a danger-marked Wreck Point/Label while preserving the source coordinate as a single point; they do not authorize an Area, Line, or Circle.

**Why:** A physical ECDIS check showed that the coordinate and label can be correct while the object remains informational orange and has no danger flag.

**How to apply:** Detect the hazard wording in both color and danger-flag classification, keep the point style unchanged, and regression-test the resulting XML attributes on a real ECDIS case.