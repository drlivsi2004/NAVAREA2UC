import re
import sys
import glob
import os
from xml.sax.saxutils import escape


def dm_to_decimal(deg, minutes, hemi):

    deg = abs(int(deg))
    minutes = abs(float(minutes))

    if minutes >= 60:
        return None

    value = deg + minutes / 60

    if hemi in ("S", "W"):
        value = -value

    if hemi in ("N", "S"):
        if abs(value) > 90:
            return None
    else:
        if abs(value) > 180:
            return None

    return round(value, 6)


def extract_coordinates(text):

    # Accept several common deg-min formats: "DD-MM.MMN DDD-MM.MME",
    # "DD MM.MMN DDD MM.MME", and comma-separated variants.
    patterns = [
        # 17-30N 083-43E or 17 30N 083 43E (space or hyphen)
        r"(\d{1,3})[- ]+([\d.]+)\s*([NS])\s*[ ,\t]+(\d{1,3})[- ]+([\d.]+)\s*([EW])",
        # 17-30N,083-43E (comma between lat and lon)
        r"(\d{1,3})-([\d.]+)([NS])\s*,\s*(\d{1,3})-([\d.]+)([EW])",
    ]

    coords = []

    for pat in patterns:
        for m in re.finditer(pat, text, flags=re.IGNORECASE):

            lat = dm_to_decimal(
                m.group(1),
                m.group(2),
                m.group(3).upper()
            )

            lon = dm_to_decimal(
                m.group(4),
                m.group(5),
                m.group(6).upper()
            )

            if lat is None or lon is None:
                continue

            coords.append((lat, lon))

    # Fallback: keep existing strict hyphen pattern for anything missed
    fallback = r'([+-]?\d+)-([\d.]+)([NS])\s+([+-]?\d+)-([\d.]+)([EW])'
    for m in re.finditer(fallback, text):
        lat = dm_to_decimal(m.group(1), m.group(2), m.group(3))
        lon = dm_to_decimal(m.group(4), m.group(5), m.group(6))
        if lat is None or lon is None:
            continue
        pair = (lat, lon)
        if pair not in coords:
            coords.append(pair)

    return coords


def extract_sublabels(block):
    """Extract lettered sublabels (A., B., ...). Returns list of dicts with
    'letter', 'text', and 'coords' (list of (lat,lon)).
    """
    markers = list(re.finditer(r'(?:^|\n)\s*([A-Z]{1,4})\.\s*', block))
    if not markers:
        return []

    items = []
    for i, m in enumerate(markers):
        start = m.start()
        end = markers[i + 1].start() if i + 1 < len(markers) else len(block)
        snippet = block[start:end].strip()
        snippet_text = " ".join(snippet.split())
        coords = extract_coordinates(snippet)
        items.append({
            "letter": m.group(1),
            "text": snippet_text,
            "coords": coords,
        })

    return items


def build_navarea_label(navarea_name):

    m = re.search(
        r'NAVAREA\s+([A-Z0-9]+)\s+(\d+/\d+)',
        navarea_name,
        re.IGNORECASE
    )

    if not m:
        return navarea_name

    return f"NAV {m.group(1)} {m.group(2)}"


def centroid(coords):

    lat = sum(x[0] for x in coords) / len(coords)
    lon = sum(x[1] for x in coords) / len(coords)

    return (
        round(lat, 6),
        round(lon, 6)
    )


def signed_area(coords):

    area = 0.0
    for i in range(len(coords)):
        x1, y1 = coords[i][1], coords[i][0]
        x2, y2 = coords[(i + 1) % len(coords)][1], coords[(i + 1) % len(coords)][0]
        area += x1 * y2 - x2 * y1

    return area / 2.0


def ensure_clockwise(coords):

    if len(coords) < 3:
        return coords

    if signed_area(coords) > 0:
        return list(reversed(coords))

    return coords


def detect_style(block):

    upper = block.upper()

    if any(x in upper for x in [
        "WRECK",
        "SANK",
        "SUNK",
        "DERELICT"
    ]):
        return 3

    if any(x in upper for x in [
        "FPSO",
        "FSO",
        "MODU",
        "RIG",
        "PLATFORM",
        "DRILLSHIP",
        "DRILL"
    ]):
        return 5

    return 2


def detect_color(block):

    upper = block.upper()

    if any(x in upper for x in [
        "WAR RISK AREA",
        "MINE DANGER",
        "FIRING PRACTICE",
        "FIRING",
        "WRECK",
        "SANK",
        "SUNK",
        "DERELICT",
        "DANGER",
        "PROHIBITED",
        "EXCLUSION"
    ]):
        return "CHRED"

    if any(x in upper for x in [
        "FPSO",
        "FSO",
        "MODU",
        "RIG",
        "PLATFORM",
        "DRILL",
        "DRILLSHIP"
    ]):
        return "RESBL"

    return "NINFO"


def detect_check_danger(block):
    upper = block.upper()

    if any(x in upper for x in [
        "WAR RISK AREA",
        "MINE DANGER",
        "FIRING PRACTICE",
        "FIRING",
        "WRECK",
        "SANK",
        "SUNK",
        "DERELICT",
        "DANGER",
        "PROHIBITED",
        "EXCLUSION"
    ]):
        return 1

    return 0


def parse_bounding_box(block):
    """Detect patterns like:
    17-30N TO 17-42N AND 083-43E TO 083-53E
    and return list of four corner coords (lat,lon) in clockwise order.
    """
    pat = re.compile(
        r"(\d{1,3})[- ]+([\d.]+)\s*([NS])\s+TO\s+(\d{1,3})[- ]+([\d.]+)\s*([NS])\s+AND\s+(\d{1,3})[- ]+([\d.]+)\s*([EW])\s+TO\s+(\d{1,3})[- ]+([\d.]+)\s*([EW])",
        flags=re.IGNORECASE
    )

    m = pat.search(block)
    if not m:
        return None

    lat1 = dm_to_decimal(m.group(1), m.group(2), m.group(3).upper())
    lat2 = dm_to_decimal(m.group(4), m.group(5), m.group(6).upper())
    lon1 = dm_to_decimal(m.group(7), m.group(8), m.group(9).upper())
    lon2 = dm_to_decimal(m.group(10), m.group(11), m.group(12).upper())

    if None in (lat1, lat2, lon1, lon2):
        return None

    # Build rectangle corners: (lat1,lon1),(lat1,lon2),(lat2,lon2),(lat2,lon1)
    coords = [
        (round(lat1, 6), round(lon1, 6)),
        (round(lat1, 6), round(lon2, 6)),
        (round(lat2, 6), round(lon2, 6)),
        (round(lat2, 6), round(lon1, 6)),
    ]

    return ensure_clockwise(coords)


def get_point_style(block):
    """Return label style for point features per user request.
    BUOY, LIGHT, SPECIAL MARK, MOORING -> style 2
    Otherwise fallback to detect_style().
    """
    upper = block.upper()
    if any(x in upper for x in ["BUOY", "LIGHT", "SPECIAL MARK", "SPECIAL-MARK", "MOORING", "MOORING BUOY", "MOORING BUOYS"]):
        return 2

    return detect_style(block)


def is_multi_point_navarea(block):

    upper = block.upper()

    triggers = [

        "RIG LIST",
        "RIGLIST",

        "MOBILE OFFSHORE DRILLING UNITS",

        "LIGHTS UNLIT",
        "LIGHT UNLIT",

        "BUOY REMOVED",
        "BUOYS REMOVED",

        "DEPTHS REPORTED",

        "MOORINGS DEPLOYED",
        "OCEAN BOTTOM MOORINGS",

        "REMOTE COMMUNICATION FACILITIES",
        "MESSAGING SERVICES UNAVAILABLE"
    ]

    return any(x in upper for x in triggers)


def is_target_object_type(block):
    """Return True if the block matches one of the object types the user
    requested we apply sublabel-splitting to.
    """
    upper = block.upper()

    targets = [
        "RIGLIST",
        "RIG LIST",
        "MODU",
        "MOBILE OFFSHORE",
        "FPSO",
        "LIGHTS UNLIT",
        "BUOYS REMOVED",
        "DEPTHS REPORTED",
        "MOORINGS",
        "FACILITY OUTAGES",
        "FACILITY OUTAGE",
    ]

    return any(t in upper for t in targets)


def collect_text_from_sources(sources):
    parts = []
    for src in sources:
        # If src is a directory, read all .txt/.xml inside
        if os.path.isdir(src):
            for fpath in sorted(glob.glob(os.path.join(src, "*.txt")) + glob.glob(os.path.join(src, "*.xml"))):
                try:
                    with open(fpath, 'r', encoding='utf-8') as fh:
                        parts.append(fh.read())
                except Exception:
                    continue
            continue

        # Expand globs and accept literal filenames
        paths = glob.glob(src) if any(c in src for c in ['*', '?', '[']) else [src]

        for p in paths:
            if not os.path.isfile(p):
                continue
            if not p.lower().endswith(('.txt', '.xml')):
                continue
            try:
                with open(p, 'r', encoding='utf-8') as fh:
                    parts.append(fh.read())
            except Exception:
                continue

    return "\n".join(parts)


# Determine input sources: command-line args or all *.txt/*.xml in cwd
if len(sys.argv) > 1:
    sources = sys.argv[1:]
else:
    sources = sorted(glob.glob('*.txt') + glob.glob('*.xml'))

if not sources:
    # fallback to input.txt if present
    if os.path.isfile('input.txt'):
        sources = ['input.txt']

text = collect_text_from_sources(sources)

blocks = re.split(
    r'(?=NAVAREA\s+[A-ZIVXLC]+\s+\d+/\d+)',
    text,
    flags=re.IGNORECASE
)

areas = []
lines = []
circles = []
labels = []

navs = {}

for block in blocks:

    block = block.strip()

    if not block:
        continue

    nav_match = re.search(
        r'(NAVAREA\s+[A-ZIVXLC]+\s+\d+/\d+)',
        block,
        re.IGNORECASE
    )

    if not nav_match:
        continue

    navarea_name = nav_match.group(1)

    # NAVAREA code (e.g., I, II, III) — extract the short code
    m_code = re.search(r'NAVAREA\s+([A-Z0-9]+)\s+(\d+/\d+)', navarea_name, re.IGNORECASE)
    if m_code:
        nav_code = m_code.group(1).upper()
    else:
        # fallback: sanitize the whole name
        nav_code = re.sub(r'[^A-Z0-9]', '_', navarea_name.upper())

    # ensure container for this NAVAREA
    if nav_code not in navs:
        navs[nav_code] = {'areas': [], 'lines': [], 'circles': [], 'labels': []}

    container = navs[nav_code]

    label_text = build_navarea_label(navarea_name)

    coords = extract_coordinates(block)

    description = escape(block.replace('"', "'").replace("\n", " ").strip())

    upper = block.upper()

    # If this block contains lettered sublabels and is one of the target
    # object types, create one label per sublabel using only the sublabel
    # snippet as the description.
    sublabels = extract_sublabels(block)

    if sublabels and is_target_object_type(block):
        style = get_point_style(block)
        color = detect_color(block)
        check_danger = detect_check_danger(block)

        for s in sublabels:
            if not s['coords']:
                continue

            desc = escape(s['text'])

            for coord in s['coords']:
                container['labels'].append({
                    "style": style,
                    "color": color,
                    "checkDanger": check_danger,
                    "text": label_text,
                    "description": desc,
                    "coord": coord
                })

        continue

    # CIRCLE

    circle_match = re.search(
        r'WITHIN\s+([0-9.]+)\s+(?:NM|MILE|MILES)',
        upper
    )

    if circle_match and len(coords) >= 1:

        container['circles'].append({
            "name": label_text,
            "description": description,
            "range": float(
                circle_match.group(1)
            ),
            "coord": coords[0],
            "color": detect_color(block),
            "checkDanger": detect_check_danger(block)
        })

        continue

    # AREA

    # First: bounding-box grammar -> area
    bb = parse_bounding_box(block)
    if bb:
        container['areas'].append({
            "name": label_text,
            "description": description,
            "coords": bb,
            "color": detect_color(block),
            "checkDanger": detect_check_danger(block)
        })
        continue

    # AREA by wording
    if (
        "AREA BOUND BY" in upper
        or "BOUNDED BY" in upper
        or "AREA BOUNDED" in upper
    ):

        if len(coords) >= 3:

            area_coords = ensure_clockwise(coords)

            container['areas'].append({

                "name": label_text,

                "description": description,

                "coords": area_coords,

                "color": detect_color(block),

                "checkDanger": detect_check_danger(block)

            })

        continue

    # NO ANCHORING / ANCHORING PROHIBITED -> area (non-danger unless matched)
    if ("NO ANCHOR" in upper or "ANCHORING PROHIBITED" in upper) and len(coords) >= 3:
        area_coords = ensure_clockwise(coords)
        container['areas'].append({
            "name": label_text,
            "description": description,
            "coords": area_coords,
            "color": detect_color(block),
            "checkDanger": 0
        })
        continue

    # TRACKLINE

    # Treat channel/route/pipeline/cable as lines as well
    if (
        "TRACKLINE" in upper
        or "JOINING" in upper
        or "ROUTE" in upper
        or "CHANNEL" in upper
        or "PIPELINE" in upper
        or "CABLE" in upper
    ):

        if len(coords) >= 2:

            container['lines'].append({

                "name": label_text,

                "description": description,

                "coords": coords,

                "color": detect_color(block),

                "checkDanger": detect_check_danger(block)

            })

            mid = len(coords) // 2

            container['labels'].append({

                "style": 6,

                "color": detect_color(block),
                "checkDanger": detect_check_danger(block),
                "text": label_text,

                "description": description,

                "coord": coords[mid]

            })

        continue

    # MULTI POINT

    if is_multi_point_navarea(block):

        style = get_point_style(block)
        color = detect_color(block)

        check_danger = detect_check_danger(block)

        for coord in coords:

            container['labels'].append({

                "style": style,

                "color": color,

                "checkDanger": check_danger,

                "text": label_text,

                "description": description,

                "coord": coord

            })

        continue

    # SINGLE POINT

    if len(coords) >= 1:

        container['labels'].append({

            "style": get_point_style(block),

            "color": detect_color(block),

            "checkDanger": detect_check_danger(block),

            "text": label_text,

            "description": description,

            "coord": coords[0]

        })


total_areas = total_lines = total_circles = total_labels = 0

for nav_id in sorted(navs.keys()):
    data = navs[nav_id]

    xml = []
    xml.append('<?xml version="1.0" encoding="UTF-8"?>')
    xml.append(f'<userchart name="NAVAREA {nav_id} IMPORT" description="" version="1.3">')

    # LINES
    if data['lines']:
        xml.append('<lines>')
        for line in data['lines']:
            xml.append(f'<line name="{line["name"]}" description="{line["description"]}">')
            xml.append('<position>')
            for idx, (lat, lon) in enumerate(line['coords'], start=1):
                xml.append(f'<vertex id="{idx}" latitude="{lat}" longitude="{lon}"/>')
            xml.append('</position>')
            xml.append('<attribute lineType="2" linkedDocument=""/>')
            xml.append(f'<type checkDanger="{line["checkDanger"]}" displayRadar="0" hasNotes="0" rangeOfNotes="1.000000"/>')
            xml.append(f'<display S52colorcode="{line["color"]}" lineWidth="3"/>')
            xml.append('</line>')
        xml.append('</lines>')

    # AREAS
    if data['areas']:
        xml.append('<areas>')
        for area in data['areas']:
            xml.append(f'<area name="{area["name"]}" description="{area["description"]}">')
            xml.append('<position>')
            for idx, (lat, lon) in enumerate(area['coords'], start=1):
                xml.append(f'<vertex id="{idx}" latitude="{lat}" longitude="{lon}"/>')
            xml.append('</position>')
            xml.append('<attribute linkedDocument=""/>')
            xml.append(f'<type checkDanger="{area["checkDanger"]}" displayRadar="0" hasNotes="0" notesType="0"/>')
            xml.append(f'<display S52colorcode="{area["color"]}" lineWidth="2" density="25"/>')
            xml.append('</area>')
        xml.append('</areas>')

    # CIRCLES
    if data['circles']:
        xml.append('<circles>')
        for circle in data['circles']:
            lat, lon = circle['coord']
            xml.append(f'<circle name="{circle["name"]}" description="{circle["description"]}">')
            xml.append('<position>')
            xml.append(f'<vertex id="1" latitude="{lat}" longitude="{lon}"/>')
            xml.append('</position>')
            xml.append(f'<attribute range="{circle["range"]:.6f}" linkedDocument=""/>')
            xml.append(f'<type checkDanger="{circle["checkDanger"]}" displayRadar="0" hasNotes="0" notesType="0"/>')
            xml.append(f'<display S52colorcode="{circle["color"]}" lineWidth="2" density="25"/>')
            xml.append('</circle>')
        xml.append('</circles>')

    # LABELS
    if data['labels']:
        xml.append('<labels>')
        for label in data['labels']:
            lat, lon = label['coord']
            xml.append(f'<label name="{label["text"]}" description="{label["description"]}">')
            xml.append('<position>')
            xml.append(f'<vertex id="1" latitude="{lat}" longitude="{lon}"/>')
            xml.append('</position>')
            xml.append(f'<attribute labelStyle="{label["style"]}" labelText="{label["text"]}" linkedDocument=""/>')
            xml.append(f'<type checkDanger="{label["checkDanger"]}" displayRadar="0"/>')
            xml.append(f'<display S52colorcode="{label["color"]}"/>')
            xml.append('</label>')
        xml.append('</labels>')

    xml.append('</userchart>')

    outname = f'output_NAVAREA_{nav_id}.xml'
    try:
        with open(outname, 'w', encoding='utf-8') as f:
            f.write('\n'.join(xml))
    except Exception as e:
        print('Failed to write', outname, e)

    # update totals
    total_areas += len(data['areas'])
    total_lines += len(data['lines'])
    total_circles += len(data['circles'])
    total_labels += len(data['labels'])

    print(f'Wrote {outname}: Areas={len(data["areas"])}, Lines={len(data["lines"])}, Circles={len(data["circles"])}, Labels={len(data["labels"]) }')


print()
print('===== TOTAL SUMMARY =====')
print(f'Areas   : {total_areas}')
print(f'Lines   : {total_lines}')
print(f'Circles : {total_circles}')
print(f'Labels  : {total_labels}')
print()
print(f'Objects : {total_areas+total_lines+total_circles+total_labels}')
