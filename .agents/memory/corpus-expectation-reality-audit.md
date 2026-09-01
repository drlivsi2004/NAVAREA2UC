---
name: Corpus expectation–reality audit
description: The project method for reducing a large NAVAREA corpus to actionable XML and physical ECDIS checks.
---

Always audit the complete corpus before broad physical ECDIS review:

```text
source block
→ expected geometry/style/color/Danger/Description
→ actual Modern and Legacy XML
→ PASS / FAIL / REVIEW / PHYSICAL RETEST
```

Treat `REFERENCE_ONLY_COORDINATES` as a safe non-geometry result unless the source explicitly defines separate objects. Keep geometry, object semantics, color/Danger, and Description as independent verdicts. Physically inspect only the filtered mismatches and unresolved semantic cases.

**Why:** One corpus pass separates XML structural integrity from genuine source-to-object mismatches and can reveal class-level defects, such as one dangerous row in a grouped buoy list contaminating the danger state of every other row.

**How to apply:** Run the expectation–reality pass over every source region before requesting or interpreting ECDIS photographs. For grouped or mixed messages, verify that status and color are isolated per source row; never infer correctness from aggregate object counts alone.