---
name: Tablet banner safety
description: Responsive image behavior for the information-rich NAVAREA2UC landing-page banner
---

On touch tablets, the banner must preserve the complete source image and its upper edge. Prefer a matching square container with `object-fit: contain` over cropping a square source into a wide `cover` frame.

When no higher-resolution source exists, a composition-first visual reconstruction is acceptable for this marketing banner; preserve the original as a reference and refine small details separately.

**Why:** The upper portion contains meaningful ECDIS detail that can be lost when a square source is forced into a desktop-wide aspect ratio.

**How to apply:** Keep the wide crop only for desktop presentation. For tablet breakpoints and touch-tablet media queries, use a full-image layout with top-priority positioning.