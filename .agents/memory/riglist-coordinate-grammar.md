---
name: RIGLIST coordinate grammar
description: RIGLIST parsing must support both compact and whitespace-separated degree-minute coordinates without changing established compact grouping.
---

Specialized RIGLIST extraction must recognize the same compact and whitespace-separated coordinate forms accepted by generic coordinate extraction. When legacy entry grouping is retained for compact messages, spaced-format messages with mismatched entry and coordinate counts must use coordinate boundaries so one rig entry cannot absorb another.

**Why:** A RIGLIST message can retain all generic coordinates while producing zero or incomplete labels if its specialized regex is stricter, and broad fallback segmentation can change established compact-message object counts.

**How to apply:** Scope grammar and segmentation changes to the RIGLIST extraction/processing path; verify both the failing spaced-format message and the established compact RIGLIST regression family.