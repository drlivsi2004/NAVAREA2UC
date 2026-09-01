---
name: NAVAREA corpus validation
description: Preserve source boundaries before normalization when auditing NAVAREA warning blocks.
---

Corpus audits must discover NAVAREA block boundaries from decoded source text
before applying normalization. Normalization can join cancellation references
into lines that resemble new warning headers, which inflates the corpus and
misaligns source references.

**Why:** The source corpus contains standalone cancelled-warning references
and formatting artifacts that become false block boundaries after normalization.

**How to apply:** Keep raw-source line numbers and block boundaries for the
audit, then normalize each retained block independently for parser dispatch.

Release validation should compare a compact reviewed baseline fingerprint while
keeping the full current JSON report as the investigation artifact. Existing
component-loss findings are reviewed individually; newly appearing loss kinds
or message locations must block validation.

**Why:** The full corpus report is too large and noisy to maintain as a
baseline, but release checks still need to detect any parser-output drift and
identify new geometry loss without blocking on already reviewed findings.

**How to apply:** Update the reviewed baseline deliberately after an accepted
parser or corpus change, and inspect the uploaded report before doing so.

Some regional sources wrap a latitude after its degree value (for example,
`43` followed by `05.03 N`).  Intake cleanup must preserve that degree-only
line long enough for coordinate normalization to rejoin it; treating every
numeric-only line as a PDF page number loses real polygon vertices.

**Why:** The replacement regional corpus contains publisher-specific line
wrapping that is not present in the compact historical fixtures.

**How to apply:** Keep numeric-only lines when the following line is coordinate
minutes plus a hemisphere, while continuing to remove standalone page numbers.