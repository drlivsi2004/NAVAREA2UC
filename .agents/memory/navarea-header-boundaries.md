---
name: NAVAREA header boundaries
description: Distinguish descriptive warning headers from cancellation references when normalizing and splitting NAVAREA text.
---

NAVAREA inputs may put a publisher or country label between the area code and warning number, while message bodies may repeat a valid-looking NAVAREA number as a cancellation reference. These cases must be normalized and bounded separately.

**Why:** Treating every `NAVAREA <area> <number/year>` occurrence as a new message can export a cancellation reference as a false warning and drop the geometry belonging to the real warning.

**How to apply:** Canonicalize descriptive header lines before parsing; split only at actual header lines, and treat numbered cancellation notices as metadata rather than child sections.