# NAVAREA2UC expectation vs reality audit

**Audit date:** 2026-09-01  
**Release target:** NAVAREA2UC v1.3.0  
**Primary evidence:** `reports/release-corpus.json`,
`reports/corpus_baseline.json`, `reports/physical-ecdis-case-register.md`,
the full test suite, and the current Modern/Legacy export code.

## Scope and method

The audit covers every selected NAVAREA source in the release corpus. For each
source block and partitioned message it compares:

1. source expectation: geometry statements, source coordinates, operation
   context, section/footer context, and cancellation context;
2. actual parser result: selected handler, Areas/Circles/Lines/Labels,
   geometry diagnostics, source/raw provenance, and component-loss state;
3. actual Description path: handler Description, Modern Description, and
   Legacy Description with the mandatory 999-character ceiling;
4. physical status: the independent ECDIS case register, which is not
   promoted to a pass from code-only evidence.

The full per-message evidence remains in `reports/release-corpus.json`; this
file records the audit verdict and the cases requiring physical follow-up.

## Complete corpus result

| Check | Result |
|---|---:|
| Source files | 21 |
| Source blocks | 653 |
| Partitioned messages | 983 |
| Intake errors | 0 |
| Processing errors | 0 |
| Mixed-geometry source messages | 25 |
| Messages with explicit multi-geometry blocks | 6 |
| Component-loss records | 0 |
| Unexpected release differential | 0 |
| Description objects audited | 1,277 |
| Description semantic contexts present | 1,277 |

**Overall code-side verdict: PASS.** Every corpus message remains represented;
no message or geometry component was dropped by the new Line repair/split
policy.

## Geometry expectation vs reality

The final geometry distribution is:

| Actual result | Messages | Interpretation |
|---|---:|---|
| `CONFIRMED_GEOMETRY` | 145 | Structured chart geometry was emitted and no loss was recorded. |
| `REFERENCE_ONLY_COORDINATES` | 562 | Coordinates were retained as Labels/reference points because the source did not establish a chart polygon/line/circle. |
| `OPERATION_ONLY` | 109 | Operational notice retained without invented chart geometry. |
| `NO_GEOMETRY` | 167 | No chart geometry was expected or available. |

The non-blocking geometry diagnostics are included as flags, not rejected
messages:

- `GEOMETRY_LINE_ORDER_REPAIRED`: 2 messages. A validated single connected
  track received a non-crossing candidate order; raw source coordinates remain
  in provenance.
- `GEOMETRY_LINE_TRACKS_SPLIT`: 3 messages. Independent components were
  emitted separately, with Labels for singleton components where necessary; no
  false connecting Line was emitted.
- `GEOMETRY_LINE_ORDER_REVIEW`: 2 messages. The raw Line remains available
  because the evidence is suspicious but not sufficient for a safe repair.

The release gate treats all three outcomes as available results. No
order-related diagnostic is a component-loss or message-rejection condition.

## Description expectation vs reality

All 1,277 emitted objects retained source semantic context in the audit.
Differences between layers are classified rather than silently ignored:

| Classification | Objects | Meaning |
|---|---:|---|
| `MATCH` | 514 | Handler, Modern, and Legacy descriptions match. |
| `HANDLER_TO_MODERN_SANITIZED` | 647 | XML-safe serialization normalized formatting; source semantic terms remain present. |
| `LEGACY_CAPPED` | 116 | Modern/handler content exceeds the Furuno Legacy limit and is capped at 999 characters by contract. |

Cancellation references remain in the operator Description with their ending
context; they are not implemented as automatic object deletion. For
multi-object messages, the common header/footer and the object-specific
section are audited independently.

## Physical ECDIS case inventory

The register contains 20 numbered cases. The code-side audit does not replace a
physical import on the new EXE. Current physical status is:

| Status | Cases |
|---|---|
| Geometry/style or partial evidence only; retest required | ECDIS-001, 002, 005, 006, 008, 009, 010, 011, 012, 013, 014, 015, 017, 018, 019, 020 |
| Code/design reference, not new-EXE physical confirmation | ECDIS-007 |
| Physical geometry confirmed but Description/context remains open | ECDIS-003, 004, 009, 011, 015, 016, 017, 019, 020 |
| Fresh partial retest with remaining selections/open checks | ECDIS-018 |

The register's more specific verdicts remain authoritative for each case. In
particular:

- `ECDIS-005` / `V 502/26`: one repaired 11-vertex Line is code-side validated;
  the full traversal still needs authoritative or physical confirmation.
- `ECDIS-006`: endpoint-only Labels remain intentional; no straight route was
  invented from two endpoints.
- `ECDIS-008`, `ECDIS-010`, and `ECDIS-018`: corrected color/Danger semantics
  need retesting on the new EXE, including the unselected grouped-buoy row.
- `ECDIS-013`, `016`, `019`, and `020`: bounded Area classification is
  physically supported, but full scrollable Description and build identity are
  not yet evidenced for every retest.

## Release decision

**Code/XML decision: PASS.** The current corpus, Modern/Legacy Description
audit, no-loss checks, and release differential are clean.

**Physical release decision: OPEN.** The next required evidence is a Windows
EXE built from this exact audited revision, imported on the Furuno ECDIS, with
the register cases captured using the new executable identity. Physical
confirmation must record geometry type, complete coordinate order, color,
Danger, and the full scrollable Description; it must not infer completion from
the chart-wide object counter.