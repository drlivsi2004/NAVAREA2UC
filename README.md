<p align="center">
  <img src="logo.png" width="600">
</p>


<h1 align="center">NAVAREA2UC</h1>

<p align="center">

## Project Structure

NAVAREA2UC/

├── .github/

├── NAVAREA2UC_v1.2.0.exe

├── README.md

├── main.py

├── version_info.txt

├── icon.ico

└── input.txt  (example NAVAREA messages)


# NAVAREA2UC


Convert NAVAREA Navigational Warnings into Furuno User Chart XML files.

NAVAREA2UC automatically parses NAVAREA text messages and generates Furuno User Chart objects that can be imported directly into modern Furuno ECDIS systems.

Generated objects preserve original NAVAREA references and descriptions whenever possible.



## Features

✅ Automatic NAVAREA detection

✅ Multiple input files support

✅ Whole-folder processing

✅ Automatic output split by NAVAREA region

✅ Point object generation

✅ Offshore object extraction (FPSO, FSO, MODU, RIG, PLATFORM)

✅ Trackline detection

✅ Area generation

✅ Circle generation

✅ Danger zone classification

✅ Object descriptions

✅ Modern Furuno firmware compatible

✅ Supports common NAVAREA coordinate formats

✅ Legacy Furuno object-limit splitter


## Supported Objects

### Points

- FPSO
- FSO
- MODU
- Offshore rigs
- Buoys
- Lights
- Moorings
- Wrecks
- Derelicts
- Reported depths
- Communication facilities

### Lines

- Tracklines
- Routes
- Pipelines
- Cables
- Channels

### Areas

- Area bounded by coordinates
- War Risk Areas
- Mine Danger Areas
- Firing Practice Areas
- Exclusion Zones
- No Anchoring Areas

### Circles

- Warnings defined by a radius from a central position

## Compatibility

Successfully tested on:

- Furuno ECDIS (Software Ver. 2450074-05.27, UserChart v1.3)
- Furuno ECDIS Legacy (Software Ver. 2450074-03.37, UserChart v1.0)

### Legacy Furuno Support

Legacy UserChart exports are automatically split into multiple files
when the chart object count exceeds legacy system limits.
Legacy splitting preserves NAVAREA message integrity.
Objects belonging to the same NAVAREA warning are never split across multiple legacy UserChart files whenever possible.
Legacy Furuno systems may impose limits on the number of UserChart objects.
NAVAREA2UC attempts to automatically partition charts to improve compatibility, but actual limits may vary depending on Furuno software version.



## Usage

1. Create an empty working folder.
2. Copy NAVAREA2UC.exe into the folder.
3. Place one or more NAVAREA text files in the same folder.
4. Run NAVAREA2UC.exe.
5. Import the generated XML files into Furuno User Chart.

The converter automatically detects NAVAREA regions and creates separate output files for each NAVAREA.

## Corpus validation

The repeatable corpus runner evaluates every retained NAVAREA warning in the
tracked `NAV-*.txt` sources without changing parser handlers. It records source
references, selected handlers, object counts, diagnostics, geometry status, and
mixed-geometry component losses:

```bash
python corpus_runner.py --output reports/navarea-corpus.json
```

Use a prior report for a differential pass. Message IDs supplied with
`--expected-id` are allowed to change; all other changes remain visible as
unexpected:

```bash
python corpus_runner.py \
  --baseline reports/before.json \
  --output reports/after.json \
  --expected-id "NAVAREA IX 208/2026"
```

The report separates confirmed geometry, reference-only coordinates,
rejected invalid areas, operation-only results, and unclassified messages.

### Release geometry gate

Run the release gate before publishing. It returns a non-zero status for
processing errors, unexpected differential changes, or an explicit Area, Line,
or Circle statement that has not been reviewed:

```bash
bash scripts/release-validation.sh
```

The report is written to `reports/release-corpus.json`. Existing reviewed
findings remain visible in the report, while new component-loss findings block
the release and include source-line references.

After reviewing a full report, update the compact release baseline without
hand-entering its message count. The command reruns the current corpus and
rejects the update unless the reviewed report has matching message-count and
fingerprint data:

```bash
python corpus_runner.py \
  --root . \
  --update-baseline reports/corpus_baseline.json \
  --source-report reports/corpus_differential_latest.json
```

To inspect the baseline that would be derived before approving a reviewed
report, use the read-only preview mode. It shows the derived message count and
fingerprint, whether the reviewed report still matches the current corpus, and
the review metadata that would be preserved. It does not write the baseline
file; it returns a non-zero status when the reviewed report is stale:

```bash
python corpus_runner.py \
  --root . \
  --preview-baseline reports/corpus_baseline.json \
  --source-report reports/corpus_differential_latest.json
```

For release automation, add `--json` (or the explicit
`--preview-baseline-json` alias) to emit one JSON object instead of the text
preview:

```bash
python corpus_runner.py \
  --root . \
  --preview-baseline reports/corpus_baseline.json \
  --source-report reports/corpus_differential_latest.json \
  --json
```

The structured preview keeps the same exit status: `0` when the reviewed
report matches the current corpus and `1` when it is stale or otherwise does
not match. Errors are written to stderr. The JSON object has these fields:

| Field | Meaning |
| --- | --- |
| `reviewed_report_messages` | Derived message count from the reviewed report. |
| `reviewed_report_sha256` | Derived fingerprint of the reviewed report content. |
| `current_messages` | Message count in the current corpus run. |
| `current_report_sha256` | Fingerprint of the current corpus report. |
| `reviewed_report_matches_current` | Whether the reviewed report matches the current corpus. |
| `review_metadata` | Existing baseline fields preserved by an update, excluding derived baseline fields. |
| `proposed_baseline` | Compact baseline that would be written by `--update-baseline`; no file is written by preview. |

All preview JSON is written to stdout, making it safe for CI to capture and
parse without scraping the human-readable output.

## Export Modes

### Modern Furuno

Creates UserChart XML v1.3 files compatible with modern Furuno ECDIS systems.

Output:

output_NAVAREA_X.xml

### Legacy Furuno

Creates UserChart XML v1.0 files compatible with legacy Furuno ECDIS systems.

Output:

output_NAVAREA_X_legacy.xml

If chart object count exceeds legacy limits, multiple files are generated automatically:

output_NAVAREA_X_legacy_Part1.xml
output_NAVAREA_X_legacy_Part2.xml
...

## Notes

NAVAREA messages are not fully standardized.

The parser attempts to recognize common coordinate formats, tracklines, areas, circles and offshore installations automatically.

Some NAVAREA warnings may still require manual verification, especially complex area definitions.

## Disclaimer

Always verify generated chart objects against official navigational warnings and charts.

Use at your own responsibility.

## Why?

Because manually plotting dozens of NAVAREA objects into ECDIS is a headache.

---

Fair winds and following seas.

## Version History

### v1.1.0

- Added legacy Furuno UserChart export
- Improved XML compatibility
- Legacy label style normalization
- Verified on legacy Furuno ECDIS

### v1.2.0

- Added message-aware Legacy UserChart splitter
- Preserved NAVAREA message integrity during legacy export
- Added automatic generation of multi-part legacy UserCharts
- Legacy descriptions limited to 999 characters
- Improved area parsing
- Improved multi-area warning detection
- Improved circle detection
- Improved multi-point warning handling
- Expanded offshore object recognition
- Improved complex offshore installation parsing
- Improved compatibility with legacy Furuno ECDIS

### v1.2.1

- Improoved NAVAREA parsing and coordinate extraction
- Improoved Area, route, channel and point generation
- Improved RIGLIST / MODU 
- Improved coordinate parsing
- Improved geometry isolation
- Added handler diagnostics
- Added Mixed geometry support
- AddedMulti-area package support
