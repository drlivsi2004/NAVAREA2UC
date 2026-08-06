NAVAREA2UC/

README.md

src/
     main.py

samples/
    navarea.txt

output/



`markdown
# NAVAREA2UC

Convert NAVAREA Navigational Warnings into Furuno User Chart XML files.

NAVAREA2UC automatically parses NAVAREA text messages and generates Furuno User Chart objects that can be imported directly into modern Furuno ECDIS systems.

---

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

---

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

---

## Usage

Place one or more NAVAREA text files in the same folder as the executable.

Example:
