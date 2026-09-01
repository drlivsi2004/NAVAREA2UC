---
name: Section coordinate context
description: Preserve operational meaning when NAVAREA partitioning isolates a coordinate-only numbered section.
---

A numbered section containing only coordinates is not a complete Description. Its neighboring operation and mariner-instruction sections are part of the same object context and must be carried into the handler input before XML serialization.

**Why:** NAVAREA notices commonly publish the operation in one section, the position in the next, and caution or restrictions afterward. Treating each section as an independent description produces an apparently valid point with no usable operational meaning.

**How to apply:** When partitioning numbered sections, keep section-scoped geometry separation, but attach nearby non-coordinate operation, contact, caution, and cancellation prose to geometry sections. Do not merge sections that contain separate explicit geometries.