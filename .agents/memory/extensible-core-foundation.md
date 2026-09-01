---
name: Extensible core foundation
description: The long-term architecture principle for expanding NAVAREA2UC without weakening its safety-critical core.
---

The project should grow from a strict, reviewable core rather than prematurely becoming a universal converter. Keep the object contract versioned and stable, isolate source and ECDIS adapters, support configurable colour/style profiles, and preserve source-to-output traceability.

**Why:** The first product value is trustworthy NAVAREA-to-UserChart conversion, but future sources, devices and user preferences should be addable without rewriting or weakening the geometry and safety rules.

**How to apply:** Prefer narrow, well-tested extensions behind explicit interfaces. Never trade away geometry evidence, auditability or clear user review for broader format coverage.