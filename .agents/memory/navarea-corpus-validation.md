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