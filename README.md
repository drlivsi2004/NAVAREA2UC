<p align="center">
  logo.png
</p>

NAVAREA2UC/

## Project Structure

NAVAREA2UC/

├── .github/

├── NAVAREA2UC.exe

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

Tested on Furuno ECDIS with modern User Chart firmware.

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
- Improved area parsing
- Improved multi-area warning detection
- Improved circle detection
- Improved multi-point warning handling
- Expanded offshore object recognition
- Improved complex offshore installation parsing
- Improved compatibility with legacy Furuno ECDIS




