# NAVAREA2UC ROADMAP
## Any Source. Any Format. Any ECDIS.

---

## 1. Vision

NAVAREA2UC is evolving from a command-line NAVAREA converter into a unified
platform for processing maritime navigational information.

The central idea:

```text
Any source
    ↓
Any message format
    ↓
Unified navigation model
    ↓
Any supported ECDIS
```

Project slogan:

> **Any Source. Any Format. Any ECDIS.**

The target platform must be able to accept data from email, websites, agent
messages, PDF, TXT, SafetyNET, NavStation, and future sources; understand
their structure and content; extract navigation objects; and export them in
the required format.

---

## 2. Core Principles

### 2.1 Source-Agnostic

The source must not determine the internal object model.

Email, PDF, website, copy/paste, NAVAREA, AIO, or a local message must pass
through a source adapter and be converted into a unified input
representation.

### 2.2 Format-Agnostic

Message headers and formats may vary. The engine must not assume that every
document starts with `NAVAREA`.

NAVAREA is the first supported message pipeline, not a universal model for
all future messages.

### 2.3 ECDIS-Agnostic

Furuno modern and Furuno legacy are export adapters. The internal model must
not depend on the XML fields, colors, or limitations of a single ECDIS.

### 2.4 No Silent Geometry Repair

The engine must never silently:

- reorder coordinates;
- change line direction;
- turn a Line into an Area;
- connect independent points;
- create geometry merely because coordinates appear in the text;
- replace ambiguous meaning with a guess.

Suspicious results must be marked with diagnostics and preserved in the
source order.

### 2.5 Provenance First

For every message and every object it must be possible to determine:

- which source produced it;
- which source fragment produced it;
- which encoding was used;
- which parser/profile was applied;
- why that geometry type was selected;
- which warnings were detected.

### 2.6 Deterministic Processing

The same input, engine version, and configuration must produce the same
result.

---

## 3. Current Product Position

### Current Product

Command-line NAVAREA to Furuno UserChart XML converter.

### Current Release

v1.3.0 — core engine stabilization before the transition to HTML.

### Current Branch Policy

- current work is performed in a test branch;
- `main` is not changed without separate approval;
- no release is published without confirmation;
- the Windows EXE is built after the current version has completed review;
- the latest parser fix must be included in the new Windows build before the
  final operational test.

### Current Interface Policy

In v1.3.0 the application remains command-line based.

HTML/Web UI is not part of the current release. The HTML transition starts
only after engine stability has been confirmed.

---

# PHASE 1 — NAVAREA ENGINE ERA
## Status: Functionally implemented; release hardening in progress

## 1.1 Implemented Capabilities

### Geometry Engine

- Area;
- Line;
- Circle;
- Label;
- multiple geometry objects in one message;
- repeated boundary sections as separate Areas;
- grouped and named Areas;
- rectangle Areas;
- ARC Areas;
- geometry rejection diagnostics.

### Geometry Semantics

- `AREA BOUND BY` → Area;
- `AREA BOUNDED WITHIN` → Area;
- `TRACKLINE` → Line;
- `JOINING` → Line;
- `BETWEEN THE POINTS` → Line;
- `PIPELINE` → Line;
- `CABLE` → Line;
- `ROUTE` → Line;
- explicit geometry takes priority over inferred geometry;
- operation-only messages are not automatically converted into geometry;
- multiple buoy coordinates are not automatically connected;
- a radius without an explicit center does not create a Circle.

### Semantic Classification

- operation-first processing;
- hazard override;
- offshore operational objects;
- rigs, platforms, MODU, FPSO, FSO, drillships, and platform jackets;
- security incidents;
- iceberg tracklines and labels;
- active and inactive buoy semantics;
- semantic color and style policies;
- preservation of the original message description.

### Output

- Furuno UserChart XML v1.3 modern export;
- Furuno legacy export;
- legacy object-limit splitting;
- XML attribute sanitization;
- description length handling;
- independent modern and legacy validation.

### Input and Normalization

- multiple input files;
- folder processing;
- NAVAREA discovery;
- descriptive NAVAREA headers;
- line-anchored message splitting;
- cancellation-aware section handling;
- common coordinate format normalization;
- PDF artifact cleanup;
- NAVAREA phrase normalization;
- debug mode only when explicitly requested;
- visible console progress.

### Initial Source Intake Foundation

The project already contains an initial `source_intake` layer:

- reading source data as bytes;
- BOM detection;
- UTF-8 and UTF-16 detection;
- chardet-based detection;
- Windows-1252 and CP1251 fallback;
- confidence value;
- replacement-character count;
- source type metadata;
- intake warnings.

This is the foundation for future email, PDF, web, AIO, and local sources,
but it is not yet a complete universal source platform.

### Validation

- regression tests;
- full corpus runner;
- differential validation;
- reviewed compact baseline;
- release geometry gate;
- component-loss detection;
- source-line references;
- geometry status classification;
- operation-only and reference-only statuses.

## 1.2 Current Verified State

- current test suite: `94/94 OK`;
- current comparison corpus: 21 primary global NAVAREA files;
- current primary corpus: 653 blocks;
- processed in the primary corpus: 995 messages;
- 48 coastal/sub-area and other regional files are retained as a separate
  future scope and are excluded from the current release baseline;
- component loss: `0`;
- differential: `0 changed / 0 unexpected`;
- release geometry gate: `PASS`;
- encoding intake across the retained library: 41 UTF-8 and 28 Windows-1252
  sources, with no intake errors;
  fallback decoding is accepted only at the documented `0.50` confidence
  floor and is surfaced as a review warning;
- the previous Windows artifact was imported into Furuno and displayed
  correctly.

## 1.3 Remaining Work Before v1.3.0 Freeze

- add diagnostics for suspicious tracklines;
- never perform automatic coordinate reordering;
- preserve the boundaries and provenance of every source;
- rebuild the Windows EXE after the latest parser fix;
- recheck generated XML on a real Furuno unit.

## 1.4 v1.3.0 Exit Criteria

v1.3.0 is considered stable when:

- all regression tests pass;
- the complete primary corpus passes;
- the release gate passes;
- no component loss is present;
- Line coordinate order is confirmed by exact tests;
- modern and legacy XML are valid;
- suspicious data is not silently repaired;
- the Windows artifact is built from the reviewed branch;
- the artifact is tested on the target Furuno unit;
- the list of known limitations is published;
- the user confirms the operational result.

## Explicit Non-Goals for v1.3.0

- HTML UI;
- Web API;
- full AIO processing;
- PDF OCR pipeline;
- email/web connectors;
- automatic translation of local messages;
- automatic geometric reconstruction;
- import from other ECDIS systems;
- publishing a release without approval.

---

# PHASE 1.5 — TEXT, ENCODING AND PROVENANCE FOUNDATION
## Status: Partially implemented; required foundation

This phase is required before full source-agnostic processing and the
transition to the web platform.

## 1.5.1 Encoding Layer

Pipeline:

```text
Raw bytes
    ↓
Source-declared encoding
    ↓
BOM detection
    ↓
Strict decoder candidates
    ↓
Encoding detector
    ↓
Language and structure validation
    ↓
Decoded text + confidence
```

Support:

- UTF-8;
- UTF-8 with BOM;
- UTF-16 LE/BE;
- Windows-1252;
- Windows-1251;
- ISO-8859 family;
- other encodings through an extensible detector;
- user encoding override;
- MIME charset for email;
- HTTP charset for web;
- PDF metadata.

Automatic import is allowed at confidence `>= 0.50`. A strict fallback at
the `0.50` boundary remains available for compatibility with the current
corpus, but always adds a review warning. Confidence below `0.50`, a damaged
BOM/UTF-16 sequence, ambiguous bytes, or the absence of a strict decoder must
produce a safe `FAILED` report with `text=None`. Latin-1 fallback is forbidden
because it accepts every byte and masks corruption.

## 1.5.2 Unicode and Text Normalization

- Unicode normalization;
- preservation of the original text;
- handling of non-breaking spaces;
- special dashes and quotation marks;
- degree/minute symbols;
- OCR artifacts;
- hyphenation;
- confusable characters;
- punctuation normalization without losing the original fragment.

## 1.5.3 Language and Script Layer

- language detection;
- script detection;
- multilingual semantic dictionaries;
- source-specific vocabulary;
- canonical semantic keys;
- preservation of the original language;
- optional translated description;
- no dependency of the geometry engine on the English language.

## 1.5.4 Provenance Model

Preserve:

- raw bytes;
- decoded text;
- encoding;
- encoding confidence;
- language;
- source type;
- source identifier;
- original filename;
- page/section/line reference;
- raw message fragment;
- normalized message fragment;
- parser/profile;
- diagnostics.

---

# PHASE 2 — MINIMAL UNIFIED MARITIME INFORMATION MODEL
## Status: Required before full Web API; architecture definition

The minimum internal model must be platform-independent.

```text
SourceDocument
    ↓
NavigationNotice[]
    ↓
ChartObject[]
```

## 2.1 SourceDocument

```text
raw_content
decoded_text
source_type
source_reference
encoding
language
provenance
```

## 2.2 NavigationNotice

```text
notice_id
message_family
region
issue_time
valid_from
valid_until
status
cancellation
original_text
sections[]
objects[]
diagnostics[]
```

## 2.3 ChartObject

```text
object_type:
    Point
    Line
    Polygon
    Circle
    Label
    Route
    AtoN
    Incident

geometry
semantics
temporal_validity
display_intent
provenance
confidence
diagnostics
```

## 2.4 Mandatory Model Rules

- geometry and semantics are separate;
- source text is not lost;
- Line vertex order is preserved;
- Area closure is stored explicitly;
- datum is stored explicitly;
- one Notice may contain multiple objects;
- a Notice may contain no geometry;
- a cancellation is not automatically a new Notice;
- identical coordinate sets from different messages are not silently merged;
- Furuno-specific fields exist only in the export adapter.

## 2.5 Deferred: Coast-Aware NAVAREA Operation Geometry

### Status

Roadmap item only. Not a v1.3.0 release blocker.

Some TOW warnings publish two endpoints with `BETWEEN`, while NavStation may
display a multi-vertex coastal geometry for the warning. The endpoint pair is
an operation description, not sufficient evidence for a safe route.

The future implementation must determine whether that geometry comes from:

- a NAVAREA provider's pre-encoded warning object;
- ENC/coastal chart data updated by coastal notices;
- a provider-side coastal corridor or route graph;
- a separate route-resolution service.

It must not treat a coordinate table copied from NavStation as the source of
truth. Such a table is an observed output that can help reverse-engineer the
logic, but it does not establish the source or algorithm.

### Target model

```text
TOW notice
    ↓
operation metadata + published endpoints
    ↓
geometry resolver with explicit provenance
    ↓
confirmed multi-vertex Line, or unresolved endpoint-only Points
```

### Safety rules

- do not create a straight A–B line merely because two positions are present;
- preserve the published endpoint order;
- distinguish an operation corridor from a navigable safe route;
- require provenance for every generated intermediate vertex;
- return endpoint-only Points when the route source cannot be verified;
- keep this resolver separate from the text parser and from Auto Routeing.

### Entry criteria

- identify the NAVAREA module's actual geometry source or obtain a documented
  equivalent;
- compare several controlled NAVAREA examples with the same coastal region;
- define the route/operation semantics independently of Furuno XML;
- add source, provenance, order, unresolved-fallback, and export regressions;
- validate the resulting geometry on the target ECDIS.

---

# PHASE 3 — SOURCE AND PACKAGE ADAPTER LAYER
## Status: Planned; initial source_intake exists

## 3.1 Source Adapters

Support:

- plain text files;
- clipboard;
- phone camera/photo input;
- photo selection from the device gallery;
- image selection from the device file manager;
- email;
- website;
- PDF;
- SafetyNET;
- NavStation;
- agent upload;
- AIO package;
- future local maritime formats.

The source adapter is responsible for acquiring and describing data, not for
semantic interpretation or geometry selection.

## 3.2 Package Discovery

For ZIP/package input:

```text
Package
    ├── text notice
    ├── raster asset
    ├── metadata
    ├── coverage/no-overlap information
    └── service/signature files
```

Each file type is processed separately. The entire package must not be sent
to the ordinary NAVAREA text parser.

## 3.3 AIO Input Profile

An example AIO package contained:

- 463 TXT notices;
- 634 TIF assets;
- T/P notice classification;
- notices without a NAVAREA header;
- source references;
- multiple semantic categories;
- multiple objects within one notice;
- degree/minute/decimal coordinate notation;
- WGS84 and other datum references;
- text encoded primarily in Windows-1252;
- raster and service files alongside the text.

The AIO adapter must support:

- `(T)` Temporary Notice;
- `(P)` Preliminary Notice;
- notice number and year;
- region/coast;
- source organization;
- WGS84 and declared datum;
- one-point objects;
- multi-point objects;
- line joining;
- area boundaries;
- multiple objects in one notice;
- designation/position tables;
- object-specific source fragments.

---

# PHASE 4 — DOCUMENT AND NOTICE CLASSIFICATION
## Status: Planned; NAVAREA profile exists

Classification must occur after source extraction and before pipeline
processing.

```text
Source Discovery
    ↓
Document Classification
    ↓
Notice Boundary Discovery
    ↓
Message Family Profile
    ↓
Dedicated Pipeline
```

## Planned Message Families

- NAVAREA;
- AIO;
- T&P;
- local hydrographic notice;
- port information;
- pre-arrival information;
- security/incident notice;
- future maritime formats.

## Classification Inputs

- header patterns;
- notice number format;
- language;
- source metadata;
- document title;
- body markers;
- coordinate syntax;
- publication type;
- source organization.

Classification should produce confidence and diagnostics. Unknown documents
must not silently be treated as NAVAREA.

---

# PHASE 5 — CORE API SEPARATION
## Status: Planned; required before Web API

The CLI, tests, and future Web API must use the same core.

```text
CLI       ─┐
Web API   ─┼── Core Engine ── Export Adapters
Tests     ─┘
```

The Core API must accept a SourceDocument/InputDocument and return a
structured ProcessingResult:

```text
ProcessingResult
    notices[]
    chart_objects[]
    diagnostics[]
    source_reports[]
    export_capabilities[]
```

The Web API should not be built by launching the CLI as a subprocess. That
would make the following harder:

- error handling;
- progress reporting;
- sessions;
- cancellation;
- structured diagnostics;
- testability.

The CLI remains a wrapper around the Core API.

---

# PHASE 6 — WEB PLATFORM TRANSITION
## Status: Next platform stage after engine freeze

## 6.1 Web API

Minimum operations:

- upload;
- paste text;
- process;
- list notices;
- list chart objects;
- show diagnostics;
- download modern XML;
- download legacy XML;
- download processing report.

### 6.1.1 Online NAVAREA Feed and User Map

The first online NAVAREA experience must let a user open the site, see the
latest available NAVAREA data, select the notices they need, and generate a
new User Map for download.

Initial scope:

- retrieve current/in-force NAVAREA notices from approved online sources;
- start with the 21 primary global NAVAREA regions;
- keep coastal and sub-area sources as a separate later scope;
- normalize every online source through a source adapter;
- preserve source organization, source URL or reference, retrieval time,
  notice issue time, and validity status;
- show the last successful synchronization time and source coverage;
- show an explicit stale, unavailable, partial, or failed-source state;
- never present cached data as current without a visible freshness warning;
- allow the user to select a NAVAREA region, notice set, and export profile;
- generate a new user map from the selected current notices;
- show the resulting objects and diagnostics before download;
- download modern XML, legacy XML, and a processing/provenance report;
- retain the source snapshot used to generate the map so the result is
  reproducible and auditable;
- fail explicitly when a source cannot be refreshed instead of silently
  generating a map from unknown data.

Target user flow:

```text
Open site
    ↓
Latest NAVAREA status and freshness
    ↓
Select region and current notices
    ↓
Generate new User Map
    ↓
Review objects, diagnostics, and source time
    ↓
Download ECDIS package and report
```

The online feed is a source-acquisition capability, not a replacement for the
Core API or the NAVAREA parser. It must use the same processing, validation,
provenance, and export paths as local input.

## 6.2 Job and Session Handling

Define:

- single-user or multi-user deployment;
- job lifecycle;
- upload limits;
- processing timeouts;
- temporary file cleanup;
- session expiration;
- error recovery;
- audit trail.

If the application is accessible over a network, a self-hosted deployment
must have access protection. A local-only mode may be simpler, but this must
be explicitly defined.

## 6.3 HTML UI

First HTML flow:

```text
Upload / Paste
    ↓
Detected source and encoding
    ↓
Extracted notices
    ↓
Chart objects and diagnostics
    ↓
Export profile
    ↓
Download
```

The first web release must not begin with a full-size map. Reliable
upload/process/review/export workflows come first.

Map visualization and manual geometry editing are separate later stages.

The current HTML artifact is a visual foundation/preview and landing-page
direction, not yet a functional Web Platform.

## 6.4 Mobile Photo Intake

After the Core API is stable, add one mobile-friendly intake flow for photos
and scans:

```text
Take photo with camera
        or
Choose from gallery
        or
Choose from device files
        ↓
Image quality and orientation check
        ↓
OCR / text extraction
        ↓
Original image + extracted text + diagnostics
        ↓
Document classification and processing
```

Required behavior:

- on a phone, the user can open the camera directly from the web interface;
- the user can choose an existing photo from the gallery;
- the user can choose an image or PDF through the file manager;
- if the camera is unavailable, the interface must clearly retain gallery
  and file fallbacks;
- the original file or photo is stored together with extracted text and
  provenance;
- EXIF orientation, resolution, blur, and unreadable-image warnings are
  checked before OCR;
- OCR must not replace the original or silently correct coordinates;
- low OCR or coordinate-recognition confidence moves the object to
  warning/needs-review;
- multi-page photos/scans are combined into one document while preserving
  page order;
- local processing must have a privacy-first policy so the user understands
  whether images leave the device.

In the browser, a standard file input with `accept="image/*"` and a camera
capture hint is preferred, but camera availability depends on the device,
browser, and permissions. Therefore, camera flow must always have two
equally valid fallback paths: gallery and file manager.

Photo intake is a source adapter and must not call the NAVAREA parser
directly. After OCR, the document passes through the common
encoding/language/provenance layer, document classification, and only then
enters a specialized pipeline — NAVAREA, AIO, T&P, or another pipeline.

---

# PHASE 7 — SPECIALIZED MARITIME PIPELINES
## Status: Planned

## 7.1 AIO Pipeline

- Temporary and Preliminary status;
- chart applicability;
- source references;
- datum handling;
- multiple chart objects;
- notices without geometry;
- text and raster asset relationships;
- AIO visualization metadata.

## 7.2 T&P Pipeline

- Temporary Notices;
- Preliminary Notices;
- separate classification;
- separate temporal semantics;
- separate export policy;
- distinction between chart update and navigational warning.

NAVAREA, AIO, and T&P must remain separate pipelines even when they share
normalization and geometry primitives.

## 7.3 Pre-Arrival Pipeline

- port restrictions;
- arrival information;
- voyage information;
- operational advisories;
- port-specific source formats.

---

# PHASE 8 — ECDIS INTEROPERABILITY
## Status: Planned

## 8.1 Export Adapters

- Furuno modern;
- Furuno legacy;
- other UserChart formats;
- GeoJSON/KML or neutral exchange formats where appropriate;
- future ECDIS-specific profiles.

## 8.2 Import Adapters

Long-term objective:

```text
ECDIS A
    ↓
Unified Maritime Information Model
    ↓
ECDIS B
```

Import and export must evolve separately. Maintain a capability matrix for
each ECDIS:

- supported object types;
- coordinate precision;
- style support;
- description limits;
- object limits;
- supported geometry;
- unknown-object behavior;
- round-trip behavior.

---

# PHASE 9 — GEOMETRY INTEGRITY AND REVIEW
## Status: Basic checks required before v1.3.0; advanced layer planned

## Basic Checks

- coordinate validity;
- duplicate vertices;
- Area closure;
- Line coordinate order;
- self-intersection diagnostics;
- anomalous segment lengths;
- sharp route reversals;
- geometry/semantic mismatch;
- component loss;
- missing explicit geometry.

## Review Policy

Automatic validation may detect a suspicious route, but must not reorder
points on its own.

In the console:

```text
WARNING: suspicious trackline
Source order preserved
No automatic geometry repair performed
```

In the future HTML interface:

- show the original fragment;
- show the detected geometry;
- show the warning;
- allow the user to confirm the source order;
- allow the user to skip the object or stop the export.

---

# PHASE 10 — SEMANTIC POLICY
## Status: v1 foundation implemented; expansion planned

## Current Direction

- hazards;
- degraded AtoN;
- navigation aids;
- operational activities;
- security incidents;
- buoy semantic layer;
- separate style policy.

## Future Direction

- multilingual semantic dictionaries;
- local source terminology;
- semantic style expansion;
- source-specific semantic profiles;
- ECDIS-specific display mapping;
- explanations of classification decisions.

Semantic class, geometry type, and export style must remain separate levels of
the model.

---

# 4. Cross-Cutting Quality Requirements

Every new pipeline must have:

- raw fixture;
- decoded fixture;
- normalized fixture;
- exact geometry assertions;
- exact coordinate-order assertions;
- semantic assertions;
- provenance assertions;
- malformed-input tests;
- encoding tests;
- no-geometry tests;
- multiple-object tests;
- cancellation tests;
- modern and legacy export tests where applicable;
- corpus/differential review;
- release-gate integration.

For every new source, verify not only:

```text
how many coordinates were found
```

but also:

```text
in what order;
from which fragment;
what object type;
why this type was selected;
what happened to the original text.
```

---

# 5. Recommended Delivery Order

```text
1. Finish NAVAREA v1.3.0 stabilization
2. Freeze geometry and processing contracts
3. Formalize the minimal Unified Maritime Information Model
4. Preserve raw input, encoding, and provenance
5. Separate the Core API from the CLI
6. Add source/package adapter interfaces
7. Add the Web API
8. Add online NAVAREA freshness and User Map generation
9. Add the minimal HTML upload/process/review/export flow
10. Add mobile photo intake with camera/gallery/file-manager fallback
11. Add OCR and image-quality diagnostics without losing originals
12. Add AIO and T&P pipelines
13. Add additional source adapters
14. Add ECDIS interoperability adapters
15. Add advanced map review and editing
16. Expand toward a Unified Maritime Information Platform
```

---

# 6. Definition of the Final Product

## Current Product

NAVAREA Converter.

## Next Product

Maritime Information Processing Platform.

## Final Product

Unified Maritime Information Platform.

## Final Capabilities

- ingest maritime information from any supported source;
- decode different encodings;
- understand different languages and message structures;
- classify documents and notice families;
- normalize text and coordinates;
- preserve provenance and original content;
- identify points, lines, polygons, circles, and other objects;
- separate geometry from semantics;
- validate and explain ambiguous results;
- generate a unified chart object model;
- export to multiple ECDIS platforms;
- support specialized NAVAREA, AIO, T&P, and Pre-Arrival pipelines;
- provide a self-hosted web interface.

Mission:

> **Any Source. Any Format. Any ECDIS.**