---
name: Physical ECDIS coordinate order
description: Physical UserChart validation must distinguish source-list preservation from the intended geometric order of a multi-vertex object.
---

For multi-vertex NAVAREA objects, matching the coordinate order printed in the source is not sufficient evidence that the geometry is correct. Physical ECDIS review must compare the displayed sequence with the intended route or boundary order, and regression tests should encode that authoritative order when it differs from raw source order.

**Why:** A trackline can preserve all source coordinates, pass count and loss checks, and still be geometrically wrong if the source list is not the intended traversal order.

**How to apply:** Keep source order and authoritative geometric order as separate review fields. Do not close a physical case as confirmed from `coordinate_count`, object type, or source-order equality alone. Keep the ring closed in the internal model for validation, but export each Area boundary vertex once; Furuno ECDIS should perform the closing edge itself.

**Why:** Physical Furuno evidence showed that serializing `A,B,C,D,A` can be interpreted as a malformed `B,C,D,B` triangle with a duplicate-point warning, even though the parser's internal ring is correct.

`NAVAREA V 502/26` is the corresponding Line-order control: all 11 coordinates are present, but the published list creates two non-adjacent segment crossings and a much longer zig-zag than the non-crossing order published for the same coordinate set in `NAVAREA IV 789/2026`. The IV 789 order is comparative evidence that the V 502 list may be an artifact, not a case-specific reorder rule.

**Why:** The V 502 Line can pass coordinate-count and source-order assertions while still representing broken route geometry. The paired IV 789 message provides comparative evidence for a candidate traversal order, not permission to auto-reorder V 502 or any future case without authoritative confirmation.

**How to apply:** Before physical confirmation, keep V 502 open for authoritative review but do not block its output. The centralized geometry policy detects crossings, repeats, long-leg signals, and track connectivity for any multi-vertex Line. It may emit a validated single-track candidate order, splits clearly independent tracks, and otherwise preserves raw geometry with reference-point fallback; every decision carries provenance.

Physical Furuno verification confirmed that NAVAREA V 502/26 displays the correct traversal geometry.

**Why:** This closes the previously unresolved distinction between a source coordinate list that is complete and a line that is operationally correct on the target ECDIS.

**How to apply:** Treat V 502/26 as a physically confirmed regression case, while continuing to require separate authoritative or physical evidence for future ambiguous multi-vertex Lines.

Successful geometry repair is a confirmed geometry outcome, not an invalid-area rejection. Report classifiers must use the explicit rejection flag or a non-repair geometry diagnostic for rejection, while preserving the repair diagnostic as positive provenance.

**Why:** Treating every `GEOMETRY_*` diagnostic as rejection caused repaired Areas to appear simultaneously confirmed and rejected in corpus summaries.

**How to apply:** Keep repair codes distinguishable from failure codes in machine reports, baselines, and physical-review registers.