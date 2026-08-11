import re
import sys
import glob
import os
from xml.sax.saxutils import escape

APP_NAME = "NAVAREA2UC"
APP_VERSION = "1.2.0"
APP_AUTHOR = "dr_livsi2004"

# -------------------- CONSTANTS --------------------
LEGACY_MAX_OBJECTS = 150  # maximum objects per legacy UserChart
LEGACY_MAX_DESC = 999  # maximum characters for description
LEGACY_MAX_CIRCLE_RANGE = 100.0   # max radius (NM) for circles

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
    patterns = [
        r"(\d{1,3})[- ]+([\d.]+)\s*([NS])[\s,]+(\d{1,3})[- ]+([\d.]+)\s*([EW])",
        r"(\d{1,3})-([\d.]+)([NS])\s*,\s*(\d{1,3})-([\d.]+)([EW])",
        r"(\d{1,3})-([\d.]+)([NS])(\d{1,3})-([\d.]+)([EW])"
    ]
    coords = []
    for pat in patterns:
        for m in re.finditer(pat, text, flags=re.IGNORECASE):
            lat = dm_to_decimal(m.group(1), m.group(2), m.group(3).upper())
            lon = dm_to_decimal(m.group(4), m.group(5), m.group(6).upper())
            if lat is None or lon is None:
                continue
            coords.append((lat, lon))
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
    m = re.search(r'NAVAREA\s+([A-Z0-9]+)\s+(\d+/\d+)', navarea_name, re.IGNORECASE)
    if not m:
        return navarea_name
    return f"NAV {m.group(1)} {m.group(2)}"


def centroid(coords):
    lat = sum(x[0] for x in coords) / len(coords)
    lon = sum(x[1] for x in coords) / len(coords)
    return (round(lat, 6), round(lon, 6))


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


import math

def segments_intersect(p1, p2, p3, p4):
    def ccw(a, b, c):
        return (c[1] - a[1]) * (b[0] - a[0]) > (b[1] - a[1]) * (c[0] - a[0])
    return ccw(p1, p3, p4) != ccw(p2, p3, p4) and ccw(p1, p2, p3) != ccw(p1, p2, p4)


def has_self_intersection(coords):
    n = len(coords)
    if n < 4:
        return False
    for i in range(n):
        a1 = coords[i]
        a2 = coords[(i + 1) % n]
        for j in range(i + 1, n):
            if abs(i - j) <= 1:
                continue
            if i == 0 and j == n - 1:
                continue
            b1 = coords[j]
            b2 = coords[(j + 1) % n]
            if segments_intersect(a1, a2, b1, b2):
                return True
    return False


def sort_area_vertices(coords):
    c_lat, c_lon = centroid(coords)
    return sorted(coords, key=lambda p: math.atan2(p[0] - c_lat, p[1] - c_lon))


def detect_style(block):
    upper = block.upper()
    if any(x in upper for x in ["WRECK", "SANK", "SUNK", "DERELICT"]):
        return 3
    if any(x in upper for x in ["FPSO", "FSO", "MODU", "RIG", "PLATFORM", "DRILLSHIP", "DRILL"]):
        return 5
    return 2


def detect_color(block):
    upper = block.upper()
    if any(x in upper for x in ["WAR RISK AREA", "MINE DANGER", "FIRING PRACTICE", "FIRING",
                                "WRECK", "SANK", "SUNK", "DERELICT", "DANGER", "PROHIBITED", "EXCLUSION"]):
        return "CHRED"
    if any(x in upper for x in ["FPSO", "FSO", "MODU", "RIG", "PLATFORM", "DRILL", "DRILLSHIP"]):
        return "RESBL"
    return "NINFO"


def detect_check_danger(block):
    upper = block.upper()
    if any(x in upper for x in ["WAR RISK AREA", "MINE DANGER", "FIRING PRACTICE", "FIRING",
                                "WRECK", "SANK", "SUNK", "DERELICT", "DANGER", "PROHIBITED", "EXCLUSION"]):
        return 1
    return 0


def parse_bounding_box(block):
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
    coords = [
        (round(lat1, 6), round(lon1, 6)),
        (round(lat1, 6), round(lon2, 6)),
        (round(lat2, 6), round(lon2, 6)),
        (round(lat2, 6), round(lon1, 6)),
    ]
    return coords


def get_point_style(block):
    upper = block.upper()
    if any(x in upper for x in ["BUOY", "LIGHT", "SPECIAL MARK", "SPECIAL-MARK", "MOORING", "MOORING BUOY", "MOORING BUOYS"]):
        return 2
    return detect_style(block)


def is_multi_point_navarea(block):
    upper = block.upper()
    triggers = [
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


def count_objects(msg):
    """Return total number of objects (areas+lines+circles+labels) in a message."""
    return (len(msg.get('areas', [])) +
            len(msg.get('lines', [])) +
            len(msg.get('circles', [])) +
            len(msg.get('labels', [])))


print()
print("=" * 60)
print(f" {APP_NAME} v{APP_VERSION}")
print()
print(" NAVAREA to Furuno UserChart Converter")
print()
print(f" Author : {APP_AUTHOR}")
print("=" * 60)
print()


def collect_text_from_sources(sources):
    parts = []
    for src in sources:
        if os.path.isdir(src):
            for fpath in sorted(glob.glob(os.path.join(src, "*.txt")) + glob.glob(os.path.join(src, "*.xml"))):
                try:
                    with open(fpath, 'r', encoding='utf-8') as fh:
                        parts.append(fh.read())
                except Exception:
                    continue
            continue
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


if len(sys.argv) > 1:
    sources = sys.argv[1:]
else:
    sources = sorted(glob.glob('*.txt'))

if not sources:
    if os.path.isfile('input.txt'):
        sources = ['input.txt']

text = collect_text_from_sources(sources)

blocks = re.split(r'(?=NAVAREA\s+[A-ZIVXLC]+\s+\d+/\d+)', text, flags=re.IGNORECASE)

navs = {}

for block in blocks:
    block = block.strip()
    if not block:
        continue

    nav_match = re.search(r'(NAVAREA\s+[A-ZIVXLC]+\s+\d+/\d+)', block, re.IGNORECASE)
    if not nav_match:
        continue

    navarea_name = nav_match.group(1)
    m_code = re.search(r'NAVAREA\s+([A-Z0-9]+)\s+(\d+/\d+)', navarea_name, re.IGNORECASE)
    if m_code:
        nav_code = m_code.group(1).upper()
    else:
        nav_code = re.sub(r'[^A-Z0-9]', '_', navarea_name.upper())

    if nav_code not in navs:
        navs[nav_code] = {
            'areas': [],
            'lines': [],
            'circles': [],
            'labels': [],
            'messages': []
        }
    container = navs[nav_code]

    # ---- CREATE MESSAGE AND IMMEDIATELY STORE IT ----
    message = {
        'id': navarea_name,
        'areas': [],
        'lines': [],
        'circles': [],
        'labels': []
    }
    container['messages'].append(message)

    label_text = build_navarea_label(navarea_name)
    coords = extract_coordinates(block)
    clean_block = re.sub(r'-{5,}', ' ', block)
    clean_block = re.sub(r'\s+', ' ', clean_block)
    description = escape(clean_block.replace('"', "'").strip())
    upper = block.upper()

    # ---- SUBLABELS (lettered) ----
    sublabels = extract_sublabels(block)
    if sublabels and is_target_object_type(block) and "RIGLIST" not in upper:
        style = get_point_style(block)
        color = detect_color(block)
        check_danger = detect_check_danger(block)
        for s in sublabels:
            if not s['coords']:
                continue
            desc = escape(s['text'])
            for coord in s['coords']:
                obj = {
                    "style": style,
                    "color": color,
                    "checkDanger": check_danger,
                    "text": label_text,
                    "description": desc,
                    "coord": coord
                }
                container['labels'].append(obj)
                message['labels'].append(obj.copy())
        continue

    # ---- CIRCLE ----
    circle_match = re.search(r'WITHIN\s+([0-9.]+)\s+(?:NM|MILE|MILES)', upper)
    if circle_match and len(coords) >= 1:
        obj = {
            "name": label_text,
            "description": description,
            "range": float(circle_match.group(1)),
            "coord": coords[0],
            "color": detect_color(block),
            "checkDanger": detect_check_danger(block)
        }
        container['circles'].append(obj)
        message['circles'].append(obj.copy())
        continue

    # ---- AREA via bounding box ----
    bb = parse_bounding_box(block)
    if bb:
        obj = {
            "name": label_text,
            "description": description,
            "coords": bb,
            "color": detect_color(block),
            "checkDanger": detect_check_danger(block)
        }
        container['areas'].append(obj)
        message['areas'].append(obj.copy())
        continue

    # ---- AREA by wording ----
    if ("AREA BOUND BY" in upper or "BOUNDED BY" in upper or "AREA BOUNDED" in upper or
        "AREAS BOUNDED" in upper or "AREAS BOUND BY" in upper):
        area_groups = []
        for m in re.finditer(r'(?:\(([A-Z])\)|\b([A-Z])\.)\s*(.*?)(?=(?:\(([A-Z])\)|\b[A-Z]\.)|WIDE BERTH|$)',
                             block, flags=re.S):
            area_id = m.group(1) or m.group(2)
            area_text = (m.group(3) or '').strip()
            if area_id:
                area_groups.append((area_id, area_text))
        if len(area_groups) > 1:
            for area_id, area_text in area_groups:
                sub_coords = extract_coordinates(area_text)
                if len(sub_coords) < 3:
                    continue
                area_coords = sub_coords
                if has_self_intersection(area_coords):
                    fixed = sort_area_vertices(area_coords)
                    if not has_self_intersection(fixed):
                        area_coords = fixed
                obj = {
                    "name": f"{label_text} ({area_id})",
                    "description": description,
                    "coords": area_coords,
                    "color": detect_color(block),
                    "checkDanger": detect_check_danger(block)
                }
                container['areas'].append(obj)
                message['areas'].append(obj.copy())
            continue
        if len(coords) >= 3:
            area_coords = coords
            if has_self_intersection(area_coords):
                fixed = sort_area_vertices(area_coords)
                if not has_self_intersection(fixed):
                    print(f"AUTO-FIX AREA: {label_text}")
                    area_coords = fixed
            obj = {
                "name": label_text,
                "description": description,
                "coords": area_coords,
                "color": detect_color(block),
                "checkDanger": detect_check_danger(block)
            }
            container['areas'].append(obj)
            message['areas'].append(obj.copy())
            continue

    # ---- NO ANCHORING ----
    if "NO ANCHOR" in upper or "ANCHORING PROHIBITED" in upper:
        if len(coords) >= 3:
            area_coords = ensure_clockwise(coords)
            obj = {
                "name": label_text,
                "description": description,
                "coords": area_coords,
                "color": detect_color(block),
                "checkDanger": 0
            }
            container['areas'].append(obj)
            message['areas'].append(obj.copy())
            continue

    # ---- TRACKLINE / ROUTE / PIPELINE / CABLE ----
    if ("TRACKLINE" in upper or "JOINING" in upper or "ROUTE" in upper or
        "CHANNEL" in upper or "PIPELINE" in upper or "CABLE" in upper):
        if len(coords) >= 2:
            obj = {
                "name": label_text,
                "description": description,
                "coords": coords,
                "color": detect_color(block),
                "checkDanger": detect_check_danger(block)
            }
            container['lines'].append(obj)
            message['lines'].append(obj.copy())

            mid = len(coords) // 2
            label_obj = {
                "style": 6,
                "color": detect_color(block),
                "checkDanger": detect_check_danger(block),
                "text": label_text,
                "description": description,
                "coord": coords[mid]
            }
            container['labels'].append(label_obj)
            message['labels'].append(label_obj.copy())
        continue

    # ---- RIG LIST / MODU LIST ----
    if "RIG LIST" in upper or "RIGLIST" in upper:
        entries = re.split(r'\n\s*\d+\.\s+', block)
        if len(entries) > 10:
            for entry in entries:
                coords_found = extract_coordinates(entry)
                if not coords_found:
                    continue
                coord_match = re.search(r'\d{1,3}-[\d.]+[NS]\s+\d{1,3}-[\d.]+[EW]', entry)
                if not coord_match:
                    continue
                coord_text = coord_match.group(0)
                rig_name = entry[:coord_match.start()].strip()
                rig_name = " ".join(rig_name.split())
                if not rig_name:
                    continue
                obj = {
                    "style": 5,
                    "color": "RESBL",
                    "checkDanger": 0,
                    "text": label_text,
                    "description": f"{rig_name} | {coord_text}",
                    "coord": coords_found[0]
                }
                container['labels'].append(obj)
                message['labels'].append(obj.copy())
            continue
        # UK style
        rig_block = re.sub(r'\s+', ' ', block)
        coord_pattern = re.compile(r'\d{1,3}-[\d.]+[NS]\s+\d{1,3}-[\d.]+[EW]', re.I)
        matches = list(coord_pattern.finditer(rig_block))
        for i, m in enumerate(matches):
            coord_text = m.group(0)
            coords_found = extract_coordinates(coord_text)
            if not coords_found:
                continue
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else rig_block.find("NOTES:")
            if end < 0:
                end = len(rig_block)
            tail = rig_block[start:end].strip()
            rig_name = re.split(r'\s+ACP\s+', tail, maxsplit=1, flags=re.I)[0]
            rig_name = " ".join(rig_name.split())
            if not rig_name:
                continue
            obj = {
                "style": 5,
                "color": "RESBL",
                "checkDanger": 0,
                "text": label_text,
                "description": f"{rig_name} | {coord_text}",
                "coord": coords_found[0]
            }
            container['labels'].append(obj)
            message['labels'].append(obj.copy())
        continue

    # ---- MULTI POINT ----
    if is_multi_point_navarea(block):
        style = get_point_style(block)
        color = detect_color(block)
        check_danger = detect_check_danger(block)
        for coord in coords:
            obj = {
                "style": style,
                "color": color,
                "checkDanger": check_danger,
                "text": label_text,
                "description": description,
                "coord": coord
            }
            container['labels'].append(obj)
            message['labels'].append(obj.copy())
        continue

    # ---- SINGLE POINT ----
    if len(coords) >= 1:
        obj = {
            "style": get_point_style(block),
            "color": detect_color(block),
            "checkDanger": detect_check_danger(block),
            "text": label_text,
            "description": description,
            "coord": coords[0]
        }
        container['labels'].append(obj)
        message['labels'].append(obj.copy())
        continue

    # ---- FALLBACK ----
    if len(coords) >= 1:
        obj = {
            "style": 2,
            "color": "NINFO",
            "checkDanger": 0,
            "text": label_text,
            "description": description,
            "coord": coords[0]
        }
        container['labels'].append(obj)
        message['labels'].append(obj.copy())


# -------------------- SPLITTER --------------------
def split_legacy_messages(messages, limit):
    """
    Split messages into parts, each with <= limit objects.
    Messages are atomic and never split across parts.
    Returns list of parts (each part is a list of messages).
    """
    if not messages:
        return []

    if limit <= 0:
        raise ValueError("Legacy object limit must be positive")

    # First pass: count total objects and detect oversized messages
    total_objects = 0
    oversized = []
    for msg in messages:
        cnt = count_objects(msg)
        total_objects += cnt
        if cnt > limit:
            oversized.append(msg['id'])

    if oversized:
        print("WARNING: Some messages exceed legacy object limit:")
        for mid in oversized:
            print(f"  {mid}")

    # If total fits in one part, return a single part
    if total_objects <= limit:
        print(f"Total objects: {total_objects}, Legacy limit: {limit} → single part")
        return [messages]

    parts = []
    current_part = []
    current_count = 0

    for msg in messages:
        cnt = count_objects(msg)

        # Oversized message: close current part, start new part with this message
        if cnt > limit:
            if current_part:
                parts.append(current_part)
                current_part = []
                current_count = 0
            parts.append([msg])
            continue

        # Normal case: try to fit in current part
        if current_count + cnt <= limit:
            current_part.append(msg)
            current_count += cnt
        else:
            # Not enough space – finish current part and start a new one
            if current_part:
                parts.append(current_part)
            current_part = [msg]
            current_count = cnt

    # Append last part if not empty
    if current_part:
        parts.append(current_part)

    # Log part details
    print(f"Total objects: {total_objects}, Legacy limit: {limit}")
    for i, part in enumerate(parts, 1):
        part_count = sum(count_objects(m) for m in part)
        print(f"Part {i} = {part_count} objects")

    return parts


# -------------------- LEGACY XML GENERATORS --------------------
def generate_legacy_xml_from_messages(nav_id, part_messages, part_index, total_parts):
    """
    Merge objects from a list of messages and generate legacy XML.
    File name includes '_PartX' if more than one part.
    UserChart name includes '(Part X)' if more than one part.
    """
    combined = {
        'areas': [],
        'lines': [],
        'circles': [],
        'labels': []
    }
    for msg in part_messages:
        combined['areas'].extend(msg.get('areas', []))
        combined['lines'].extend(msg.get('lines', []))
        combined['circles'].extend(msg.get('circles', []))
        combined['labels'].extend(msg.get('labels', []))

    # Generate unique UserChart name if multiple parts
    if total_parts > 1:
        name_suffix = f"(Part {part_index})"
    else:
        name_suffix = None

    xml_str = generate_legacy_xml(nav_id, combined, name_suffix=name_suffix)

    if total_parts > 1:
        filename = f'output_NAVAREA_{nav_id}_legacy_Part{part_index}.xml'
    else:
        filename = f'output_NAVAREA_{nav_id}_legacy.xml'

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(xml_str)

    obj_count = (len(combined['areas']) + len(combined['lines']) +
                 len(combined['circles']) + len(combined['labels']))
    print(f'Wrote {filename}: Objects={obj_count}')
    return filename, obj_count


def generate_legacy_xml(nav_id, data, name_suffix=None):
    import xml.etree.ElementTree as ET
    from xml.dom import minidom

    # Build unique UserChart name
    base_name = f'NAVAREA {nav_id}'
    if name_suffix:
        full_name = f'{base_name} {name_suffix}'
    else:
        full_name = base_name

    root = ET.Element('userchart', name=full_name, description='', version='1.0')

    def get_attrs(obj_type, obj_data):
        if obj_type == 'area':
            name = obj_data.get('name', f'NAV {nav_id}')
            desc = obj_data.get('description', '')
        elif obj_type == 'label':
            name = obj_data.get('text', f'NAV {nav_id}')
            desc = obj_data.get('description', name)
        else:  # line, circle, clearingLine
            name = obj_data.get('name', '')
            desc = obj_data.get('description', '')

        if len(desc) > LEGACY_MAX_DESC:
            print(
                f"DESC TRUNCATED [{obj_type}] "
                f"{len(desc)} -> {LEGACY_MAX_DESC}"
            )
            desc = desc[:LEGACY_MAX_DESC]
        return name, desc

    # LINES
    if data.get('lines'):
        lines_elem = ET.SubElement(root, 'lines')
        for line in data['lines']:
            name, desc = get_attrs('line', line)
            line_elem = ET.SubElement(lines_elem, 'line', name=name, description=desc)
            pos = ET.SubElement(line_elem, 'position')
            for idx, (lat, lon) in enumerate(line['coords'], start=1):
                ET.SubElement(pos, 'vertex', id=str(idx),
                              latitude=f"{lat:.6f}", longitude=f"{lon:.6f}")
            ET.SubElement(line_elem, 'attribute', lineType=str(line.get('lineType', 2)))
            ET.SubElement(line_elem, 'type',
                          checkDanger=str(line.get('checkDanger', 0)),
                          displayRadar='0', hasNotes='0', rangeOfNotes='1.000000')

    # CLEARING LINES
    if data.get('clearingLines'):
        clearing_elem = ET.SubElement(root, 'clearingLines')
        for cl in data['clearingLines']:
            name, desc = get_attrs('line', cl)
            cl_elem = ET.SubElement(clearing_elem, 'clearingLine', name=name, description=desc)
            pos = ET.SubElement(cl_elem, 'position')
            for idx, (lat, lon) in enumerate(cl['coords'], start=1):
                ET.SubElement(pos, 'vertex', id=str(idx),
                              latitude=f"{lat:.6f}", longitude=f"{lon:.6f}")
            ET.SubElement(cl_elem, 'attribute', lineType=str(cl.get('lineType', 1)))
            ET.SubElement(cl_elem, 'type', isDanger=str(cl.get('isDanger', 0)))

    # AREAS
    if data.get('areas'):
        areas_elem = ET.SubElement(root, 'areas')
        for area in data['areas']:
            name, desc = get_attrs('area', area)
            area_elem = ET.SubElement(areas_elem, 'area', name=name, description=desc)
            pos = ET.SubElement(area_elem, 'position')
            for idx, (lat, lon) in enumerate(area['coords'], start=1):
                ET.SubElement(pos, 'vertex', id=str(idx),
                              latitude=f"{lat:.6f}", longitude=f"{lon:.6f}")
            ET.SubElement(area_elem, 'type',
                          checkDanger=str(area.get('checkDanger', 0)),
                          displayRadar='0', hasNotes='0', notesType='0')

    # LABELS
    if data.get('labels'):
        labels_elem = ET.SubElement(root, 'labels')
        for label in data['labels']:
            name, desc = get_attrs('label', label)
            label_elem = ET.SubElement(labels_elem, 'label', name=name, description=desc)
            pos = ET.SubElement(label_elem, 'position')
            lat, lon = label['coord']
            ET.SubElement(pos, 'vertex', id='1',
                          latitude=f"{lat:.6f}", longitude=f"{lon:.6f}")
            ET.SubElement(label_elem, 'attribute',
                          labelStyle='2',
                          labelText=label.get('text', f'NAV {nav_id}'))
            ET.SubElement(label_elem, 'type',
                          checkDanger=str(label.get('checkDanger', 0)),
                          displayRadar='0')

    # CIRCLES
    if data.get('circles'):
        circles_elem = ET.SubElement(root, 'circles')
        for circle in data['circles']:
            name, desc = get_attrs('circle', circle)
            circle_elem = ET.SubElement(circles_elem, 'circle', name=name, description=desc)
            pos = ET.SubElement(circle_elem, 'position')
            lat, lon = circle['coord']
            ET.SubElement(pos, 'vertex', id='1',
                          latitude=f"{lat:.6f}", longitude=f"{lon:.6f}")
            range_val = circle.get('range', 0.0)
            # Legacy ECDIS limitation: maximum circle range is 100 NM
            if range_val > 100.0:
                print(f"WARNING: Circle range {range_val} NM exceeds legacy limit (100 NM). Will be reduced to 100 NM.")
                range_val = 100.0
            ET.SubElement(circle_elem, 'attribute',
                          range=f"{range_val:.6f}")
            ET.SubElement(circle_elem, 'type',
                          checkDanger=str(circle.get('checkDanger', 0)),
                          displayRadar='0', hasNotes='0', notesType='0')

    rough_string = ET.tostring(root, encoding='unicode')
    reparsed = minidom.parseString(rough_string)

    root_node = reparsed.documentElement
    section_tags = ['lines', 'clearingLines', 'areas', 'labels', 'circles']
    comment_map = {
        'lines': 'userchart line',
        'clearingLines': 'userchart clearingLine',
        'areas': 'userchart area',
        'labels': 'userchart label',
        'circles': 'userchart circle'
    }
    for tag in section_tags:
        elem = root_node.getElementsByTagName(tag)
        if elem:
            elem = elem[0]
            comment = reparsed.createComment(comment_map.get(tag, tag))
            root_node.insertBefore(comment, elem)

    xml_str = reparsed.toprettyxml(indent='  ')
    lines = xml_str.splitlines()
    if lines and lines[0].startswith('<?xml'):
        lines = lines[1:]
    xml_str = '\n'.join([
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<!--userchart node-->',
        *lines
    ])
    return xml_str


# -------------------- MAIN LOOP --------------------
total_areas = total_lines = total_circles = total_labels = 0

for nav_id in sorted(navs.keys()):
    data = navs[nav_id]

    # ---- MODERN FURUNO (unchanged) ----
    xml = []
    xml.append('<?xml version="1.0" encoding="UTF-8"?>')
    xml.append(f'<userchart name="NAVAREA {nav_id} IMPORT" description="" version="1.3">')

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
        print(f'Wrote {outname}: Areas={len(data["areas"])}, Lines={len(data["lines"])}, Circles={len(data["circles"])}, Labels={len(data["labels"])}')
    except Exception as e:
        print('Failed to write', outname, e)

    # ---- LEGACY FURUNO (with splitter) ----
    messages = data.get('messages', [])
    # Filter out completely empty messages to avoid creating empty UserCharts
    non_empty_messages = [m for m in messages if count_objects(m) > 0]

    if non_empty_messages:
        parts = split_legacy_messages(non_empty_messages, LEGACY_MAX_OBJECTS)
        for idx, part in enumerate(parts, start=1):
            generate_legacy_xml_from_messages(nav_id, part, idx, len(parts))
    else:
        # Fallback for old data without messages – generate one legacy file
        legacy_xml = generate_legacy_xml(nav_id, data)
        with open(f'output_NAVAREA_{nav_id}_legacy.xml', 'w', encoding='utf-8') as f:
            f.write(legacy_xml)
        obj_count = len(data['areas']) + len(data['lines']) + len(data['circles']) + len(data['labels'])
        print(f'Wrote output_NAVAREA_{nav_id}_legacy.xml: Objects={obj_count}')

    # Update totals (for summary)
    total_areas += len(data['areas'])
    total_lines += len(data['lines'])
    total_circles += len(data['circles'])
    total_labels += len(data['labels'])

print()
print('===== TOTAL SUMMARY =====')
print(f'Areas   : {total_areas}')
print(f'Lines   : {total_lines}')
print(f'Circles : {total_circles}')
print(f'Labels  : {total_labels}')
print()
print(f'Objects : {total_areas+total_lines+total_circles+total_labels}')
print()
print("Conversion completed successfully.")
if getattr(sys, "frozen", False):
    input("\nPress ENTER to exit...")