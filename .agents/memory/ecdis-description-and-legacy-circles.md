---
name: ECDIS descriptions and Legacy contract
description: Build complete Modern descriptions in handlers, then preserve the immutable Legacy copy-and-cap contract.
---

ECDIS object descriptions should carry the operational meaning, cancellation/end-time information, and published verification coordinates needed by the operator. Legacy circle export has a hard inclusive maximum of 50 range units: values above it must be written as exactly 50.

**Why:** The operator must be able to verify the published position from the Description as well as the structured geometry, while legacy imports can reject or misrepresent circles beyond the supported range.

**How to apply:** Keep coordinates in both the XML position section and Description in published order, preserve cancellation references without scheduling self-deletion, preserve explicit centers even when a source wraps them onto the next line, and test the boundary as below/equal/above (49, 50, 51).

The Legacy Description format is immutable. Legacy XML must contain a copy of the Modern Description, truncated only to the mandatory 999-character maximum; this limit is required for Furuno acceptance and has been confirmed experimentally on physical ECDIS. Do not fix Description problems in the exporter or change the 999 limit. Fix them in the handlers that construct the Modern Description.

**Why:** A Legacy file with a Description above 999 is rejected by the physical ECDIS, while changing the serializer would violate the proven compatibility contract. The real product defect is missing or prematurely discarded context before serialization.

**How to apply:** Treat Modern Description as the source of truth. Audit source → handler-built Modern text → Legacy copy/cap separately, and target handler context, sublabel parsing, and post-coordinate text loss—not Legacy export.

Descriptions are section-scoped: each generated object should carry the exact source section relevant to that object, rather than the whole parent notice or an invented short summary. The physical ECDIS is treated as a faithful renderer of the XML, so any missing Description content must be traced to source parsing, handler construction, or XML serialization rather than assigned to an ECDIS-side cut.

**Why:** The confirmed ECDIS behavior is to display exactly what is present in the XML. A screenshot showing only the beginning of a field is therefore incomplete evidence, not evidence of an ECDIS truncation.

**How to apply:** Preserve the complete relevant section in the export when supported, keep unrelated sections out, compare source/parser/Modern XML/Legacy XML/screen endings, and classify any missing text as an upstream generation issue.

For complex, partitioned, or multi-geometry messages, the intended Modern Description is not the entire parent notice on every object. It is the shared parent header/context plus the section or local fragment that defines that object's geometry and meaning. Grouped Areas additionally use their own group header and coordinates.

**Why:** Copying the full parent notice to every Line, Area, Circle, or Point would duplicate unrelated instructions and make the ECDIS Description less useful. The handler must retain the relevant object context while excluding unrelated sections.

**How to apply:** Treat `parent_context` plus the handler's section-scoped Description as the normal contract. This is confirmed by the partitioned `IX 208/2026` sections: Section 8's Circle receives the header plus Section 8, while Section 9's Line/Label receives the header plus Section 9. For inline facility lists, recognize only ordered line-start list markers; wrapped parenthetical facility codes remain part of the local fragment.