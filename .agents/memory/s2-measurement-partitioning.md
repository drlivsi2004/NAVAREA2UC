---
name: S2 measurement partitioning
description: Measurement-shaped decimals must be excluded before downstream handlers inspect partition input.
---

Measurement values that resemble numeric section markers must be filtered in the partition flow and made non-marker-shaped in the returned block; filtering only the marker list leaves structured handlers able to misclassify the original text.

**Why:** Downstream handlers independently scan their input for numeric section markers, so partition metadata alone cannot prevent a false structured route.

**How to apply:** Keep the rule narrowly scoped to decimal values with measurement units; do not combine it with distance, coordinate-fragment, or nested-numbering handling.