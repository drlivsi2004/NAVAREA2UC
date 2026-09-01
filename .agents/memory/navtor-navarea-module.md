---
name: NAVTOR NAVAREA module
description: Public NAVTOR documentation distinguishes NAVAREA warning overlays from Auto Routeing.
---

NAVTOR describes NavStation's NAVAREA Warnings service as a daily updated,
geo-referenced overlay of warnings displayed as Point, Line, or Area. It also
adds in-force warnings intersecting a planned route to the Passage Plan.

**Why:** The public product description supports treating NAVAREA geometry as
provider-prepared warning geometry, not assuming the client calculates a safe
route from two coordinates.

**How to apply:** Keep NAVAREA parsing and route resolution separate. Do not
infer that a TOW warning's endpoint pair is a safe line; require a documented
geometry source before adding intermediate vertices.

The photograph `attached_assets/IMG_6691_1788015974418.jpeg` is a separate
physical ECDIS User Chart reference: it is a manual visualization of the
proposed blue Point/Label for `NAVAREA V 449/26`, not a NavStation screenshot
and not evidence of a provider route algorithm.

**Why:** The visual reference helps define the intended distinction between a
confirmed blue platform diamond and related preparatory activity, while
preserving the unresolved-geometry warning.

**How to apply:** Treat this image as a design/physical-ECDIS reference only.
Do not attribute its manual styling to NavStation or infer route geometry from
the blue label.