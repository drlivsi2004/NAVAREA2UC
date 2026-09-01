# Data sources and derived output policy

## Scope

NAVAREA2UC uses navigational-notice text as input for parsing and
interpretation. The project does not publish, redistribute, or provide
an archive of NAVAREA notices.

The normal processing boundary is:

```text
notice text supplied from an authorized source
        ↓
NAVAREA2UC interpretation and geometry validation
        ↓
derived ECDIS UserChart XML
```

## Source material

Source notices, charts, provider feeds, and other maritime data remain
subject to the terms, attribution requirements, and restrictions of
their original publishers or providers. A source reference, message
identifier, date, or fingerprint may be retained for traceability
without republishing the source notice itself.

Before using a new source in a public or commercial workflow, confirm
that the source terms permit the intended access and processing.

## Derived output

NAVAREA2UC generates a normalized, derived representation for
UserChart preparation. It is not an official navigational warning, an
official chart, or a substitute for checking current official
information and the target ECDIS import result.

The engine must not silently invent geometry. When the source does not
provide enough reliable evidence for a Point, Line, Area, or Circle,
the result should remain reviewable as a non-geometry or unresolved
case rather than becoming an asserted chart object.

## Brand and compatibility wording

NAVAREA2UC is independent. References to Furuno or other ECDIS
manufacturers describe compatibility or a target workflow only and do
not imply endorsement, affiliation, or certification.