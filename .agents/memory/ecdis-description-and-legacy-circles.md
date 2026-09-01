---
name: ECDIS descriptions and Legacy contract
description: Build complete Modern descriptions in handlers, then preserve the immutable Legacy copy-and-cap contract.
---

ECDIS object descriptions should carry the operational meaning, cancellation/end-time information, and published verification coordinates needed by the operator. Legacy circle export has a hard inclusive maximum of 50 range units: values above it must be written as exactly 50.

**Why:** The operator must be able to verify the published position from the Description as well as the structured geometry, while legacy imports can reject or misrepresent circles beyond the supported range.

**How to apply:** Keep coordinates in both the XML position section and Description in published order, preserve cancellation references without scheduling self-deletion, preserve explicit centers even when a source wraps them onto the next line, and test the boundary as below/equal/above (49, 50, 51).

Golden rule: Furuno ECDIS is a faithful XML renderer. It does not interpret NAVAREA prose, choose geometry, repair topology, truncate or format Description, or decide semantic correctness; it displays what the generated XML contains.

**Why:** Physical evidence can prove what a particular XML file rendered on Furuno, but cannot prove that the source justified that Line, Area, Circle, Point, style, Danger flag, or Description. Source semantics and XML generation are upstream responsibilities.

**How to apply:** Audit every physical result as `source semantics → parser/handler → Modern XML → Legacy XML → Furuno rendering`. Never use a Furuno screenshot to infer that the XML geometry was correct; use it only to confirm the rendered result of that XML.

NavStation and other provider tools have their own mapping and display logic. They
are reference material for investigating ambiguous cases, not semantic
authority and not a source of truth for our XML geometry or attributes.

**Why:** A provider may normalize, group, approximate, or visualize a notice
according to rules that are different from NAVAREA wording and this project's
contract. Matching NavStation can therefore reproduce another adapter's
decision rather than the source meaning.

**How to apply:** Keep the evidence chain separate: source wording is the
semantic input, our parser/handler is the explicit mapping decision, XML is the
serialized contract, Furuno verifies rendering, and NavStation is only a
cross-reference when source semantics remain ambiguous.

The Legacy Description format is immutable. Legacy XML must contain a copy of the Modern Description, truncated only to the mandatory 999-character maximum; this limit is required for Furuno acceptance and has been confirmed experimentally on physical ECDIS. Do not fix Description problems in the exporter or change the 999 limit. Fix them in the handlers that construct the Modern Description.

**Why:** A Legacy file with a Description above 999 is rejected by the physical ECDIS, while changing the serializer would violate the proven compatibility contract. The real product defect is missing or prematurely discarded context before serialization.

**How to apply:** Treat Modern Description as the source of truth. Audit source → handler-built Modern text → Legacy copy/cap separately, and target handler context, sublabel parsing, and post-coordinate text loss—not Legacy export.

Descriptions are section-scoped: each generated object should carry the exact source section relevant to that object, rather than the whole parent notice or an invented short summary. The physical ECDIS is treated as a faithful renderer of the XML, so any missing Description content must be traced to source parsing, handler construction, or XML serialization rather than assigned to an ECDIS-side cut.

**Why:** The confirmed ECDIS behavior is to display exactly what is present in the XML. A screenshot showing only the beginning of a field is therefore incomplete evidence, not evidence of an ECDIS truncation.

**How to apply:** Preserve the complete relevant section in the export when supported, keep unrelated sections out, compare source/parser/Modern XML/Legacy XML/screen endings, and classify any missing text as an upstream generation issue.

For complex, partitioned, or multi-geometry messages, the intended Modern Description is not the entire parent notice on every object. It is the shared parent header/context plus the section or local fragment that defines that object's geometry and meaning. Grouped Areas additionally use their own group header and coordinates.

**Why:** Copying the full parent notice to every Line, Area, Circle, or Point would duplicate unrelated instructions and make the ECDIS Description less useful. The handler must retain the relevant object context while excluding unrelated sections.

**How to apply:** Treat `parent_context` plus the handler's section-scoped Description as the normal contract. This is confirmed by the partitioned `IX 208/2026` sections: Section 8's Circle receives the header plus Section 8, while Section 9's Line/Label receives the header plus Section 9. For inline facility lists, recognize only ordered line-start list markers; wrapped parenthetical facility codes remain part of the local fragment.

Physical testing of the Windows release build found heterogeneous Description defects across multiple geometry cases: some texts are incomplete, some duplicate content, and even single-message cases can lose text.

**Why:** A clean handler-to-Modern-to-Legacy equality audit can still pass when the handler itself assembled the wrong Description; XML-stage equality is not source-semantic completeness.

**How to apply:** Audit source section → handler text in addition to serializer equality, with explicit checks for missing spans and duplicated normalized spans. Keep geometry verdicts independent: a physically correct object does not close its Description review.

For Description partitioning, keep a normalized source message at or below 999
characters intact. Only messages above that boundary should be split at
semantic sections; each long object Description is ordered as shared header,
the object-bearing section, and shared cancellation footer.

**Why:** Splitting short notices discards valid context and changes the
published meaning, while copying every section into a long object Description
causes the omissions and duplicates found during physical ECDIS review.

**How to apply:** Keep geometry classification independent from Description
partitioning. If a short message contains mixed aids, derive each object's
colour and Danger flag from its own source fragment even when the message is
processed as one block.

Rig-list descriptions use the same section-scoped contract across NAVAREA
regions and list spellings. Each rig entry receives the shared NAVAREA/header
and list preamble, only its own rig name and coordinate, and the shared
cancellation footer when present; sibling entries and post-list notes are
excluded.

**Why:** Coordinate-first, numbered, lettered, and MODU lists all describe one
object per partition, but the useful operational context sits before the first
entry. Cutting the preamble at the list marker loses timing/reporting context,
while copying the whole list mixes unrelated rigs.

**How to apply:** Determine the first actual entry boundary after the list
marker, preserve the preceding shared context, then compose the local entry
and footer. Keep Modern as the source description and let Legacy copy it,
applying only the existing 999-character cap.