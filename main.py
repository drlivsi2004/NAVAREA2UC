from normalizer import normalize_input, NormalizerStats
import re
import sys
import glob
import os
import copy
import math
import time
import xml.etree.ElementTree as ET
from xml.dom import minidom
from xml.sax.saxutils import escape, unescape


APP_NAME = "NAVAREA2UC"
APP_VERSION = "1.3.0"
APP_AUTHOR = "dr_livsi2004"

# -------------------- CONSTANTS --------------------
LEGACY_MAX_OBJECTS = 150
LEGACY_MAX_DESC = 999
LEGACY_MAX_CIRCLE_RANGE = 50.0
RISK_LOW_MAX = 500
RISK_MEDIUM_MAX = 2000
RISK_HIGH_MAX = 5000
MAX_VERTICES_PER_OBJECT = None
MAX_VERTICES_PER_MESSAGE = None
STYLE_SECURITY = 5

# Source notices occasionally spell buoy as "BOUY".  Keep the correction
# semantic-only: the original source text remains untouched in descriptions
# and audit records.
BUOY_WORD = r"(?:BUOYS?|BOUYS?)"
BUOY_TEXT_RE = re.compile(
    rf"\b(?:{BUOY_WORD}|LIGHT{BUOY_WORD})\b",
    re.IGNORECASE,
)

DEBUG_VALUES = {"1", "true", "yes", "on"}
DEBUG = (
    os.getenv("NAVAREA2UC_DEBUG", "").strip().lower() in DEBUG_VALUES
    or "--debug" in sys.argv
)

NAVAREA_HEADER_RE = re.compile(
    r"(?im)^[ \t]*(NAVAREA\s+[A-Z0-9]+\s+\d+/\d+)\b"
)
NAVAREA_BLOCK_BOUNDARY_RE = re.compile(
    r"(?im)(?=^[ \t]*NAVAREA\s+[A-Z0-9]+\s+\d+/\d+\b)"
)


def debug(msg):
    if DEBUG:
        print(f"DEBUG: {msg}")


# -------------------- COORDINATE & UTILITY FUNCTIONS --------------------
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
    # NAVAREA sources may separate a latitude/longitude pair with "/".
    # Normalize only the coordinate boundary so other slash-delimited text
    # remains untouched.
    text = re.sub(
        r"([NS])\s*/\s*(?=\d{1,3}[- ]+[\d.]+\s*[EW])",
        r"\1 ",
        text,
        flags=re.IGNORECASE,
    )
    # Replace commas with dots in coordinate numbers (e.g. 46-02,80N -> 46-02.80N)
    text = re.sub(
        r"(\d)-([\d,]+)\s*([NS])",
        lambda m: f"{m.group(1)}-{m.group(2).replace(',', '.')}{m.group(3)}",
        text,
        flags=re.I,
    )
    text = re.sub(
        r"(\d)-([\d,]+)\s*([EW])",
        lambda m: f"{m.group(1)}-{m.group(2).replace(',', '.')}{m.group(3)}",
        text,
        flags=re.I,
    )

    patterns = [
        r"(\d{1,3})[-\s]+([\d.]+)\s*([NS])[\s,]+(\d{1,3})[-\s]+([\d.]+)\s*([EW])",
        r"(\d{1,3})-([\d.]+)([NS])\s*,\s*(\d{1,3})-([\d.]+)([EW])",
        r"(\d{1,3})-([\d.]+)([NS])(\d{1,3})-([\d.]+)([EW])",
    ]
    coords = []
    for pat in patterns:
        for m in re.finditer(pat, text, flags=re.IGNORECASE):
            lat = dm_to_decimal(m.group(1), m.group(2), m.group(3).upper())
            lon = dm_to_decimal(m.group(4), m.group(5), m.group(6).upper())
            if lat is None or lon is None:
                continue
            coords.append((lat, lon))

    # Existing fallback for simple DM
    fallback = r"([+-]?\d+)[-\s]+([\d.]+)([NS])\s+([+-]?\d+)[-\s]+([\d.]+)([EW])"
    for m in re.finditer(fallback, text):
        lat = dm_to_decimal(m.group(1), m.group(2), m.group(3))
        lon = dm_to_decimal(m.group(4), m.group(5), m.group(6))
        if lat is None or lon is None:
            continue
        pair = (lat, lon)
        if pair not in coords:
            coords.append(pair)

    # NEW FALLBACK: Handle DMS with double hyphens and DM without separator
    if not coords:
        # DMS with double hyphens: dd-mm-ss.sN dd-mm-ss.sE
        dms_double_hyphen_pattern = re.compile(
            r"(\d{1,3})-(\d{1,2})-([\d.]+)\s*([NS])\s+(\d{1,3})-(\d{1,2})-([\d.]+)\s*([EW])",
            re.IGNORECASE,
        )
        for m in dms_double_hyphen_pattern.finditer(text):
            lat_deg = int(m.group(1))
            lat_min = float(m.group(2))
            lat_sec = float(m.group(3))
            lat_hemi = m.group(4).upper()
            lon_deg = int(m.group(5))
            lon_min = float(m.group(6))
            lon_sec = float(m.group(7))
            lon_hemi = m.group(8).upper()

            lat_dec = lat_deg + lat_min / 60.0 + lat_sec / 3600.0
            lon_dec = lon_deg + lon_min / 60.0 + lon_sec / 3600.0
            if lat_hemi == "S":
                lat_dec = -lat_dec
            if lon_hemi == "W":
                lon_dec = -lon_dec
            coords.append((round(lat_dec, 6), round(lon_dec, 6)))

        # DM without separator: ddmm.sN ddmm.sE
        dm_no_separator_pattern = re.compile(
            r"(\d{1,2})(\d{2}\.\d+)\s*([NS])\s+(\d{1,3})(\d{2}\.\d+)\s*([EW])",
            re.IGNORECASE,
        )
        for m in dm_no_separator_pattern.finditer(text):
            lat_deg = int(m.group(1))
            lat_min = float(m.group(2))
            lat_hemi = m.group(3).upper()
            lon_deg = int(m.group(4))
            lon_min = float(m.group(5))
            lon_hemi = m.group(6).upper()

            lat_dec = lat_deg + lat_min / 60.0
            lon_dec = lon_deg + lon_min / 60.0
            if lat_hemi == "S":
                lat_dec = -lat_dec
            if lon_hemi == "W":
                lon_dec = -lon_dec
            coords.append((round(lat_dec, 6), round(lon_dec, 6)))

    return coords


def extract_circle_spec(block):
    """
    Extract an explicit radius/center statement from a local text scope.

    Supports common variants such as:
      WITHIN 3 NM OF POSITION 26-16.17N/055-46.52E
      WITHIN A 3 NM RADIUS OF POSITION 26-16.17N/055-46.52E
    """
    coord_pattern = (
        r"(?P<coord>\d{1,3}[- ]+[\d.]+\s*[NS]\s*"
        r"(?:/|,|\s)\s*\d{1,3}[- ]+[\d.]+\s*[EW])"
    )
    pattern = re.compile(
        r"\bWITHIN\s+(?:A\s+)?"
        r"(?P<radius>[0-9]+(?:\.[0-9]+)?)\s*"
        r"(?P<unit>NM|MILES?|MI)\s+"
        r"(?:RADIUS\s+)?OF\s+(?:POSITION\s+)?"
        + coord_pattern,
        flags=re.IGNORECASE,
    )
    match = pattern.search(block)
    if not match:
        pattern = re.compile(
            r"\b(?:ARC\s+OF\s+)?RADIUS\s+"
            r"(?P<radius>[0-9]+(?:\.[0-9]+)?)\s*"
            r"(?P<unit>NM|MILES?|MI|METERS?|METRES?)\s+"
            r"(?:RADIUS\s+)?CENTER(?:ED|RE)?\s+(?:AT|ON)\s+"
            + coord_pattern,
            flags=re.IGNORECASE,
        )
        match = pattern.search(block)
    if not match:
        return None

    coords = extract_coordinates(match.group("coord"))
    if len(coords) != 1:
        return None

    unit = match.group("unit").upper()
    if unit == "MI":
        unit = "MILE"
    radius = float(match.group("radius"))
    if unit in ("METER", "METERS", "METRE", "METRES"):
        radius /= 1852.0
    return {
        "center": coords[0],
        "radius": radius,
        "unit": unit,
    }


def extract_safety_zone_circle_specs(block):
    """
    Extract one circle per named SPM from a plural safety-zone statement.

    Example:
      SAFETY ZONES OF 1500 METER ESTABLISHED AROUND SPMs
      IN FOLLOWING POSITIONS:
      SPM2 26-35.496N 052-01.986E
      SPM3 26-38.808N 051-53.496E
      SPM4 26-40.375N 051-53.896E

    The source supplies an explicit radius and one center for each named
    point, so no connecting geometry is inferred.
    """
    pattern = re.compile(
        r"\bSAFETY\s+ZONES?\s+OF\s+"
        r"(?P<radius>[0-9]+(?:\.[0-9]+)?)\s*"
        r"(?P<unit>METERS?|METRES?|NM|MILES?|MI)\s+"
        r"ESTABLISHED\s+AROUND\s+SPMS?\s+"
        r"IN\s+FOLLOWING\s+POSITIONS?\s*:?",
        flags=re.IGNORECASE,
    )
    match = pattern.search(block)
    if not match:
        return []

    position_text = re.split(
        r"(?:^|\n)\s*\d+(?:\.\d+)*\.\s+",
        block[match.end() :],
        maxsplit=1,
        flags=re.MULTILINE,
    )[0]
    coords = extract_coordinates(position_text)
    names = [
        re.sub(r"\s+", "", name.group(0)).upper()
        for name in re.finditer(r"\bSPM\s*\d+\b", position_text, re.IGNORECASE)
    ]
    if not coords or len(names) != len(coords):
        return []

    unit = match.group("unit").upper()
    if unit == "MI":
        unit = "MILE"
    radius = float(match.group("radius"))
    if unit in ("METER", "METERS", "METRE", "METRES"):
        radius /= 1852.0

    return [
        {
            "center": coord,
            "radius": radius,
            "unit": unit,
            "object_name": object_name,
        }
        for object_name, coord in zip(names, coords)
    ]


def extract_explicit_route_waypoints(block):
    """
    Extract the waypoint list from the IX 208-style authorized-route clause.

    This is intentionally narrow: it requires the explicit authorized-route
    wording and scopes coordinates to the A./B./... waypoint list.
    """
    route_anchor = re.search(
        r"\bROUTES?\s+THAT\s+HAVE\s+BEEN\s+AUTHORIZED\b"
        r"[\s\S]*?\bAS\s+FOLLOWS\s*:?",
        block,
        flags=re.IGNORECASE,
    )
    if not route_anchor:
        return []

    route_text = block[route_anchor.end() :]
    route_text = re.split(r"(?m)^\s*\d+\.\s+", route_text, maxsplit=1)[0]
    markers = list(
        re.finditer(
            r"(?im)^\s*(?:\(([A-F])\)|([A-F])\.?(?=\s+\d{1,3}[- ]+))\s*",
            route_text,
        )
    )
    if len(markers) < 2:
        return []

    waypoints = []
    for index, marker in enumerate(markers):
        end = markers[index + 1].start() if index + 1 < len(markers) else len(route_text)
        segment = route_text[marker.end() : end]
        coords = extract_coordinates(segment)
        if len(coords) != 1:
            return []
        waypoints.append(coords[0])
    return waypoints


def deduplicate_consecutive(points):
    """
    Удаляет только соседние точные дубли.

    Вход:
        points: list[tuple[float, float]]

    Выход:
        list[tuple[float, float]]

    Гарантии:
        - порядок сохраняется
        - дубли, идущие подряд, удаляются
    """
    result = []
    for p in points:
        if not result or result[-1] != p:
            result.append(p)
    return result


def ensure_closed(vertices):
    """
    Замыкает полигон, если первая и последняя вершины не совпадают.

    Вход:
        vertices: list[tuple[float, float]]

    Выход:
        list[tuple[float, float]]
    """
    if not vertices:
        return vertices
    if vertices[0] != vertices[-1]:
        return vertices + [vertices[0]]
    return vertices


def normalize_area_vertices(points):
    """
    Единая точка нормализации вершин area.

    Гарантии:
        - Input order preserved
        - Consecutive duplicates removed
        - Area is closed
    """
    points = deduplicate_consecutive(points)
    points = ensure_closed(points)
    return points


def area_vertices_for_xml(points):
    """
    Return one copy of each boundary vertex for UserChart XML.

    The internal object model keeps a repeated first vertex so geometry
    validation and reports can reason about a closed ring. Furuno ECDIS,
    however, closes an Area itself; serializing the repeated vertex can make
    some imports treat the first boundary point as a duplicate and drop it.
    """
    if len(points) >= 2 and points[0] == points[-1]:
        return points[:-1]
    return points


def extract_sublabels(block):
    markers = list(
        re.finditer(r"(?:^|\n)\s*(?:\(([A-Z])\)|([A-Z])\.)\s*", block)
    )
    if not markers:
        return []
    items = []
    for i, m in enumerate(markers):
        letter = m.group(1) or m.group(2)
        start = m.start()
        end = markers[i + 1].start() if i + 1 < len(markers) else len(block)
        snippet = block[start:end].strip()
        snippet_text = " ".join(snippet.split())
        coords = extract_coordinates(snippet)
        items.append(
            {
                "letter": letter,
                "text": snippet_text,
                "coords": coords,
            }
        )
    return items


def extract_sublabels_inline(block):
    """
    Извлекает (A)/(B)/(C) маркеры, находящиеся внутри строки,
    а не только в начале строки.

    Пример:
        1. MF R/T AND DSC SERVICES OFF AIR FROM SITES:
        (A) BAWDSEY 51-59.6N 001-24.5E.
        (B) CULLERCOATS 55-04.4N 001-27.8W.
    """
    items = []

    for m in re.finditer(r"\(([A-Z])\)\s*([^()]+)", block):
        text = m.group(2).strip()
        coords = extract_coordinates(text)

        if coords:
            items.append(
                {
                    "text": text,
                    "coords": coords,
                }
            )

    return items


def build_navarea_label(navarea_name):
    m = re.search(r"NAVAREA\s+([A-Z0-9]+)\s+(\d+/\d+)", navarea_name, re.IGNORECASE)
    if not m:
        return navarea_name
    return f"NAV {m.group(1)} {m.group(2)}"


def split_navarea_blocks(text):
    """Split normalized text at actual message-header lines only.

    Cancellation references can contain a valid-looking NAVAREA number, but
    they are not new messages.  Requiring the header at the start of a line
    prevents inline references from becoming separate blocks.
    """

    return NAVAREA_BLOCK_BOUNDARY_RE.split(text)


def haversine_distance_nm(coord1, coord2):
    """
    Ð Ð°ÑÑÑÐ¾ÑÐ½Ð¸Ðµ Ð¼ÐµÐ¶Ð´Ñ Ð´Ð²ÑÐ¼Ñ ÐºÐ¾Ð¾ÑÐ´Ð¸Ð½Ð°ÑÐ°Ð¼Ð¸ Ð² Ð¼Ð¾ÑÑÐºÐ¸Ñ Ð¼Ð¸Ð»ÑÑ.
    """
    R_NM = 3440.065  # ÑÑÐµÐ´Ð½Ð¸Ð¹ ÑÐ°Ð´Ð¸ÑÑ ÐÐµÐ¼Ð»Ð¸ Ð² Ð¼Ð¾ÑÑÐºÐ¸Ñ Ð¼Ð¸Ð»ÑÑ

    lat1, lon1 = coord1
    lat2, lon2 = coord2

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = (
        math.sin(dphi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    return R_NM * c


def generate_arc_points(center, start, end, steps=24, direction="shortest"):
    """
    ÐÐµÐ½ÐµÑÐ¸ÑÑÐµÑ ÑÐ¾ÑÐºÐ¸ Ð´ÑÐ³Ð¸ Ð¾Ñ start Ð´Ð¾ end Ñ ÑÐµÐ½ÑÑÐ¾Ð¼ Ð² center.

    ÐÐ°ÑÐ°Ð¼ÐµÑÑÑ:
      center    : ÐºÐ¾Ð¾ÑÐ´Ð¸Ð½Ð°ÑÐ° ÑÐµÐ½ÑÑÐ° (lat, lon)
      start     : ÐºÐ¾Ð¾ÑÐ´Ð¸Ð½Ð°ÑÐ° Ð½Ð°ÑÐ°Ð»Ð° Ð´ÑÐ³Ð¸
      end       : ÐºÐ¾Ð¾ÑÐ´Ð¸Ð½Ð°ÑÐ° ÐºÐ¾Ð½ÑÐ° Ð´ÑÐ³Ð¸
      steps     : ÐºÐ¾Ð»Ð¸ÑÐµÑÑÐ²Ð¾ Ð¿ÑÐ¾Ð¼ÐµÐ¶ÑÑÐ¾ÑÐ½ÑÑ ÑÐ¾ÑÐµÐº
      direction : ÑÐµÐ¶Ð¸Ð¼ Ð¿Ð¾ÑÑÑÐ¾ÐµÐ½Ð¸Ñ Ð´ÑÐ³Ð¸.
                  Ð¡ÐµÐ¹ÑÐ°Ñ Ð¿Ð¾Ð´Ð´ÐµÑÐ¶Ð¸Ð²Ð°ÐµÑÑÑ ÑÐ¾Ð»ÑÐºÐ¾ "shortest".
                  ÐÐ°ÑÐ°Ð¼ÐµÑÑ Ð´Ð¾Ð±Ð°Ð²Ð»ÐµÐ½ Ð´Ð»Ñ Ð±ÑÐ´ÑÑÐµÐ¹ Ð¿Ð¾Ð´Ð´ÐµÑÐ¶ÐºÐ¸:
                    "cw"  - Ð¿Ð¾ ÑÐ°ÑÐ¾Ð²Ð¾Ð¹
                    "ccw" - Ð¿ÑÐ¾ÑÐ¸Ð² ÑÐ°ÑÐ¾Ð²Ð¾Ð¹

    ÐÐ¾Ð·Ð²ÑÐ°ÑÐ°ÐµÑ:
      [start, p1, p2, ..., end]
    """
    import math

    lat_c = math.radians(center[0])
    lon_c = math.radians(center[1])

    def to_local_xy(point):
        lat = math.radians(point[0])
        lon = math.radians(point[1])
        x = (lon - lon_c) * 60.0 * math.cos(lat_c)
        y = (lat - lat_c) * 60.0
        return x, y

    def from_local_xy(x, y):
        lat = math.degrees(lat_c + y / 60.0)
        lon = math.degrees(lon_c + x / (60.0 * math.cos(lat_c)))
        return (round(lat, 6), round(lon, 6))

    x_start, y_start = to_local_xy(start)
    x_end, y_end = to_local_xy(end)

    radius = math.hypot(x_start, y_start)

    angle_start = math.atan2(x_start, y_start)
    angle_end = math.atan2(x_end, y_end)

    delta_angle = angle_end - angle_start

    if direction == "shortest":
        while delta_angle > math.pi:
            delta_angle -= 2.0 * math.pi
        while delta_angle < -math.pi:
            delta_angle += 2.0 * math.pi

    if abs(delta_angle) < 1e-9:
        return [start, end]

    points = [start]

    for i in range(1, steps):
        fraction = i / steps
        angle = angle_start + delta_angle * fraction
        x = radius * math.sin(angle)
        y = radius * math.cos(angle)
        points.append(from_local_xy(x, y))

    points.append(end)
    return points


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


def segments_intersect(p1, p2, p3, p4):
    def ccw(a, b, c):
        return (c[1] - a[1]) * (b[0] - a[0]) > (b[1] - a[1]) * (c[0] - a[0])

    return ccw(p1, p3, p4) != ccw(p2, p3, p4) and ccw(p1, p2, p3) != ccw(p1, p2, p4)


def has_self_intersection(coords):
    # Area rings are normally stored closed for XML export.  The repeated
    # first vertex is a delimiter, not a second polygon vertex; remove it
    # before comparing non-adjacent edges.
    if len(coords) >= 2 and coords[0] == coords[-1]:
        coords = coords[:-1]
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


def _line_crossing_segments(coords):
    """Return crossing segment pairs for an open polyline."""

    crossings = []
    segment_count = len(coords) - 1
    for i in range(segment_count):
        for j in range(i + 2, segment_count):
            if segments_intersect(
                coords[i], coords[i + 1], coords[j], coords[j + 1]
            ):
                crossings.append([i, j])
    return crossings


def _line_unique_coords(coords):
    unique = []
    source_indices = []
    index_by_coord = {}
    for index, coord in enumerate(coords):
        if coord not in index_by_coord:
            index_by_coord[coord] = len(unique)
            unique.append(coord)
            source_indices.append([index])
        else:
            source_indices[index_by_coord[coord]].append(index)
    return unique, source_indices


def _line_mst_edges(coords):
    """Build a distance MST used only to detect disconnected tracks."""

    if len(coords) < 2:
        return []
    connected = {0}
    edges = []
    while len(connected) < len(coords):
        best = None
        for start in connected:
            for end in range(len(coords)):
                if end in connected:
                    continue
                distance = haversine_distance_nm(coords[start], coords[end])
                candidate = (distance, start, end)
                if best is None or candidate < best:
                    best = candidate
        distance, start, end = best
        connected.add(end)
        edges.append((distance, start, end))
    return edges


def _line_track_components(coords):
    """Split clearly separated vertex clusters without joining them."""

    unique_coords, _ = _line_unique_coords(coords)
    if len(unique_coords) < 2:
        return [list(range(len(unique_coords)))] if unique_coords else []

    mst_edges = _line_mst_edges(unique_coords)
    sorted_distances = sorted(edge[0] for edge in mst_edges)
    median_distance = sorted_distances[len(sorted_distances) // 2]
    separation_limit = max(250.0, median_distance * 3.0)

    parent = list(range(len(unique_coords)))

    def find(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left, right):
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for distance, start, end in mst_edges:
        if distance <= separation_limit:
            union(start, end)

    components = {}
    for index in range(len(unique_coords)):
        components.setdefault(find(index), []).append(index)
    return list(components.values())


def _line_path_distance(coords, order):
    return sum(
        haversine_distance_nm(coords[start], coords[end])
        for start, end in zip(order, order[1:])
    )


def _line_best_order(coords, preferred_start=None, preferred_end=None):
    """Find a short, non-crossing open path using all supplied vertices."""

    unique_coords, _ = _line_unique_coords(coords)
    if len(unique_coords) < 2:
        return list(range(len(unique_coords))), 0.0, False

    candidates = []
    for start in range(len(unique_coords)):
        path = [start]
        remaining = set(range(len(unique_coords))) - {start}
        while remaining:
            next_index = min(
                remaining,
                key=lambda index: (
                    haversine_distance_nm(unique_coords[path[-1]], unique_coords[index]),
                    index,
                ),
            )
            path.append(next_index)
            remaining.remove(next_index)
        candidates.append(path)

    valid_candidates = [
        path
        for path in candidates
        if not _line_crossing_segments([unique_coords[index] for index in path])
    ]
    if not valid_candidates:
        return list(range(len(unique_coords))), None, False

    def order_key(path):
        endpoint_score = 0.0
        if preferred_start is not None:
            endpoint_score += haversine_distance_nm(
                unique_coords[path[0]], preferred_start
            )
        if preferred_end is not None:
            endpoint_score += haversine_distance_nm(
                unique_coords[path[-1]], preferred_end
            )
        return (
            _line_path_distance(unique_coords, path),
            endpoint_score,
            path,
        )

    best_order = min(valid_candidates, key=order_key)
    return (
        best_order,
        _line_path_distance(unique_coords, best_order),
        best_order != list(range(len(unique_coords))),
    )


def line_traversal_review(coords):
    """Report suspicious source ordering without mutating source coordinates."""

    coords = list(coords)
    if len(coords) < 3:
        return []

    issues = []
    duplicate_indices = []
    for i, coord in enumerate(coords):
        for j in range(i):
            if coords[j] == coord and i - j > 1:
                duplicate_indices.append([j, i])
    if duplicate_indices:
        issues.append(
            {
                "kind": "REPEATED_NON_ADJACENT_VERTEX",
                "vertex_pairs": duplicate_indices,
            }
        )

    crossing_segments = _line_crossing_segments(coords)
    if crossing_segments:
        issues.append(
            {
                "kind": "NON_ADJACENT_SEGMENT_CROSSING",
                "segment_pairs": crossing_segments,
            }
        )

    leg_distances = [
        haversine_distance_nm(start, end)
        for start, end in zip(coords, coords[1:])
    ]
    nearest_distances = []
    for i, coord in enumerate(coords):
        other_distances = [
            haversine_distance_nm(coord, other)
            for j, other in enumerate(coords)
            if i != j
        ]
        nearest_distances.append(min(other_distances))
    nearest_sorted = sorted(nearest_distances)
    nearest_median = nearest_sorted[len(nearest_sorted) // 2]
    jump_limit_nm = max(250.0, nearest_median * 2.5)
    suspicious_jumps = [
        {
            "segment": i,
            "distance_nm": round(distance, 2),
            "review_limit_nm": round(jump_limit_nm, 2),
        }
        for i, distance in enumerate(leg_distances)
        if distance > jump_limit_nm
    ]
    if suspicious_jumps:
        issues.append(
            {
                "kind": "SUSPICIOUS_LONG_LEG",
                "legs": suspicious_jumps,
                "nearest_vertex_median_nm": round(nearest_median, 2),
            }
        )

    return issues


def sort_area_vertices(coords):
    c_lat, c_lon = centroid(coords)
    return sorted(coords, key=lambda p: math.atan2(p[0] - c_lat, p[1] - c_lon))


def detect_style(block):
    upper = block.upper()
    if any(
        x in upper
        for x in [
            "WRECK",
            "SANK",
            "SUNK",
            "AGROUND",
            "DERELICT",
            "OBSTRUCTION",
            "SUBMERGED WELLHEAD",
            "SUBMERGED OBJECT",
            "UNMARKED SUBMERGED WELLHEAD",
            "ICEBERG",
            "ICEBERGS",
        ]
    ):
        return 3
    if any(
        x in upper
        for x in ["FPSO", "FSO", "MODU", "RIG", "PLATFORM", "DRILLSHIP", "DRILL"]
    ):
        return 5
    return 2


def detect_color(block):
    upper = block.upper()

    if detect_security_incident(block):
        return "CHRED"
    if any(
        x in upper
        for x in [
            "SEA ICE LIMIT",
            "SEA ICE",
            "ICE LIMIT",
        ]
    ):
        return "NINFO"

    if any(
        x in upper
        for x in [
            "SEISMIC SURVEY",
            "SURVEY OPERATIONS",
            "ROUTE SURVEY",
        ]
    ):
        return "NINFO"
    if "MINING/AMPLING/EXPLORATION VESSELS" in upper:
        return "RESBL"
    if any(
        x in upper
        for x in [
            "WAR RISK AREA",
            "MINE DANGER",
            "FIRING PRACTICE",
            "FIRING",
            "WRECK",
            "SANK",
            "SUNK",
            "AGROUND",
            "DERELICT",
            "DANGER",
            "PROHIBITED",
            "EXCLUSION",
            "OBSTRUCTION",
            "SUBMERGED WELLHEAD",
            "SUBMERGED OBJECT",
            "UNMARKED SUBMERGED WELLHEAD",
            "NAVAL OPERATION",
            "NAVAL OPERATIONS",
            "NAVAL EXERCISE",
            "NAVAL EXERCISES",
            "MILITARY OPERATION",
            "MILITARY EXERCISE",
            "MILITARY EXERCISES",
            "WAR GAME",
            "WAR GAMES",
            "FIRING EXERCISE",
            "GUNNERY",
            "MINE CLEARANCE",
            "MINE SWEEPING",
            "AMMUNITION DUMP",
            "AMMUNITION DUMPING",
            "MILITARY MANOEUVRE",
            "MILITARY MANOEUVRES",
            "NAVAL DRILL",
            "MILITARY DRILL",
            "WARSHIP",
            "NAVAL ACTIVITY",
            "MILITARY ACTIVITY",
            "DEFENCE OPERATION",
            "HAZARDOUS OPERATIONS",
            "DRIFTING HAZARDS",
            "ADRIFT",
            "DRIFTING",
            "ROCKET LAUNCHING",
            "ICEBERG",
            "ICEBERGS",
        ]
    ):
        return "CHRED"
    if "LAUNCH OF" in upper and "ANCHORAGE LINES" in upper:
        return "RESBL"
    if any(
        x in upper
        for x in ["FPSO", "FSO", "MODU", "RIG", "PLATFORM", "DRILL", "DRILLSHIP"]
    ):
        return "RESBL"
    return "NINFO"


RECOMMENDED_ROUTE_RE = re.compile(r"\bRECOMMENDED\s+ROUTE\b", re.IGNORECASE)


def get_line_presentation(block, *semantic_text, base_color=None):
    """Return the confirmed Furuno presentation for a line semantic."""
    text = " ".join(str(value or "") for value in semantic_text)
    if RECOMMENDED_ROUTE_RE.search(text):
        return {"color": "NINFO", "lineType": 1}
    return {
        "color": base_color if base_color is not None else detect_color(block),
        "lineType": 2,
    }


def detect_check_danger(block):
    upper = block.upper()
    if detect_security_incident(block):
        return 1
    if any(
        x in upper
        for x in [
            "WAR RISK AREA",
            "MINE DANGER",
            "FIRING PRACTICE",
            "FIRING",
            "NAVAL OPERATIONS",
            "HAZARDOUS OPERATIONS",
            "DRIFTING HAZARDS",
            "ADRIFT",
            "DRIFTING",
            "ROCKET LAUNCHING",
            "ICEBERG",
            "ICEBERGS",
            "SUBMERGED WELLHEAD",
            "SUBMERGED OBJECT",
            "UNMARKED SUBMERGED WELLHEAD",
            "WRECK",
            "SANK",
            "SUNK",
            "AGROUND",
            "DERELICT",
            "DANGER",
            "PROHIBITED",
            "EXCLUSION",
            "OBSTRUCTION",
        ]
    ):
        return 1
    return 0


def parse_bounding_box(block):
    pat = re.compile(
        r"(\d{1,3})[- ]+([\d.]+)\s*([NS])\s+TO\s+(\d{1,3})[- ]+([\d.]+)\s*([NS])\s+AND\s+(\d{1,3})[- ]+([\d.]+)\s*([EW])\s+TO\s+(\d{1,3})[- ]+([\d.]+)\s*([EW])",
        flags=re.IGNORECASE,
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

    if any(
        x in upper
        for x in [
            "DERELICT",
            "WRECK",
            "SUNKEN",
            "SUNK",
            "OBSTRUCTION",
            "ICEBERG",
            "ICEBERGS",
            "SUBMERGED WELLHEAD",
            "SUBMERGED OBJECT",
            "UNMARKED SUBMERGED WELLHEAD",
        ]
    ):
        return 3
    if detect_security_incident(block):
        debug("Security incident detected")
        return STYLE_SECURITY

    if any(
        x in upper
        for x in [
            "LIGHT",
            "SPECIAL MARK",
            "SPECIAL-MARK",
            "MOORING",
            "MOORING BUOY",
            "MOORING BUOYS",
        ]
    ) or BUOY_TEXT_RE.search(upper):
        return 2
    return detect_style(block)


def is_multi_point_navarea(block):
    upper = block.upper()
    depth_report_pattern = re.compile(
        r"\bDEPTHS?\b[\s\S]{0,120}\bREPORTED\b",
        re.IGNORECASE,
    )
    triggers = [
        "MOBILE OFFSHORE DRILLING UNITS",
        "LIGHTS UNLIT",
        "LIGHT UNLIT",
        "MOORINGS DEPLOYED",
        "OCEAN BOTTOM MOORINGS",
        "REMOTE COMMUNICATION FACILITIES",
        "MESSAGING SERVICES UNAVAILABLE",
        "REMOVAL OF SUBMERGED LINES",
        "CHANNEL MARKING BUOY",
    ]
    if (
        any(x in upper for x in triggers)
        or depth_report_pattern.search(upper)
        or re.search(rf"\b{BUOY_WORD}\s+REMOVED\b", upper)
    ):
        return True

    platform_count = len(re.findall(r"\bPLATAFORMA\b", upper))
    coordinate_count = len(extract_coordinates(block))
    return platform_count >= 2 and coordinate_count >= 2


def is_buoy_group(text):
    return re.search(rf"\b{BUOY_WORD}\s+GROUP\b", text, re.IGNORECASE) is not None


def detect_arc_area(block):
    """
    ÐÐ¿ÑÐµÐ´ÐµÐ»ÑÐµÑ, ÑÐ²Ð»ÑÐµÑÑÑ Ð»Ð¸ ÑÐ¾Ð¾Ð±ÑÐµÐ½Ð¸Ðµ ARC-DEFINED AREA.

    ÐÑÐµÑ:
      ARC OF XX NM RADIUS
      JOINING POINT X AND Y

    ÐÐ¾Ð·Ð²ÑÐ°ÑÐ°ÐµÑ ÑÐ»Ð¾Ð²Ð°ÑÑ Ñ ÐºÐ»ÑÑÐ°Ð¼Ð¸:
        center, start, end, named_points, radius_nm

    ÐÑÐ»Ð¸ ÑÑÑÑÐºÑÑÑÐ° Ð½Ðµ Ð½Ð°Ð¹Ð´ÐµÐ½Ð°:
        return None
    """
    arc_phrase = re.search(
        r"ARC\s+OF\s+(\d+(?:\.\d+)?)\s*NM\s+RADIUS", block, re.IGNORECASE
    )
    joining_phrase = re.search(
        r"JOINING\s+POINT\s+([A-Z])\s+AND\s+([A-Z])", block, re.IGNORECASE
    )

    if not arc_phrase or not joining_phrase:
        return None

    start_letter = joining_phrase.group(1).upper()
    end_letter = joining_phrase.group(2).upper()

    named_points = {}
    for m in re.finditer(r"\(([A-Z])\)\s*([^()]*)", block, re.IGNORECASE):
        letter = m.group(1).upper()
        coords = extract_coordinates(m.group(2))
        if coords:
            named_points[letter] = coords[0]

    if start_letter not in named_points or end_letter not in named_points:
        return None

    start = named_points[start_letter]
    end = named_points[end_letter]

    center = None
    for letter, coord in named_points.items():
        if letter != start_letter and letter != end_letter:
            center = coord
            break

    if center is None:
        return None

    radius_nm = haversine_distance_nm(center, start)

    return {
        "center": center,
        "start": start,
        "end": end,
        "named_points": named_points,
        "radius_nm": radius_nm,
    }


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
        "REMOTE COMMUNICATION FACILITIES",
        "FACILITIES",
        "SERVICES UNRELIABLE",
    ]
    return any(t in upper for t in targets)


def detect_security_incident(text):
    """
    ÐÐ¿ÑÐµÐ´ÐµÐ»ÑÐµÑ, Ð¾ÑÐ½Ð¾ÑÐ¸ÑÑÑ Ð»Ð¸ ÑÐ¾Ð¾Ð±ÑÐµÐ½Ð¸Ðµ Ðº security incident.
    """
    upper = text.upper()
    return any(keyword in upper for keyword in SECURITY_KEYWORDS)


def parse_structured_sections(block):
    # A decimal coordinate such as ``38.21 S`` is not a numbered section.
    # Require whitespace after the section delimiter so wrapped coordinates
    # cannot split a section and silently lose its preceding positions.
    section_marker = r"(?:^|\n)\s*\d+\.(?=\s|$)\s*"
    if not re.search(section_marker, block):
        return None

    parts = re.split(r"\n\s*(\d+)\.(?=\s|$)\s*", block)
    sections = []
    for i in range(1, len(parts), 2):
        num = parts[i]
        text = parts[i + 1].strip()
        if not text:
            continue

        lines = text.split("\n")
        title = lines[0].strip()
        # The complete section is the relevant object context. Coordinate
        # vertices are removed only by the XML description sanitizer; keeping
        # the rest here preserves status, caution, and post-coordinate prose.
        description = " ".join(text.split()).strip() or title

        sections.append(
            {
                "number": num,
                "text": text,
                "title": title,
                "description": description,
            }
        )
    if DEBUG:
        for sec in sections:
            print(f"DEBUG: Detected section {sec['number']}: {sec['title']}")

    if not sections:
        return None

    objects = []

    for sec in sections:
        coords = extract_coordinates(sec["text"])
        if not coords or len(coords) < 2:
            continue

        desc = sec.get("description", sec.get("title", "")).strip()
        upper_text = sec["text"].upper()

        is_boundary_line = BOUNDARY_LINE_PATTERN.search(upper_text) is not None

        is_area = (
            not is_boundary_line and has_area_pattern(sec["text"]) and len(coords) >= 3
        )

        if is_area:
            area_coords = normalize_area_vertices(coords)
            objects.append(
                {
                    "type": "area",
                    "coords": area_coords,
                    "description": desc,
                    "name": None,
                }
            )
        else:
            objects.append(
                {
                    "type": "line",
                    "coords": coords,
                    "description": desc,
                    "name": None,
                }
            )

    return objects if objects else None


# -------------------- RIGLIST EXTRACTION --------------------
RIGLIST_COORD_PATTERN = re.compile(
    r"\d{1,3}\s*-\s*[\d.]+\s*[NS]\s+\d{1,3}\s*-\s*[\d.]+\s*[EW]",
    re.I,
)
RIGLIST_ENTRY_MARKER_PATTERN = re.compile(
    r"(?m)^\s*(?:\d+|[A-Z]{1,4})\.\s+"
)


def _riglist_body(block):
    marker = re.search(
        r"\b(?:RIGLIST|RIG\s+LIST|MODU\s+LIST|"
        r"MOBILE\s+OFFSHORE\s+DRILLING\s+UNITS)\b",
        block,
        re.I,
    )
    if not marker:
        return block

    body = block[marker.end() :]
    stop = re.search(
        r"(?im)(?:^|\n)\s*(?:NOTES\b|DISCLAIMER\b|"
        r"CANCEL\b|NNNN\b|-{10,})",
        body,
    )
    if stop:
        body = body[: stop.start()]

    # Some source feeds place the next numbered warning section directly
    # after the final rig entry, without a newline.  Keep the rig name but
    # remove that following operational text from the entry body.
    first_coord = RIGLIST_COORD_PATTERN.search(body)
    if first_coord:
        prefix = body[: first_coord.start()]
        coordinate_body = body[first_coord.start() :]
        coordinate_body = re.split(
            r"(?i)\s+(?:\d+\.\s+)?(?:4NM\s+EXCLUSION\b|"
            r"UNTIL\s+FURTHER\b|CANCEL\s+NAVAREA\b|"
            r"VESSELS\s+TO\s+KEEP\b|TO\s+REPORT\s+A\s+MOBILE\s+"
            r"OFFSHORE\s+DRILLING\s+UNIT\b)",
            coordinate_body,
            maxsplit=1,
        )[0]
        body = prefix + coordinate_body
    return body


def _trim_riglist_entry(entry):
    entry = entry.strip()
    entry = re.sub(r"^\s*(?:\d+|[A-Z]{1,4})\.\s+", "", entry)

    # Coordinate-first lists can contain a geographic section heading
    # between the rig name and the next coordinate.
    entry = re.split(
        r"(?im)\n\s*(?=[A-Z][A-Z ]{2,}:)",
        entry,
        maxsplit=1,
    )[0]
    entry = re.split(
        r"(?i)\s+(?:\d+\.\s+)?(?:4NM\s+EXCLUSION\b|"
        r"UNTIL\s+FURTHER\b|CANCEL\s+NAVAREA\b|"
        r"VESSELS\s+TO\s+KEEP\b|TO\s+REPORT\s+A\s+MOBILE\s+"
        r"OFFSHORE\s+DRILLING\s+UNIT\b|NOTES\b|DISCLAIMER\b|NNNN\b)",
        entry,
        maxsplit=1,
    )[0]
    return entry.strip()


def extract_riglist_entries(block):
    upper = block.upper()
    if not any(
        x in upper
        for x in ["RIGLIST", "RIG LIST", "MODU LIST", "MOBILE OFFSHORE DRILLING UNITS"]
    ):
        return None

    body = _riglist_body(block)

    # Prefer explicit entry markers.  This path handles both the normalized
    # numbered form and raw A./B./... lists, while preserving the text
    # between a coordinate and the next coordinate.
    marked_entries = [
        _trim_riglist_entry(entry)
        for entry in RIGLIST_ENTRY_MARKER_PATTERN.split(body)
        if entry.strip()
    ]
    marked_entries = [
        entry
        for entry in marked_entries
        if len(RIGLIST_COORD_PATTERN.findall(entry)) == 1
    ]
    if marked_entries and len(marked_entries) == len(
        RIGLIST_COORD_PATTERN.findall(body)
    ):
        return marked_entries

    # Coordinate-first lists (for example NAVAREA I and XIX) have no
    # per-entry marker.  Keep newlines during segmentation so the next
    # entry's number or name cannot be absorbed into the current name.
    matches = list(RIGLIST_COORD_PATTERN.finditer(body))
    if not matches:
        return [body.strip()] if body.strip() else []

    entries = []
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        entry = _trim_riglist_entry(body[match.start() : end])
        if entry and len(RIGLIST_COORD_PATTERN.findall(entry)) == 1:
            entries.append(entry)

    return entries


def process_riglist_entry(entry_text, label_text, container, message):
    matches = list(RIGLIST_COORD_PATTERN.finditer(entry_text))
    if not matches:
        return
    m = matches[0]
    coord_text = m.group(0)
    coords_found = extract_coordinates(coord_text)
    if not coords_found:
        return

    before = entry_text[: m.start()].strip()
    rig_name = re.sub(r"^\d+\.\s*", "", before)
    if not rig_name:
        after = entry_text[m.end() :].strip()
        rig_name = after
    if not rig_name:
        rig_name = "RIG"
    rig_name = re.sub(r"^[\s\-–—]+", "", rig_name).strip()

    obj = {
        "style": 5,
        "color": "RESBL",
        "checkDanger": 0,
        "text": label_text,
        "description": compose_description(entry_text),
        "coord": coords_found[0],
    }
    container["labels"].append(obj)
    message["labels"].append(obj.copy())


# -------------------- COMPLEXITY FRAMEWORK --------------------
def count_objects(msg):
    return (
        len(msg.get("areas", []))
        + len(msg.get("lines", []))
        + len(msg.get("circles", []))
        + len(msg.get("labels", []))
    )


def vertices_in_line(line):
    return len(line.get("coords", []))


def vertices_in_area(area):
    return len(area.get("coords", []))


def vertices_in_circle(circle):
    return 1


def vertices_in_label(label):
    return 0


def total_vertices_in_message(msg):
    total = 0
    for area in msg.get("areas", []):
        total += vertices_in_area(area)
    for line in msg.get("lines", []):
        total += vertices_in_line(line)
    for circle in msg.get("circles", []):
        total += vertices_in_circle(circle)
    return total


def classify_geometry_risk(vertices):
    if vertices < RISK_LOW_MAX:
        return "LOW"
    elif vertices < RISK_MEDIUM_MAX:
        return "MEDIUM"
    elif vertices < RISK_HIGH_MAX:
        return "HIGH"
    else:
        return "EXTREME"


def analyze_message_complexity(msg):
    areas = msg.get("areas", [])
    lines = msg.get("lines", [])
    circles = msg.get("circles", [])
    labels = msg.get("labels", [])

    area_count = len(areas)
    line_count = len(lines)
    circle_count = len(circles)
    label_count = len(labels)
    obj_count = area_count + line_count + circle_count + label_count

    total_vertices = 0
    max_area_vertices = 0
    max_line_vertices = 0

    for area in areas:
        v = vertices_in_area(area)
        total_vertices += v
        if v > max_area_vertices:
            max_area_vertices = v

    for line in lines:
        v = vertices_in_line(line)
        total_vertices += v
        if v > max_line_vertices:
            max_line_vertices = v

    for circle in circles:
        total_vertices += 1

    risk = classify_geometry_risk(total_vertices)

    return {
        "object_count": obj_count,
        "area_count": area_count,
        "line_count": line_count,
        "circle_count": circle_count,
        "label_count": label_count,
        "total_vertices": total_vertices,
        "max_area_vertices": max_area_vertices,
        "max_line_vertices": max_line_vertices,
        "risk": risk,
    }


def analyze_part_complexity(part_messages):
    total_objects = 0
    total_vertices = 0
    area_count = 0
    line_count = 0
    circle_count = 0
    label_count = 0

    for msg in part_messages:
        total_objects += count_objects(msg)
        total_vertices += total_vertices_in_message(msg)
        area_count += len(msg.get("areas", []))
        line_count += len(msg.get("lines", []))
        circle_count += len(msg.get("circles", []))
        label_count += len(msg.get("labels", []))

    risk = classify_geometry_risk(total_vertices)

    return {
        "message_count": len(part_messages),
        "total_objects": total_objects,
        "total_vertices": total_vertices,
        "area_count": area_count,
        "line_count": line_count,
        "circle_count": circle_count,
        "label_count": label_count,
        "risk": risk,
    }


def analyze_container_complexity(container):
    total_messages = len(container.get("messages", []))
    total_objects = 0
    total_vertices = 0
    area_count = 0
    line_count = 0
    circle_count = 0
    label_count = 0

    for msg in container.get("messages", []):
        total_objects += count_objects(msg)
        total_vertices += total_vertices_in_message(msg)
        area_count += len(msg.get("areas", []))
        line_count += len(msg.get("lines", []))
        circle_count += len(msg.get("circles", []))
        label_count += len(msg.get("labels", []))

    risk = classify_geometry_risk(total_vertices)

    return {
        "message_count": total_messages,
        "total_objects": total_objects,
        "total_vertices": total_vertices,
        "area_count": area_count,
        "line_count": line_count,
        "circle_count": circle_count,
        "label_count": label_count,
        "risk": risk,
    }


def print_complexity_report(msg):
    stats = analyze_message_complexity(msg)
    print(f"  Objects: {stats['object_count']}")
    print(f"  Vertices: {stats['total_vertices']}")
    print(f"  Risk: {stats['risk']}")
    print(f"  Areas: {stats['area_count']}")
    print(f"  Lines: {stats['line_count']}")
    print(f"  Circles: {stats['circle_count']}")
    print(f"  Labels: {stats['label_count']}")
    print(f"  Max Area Vertices: {stats['max_area_vertices']}")
    print(f"  Max Line Vertices: {stats['max_line_vertices']}")


def check_geometry_warnings(msg):
    stats = analyze_message_complexity(msg)
    msg_id = msg.get("id", "unknown")
    if MAX_VERTICES_PER_OBJECT is not None:
        if stats["max_area_vertices"] > MAX_VERTICES_PER_OBJECT:
            print(
                f"WARNING: Message {msg_id} has area with {stats['max_area_vertices']} vertices "
                f"(limit: {MAX_VERTICES_PER_OBJECT})"
            )
        if stats["max_line_vertices"] > MAX_VERTICES_PER_OBJECT:
            print(
                f"WARNING: Message {msg_id} has line with {stats['max_line_vertices']} vertices "
                f"(limit: {MAX_VERTICES_PER_OBJECT})"
            )
    if MAX_VERTICES_PER_MESSAGE is not None:
        if stats["total_vertices"] > MAX_VERTICES_PER_MESSAGE:
            print(
                f"WARNING: Message {msg_id} total vertices {stats['total_vertices']} "
                f"exceeds limit {MAX_VERTICES_PER_MESSAGE}"
            )


# -------------------- FACTORIES --------------------
def create_container(nav_id):
    return {"areas": [], "lines": [], "circles": [], "labels": [], "messages": []}


def create_message(msg_id, metadata=None):
    return {
        "id": msg_id,
        "areas": [],
        "lines": [],
        "circles": [],
        "labels": [],
        "metadata": metadata or {},
        "geometry_audit": [],
    }


def create_area(name, description, coords, color, check_danger):
    return {
        "name": name,
        "description": description,
        "coords": coords,
        "color": color,
        "checkDanger": check_danger,
    }


def create_line(name, description, coords, color, check_danger, line_type=2):
    return {
        "name": name,
        "description": description,
        "coords": coords,
        "color": color,
        "checkDanger": check_danger,
        "lineType": line_type,
    }


def create_circle(name, description, coord, range_val, color, check_danger):
    return {
        "name": name,
        "description": description,
        "coord": coord,
        "range": range_val,
        "color": color,
        "checkDanger": check_danger,
    }


def create_label(style, color, check_danger, text, description, coord):
    return {
        "style": style,
        "color": color,
        "checkDanger": check_danger,
        "text": text,
        "description": description,
        "coord": coord,
    }


# -------------------- OBJECT INSERTION HELPERS --------------------
def _area_validation_vertices(coords):
    """Return the open ring used by the geometry validator."""
    if len(coords) >= 2 and coords[0] == coords[-1]:
        return coords[:-1]
    return list(coords)


def _area_reference_fallback(area_obj, raw_coords, container, message):
    """Keep failed Area coordinates as unconnected review/reference points."""
    reference_coords = list(dict.fromkeys(_area_validation_vertices(raw_coords)))
    description = (
        f"{area_obj.get('description', '')}\n"
        "AREA GEOMETRY REQUIRES REVIEW; SOURCE VERTEX REFERENCE ONLY."
    ).strip()
    for coord in reference_coords:
        add_label(
            create_label(
                style=2,
                color=area_obj.get("color", "NINFO"),
                check_danger=area_obj.get("checkDanger", 0),
                text=area_obj.get("name", message.get("id", "AREA REVIEW")),
                description=description,
                coord=coord,
            ),
            container,
            message,
        )


def add_area(area_obj, container, message):
    coords = normalize_area_vertices(area_obj.get("coords", []))
    area_obj["coords"] = coords
    raw_coords = list(coords)

    validation_code = None
    repair_method = None
    validation_coords = _area_validation_vertices(coords)
    source_unique_vertices = set(validation_coords)
    if len(set(validation_coords)) < 3:
        validation_code = "GEOMETRY_TOO_FEW_VERTICES"
    else:
        if has_self_intersection(validation_coords):
            # Sort only genuine Areas and only after the published/source order
            # has failed validation.  The source order remains in raw_coords.
            candidate_input = list(dict.fromkeys(validation_coords))
            fixed_coords = normalize_area_vertices(
                ensure_clockwise(sort_area_vertices(candidate_input))
            )
            fixed_validation_coords = _area_validation_vertices(fixed_coords)
            candidate_unique_vertices = set(fixed_validation_coords)
            if (
                len(candidate_unique_vertices) >= 3
                and len(fixed_validation_coords) == len(candidate_unique_vertices)
                and candidate_unique_vertices == source_unique_vertices
                and not has_self_intersection(fixed_validation_coords)
            ):
                area_obj["coords"] = fixed_coords
                coords = fixed_coords
                validation_coords = fixed_validation_coords
                repair_method = "centroid_angle"
            else:
                validation_code = "GEOMETRY_SELF_INTERSECTION"

    if validation_code:
        diagnostics = message.setdefault("diagnostics", [])
        diagnostic = {
            "code": validation_code,
            "object_type": "area",
            "message_id": message.get("id", "unknown"),
            "fallback": "REFERENCE_POINTS",
            "source_vertex_count": len(source_unique_vertices),
        }
        diagnostics.append(diagnostic)
        message["geometry_rejected"] = True
        _area_reference_fallback(area_obj, raw_coords, container, message)
        message.setdefault("geometry_audit", []).append(
            {
                "event": "area_geometry_review_fallback",
                "object_type": "area",
                "message_id": message.get("id", "unknown"),
                "reason": validation_code,
                "raw_coords": raw_coords,
                "reference_vertex_count": len(source_unique_vertices),
            }
        )
        return False

    if repair_method:
        area_obj["geometry_repaired"] = True
        area_obj["repair_method"] = repair_method
        area_obj["raw_coords"] = raw_coords
        diagnostics = message.setdefault("diagnostics", [])
        diagnostics.append(
            {
                "code": "GEOMETRY_ORDER_REPAIRED",
                "object_type": "area",
                "message_id": message.get("id", "unknown"),
                "method": repair_method,
                "source_vertex_count": len(validation_coords),
                "output_vertex_count": len(
                    coords[:-1] if coords and coords[0] == coords[-1] else coords
                ),
                "raw_coords": raw_coords,
            }
        )
        message.setdefault("geometry_audit", []).append(
            {
                "event": "area_geometry_repaired",
                "object_type": "area",
                "message_id": message.get("id", "unknown"),
                "method": repair_method,
                "raw_coords": raw_coords,
                "repaired_coords": list(coords),
            }
        )

    container["areas"].append(area_obj)
    message["areas"].append(area_obj.copy())
    return True


def add_line(line_obj, container, message):
    coords = list(line_obj.get("coords", []))
    review_issues = line_traversal_review(coords)
    raw_coords = list(coords)
    unique_coords, _ = _line_unique_coords(raw_coords)
    components = _line_track_components(raw_coords)
    if len(components) > 1:
        emitted_lines = []
        reference_coords = []
        for component_index, component in enumerate(components, start=1):
            component_set = set(component)
            component_coords = [
                coord
                for index, coord in enumerate(unique_coords)
                if index in component_set
            ]
            component_source_order = [
                index
                for index, coord in enumerate(raw_coords)
                if unique_coords.index(coord) in component_set
            ]
            if len(component_coords) < 2:
                reference_coords.extend(component_coords)
                continue

            component_raw_coords = [
                coord
                for coord in raw_coords
                if unique_coords.index(coord) in component_set
            ]
            candidate_order, _, _ = _line_best_order(
                component_coords,
                preferred_start=component_raw_coords[0],
                preferred_end=component_raw_coords[-1],
            )
            selected_coords = [
                component_coords[index] for index in candidate_order
            ]
            part = line_obj.copy()
            part["name"] = f"{line_obj.get('name', 'LINE')} TRACK {component_index}"
            part["coords"] = selected_coords
            part["raw_coords"] = raw_coords
            part["source_vertex_indices"] = component_source_order
            part["geometry_order_status"] = "TRACK_SPLIT"
            part["geometry_order_review"] = {
                "source_order_preserved": False,
                "component_index": component_index,
                "component_count": len(components),
            }
            container["lines"].append(part)
            message["lines"].append(part.copy())
            emitted_lines.append(part)

        if reference_coords:
            _line_reference_fallback(
                line_obj, reference_coords, container, message
            )
        message.setdefault("diagnostics", []).append(
            {
                "code": "GEOMETRY_LINE_TRACKS_SPLIT",
                "object_type": "line",
                "message_id": message.get("id", "unknown"),
                "source_order_preserved": False,
                "raw_coords": raw_coords,
                "component_count": len(components),
                "component_sizes": [
                    len(component) for component in components
                ],
                "issues": review_issues,
            }
        )
        message.setdefault("geometry_audit", []).append(
            {
                "event": "line_tracks_split",
                "object_type": "line",
                "message_id": message.get("id", "unknown"),
                "raw_coords": raw_coords,
                "component_count": len(components),
                "component_sizes": [
                    len(component) for component in components
                ],
                "source_order_preserved": False,
            }
        )
        return emitted_lines

    if not review_issues:
        container["lines"].append(line_obj)
        message["lines"].append(line_obj.copy())
        return [line_obj]

    candidate_order, candidate_distance, candidate_changed = _line_best_order(
        unique_coords,
        preferred_start=raw_coords[0],
        preferred_end=raw_coords[-1],
    )
    raw_order = []
    seen = set()
    for coord in raw_coords:
        index = unique_coords.index(coord)
        if index not in seen:
            raw_order.append(index)
            seen.add(index)
    raw_distance = _line_path_distance(unique_coords, raw_order)
    candidate_coords = [unique_coords[index] for index in candidate_order]
    can_repair = (
        candidate_distance is not None
        and not _line_crossing_segments(candidate_coords)
        and candidate_distance < raw_distance * 0.98
    )

    if can_repair and candidate_changed:
        line_obj["coords"] = candidate_coords
        line_obj["raw_coords"] = raw_coords
        line_obj["geometry_order_status"] = "REPAIRED"
        line_obj["geometry_order_review"] = {
            "source_order_preserved": False,
            "repair_method": "shortest_non_crossing_path",
            "raw_distance_nm": round(raw_distance, 2),
            "selected_distance_nm": round(candidate_distance, 2),
        }
        message.setdefault("diagnostics", []).append(
            {
                "code": "GEOMETRY_LINE_ORDER_REPAIRED",
                "object_type": "line",
                "message_id": message.get("id", "unknown"),
                "source_order_preserved": False,
                "repair_method": "shortest_non_crossing_path",
                "raw_coords": raw_coords,
                "selected_coords": candidate_coords,
                "raw_distance_nm": round(raw_distance, 2),
                "selected_distance_nm": round(candidate_distance, 2),
                "issues": review_issues,
            }
        )
        message.setdefault("geometry_audit", []).append(
            {
                "event": "line_geometry_order_repaired",
                "object_type": "line",
                "message_id": message.get("id", "unknown"),
                "raw_coords": raw_coords,
                "selected_coords": candidate_coords,
                "repair_method": "shortest_non_crossing_path",
                "source_order_preserved": False,
            }
        )
    else:
        line_obj["raw_coords"] = raw_coords
        line_obj["geometry_order_status"] = "REVIEW_REQUIRED"
        line_obj["geometry_order_review"] = {
            "issues": review_issues,
            "source_order_preserved": True,
        }
        hard_review_kinds = {
            "REPEATED_NON_ADJACENT_VERTEX",
            "NON_ADJACENT_SEGMENT_CROSSING",
        }
        if any(
            issue["kind"] in hard_review_kinds for issue in review_issues
        ):
            _line_reference_fallback(
                line_obj, raw_coords, container, message
            )
        message.setdefault("diagnostics", []).append(
            {
                "code": "GEOMETRY_LINE_ORDER_REVIEW",
                "object_type": "line",
                "message_id": message.get("id", "unknown"),
                "source_order_preserved": True,
                "raw_coords": raw_coords,
                "issues": review_issues,
            }
        )
        message.setdefault("geometry_audit", []).append(
            {
                "event": "line_geometry_order_review",
                "object_type": "line",
                "message_id": message.get("id", "unknown"),
                "raw_coords": raw_coords,
                "issues": review_issues,
                "source_order_preserved": True,
            }
        )
    container["lines"].append(line_obj)
    message["lines"].append(line_obj.copy())
    return [line_obj]


def add_circle(circle_obj, container, message):
    container["circles"].append(circle_obj)
    message["circles"].append(circle_obj.copy())


def add_label(label_obj, container, message):
    container["labels"].append(label_obj)
    message["labels"].append(label_obj.copy())


def _line_reference_fallback(line_obj, coords, container, message):
    description = (
        f"{line_obj.get('description', '')}\n"
        "LINE GEOMETRY REVIEW; SOURCE VERTEX REFERENCE ONLY."
    ).strip()
    for coord in dict.fromkeys(coords):
        add_label(
            create_label(
                style=2,
                color=line_obj.get("color", "NINFO"),
                check_danger=line_obj.get("checkDanger", 0),
                text=line_obj.get("name", message.get("id", "LINE REVIEW")),
                description=description,
                coord=coord,
            ),
            container,
            message,
        )


def add_line_labels(line_objects, container, message):
    """Add one chart label for every emitted Line component."""

    for line_obj in line_objects:
        coords = line_obj.get("coords", [])
        if not coords:
            continue
        mid = len(coords) // 2
        add_label(
            create_label(
                style=6,
                color=line_obj.get("color", "NINFO"),
                check_danger=line_obj.get("checkDanger", 0),
                text=line_obj.get("name", message.get("id", "LINE")),
                description=line_obj.get("description", ""),
                coord=coords[mid],
            ),
            container,
            message,
        )


# -------------------- CONTEXT & PARTITIONING --------------------
def build_partition_context(source_navarea, partition_type, partition_id, sub_block):
    return {
        "source_navarea": source_navarea,
        "partition_type": partition_type,
        "partition_id": partition_id,
        "context_id": f"{source_navarea}|{partition_type}|{partition_id}",
    }


def _partition_parent_context(block, marker_start):
    parent = re.sub(r"-{5,}", " ", block[:marker_start])
    return re.sub(r"\s+", " ", parent).strip()


def _partition_description_length(block):
    """Return the source Description length used for semantic partitioning."""

    normalized = re.sub(r"-{5,}", " ", str(block or ""))
    return len(re.sub(r"\s+", " ", normalized).strip())


def _partition_footer_context(block):
    """Return a shared cancellation footer without treating it as a section."""

    footer = re.search(
        r"(?im)^\s*(?:\d+(?:\.\d+)*(?:\.-?|-)?\s*)?"
        r"CANCEL(?:LED|S|LATION)?"
        r"(?:\s+(?:(?:THIS\s+)?(?:MSG|MESSAGE|WARNING)|NAVAREA))?\b",
        block,
    )
    if not footer:
        return ""
    text = re.sub(r"-{5,}", " ", block[footer.start() :])
    text = re.sub(r"\bNNNN\b", " ", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def partition_riglist(block, navarea_name):
    upper = block.upper()
    if not any(
        x in upper
        for x in ["RIGLIST", "RIG LIST", "MODU LIST", "MOBILE OFFSHORE DRILLING UNITS"]
    ):
        return None

    entries = extract_riglist_entries(block)
    if not entries:
        return None
    riglist_marker = re.search(
        r"\b(?:RIGLIST|RIG\s+LIST|MODU\s+LIST|"
        r"MOBILE\s+OFFSHORE\s+DRILLING\s+UNITS)\b",
        block,
        re.IGNORECASE,
    )
    parent_context = ""
    if riglist_marker:
        body_after_marker = block[riglist_marker.end() :]
        first_coord = RIGLIST_COORD_PATTERN.search(body_after_marker)
        if first_coord:
            prefix = body_after_marker[: first_coord.start()]
            entry_markers = list(
                re.finditer(
                    r"(?m)^\s*(?:\d+|[A-Z]{1,4})\.\s+",
                    prefix,
                )
            )
            if entry_markers:
                first_entry_start = (
                    riglist_marker.end() + entry_markers[-1].start()
                )
            else:
                first_entry_start = riglist_marker.end() + first_coord.start()
            parent_context = _partition_parent_context(
                block, first_entry_start
            )

    if DEBUG:
        print(f"\nð NAVAREA {navarea_name} Partition Type: RIGLIST")
        print(f"   Entries: {len(entries)}")

    parts = []
    for idx, entry in enumerate(entries, start=1):
        meta = build_partition_context(
            source_navarea=navarea_name,
            partition_type="RIGLIST",
            partition_id=str(idx),
            sub_block=entry,
        )
        if parent_context:
            meta["parent_context"] = parent_context
        footer_context = _partition_footer_context(block)
        if footer_context:
            meta["footer_context"] = footer_context
        parts.append((entry, meta))
    return parts


def partition_navarea_block(block, navarea_name):
    if DEBUG:
        print(f"DEBUG: partition input block starts with: {block[:100]}")
    # RIGLIST
    rig_parts = partition_riglist(block, navarea_name)
    if rig_parts:
        return rig_parts

    # Keep short messages intact. Section partitioning is only a semantic
    # response to the Legacy Description ceiling; otherwise it changes the
    # source Description and can manufacture duplicated or partial context.
    if _partition_description_length(block) <= LEGACY_MAX_DESC:
        meta = build_partition_context(
            source_navarea=navarea_name,
            partition_type="NONE",
            partition_id="0",
            sub_block=block,
        )
        return [(block, meta)]

    # Explicit route segmentation
    route_markers = list(
        re.finditer(
            r"(?im)^\s*ROUTE\s+No\.\s*([0-9]+(?:\.[0-9]+)*)\s*:",
            block,
        )
    )
    if len(route_markers) > 1:
        footer_context = _partition_footer_context(block)
        footer_marker = re.search(
            r"(?im)^\s*(?:\d+(?:\.\d+)*(?:\.-?|-)?\s*)?"
            r"CANCEL(?:LED|S|LATION)?"
            r"(?:\s+(?:(?:THIS\s+)?(?:MSG|MESSAGE|WARNING)|NAVAREA))?\b",
            block,
        )
        footer_start = footer_marker.start() if footer_marker else len(block)
        numbered_markers = list(
            re.finditer(
                r"(?:^|\n)\s*(\d+(?:\.\d+)*)(?:\.-?|-)\s+",
                block,
            )
        )
        parts = []
        for i, marker in enumerate(route_markers):
            next_route = (
                route_markers[i + 1].start()
                if i + 1 < len(route_markers)
                else None
            )
            following_numbered = next(
                (
                    numbered.start()
                    for numbered in numbered_markers
                    if numbered.start() > marker.start()
                ),
                None,
            )
            end_candidates = [
                position
                for position in (next_route, following_numbered)
                if position is not None
            ]
            end = min(end_candidates + [footer_start])
            sub_block = block[marker.start() : end].strip()
            if sub_block:
                meta = build_partition_context(
                    source_navarea=navarea_name,
                    partition_type="ROUTE",
                    partition_id=f"ROUTE_{marker.group(1)}",
                    sub_block=sub_block,
                )
                if footer_context:
                    meta["footer_context"] = footer_context
                parts.append((sub_block, meta))

        first_remaining_numbered = next(
            (
                numbered
                for numbered in numbered_markers
                if numbered.start() > route_markers[-1].start()
            ),
            None,
        )
        if first_remaining_numbered:
            for i, marker in enumerate(
                numbered_markers[
                    numbered_markers.index(first_remaining_numbered) :
                ]
            ):
                start = marker.start()
                end = (
                    numbered_markers[
                        numbered_markers.index(first_remaining_numbered) + i + 1
                    ].start()
                    if numbered_markers.index(first_remaining_numbered) + i + 1
                    < len(numbered_markers)
                    else footer_start
                )
                sub_block = block[start:end].strip()
                if sub_block:
                    meta = build_partition_context(
                        source_navarea=navarea_name,
                        partition_type="SECTION_NUMBER",
                        partition_id=marker.group(1),
                        sub_block=sub_block,
                    )
                    if footer_context:
                        meta["footer_context"] = footer_context
                    parts.append((sub_block, meta))
        return parts

    # Numbered sections
    measurement_marker_re = re.compile(
        r"^\s*\d+\.\d+\s*(?:M|METERS?|METRES?)\b",
        re.IGNORECASE,
    )
    distance_marker_re = re.compile(
        r"^\s*\d+\.\d+\s*(?:NM\.?|MILES?|MI\.?)\b",
        re.IGNORECASE,
    )
    if re.search(
        r"(?im)^\s*\d+\.\d+\s*(?:M|METERS?|METRES?)\b",
        block,
    ):
        block = re.sub(
            r"\n(?=\s*\d+\.\d+\s*(?:M|METERS?|METRES?)\b)",
            " ",
            block,
            flags=re.IGNORECASE,
        )
    if re.search(
        r"(?im)^\s*\d+\.\d+\s*(?:NM\.?|MILES?|MI\.?)\b",
        block,
    ):
        block = re.sub(
            r"\n(?=\s*\d+\.\d+\s*(?:NM\.?|MILES?|MI\.?)\b)",
            " ",
            block,
            flags=re.IGNORECASE,
        )

    numbered_markers = list(
        re.finditer(
            r"(?:^|\n)\s*(\d+(?:\.\d+)*)(?:\.-?|-)\s+",
            block,
        )
    )

    def marker_line(marker):
        marker_line_start = marker.start()
        if block[marker_line_start : marker_line_start + 1] == "\n":
            marker_line_start += 1
        line_start = block.rfind("\n", 0, marker_line_start) + 1
        line_end = block.find("\n", marker_line_start)
        if line_end == -1:
            line_end = len(block)
        return block[line_start:line_end]

    def is_cancellation_section(marker, next_marker):
        section_start = marker.start()
        if block[section_start : section_start + 1] == "\n":
            section_start += 1
        section_end = next_marker.start() if next_marker else len(block)
        section_text = block[section_start:section_end].lstrip()
        section_text = re.sub(
            r"^\d+(?:\.\d+)*(?:\.-?|-)?\s*",
            "",
            section_text,
            count=1,
        )
        return bool(
            re.match(
                r"CANCEL(?:S|LED|LATION)?"
                r"(?:\s+(?:(?:THIS\s+)?(?:MSG|MESSAGE|WARNING)|NAVAREA))?\b",
                section_text,
                re.IGNORECASE,
            )
        )

    coordinate_fragment_re = re.compile(
        r"\s*\d{1,3}\.\d+\s*[NSEW]\s*", re.IGNORECASE
    )
    numbered_markers = [
        marker
        for marker in numbered_markers
        if not measurement_marker_re.match(
            block[
                marker.start() + (1 if block[marker.start() : marker.start() + 1] == "\n" else 0) :
                block.find(
                    "\n",
                    marker.start() + (1 if block[marker.start() : marker.start() + 1] == "\n" else 0),
                )
                if block.find(
                    "\n",
                    marker.start() + (1 if block[marker.start() : marker.start() + 1] == "\n" else 0),
                )
                >= 0
                else len(block)
            ]
        )
        or distance_marker_re.match(
            block[
                marker.start() + (1 if block[marker.start() : marker.start() + 1] == "\n" else 0) :
                block.find(
                    "\n",
                    marker.start() + (1 if block[marker.start() : marker.start() + 1] == "\n" else 0),
                )
                if block.find(
                    "\n",
                    marker.start() + (1 if block[marker.start() : marker.start() + 1] == "\n" else 0),
                )
                >= 0
                else len(block)
            ]
        )
        and not coordinate_fragment_re.fullmatch(marker_line(marker))
    ]
    # A cancellation notice may itself be numbered and can contain a
    # NAVAREA-looking reference.  It is message metadata, not a child
    # section; keeping it in the parent block avoids dropping the preceding
    # geometry when the source has multiple cancellation items.
    section_markers = [
        marker
        for index, marker in enumerate(numbered_markers)
        if not is_cancellation_section(
            marker,
            numbered_markers[index + 1]
            if index + 1 < len(numbered_markers)
            else None,
        )
    ]
    footer_markers = [
        marker
        for index, marker in enumerate(numbered_markers)
        if is_cancellation_section(
            marker,
            numbered_markers[index + 1]
            if index + 1 < len(numbered_markers)
            else None,
        )
    ]
    unnumbered_footer = re.search(
        r"(?im)^\s*(?:\d+(?:\.\d+)*(?:\.-?|-)?\s*)?"
        r"CANCEL(?:LED|S|LATION)?"
        r"(?:\s+(?:(?:THIS\s+)?(?:MSG|MESSAGE|WARNING)|NAVAREA))?\b",
        block,
    )
    footer_starts = [marker.start() for marker in footer_markers]
    if unnumbered_footer:
        footer_starts.append(unnumbered_footer.start())
    footer_start = min(footer_starts) if footer_starts else len(block)

    def normalize_footer(text):
        text = re.sub(r"-{5,}", " ", text)
        text = re.sub(r"\bNNNN\b", " ", text, flags=re.IGNORECASE)
        return re.sub(r"\s+", " ", text).strip()

    footer_context = normalize_footer(block[footer_start:]) if footer_starts else ""

    if section_markers and (
        len(section_markers) > 1
        or len(section_markers) < len(numbered_markers)
    ):
        semantic_context = None
        preamble = block[: section_markers[0].start()]
        parent_context = _partition_parent_context(
            block, section_markers[0].start()
        )
        for line in preamble.splitlines():
            if re.search(r"AREA\s+TEMPORARILY\s+DANGEROUS", line, re.IGNORECASE):
                semantic_context = line.strip()
                break

        parts = []
        for i, m in enumerate(section_markers):
            start = m.start()
            end = (
                section_markers[i + 1].start()
                if i + 1 < len(section_markers)
                else footer_start
            )
            sub_block = block[start:end].strip()
            if sub_block:
                meta = build_partition_context(
                    source_navarea=navarea_name,
                    partition_type="SECTION_NUMBER",
                    partition_id=m.group(1),
                    sub_block=sub_block,
                )
                if i == 0 and semantic_context:
                    meta["semantic_context"] = semantic_context
                if parent_context:
                    meta["parent_context"] = parent_context
                if footer_context:
                    meta["footer_context"] = footer_context
                parts.append((sub_block, meta))
        return parts

    # Lettered sections
    letter_markers = list(re.finditer(r"(?:^|\n)\s*([A-Z]{1,4})\.\s+", block))
    if len(letter_markers) > 1:
        letter_footer = re.search(
            r"(?im)^\s*(?:\d+(?:\.\d+)*(?:\.-?|-)?\s*)?"
            r"CANCEL(?:S|LED|LATION)?"
            r"(?:\s+(?:(?:THIS\s+)?(?:MSG|MESSAGE|WARNING)|NAVAREA))?\b",
            block,
        )
        letter_footer_start = (
            letter_footer.start() if letter_footer else len(block)
        )
        letter_footer_context = (
            normalize_footer(block[letter_footer_start:])
            if letter_footer
            else ""
        )
        parts = []
        parent_context = _partition_parent_context(
            block, letter_markers[0].start()
        )
        for i, m in enumerate(letter_markers):
            start = m.start()
            end = (
                letter_markers[i + 1].start()
                if i + 1 < len(letter_markers)
                else letter_footer_start
            )
            sub_block = block[start:end].strip()
            if sub_block:
                meta = build_partition_context(
                    source_navarea=navarea_name,
                    partition_type="LETTER",
                    partition_id=m.group(1),
                    sub_block=sub_block,
                )
                if parent_context:
                    meta["parent_context"] = parent_context
                if letter_footer_context:
                    meta["footer_context"] = letter_footer_context
                parts.append((sub_block, meta))
        return parts

    # None
    meta = build_partition_context(
        source_navarea=navarea_name,
        partition_type="NONE",
        partition_id="0",
        sub_block=block,
    )
    return [(block, meta)]


def predict_complexity(block):
    coords = extract_coordinates(block)
    coord_count = len(coords)
    section_count = len(re.findall(r"(?:^|\n)\s*\d+\.\s+", block)) + len(
        re.findall(r"(?:^|\n)\s*[A-Z]\.\s+", block)
    )
    rig_entries = extract_riglist_entries(block)
    rig_count = len(rig_entries) if rig_entries else 0

    if coord_count > 500 or section_count > 10 or rig_count > 50:
        print("WARNING: Potential Monster Message Detected")
        print(f"  Coordinates: {coord_count}")
        print(f"  Sections: {section_count}")
        if rig_count:
            print(f"  RIGLIST Entries: {rig_count}")


# -------------------- PROCESSING CONTEXT --------------------
def build_processing_context(block, navarea_name, label_text=None, metadata=None):
    semantic_context = (metadata or {}).get("semantic_context")
    parent_context = (metadata or {}).get("parent_context")
    footer_context = (metadata or {}).get("footer_context")
    partition_type = (metadata or {}).get("partition_type")
    contextual_block = (
        f"{semantic_context}\n{block}" if semantic_context else block
    )
    upper = contextual_block.upper()
    coords = extract_coordinates(block)
    clean_block = re.sub(r"-{5,}", " ", block)
    clean_block = re.sub(r"\s+", " ", clean_block)
    if semantic_context:
        clean_block = f"{semantic_context}\n{clean_block}"
    clean_description = clean_block.replace('"', "'").strip()
    description = escape(clean_description)
    if label_text is None:
        label_text = build_navarea_label(navarea_name)
    is_riglist = metadata and metadata.get("partition_type") == "RIGLIST"
    is_letter_partition = metadata and metadata.get("partition_type") == "LETTER"
    preserve_full_description = (
        partition_type in (None, "NONE")
        and _partition_description_length(clean_block) <= LEGACY_MAX_DESC
    )
    return {
        "block": block,
        "upper": upper,
        "coords": coords,
        "description": description,
        "parent_context": parent_context,
        "footer_context": footer_context,
        "navarea_name": navarea_name,
        "label_text": label_text,
        "metadata": metadata,
        "is_riglist": is_riglist,
        "is_letter_partition": is_letter_partition,
        "preserve_full_description": preserve_full_description,
    }


def _description_plain_text(value):
    """Return a normalized, unescaped description fragment."""

    return sanitize_xml_attribute(unescape(str(value or ""))).strip()


def compose_description(*parts):
    """Build one stable description from ordered, non-empty fragments.

    Object descriptions are assembled before XML serialization. Keeping this
    operation centralized prevents specialized handlers from replacing notice
    context with a coordinate-only local fragment.
    """

    normalized = []
    for part in parts:
        text = _description_plain_text(part)
        if not text:
            continue
        if any(text == existing or text in existing for existing in normalized):
            continue
        normalized = [
            existing for existing in normalized if existing not in text
        ]
        normalized.append(text)
    return escape("\n".join(normalized).strip())


def compose_partition_description(header, section, footer):
    """Compose a long-message Description as header, object section, footer."""

    normalized = []
    for part in (header, section, footer):
        text = _description_plain_text(part)
        if not text or text in normalized:
            continue
        normalized.append(text)
    return escape("\n".join(normalized).strip())


def build_list_entry_description(ctx, entry_text, heading_pattern):
    """Keep one list entry and its shared preamble, without other entries."""

    block = ctx.get("block", "")
    heading = re.search(heading_pattern, block, flags=re.IGNORECASE)
    if heading:
        shared_context = block[: heading.end()]
    else:
        shared_context = ctx.get("description", "")
    # Keep the local entry first for the ECDIS selection view, then append the
    # shared context so the object remains immediately identifiable while the
    # operation/header is still available in the same field.
    return compose_description(entry_text, shared_context)


def build_sublabel_description(ctx, sublabel_text):
    """Keep a lettered local fragment with its enclosing preamble."""

    block = ctx.get("block", "")
    first_marker = re.search(
        r"(?:^|\n)\s*(?:\([A-Z]\)|[A-Z]\.)\s*", block
    )
    if first_marker:
        shared_context = block[: first_marker.start()]
    else:
        shared_context = ctx.get("description", "")
    return compose_description(sublabel_text, shared_context)


# -------------------- SUBLABEL HELPER --------------------
def emit_sublabel_points(
    sublabels, ctx, container, message, style, color, check_danger
):
    for s in sublabels:
        if not s["coords"]:
            continue
        desc = build_sublabel_description(ctx, s["text"])
        for coord in s["coords"]:
            label_obj = create_label(
                style=style,
                color=color,
                check_danger=check_danger,
                text=ctx["label_text"],
                description=desc,
                coord=coord,
            )
            add_label(label_obj, container, message)


# -------------------- GEOMETRY KEYWORDS --------------------
GEOMETRY_KEYWORDS = [
    "ROUTE",
    "ROUTE NO",
    "ROUTE CENTERLINE",
    "CENTERLINE COORDINATES",
    "TRACKLINE",
    "TRACK",
    "DOUBLE TRACK",
    "TRACK WIDTH",
    "CHANNEL",
    "CHANNEL WIDTH",
    "TRANSIT ROUTE",
    "WAITING AREA",
    "HOLDING AREA",
    "ANCHORAGE AREA",
    "TEMPORARY STAY AREA",
    "PIPELINE",
    "CABLE",
    "JOINING",
]
BOUNDARY_LINE_PATTERN = re.compile(
    r"\b(?:TO\s+)?(?:NORTH(?:ERN)?|SOUTH(?:ERN)?|EAST(?:ERN)?|WEST(?:ERN)?)\s+OF\s+LINE\b",
    re.IGNORECASE,
)
SECURITY_KEYWORDS = [
    "SECURITY INCIDENT",
    "ARMED ROBBERY",
    "PIRACY",
    "PIRATES",
    "ATTACK",
    "ATTEMPTED ATTACK",
    "ROBBERY",
    "UNAUTHORIZED BOARDING",
    "HIJACKING",
    "SUSPICIOUS CRAFT",
    "SUSPICIOUS APPROACH",
    "ANTI PIRACY",
    "PIRATE",
    "SUSPECTED PIRATE",
    "SECURITY THREAT",
]
AREA_PATTERNS = [
    "AREA BOUND BY",
    "AREA BOUNDED BY",
    "AREAS BOUND BY",
    "AREAS BOUNDED BY",
    "AREA BOUNDED WITHIN",
]
AREA_BOUNDARY_MARKER_RE = re.compile(
    r"\b(?:IN\s+)?(?:DANGER\s+)?AREAS?\s+"
    r"(?:BOUND(?:ED)?\s+BY|DELIMITED\s+BY)\b",
    re.IGNORECASE,
)
IMPLICIT_BOUNDED_AREA_RE = re.compile(
    r"\b(?:"
    r"(?:IN\s+THE\s+)?FOLLOWING\s+BOUNDED\s+AREAS?"
    r"|(?:ROUTES?|LINES?)\s+BOUNDED\s+BY"
    r"|BOUNDED\s+BY"
    r")\b",
    re.IGNORECASE,
)

LINE_PATTERNS = [
    "ALONG TRACKLINE",
    "TRACKLINE JOINING",
]


def has_area_pattern(text):
    normalized = re.sub(r"\s+", " ", text.upper())
    return any(pattern in normalized for pattern in AREA_PATTERNS) or bool(
        IMPLICIT_BOUNDED_AREA_RE.search(normalized)
    )


def has_line_pattern(text):
    upper = text.upper()
    return any(pattern in upper for pattern in LINE_PATTERNS)


IMPLICIT_OPERATION_AREA_PROFILES = (
    {
        "name": "OPERATIONAL_VICINITY_WITH_CLEARANCE",
        "context_pattern": re.compile(
            r"\b(?:IN\s+)?VICINITY\s+OF\b", re.IGNORECASE
        ),
        "activity_terms": (
            "HYDROGRAPHIC SURVEY",
            "SEISMIC SURVEY",
            "SURVEY OPERATIONS",
            "DREDGING OPERATIONS",
            "DREDGING",
            "CONSTRUCTION OPERATIONS",
        ),
        "clearance_terms": (
            "WIDE BERTH REQUESTED",
            "WIDE BERTH",
            "KEEP CLEAR",
        ),
        "minimum_coordinates": 3,
    },
)
IMPLICIT_OPERATION_AREA_LINE_RE = re.compile(
    r"\b(?:TRACKLINES?|TRACK\s+LINES?|ROUTES?|PIPELINES?|CABLES?|"
    r"JOINING|CHANNEL\s+WIDTH|BETWEEN\s+THE\s+POINTS)\b",
    re.IGNORECASE,
)


def infer_implicit_operational_area(block):
    """Return area evidence for one undivided operational coordinate list."""
    if has_area_pattern(block):
        return None
    if IMPLICIT_OPERATION_AREA_LINE_RE.search(block):
        return None
    if re.search(
        r"(?m)^\s*(?:\([A-Z]\)|[A-Z]\.)\s+", block
    ):
        return None

    coords = extract_coordinates(block)
    if not coords:
        return None

    for profile in IMPLICIT_OPERATION_AREA_PROFILES:
        if len(coords) < profile["minimum_coordinates"]:
            continue
        if not profile["context_pattern"].search(block):
            continue
        if not any(term in block.upper() for term in profile["activity_terms"]):
            continue
        if not any(term in block.upper() for term in profile["clearance_terms"]):
            continue
        return {
            "profile": profile["name"],
            "coords": coords,
        }
    return None


# -------------------- MIXED GEOMETRY HANDLER --------------------
def extract_mixed_geometry_sections(block):
    sections = []
    subsection_split = re.search(r"\n\d+\.\d+\.\d+\.", block)
    if subsection_split:
        main_part = block[: subsection_split.start()]
        subsection_part = block[subsection_split.start() :]
    else:
        main_part = block
        subsection_part = ""

    route_pattern = re.compile(
        r"(ROUTE\s+NO\.\s+[\d.]+)\s*:\s*([\s\S]*?)(?=ROUTE\s+NO\.\s+[\d.]+|\d+\.\d+\.\d+\.|\Z)",
        re.IGNORECASE,
    )
    for match in route_pattern.finditer(main_part):
        header = match.group(1).strip()
        text = match.group(2).strip()
        if text:
            sections.append((header, text))

    if subsection_part:
        subsection_pattern = re.compile(
            r"(?:^|\n)(\d+\.\d+\.\d+)\.\s+([^\n:]+)(?:\s*:\s*|\n)\s*([\s\S]*?)(?=\n\d+\.\d+\.\d+\.|\n\d+\.|\Z)"
        )
        for match in subsection_pattern.finditer(subsection_part):
            subsection_num = match.group(1)
            header_text = match.group(2).strip()
            full_header = f"{subsection_num}. {header_text}"
            text = match.group(3).strip()
            if text:
                sections.append((full_header, text))

    return sections


def handle_mixed_geometry_package(ctx, container, message):
    debug("PROCESS: handle_mixed_geometry_package")
    if ctx["is_riglist"]:
        return False

    block = ctx["block"]
    upper = ctx["upper"]
    label_text = ctx["label_text"]

    has_routes = "ROUTE NO" in upper
    has_areas = any(
        x in upper for x in ["WAITING AREA", "HOLDING AREA", "TEMPORARY STAY AREA"]
    )

    if not (has_routes and has_areas):
        return False

    sections = extract_mixed_geometry_sections(block)

    if not sections:
        return False

    first_section = re.search(
        r"(?im)^\s*(?:ROUTE\s+NO\.\s*[\d.]+|"
        r"\d+\.\d+\.\d+\.)",
        block,
    )
    shared_context = block[: first_section.start()] if first_section else ""

    any_processed = False
    for header, text in sections:
        coords = extract_coordinates(text)
        if not coords:
            continue

        upper_header = header.upper()
        section_description = compose_description(
            f"{header} {text}", shared_context
        )

        if "ROUTE NO" in upper_header:
            if len(coords) >= 2:
                obj_name = f"{label_text} {header}"
                line_obj = create_line(
                    name=obj_name,
                    description=section_description,
                    coords=coords,
                    color=detect_color(ctx["block"]),
                    check_danger=detect_check_danger(ctx["block"]),
                )
                add_line_labels(
                    add_line(line_obj, container, message),
                    container,
                    message,
                )
                any_processed = True

        elif (
            "SOUTHERN WAITING AREA" in upper_header
            or "TEMPORARY STAY AREA" in upper_header
        ):
            if len(coords) >= 3:
                obj_name = f"{label_text} SOUTHERN WAITING AREA"
                area_coords = normalize_area_vertices(coords)
                area_obj = create_area(
                    name=obj_name,
                    description=section_description,
                    coords=area_coords,
                    color=detect_color(ctx["block"]),
                    check_danger=detect_check_danger(ctx["block"]),
                )
                add_area(area_obj, container, message)
                any_processed = True

        elif "WAITING AREA NORTH AR 354" in upper_header:
            if len(coords) >= 3:
                obj_name = f"{label_text} WAITING AREA NORTH AR 354"
                area_coords = normalize_area_vertices(coords)
                area_obj = create_area(
                    name=obj_name,
                    description=section_description,
                    coords=area_coords,
                    color=detect_color(ctx["block"]),
                    check_danger=detect_check_danger(ctx["block"]),
                )
                add_area(area_obj, container, message)
                any_processed = True

        elif "FROM" in upper_header or "OF" in upper_header:
            if len(coords) >= 2:
                if "CHORNOMORSK" in upper_header:
                    obj_name = f"{label_text} CHORNOMORSK CHANNEL"
                elif "ODESSA" in upper_header:
                    obj_name = f"{label_text} ODESSA CHANNEL"
                elif "PIVDENNYI" in upper_header:
                    obj_name = f"{label_text} PIVDENNYI CHANNEL"
                else:
                    obj_name = f"{label_text} {header}"

                line_obj = create_line(
                    name=obj_name,
                    description=section_description,
                    coords=coords,
                    color=detect_color(ctx["block"]),
                    check_danger=detect_check_danger(ctx["block"]),
                )
                add_line_labels(
                    add_line(line_obj, container, message),
                    container,
                    message,
                )
                any_processed = True

    return any_processed


# -------------------- PROCESSING HANDLERS --------------------
ICEBERG_ENTRY_RE = re.compile(
    r"(?P<id>[A-Z]\d{2}[A-Z]?)\s+"
    r"(?P<lat>\d{2}-\d{2}(?:\.\d+)?[NS])\s+"
    r"(?P<lon>\d{2,3}-\d{2}(?:\.\d+)?[EW])",
    re.IGNORECASE,
)


def _normalize_ice_coordinate_spacing(section_text: str) -> str:
    """
    Убирает пробелы вокруг дефиса только тогда, когда
    с обеих сторон находятся цифры.

    Примеры:
        052- 49W  -> 052-49W
        051- 48W  -> 051-48W
        52- 23S   -> 52-23S
    """
    return re.sub(r"(?<=\d)\s*-\s*(?=\d)", "-", section_text)


def handle_ice_report(ctx, container, message):
    debug("ICE SECTION DETECTED")

    if ctx["is_riglist"]:
        return False

    upper = ctx["upper"]
    block = ctx["block"]
    label = ctx["label_text"]

    if "SEA ICE LIMIT" in upper:
        coords = extract_coordinates(block)
        if len(coords) >= 2:
            line_obj = create_line(
                name=label,
                description="SEA ICE LIMIT",
                coords=coords,
                color="NINFO",
                check_danger=0,
            )
            add_line_labels(
                add_line(line_obj, container, message),
                container,
                message,
            )
        return True

    if "ICEBERGS GREATER" in upper:
        normalized_block = _normalize_ice_coordinate_spacing(block)

        matches = list(ICEBERG_ENTRY_RE.finditer(normalized_block))

        debug(f"ICE MATCH COUNT = {len(matches)}")

        for match in matches:
            debug(
                "ICEBERG "
                f"{match.group('id')} "
                f"{match.group('lat')} "
                f"{match.group('lon')}"
            )

        if not matches:
            return False

        for m in matches:
            name = m.group("id")
            lat_raw = m.group("lat")
            lon_raw = m.group("lon")

            coords = extract_coordinates(f"{lat_raw} {lon_raw}")
            if not coords:
                continue

            lat, lon = coords[0]
            desc = f"{name} {lat_raw} {lon_raw}"

            label_obj = create_label(
                style=3,
                color="CHRED",
                check_danger=1,
                text=label,
                description=desc,
                coord=(lat, lon),
            )
            add_label(label_obj, container, message)

        return True

    if "ICEBERGS AREA" in upper:
        for zone in re.finditer(r"\b([A-Z])-", block):
            letter = zone.group(1)
            if letter not in ("A", "B", "C"):
                continue

            start = zone.start()
            next_zone = re.search(r"\b[A-Z]-", block[start + 1 :])
            if next_zone:
                end = start + 1 + next_zone.start()
            else:
                end = len(block)

            zone_text = block[start:end]
            coords = extract_coordinates(zone_text)

            if len(coords) >= 3:
                coords = normalize_area_vertices(coords)
                area_obj = create_area(
                    name=f"{label} ({letter})",
                    description=f"ICEBERGS AREA {letter}",
                    coords=coords,
                    color="CHRED",
                    check_danger=1,
                )
                add_area(area_obj, container, message)

        return True

    return False


def handle_structured_sections(ctx, container, message):
    debug("PROCESS: handle_structured_sections")
    if ctx["is_riglist"]:
        return False

    # Explicit or implicit bounded-area evidence must be resolved by
    # handle_area, even when the notice also contains numbered sections.
    # Otherwise a route-shaped section can consume the coordinates first.
    if has_area_pattern(ctx["block"]) and len(ctx["coords"]) >= 3:
        return False

    # P0: ÑÐ³ÑÑÐ¿Ð¿Ð¸ÑÐ¾Ð²Ð°Ð½Ð½ÑÐµ Ð¿Ð¾Ð»Ð¸Ð³Ð¾Ð½Ñ (A), (B) Ð´Ð¾Ð»Ð¶Ð½Ñ Ð¾Ð±ÑÐ°Ð±Ð°ÑÑÐ²Ð°ÑÑÑÑ handle_area()
    regex_match = re.search(r"\(([A-Z])\)\s*\d", ctx["block"]) is not None
    area_context = (
        "AREAS BOUND BY" in ctx["upper"]
        or "AREA BOUND BY" in ctx["upper"]
        or "DANGER AREA" in ctx["upper"]
    )

    if regex_match and area_context:
        return False

    if not re.search(r"(?:^|\n)\s*\d+\.\s*", ctx["block"]):
        return False

    structured_objects = parse_structured_sections(ctx["block"])
    if not structured_objects:
        return False

    for obj in structured_objects:
        classification_text = obj["description"]
        object_color = detect_color(classification_text)
        object_check_danger = detect_check_danger(classification_text)
        if obj["type"] == "area":
            area_obj = create_area(
                name=ctx["label_text"],
                description=obj["description"],
                coords=obj["coords"],
                color=object_color,
                check_danger=object_check_danger,
            )
            add_area(area_obj, container, message)
        elif obj["type"] == "line":
            line_obj = create_line(
                name=ctx["label_text"],
                description=obj["description"],
                coords=obj["coords"],
                color=object_color,
                check_danger=object_check_danger,
            )
            add_line_labels(
                add_line(line_obj, container, message),
                container,
                message,
            )
        elif obj["type"] == "label":
            label_obj = create_label(
                style=6,
                color=object_color,
                check_danger=object_check_danger,
                text=ctx["label_text"],
                description=obj["description"],
                coord=obj["coord"],
            )
            add_label(label_obj, container, message)

    return True


def extract_vessel_list_positions(block):
    """Extract one independent point for each named vessel-list entry.

    A lettered vessel list is a collection of reported positions, not a
    route.  Keep each entry's complete source fragment so the vessel name
    and its DP/anchor-spread role remain available in the ECDIS Description.
    """
    list_heading = re.search(
        r"\b(?:MINING\s*/\s*AMPLING\s*/\s*EXPLORATION\s+|"
        r"EXPLORATION\s+)?VESSELS?\s+LIST\b",
        block,
        flags=re.IGNORECASE,
    )
    if not list_heading:
        return []

    list_body = block[list_heading.end() :]
    next_section = re.search(r"(?m)^\s*\d+\.(?=\s|$)\s*", list_body)
    if next_section:
        list_body = list_body[: next_section.start()]

    markers = list(
        re.finditer(
            r"(?m)^\s*(?:\(([A-Z])\)|([A-Z])\.)\s*",
            list_body,
        )
    )
    if len(markers) < 2:
        return []

    entries = []
    for index, marker in enumerate(markers):
        end = (
            markers[index + 1].start()
            if index + 1 < len(markers)
            else len(list_body)
        )
        snippet = list_body[marker.start() : end].strip()
        coords = extract_coordinates(snippet)
        if len(coords) != 1:
            return []
        entries.append(
            {
                "letter": marker.group(1) or marker.group(2),
                "text": " ".join(snippet.split()),
                "coord": coords[0],
            }
        )
    return entries


def handle_vessel_list_points(ctx, container, message):
    """Keep named vessel positions as independent point objects.

    Without explicit ROUTE/TRACKLINE-style wording, connecting reported vessel
    positions would invent navigation geometry.  An explicit geometry phrase
    leaves the notice to the normal geometry handlers.
    """
    debug("PROCESS: handle_vessel_list_points")
    if ctx["is_riglist"]:
        return False

    upper = ctx["upper"]
    if re.search(
        r"\b(?:ROUTE|TRACKLINE|TRACK\s+LINE|CENTERLINE|LINE\s+JOINING|"
        r"PIPELINE|CABLE|CHANNEL)\b|BETWEEN\s+THE\s+POINTS",
        upper,
        flags=re.IGNORECASE,
    ):
        return False

    entries = extract_vessel_list_positions(ctx["block"])
    if not entries:
        return False

    style = get_point_style(ctx["block"])
    color = detect_color(ctx["block"])
    check_danger = detect_check_danger(ctx["block"])
    for entry in entries:
        label_obj = create_label(
            style=style,
            color=color,
            check_danger=check_danger,
            text=ctx["label_text"],
            description=build_list_entry_description(
                ctx,
                entry["text"],
                r"\b(?:MINING\s*/\s*AMPLING\s*/\s*EXPLORATION\s+|"
                r"EXPLORATION\s+)?VESSELS?\s+LIST\b",
            ),
            coord=entry["coord"],
        )
        add_label(label_obj, container, message)
    return True


FACILITY_LIST_MARKER_RE = re.compile(
    r"(?m)^\s*(?:\(([A-Z])\)|([A-Z])\.)\s*"
)
FACILITY_COORDINATE_RE = re.compile(
    r"\d{1,3}[-\s]+[\d.]+\s*[NS]\s*"
    r"(?:/|,|[-\s])+\s*\d{1,3}[-\s]+[\d.]+\s*[EW]",
    re.IGNORECASE,
)


def extract_facility_list_positions(block):
    """Extract one point and local description for each facility entry.

    USCG facility notices use a lettered list, but the facility's status code
    is also parenthesized (for example ``BOSTON (F)``).  Only markers at the
    beginning of a line are list boundaries; parenthetical codes inside an
    entry must remain part of that entry's description.
    """

    heading = re.search(
        r"\b(?:REMOTE\s+)?COMMUNICATION\s+FACILITIES\s*:",
        block,
        flags=re.IGNORECASE,
    )
    if not heading:
        return []

    list_body = block[heading.end() :]
    candidate_markers = list(FACILITY_LIST_MARKER_RE.finditer(list_body))
    if len(candidate_markers) < 2:
        return []

    # A wrapped facility can put its status code on a new line, as in
    # ``(E) NEW ORLEANS`` followed by ``(G) 29-53...``.  The normalizer makes
    # both the list marker and the code look like line-start markers.  Facility
    # list letters are ordered, so retain the next expected letter and leave
    # any other parenthetical token inside the current local fragment.
    markers = []
    expected_letter = None
    for marker in candidate_markers:
        letter = marker.group(1) or marker.group(2)
        if expected_letter is None or letter == expected_letter:
            markers.append(marker)
            expected_letter = chr(ord(letter) + 1)
    if len(markers) < 2:
        return []

    entries = []
    for index, marker in enumerate(markers):
        end = (
            markers[index + 1].start()
            if index + 1 < len(markers)
            else len(list_body)
        )
        snippet = list_body[marker.start() : end].strip()
        coordinate = FACILITY_COORDINATE_RE.search(snippet)
        if not coordinate:
            return []
        coords = extract_coordinates(coordinate.group(0))
        if len(coords) != 1:
            return []

        local_text = snippet[: coordinate.start()]
        local_text = re.sub(r"-{5,}.*$", "", local_text, flags=re.DOTALL)
        local_text = " ".join(local_text.split()).strip()
        if not local_text:
            return []
        entries.append(
            {
                "letter": marker.group(1) or marker.group(2),
                "text": local_text,
                "coord": coords[0],
            }
        )
    return entries


def build_facility_list_description(ctx, entry):
    """Return shared notice context plus one facility's local fragment."""

    block = ctx["block"]
    heading = re.search(
        r"\b(?:REMOTE\s+)?COMMUNICATION\s+FACILITIES\s*:",
        block,
        flags=re.IGNORECASE,
    )
    if heading:
        parent = " ".join(block[: heading.end()].split())
    else:
        parent = sanitize_xml_attribute(ctx.get("description", ""))
    return escape(f"{parent}\n{entry['text']}".strip())


def handle_facility_list_points(ctx, container, message):
    """Preserve shared context and local names in facility-list notices."""

    debug("PROCESS: handle_facility_list_points")
    if ctx["is_riglist"]:
        return False

    entries = extract_facility_list_positions(ctx["block"])
    if not entries:
        return False

    style = get_point_style(ctx["block"])
    color = detect_color(ctx["block"])
    check_danger = detect_check_danger(ctx["block"])
    for entry in entries:
        label_obj = create_label(
            style=style,
            color=color,
            check_danger=check_danger,
            text=ctx["label_text"],
            description=build_facility_list_description(ctx, entry),
            coord=entry["coord"],
        )
        add_label(label_obj, container, message)
    return True


def handle_explicit_line_circle(ctx, container, message):
    """
    RC1 targeted handler for an explicit authorized route plus waiting circle.

    It is deliberately limited to the wording pattern used by
    NAVAREA IX 208/2026 and avoids changing the legacy first-match behavior
    for unrelated messages.
    """
    debug("PROCESS: handle_explicit_line_circle")
    if ctx["is_riglist"]:
        return False

    upper = ctx["upper"]
    if not re.search(
        r"\bROUTES?\s+THAT\s+HAVE\s+BEEN\s+AUTHORIZED\b",
        upper,
        flags=re.IGNORECASE,
    ):
        return False

    route_coords = extract_explicit_route_waypoints(ctx["block"])
    circle_spec = extract_circle_spec(ctx["block"])
    if len(route_coords) < 2 and not circle_spec:
        return False

    if len(route_coords) >= 2:
        line_obj = create_line(
            name=ctx["label_text"],
            description=ctx["description"],
            coords=route_coords,
            color=detect_color(ctx["block"]),
            check_danger=detect_check_danger(ctx["block"]),
        )
        add_line_labels(
            add_line(line_obj, container, message),
            container,
            message,
        )

    if circle_spec:
        circle_obj = create_circle(
            name=ctx["label_text"],
            description=ctx["description"],
            coord=circle_spec["center"],
            range_val=circle_spec["radius"],
            color=detect_color(ctx["block"]),
            check_danger=detect_check_danger(ctx["block"]),
        )
        add_circle(circle_obj, container, message)
    return True


def handle_platform_multipoint(ctx, container, message):
    """Keep explicitly named platform jackets as point objects."""

    debug("PROCESS: handle_platform_multipoint")
    if ctx["is_riglist"]:
        return False
    if "PLATFORM JACKET" not in ctx["upper"] or len(ctx["coords"]) < 2:
        return False

    for coord in ctx["coords"]:
        label_obj = create_label(
            style=5,
            color=detect_color(ctx["block"]),
            check_danger=detect_check_danger(ctx["block"]),
            text=ctx["label_text"],
            description=ctx["description"],
            coord=coord,
        )
        add_label(label_obj, container, message)
    return True


def extract_line_endpoint_package(block):
    """Extract a line plus separately marked endpoint positions."""
    upper = block.upper()
    if not any(
        term in upper for term in ("PIPELINE", "CABLE", "TRACKLINE", "ROUTE")
    ):
        return None
    if not re.search(
        r"\b(?:"
        rf"{BUOY_WORD}|LIGHT{BUOY_WORD}|BEACONS?|TOWERS?|LIGHTS?|"
        r"PLATFORMS?|JACKETS?|AIDS\s+TO\s+NAVIGATION"
        r")\b[\s\S]{0,180}\b(?:DEPLOYED|ESTABLISHED|"
        r"POSITION(?:S)?|MARKED)\b",
        upper,
    ):
        return None

    sublabels = extract_sublabels(block)
    if len(sublabels) < 2 or any(len(item["coords"]) != 1 for item in sublabels):
        return None

    endpoint_items = sublabels[:]
    endpoint_coords = [item["coords"][0] for item in endpoint_items]
    if len(endpoint_coords) != len(set(endpoint_coords)):
        return None
    if endpoint_coords != extract_coordinates(block):
        return None

    return endpoint_items


def handle_line_with_endpoint_objects(ctx, container, message):
    """
    Preserve a real linear object and the independent objects marking it.

    The endpoint coordinates intentionally occur in both XML geometries: they
    are vertices of the line and positions of the endpoint labels.
    """
    debug("PROCESS: handle_line_with_endpoint_objects")
    if ctx["is_riglist"]:
        return False

    endpoint_items = extract_line_endpoint_package(ctx["block"])
    if not endpoint_items:
        return False

    line_presentation = get_line_presentation(
        ctx["block"],
        ctx["label_text"],
        ctx["description"],
        base_color=detect_color(ctx["block"]),
    )
    line_obj = create_line(
        name=ctx["label_text"],
        description=ctx["description"],
        coords=ctx["coords"],
        color=line_presentation["color"],
        check_danger=detect_check_danger(ctx["block"]),
        line_type=line_presentation["lineType"],
    )
    add_line(line_obj, container, message)

    for item in endpoint_items:
        buoy = classify_buoy(ctx["block"])
        if buoy:
            style, color, check_danger = buoy_style_color(
                check_danger=detect_check_danger(item["text"]),
                status=detect_buoy_status(item["text"]),
                subtype=buoy["subtype"],
            )
        else:
            style = get_point_style(ctx["block"])
            color = detect_color(ctx["block"])
            check_danger = detect_check_danger(item["text"])
        add_label(
            create_label(
                style=style,
                color=color,
                check_danger=check_danger,
                text=ctx["label_text"],
                description=build_sublabel_description(ctx, item["text"]),
                coord=item["coords"][0],
            ),
            container,
            message,
        )

    return True


def handle_implicit_operational_area(ctx, container, message):
    """Map a reviewed operational vicinity coordinate list to one Area."""
    debug("PROCESS: handle_implicit_operational_area")
    if ctx["is_riglist"]:
        return False

    evidence = infer_implicit_operational_area(ctx["block"])
    if not evidence:
        return False

    area_coords = normalize_area_vertices(evidence["coords"])
    area_obj = create_area(
        name=ctx["label_text"],
        description=ctx["description"],
        coords=area_coords,
        color=detect_color(ctx["block"]),
        check_danger=detect_check_danger(ctx["block"]),
    )
    area_obj["geometry_evidence"] = evidence["profile"]
    add_area(area_obj, container, message)
    message.setdefault("geometry_audit", []).append(
        {
            "event": "implicit_operational_area_inferred",
            "object_type": "area",
            "message_id": message.get("id", "unknown"),
            "profile": evidence["profile"],
            "source_coords": list(evidence["coords"]),
        }
    )
    return True


def handle_circle(ctx, container, message):
    debug("PROCESS: handle_circle")
    if ctx["is_riglist"]:
        return False

    safety_zone_specs = extract_safety_zone_circle_specs(ctx["block"])
    if safety_zone_specs:
        for spec in safety_zone_specs:
            circle_obj = create_circle(
                name=ctx["label_text"],
                description=ctx["description"],
                coord=spec["center"],
                range_val=spec["radius"],
                color=detect_color(ctx["block"]),
                check_danger=detect_check_danger(ctx["block"]),
            )
            add_circle(circle_obj, container, message)
        return True

    circle_spec = extract_circle_spec(ctx["block"])
    if circle_spec:
        circle_obj = create_circle(
            name=ctx["label_text"],
            description=ctx["description"],
            coord=circle_spec["center"],
            range_val=circle_spec["radius"],
            color=detect_color(ctx["block"]),
            check_danger=detect_check_danger(ctx["block"]),
        )
        add_circle(circle_obj, container, message)
        return True

    circle_match = re.search(r"WITHIN\s+([0-9.]+)\s+(?:NM|MILE|MILES)", ctx["upper"])
    if not circle_match or len(ctx["coords"]) < 1:
        return False
    circle_obj = create_circle(
        name=ctx["label_text"],
        description=ctx["description"],
        coord=ctx["coords"][0],
        range_val=float(circle_match.group(1)),
        color=detect_color(ctx["block"]),
        check_danger=detect_check_danger(ctx["block"]),
    )
    add_circle(circle_obj, container, message)
    return True


def handle_bounding_box(ctx, container, message):
    debug("PROCESS: handle_bounding_box")
    if ctx["is_riglist"]:
        return False
    bb = parse_bounding_box(ctx["block"])
    if not bb:
        return False
    area_obj = create_area(
        name=ctx["label_text"],
        description=ctx["description"],
        coords=bb,
        color=detect_color(ctx["block"]),
        check_danger=detect_check_danger(ctx["block"]),
    )
    add_area(area_obj, container, message)
    return True


def extract_area_group_sections(block):
    INVALID_AREA_NAMES = {
        "BOUND",
        "BOUNDED",
        "OF",
        "DANGER",
        "DANGEROUS",
        "OPERATIONS",
        "OPERATION",
    }

    named_markers = list(
        re.finditer(r"\b(?:DANGER\s+)?AREA\s+([A-Z][A-Z]+)\b", block, re.IGNORECASE)
    )

    if len(named_markers) > 1:
        named_groups = []

        for i, m in enumerate(named_markers):
            zone_name = m.group(1).upper()

            if zone_name in INVALID_AREA_NAMES:
                continue

            start = m.end()
            end = (
                named_markers[i + 1].start()
                if i + 1 < len(named_markers)
                else len(block)
            )
            segment = block[start:end].strip()

            # ÐÐ¾Ð¿Ð¾Ð»Ð½Ð¸ÑÐµÐ»ÑÐ½Ð°Ñ Ð¾ÑÐ¸ÑÑÐºÐ°: ÑÐ±ÑÐ°ÑÑ ÑÐ»ÑÑÐ°Ð¹Ð½ÑÐ¹ ÑÐ²Ð¾ÑÑ ÑÐ»ÐµÐ´ÑÑÑÐµÐ¹ Ð·Ð¾Ð½Ñ
            # (ÐµÑÐ»Ð¸ ÑÑÐ¾-ÑÐ¾ Ð¾ÑÑÐ°Ð»Ð¾ÑÑ Ð¿Ð¾ÑÐ»Ðµ Ð¾Ð±ÑÐµÐ·Ð°Ð½Ð¸Ñ)
            next_marker_re = re.compile(
                r"\b(?:DANGER\s+)?AREA\s+[A-Z][A-Z]+\b", re.IGNORECASE
            )
            split_segments = next_marker_re.split(segment)
            if split_segments:
                segment = split_segments[0].strip()

            coords = extract_coordinates(segment)
            if len(coords) >= 3:
                named_groups.append((zone_name, segment))

        if named_groups:
            debug(f"Named area groups detected: {[g[0] for g in named_groups]}")
            return named_groups

    # ------------------------------------------------------------------
    # Ð¡ÑÐ°ÑÐ°Ñ Ð»Ð¾Ð³Ð¸ÐºÐ° Ð´Ð»Ñ (A)/(B)/A./B.
    # ------------------------------------------------------------------
    context_match = re.search(
        r"(?:AREA|AREAS|DANGER AREA|DANGER AREAS)\s+(?:BOUND BY|BOUNDED BY|DELIMITED BY)",
        block,
        re.IGNORECASE,
    )

    if not context_match:
        return []

    search_block = block[context_match.end() :]

    markers = {}

    for m in re.finditer(
        r"(?:^|\n)\s*(?:\(([A-Z])\)|([A-Z])\.)\s*", search_block, flags=re.MULTILINE
    ):
        letter = m.group(1) or m.group(2)
        markers[m.start()] = letter.upper()

    for m in re.finditer(r"\(([A-Z])\)\s*", search_block):
        markers[m.start()] = m.group(1).upper()

    if not markers:
        boundary_markers = list(AREA_BOUNDARY_MARKER_RE.finditer(block))

        # Some NAVAREA messages repeat a complete, unlabelled boundary
        # clause instead of using (A)/(B) or named AREA sections.  Treat
        # each explicit boundary marker as a structural section.  This must
        # happen before the flat-coordinate fallback in handle_area().
        if len(boundary_markers) > 1:
            repeated_groups = []
            for index, marker in enumerate(boundary_markers, start=1):
                end = (
                    boundary_markers[index].start()
                    if index < len(boundary_markers)
                    else len(block)
                )
                segment = block[marker.end() : end].strip()
                if len(extract_coordinates(segment)) < 3:
                    return []
                repeated_groups.append((str(index), segment))

            debug(
                "Repeated unlabelled area groups detected: "
                f"{len(repeated_groups)}"
            )
            return repeated_groups

        return []

    sorted_markers = sorted(markers.items())

    groups = []
    for i, (pos, letter) in enumerate(sorted_markers):
        end = (
            sorted_markers[i + 1][0]
            if i + 1 < len(sorted_markers)
            else len(search_block)
        )
        segment = search_block[pos:end]

        segment = re.sub(
            r"^\s*(?:\([A-Z]\)|[A-Z]\.)\s*", "", segment, count=1, flags=re.IGNORECASE
        )

        coords = extract_coordinates(segment)

        if len(coords) >= 3:
            groups.append((letter, segment.strip()))

    return groups


def build_group_area_description(ctx, area_id, area_text):
    nav_summary = sanitize_xml_attribute(ctx.get("description", ""))

    is_named = len(area_id) > 1

    # A long multi-area notice must retain the complete source context without
    # cutting coordinates or duplicating every sibling area.  Each emitted
    # object receives the common header, its own AREA section, and the shared
    # cancellation footer.
    if _partition_description_length(ctx.get("block", "")) > LEGACY_MAX_DESC:
        first_area_marker = re.search(
            r"\b(?:DANGER\s+)?AREA\s+[A-Z][A-Z]+\b",
            ctx.get("block", ""),
            flags=re.IGNORECASE,
        )
        header = (
            ctx["block"][: first_area_marker.start()]
            if first_area_marker
            else ctx.get("description", "")
        )
        section = f"AREA {area_id}\n{area_text}"
        footer = _partition_footer_context(ctx.get("block", ""))
        return compose_partition_description(header, section, footer)

    if is_named:
        # ÐÐ±ÑÐµÐ·Ð°ÐµÐ¼ Ð´Ð¾ Ð¿ÐµÑÐ²Ð¾Ð³Ð¾ named area Ð¼Ð°ÑÐºÐµÑÐ°, ÑÑÐ¾Ð±Ñ ÑÐ±ÑÐ°ÑÑ Ð²ÑÐµ ÐºÐ¾Ð¾ÑÐ´Ð¸Ð½Ð°ÑÑ Ð·Ð¾Ð½
        first_named_marker = re.search(
            r"\b(?:DANGER\s+)?AREA\s+[A-Z][A-Z]+\b", nav_summary, re.IGNORECASE
        )
        if first_named_marker:
            nav_summary = nav_summary[: first_named_marker.start()].rstrip()
            # ÑÐ±ÑÐ°ÑÑ Ð²Ð¸ÑÑÑÐ¸Ðµ Ð·Ð°Ð¿ÑÑÑÐµ/Ð¿ÑÐ¾Ð±ÐµÐ»Ñ
            nav_summary = re.sub(r"[,\s]+$", "", nav_summary)

        group_header = f"AREA {area_id}"
    else:
        boundary_match = re.search(
            r"\b(?:IN\s+)?(?:DANGER\s+)?AREAS?\s+(?:BOUND(?:ED)?\s+BY|DELIMITED\s+BY)\b",
            nav_summary,
            re.IGNORECASE,
        )
        if boundary_match:
            nav_summary = nav_summary[: boundary_match.start()].rstrip()

        group_header = f"ZONE {area_id}"

    if not nav_summary:
        nav_summary = sanitize_xml_attribute(ctx.get("navarea_name", ""))

    coords_text = sanitize_xml_attribute(" ".join(area_text.split()))

    MIN_SUMMARY = 120
    separators_len = 2  # Ð´Ð²Ð° Ð¿ÐµÑÐµÐ½Ð¾ÑÐ° ÑÑÑÐ¾ÐºÐ¸

    fixed_len = MIN_SUMMARY + len(group_header) + separators_len

    if fixed_len > LEGACY_MAX_DESC:
        available = max(0, LEGACY_MAX_DESC - len(group_header) - separators_len)
        nav_summary = nav_summary[:available].rstrip()
        coords_text = ""
    else:
        available_for_coords = LEGACY_MAX_DESC - fixed_len

        if len(coords_text) > available_for_coords:
            coords_text = coords_text[:available_for_coords].rstrip()

        max_summary = (
            LEGACY_MAX_DESC - len(group_header) - len(coords_text) - separators_len
        )

        if len(nav_summary) > max_summary:
            nav_summary = nav_summary[:max_summary].rstrip()

    return f"{nav_summary}\n{group_header}\n{coords_text}"


def handle_area(ctx, container, message):
    debug("PROCESS: handle_area")
    if ctx["is_riglist"]:
        return False
    # A channel described as running from one place to another is a line,
    # even when the destination wording contains "WAITING AREA" or
    # "HOLDING AREA".  Let handle_trackline process these local partitions.
    if (
        re.search(r"\bCHANNEL\s+WIDTH\b", ctx["upper"])
        and not re.search(
            r"\b(?:IN\s+)?(?:DANGER\s+)?AREAS?\s+"
            r"(?:BOUND(?:ED)?\s+BY|DELIMITED\s+BY)\b",
            ctx["upper"],
        )
    ):
        return False

    # ------------------------------------------------------------------
    # 1. Grouped Areas / Named Areas
    # ------------------------------------------------------------------
    area_groups = extract_area_group_sections(ctx["block"])

    if len(area_groups) > 1:
        if (
            "LAUNCH OF" in ctx["upper"]
            and "ANCHORAGE LINES" in ctx["upper"]
        ):
            for area_id, area_text in area_groups:
                sub_coords = extract_coordinates(area_text)
                if not sub_coords:
                    continue
                label_obj = create_label(
                    style=2,
                    color=detect_color(ctx["block"]),
                    check_danger=detect_check_danger(ctx["block"]),
                    text=ctx["label_text"],
                    description=build_group_area_description(
                        ctx, area_id, area_text
                    ),
                    coord=sub_coords[0],
                )
                add_label(label_obj, container, message)
            return True

        for area_id, area_text in area_groups:
            sub_coords = extract_coordinates(area_text)

            if len(sub_coords) < 3:
                continue

            print(f"AREA GROUP {area_id} -> {len(sub_coords)} vertices")

            area_coords = normalize_area_vertices(sub_coords)

            area_obj = create_area(
                name=f"{ctx['label_text']} ({area_id})",
                description=build_group_area_description(ctx, area_id, area_text),
                coords=area_coords,
                color=detect_color(ctx["block"]),
                check_danger=detect_check_danger(ctx["block"]),
            )
            add_area(area_obj, container, message)

        return True

    if len(area_groups) == 1:
        area_id, area_text = area_groups[0]
        sub_coords = extract_coordinates(area_text)

        if len(sub_coords) >= 3:
            area_coords = normalize_area_vertices(sub_coords)

            area_obj = create_area(
                name=ctx["label_text"],
                description=build_group_area_description(ctx, area_id, area_text),
                coords=area_coords,
                color=detect_color(ctx["block"]),
                check_danger=detect_check_danger(ctx["block"]),
            )
            add_area(area_obj, container, message)
            return True

    # ------------------------------------------------------------------
    # 1.5. ARC-DEFINED AREA
    # ------------------------------------------------------------------
    arc_params = detect_arc_area(ctx["block"])

    if arc_params:
        center = arc_params["center"]
        start = arc_params["start"]
        end = arc_params["end"]

        arc_points = generate_arc_points(
            center=center,
            start=start,
            end=end,
            steps=24,
            direction="shortest",
        )

        area_coords = [center] + arc_points

        area_coords = normalize_area_vertices(area_coords)

        debug(
            f"ARC area detected:\n"
            f"center={center}\n"
            f"start={start}\n"
            f"end={end}\n"
            f"vertices={len(area_coords)}"
        )

        area_obj = create_area(
            name=ctx["label_text"],
            description=ctx["description"],
            coords=area_coords,
            color=detect_color(ctx["block"]),
            check_danger=detect_check_danger(ctx["block"]),
        )
        add_area(area_obj, container, message)
        return True

    # ------------------------------------------------------------------
    # 2. Waiting / Holding / Anchorage Area shortcut
    # ------------------------------------------------------------------
    if any(
        x in ctx["upper"]
        for x in [
            "WAITING AREA",
            "HOLDING AREA",
            "ANCHORAGE AREA",
            "DESIGNATED ANCHORAGE AREA",
            "TEMPORARY STAY AREA",
            "HAZARD AREA",
        ]
    ):
        if len(ctx["coords"]) >= 3:
            area_coords = normalize_area_vertices(ctx["coords"])
            area_obj = create_area(
                name=ctx["label_text"],
                description=ctx["description"],
                coords=area_coords,
                color=detect_color(ctx["block"]),
                check_danger=detect_check_danger(ctx["block"]),
            )
            add_area(area_obj, container, message)
            return True

    # ------------------------------------------------------------------
    # 3. Single AREA BOUND BY fallback
    # ------------------------------------------------------------------
    repeated_boundary_markers = list(
        AREA_BOUNDARY_MARKER_RE.finditer(ctx["block"])
    )
    if len(repeated_boundary_markers) > 1:
        diagnostics = message.setdefault("diagnostics", [])
        diagnostics.append(
            {
                "code": "GEOMETRY_UNPARSED_AREA_GROUPS",
                "object_type": "area",
                "message_id": message.get("id", "unknown"),
                "boundary_count": len(repeated_boundary_markers),
            }
        )
        message["geometry_rejected"] = True
        return True

    if not has_area_pattern(ctx["block"]) and not (
        "AREA TEMPORARILY DANGEROUS" in ctx["upper"]
        or "HAZARD AREA" in ctx["upper"]
    ):
        return False

    if len(ctx["coords"]) >= 3:
        area_coords = normalize_area_vertices(ctx["coords"])

        area_obj = create_area(
            name=ctx["label_text"],
            description=ctx["description"],
            coords=area_coords,
            color=detect_color(ctx["block"]),
            check_danger=detect_check_danger(ctx["block"]),
        )
        add_area(area_obj, container, message)
        return True

    return False


def handle_trackline(ctx, container, message):
    debug("PROCESS: handle_trackline")
    if ctx["is_riglist"]:
        return False
    # Area patterns have priority over line
    if has_area_pattern(ctx["block"]) and "CHANNEL WIDTH" not in ctx["upper"]:
        return False

    # P2: Ð½Ðµ ÑÐ¾Ð·Ð´Ð°Ð²Ð°ÑÑ Ð»Ð¸Ð½Ð¸Ñ Ð´Ð»Ñ Ð½ÐµÐ·Ð°Ð²Ð¸ÑÐ¸Ð¼ÑÑ Ð±ÑÐµÐ²/ÑÐ¾ÑÐµÑÐ½ÑÑ Ð¾Ð±ÑÐµÐºÑÐ¾Ð²
    BUOY_SEMANTIC_TERMS = [
        "CHANNEL MARKING BUOY",
        "BUOY NO",
        "FAIRWAY BUOY",
        "BUOY GROUP",
        "MISSING BUOY",
        "UNLIT BUOY",
    ]

    has_buoy_semantics = any(term in ctx["upper"] for term in BUOY_SEMANTIC_TERMS)
    has_buoy_semantics = has_buoy_semantics or BUOY_TEXT_RE.search(
        ctx["upper"]
    ) is not None

    LINE_GEOMETRY_TERMS = [
        "TRACKLINE",
        "JOINING",
        "PIPELINE",
        "CABLE",
        "ROUTE",
        "BETWEEN THE POINTS",
    ]

    has_line_geometry = any(kw in ctx["upper"] for kw in LINE_GEOMETRY_TERMS)
    has_line_geometry = has_line_geometry or BOUNDARY_LINE_PATTERN.search(
        ctx["upper"]
    ) is not None

    if has_buoy_semantics and not has_line_geometry:
        return False

    ROUTE_KEYWORDS = [
        "ROUTE",
        "ROUTE NO",
        "ROUTE CENTERLINE",
        "CENTERLINE COORDINATES",
        "DOUBLE TRACK",
        "TRACK WIDTH",
        "TRANSIT ROUTE",
        "CHANNEL WIDTH",
    ]

    TRACK_KEYWORDS = [
        "TRACKLINE",
        "JOINING",
        "PIPELINE",
        "CABLE",
        "TRACK LINE",
        "TRACK LINE JOINING",
        "BETWEEN THE POINTS",
    ]

    if not any(kw in ctx["upper"] for kw in ROUTE_KEYWORDS + TRACK_KEYWORDS) and not BOUNDARY_LINE_PATTERN.search(
        ctx["upper"]
    ):
        return False

    if len(ctx["coords"]) < 2:
        return False

    line_presentation = get_line_presentation(
        ctx["block"],
        ctx["label_text"],
        ctx["description"],
        base_color=detect_color(ctx["block"]),
    )
    line_obj = create_line(
        name=ctx["label_text"],
        description=ctx["description"],
        coords=ctx["coords"],
        color=line_presentation["color"],
        check_danger=detect_check_danger(ctx["block"]),
        line_type=line_presentation["lineType"],
    )
    add_line_labels(
        add_line(line_obj, container, message),
        container,
        message,
    )

    return True


def handle_sublabels(ctx, container, message):
    debug("PROCESS: handle_sublabels")
    if ctx["is_riglist"] or ctx.get("is_letter_partition", False):
        return False

    if any(kw in ctx["upper"] for kw in GEOMETRY_KEYWORDS):
        return False

    # Новый inline-обработчик
    inline_sublabels = extract_sublabels_inline(ctx["block"])
    if inline_sublabels:
        style = get_point_style(ctx["block"])
        color = detect_color(ctx["block"])
        check_danger = detect_check_danger(ctx["block"])

        for s in inline_sublabels:
            for coord in s["coords"]:
                label_obj = create_label(
                    style=style,
                    color=color,
                    check_danger=check_danger,
                    text=ctx["label_text"],
                    description=build_sublabel_description(ctx, s["text"]),
                    coord=coord,
                )
                add_label(label_obj, container, message)

        return True

    # Существующая логика остаётся ниже
    sublabels = extract_sublabels(ctx["block"])
    if (
        not sublabels
        or not is_target_object_type(ctx["block"])
        or "RIGLIST" in ctx["upper"]
    ):
        return False

    style = get_point_style(ctx["block"])
    color = detect_color(ctx["block"])
    check_danger = detect_check_danger(ctx["block"])
    emit_sublabel_points(sublabels, ctx, container, message, style, color, check_danger)
    return True


def handle_lettered_sections(ctx, container, message):
    debug("PROCESS: handle_lettered_sections")
    if ctx["is_riglist"] or ctx.get("is_letter_partition", False):
        return False
    if any(kw in ctx["upper"] for kw in GEOMETRY_KEYWORDS):
        return False
    if not re.search(r"\b[A-Z]\.\s+", ctx["block"]):
        return False
    if "RIGLIST" in ctx["upper"] or "RIG LIST" in ctx["upper"]:
        return False
    sublabels = extract_sublabels(ctx["block"])
    if not sublabels:
        return False
    style = get_point_style(ctx["block"])
    color = detect_color(ctx["block"])
    check_danger = detect_check_danger(ctx["block"])
    emit_sublabel_points(sublabels, ctx, container, message, style, color, check_danger)
    return True


def handle_riglist(ctx, container, message):
    debug("PROCESS: handle_riglist")
    if ctx["is_riglist"]:
        process_riglist_entry(ctx["block"], ctx["label_text"], container, message)
        return True
    if not ("RIG LIST" in ctx["upper"] or "RIGLIST" in ctx["upper"]):
        return False
    process_riglist_entry(ctx["block"], ctx["label_text"], container, message)
    return True


def handle_multipoint(ctx, container, message):
    debug("PROCESS: handle_multipoint")
    if ctx["is_riglist"]:
        return False
    if is_buoy_group(ctx["block"]) or is_multi_point_navarea(ctx["block"]):
        style = get_point_style(ctx["block"])
        color = detect_color(ctx["block"])
        check_danger = detect_check_danger(ctx["block"])

        for coord in ctx["coords"]:
            label_obj = create_label(
                style=style,
                color=color,
                check_danger=check_danger,
                text=ctx["label_text"],
                description=ctx["description"],
                coord=coord,
            )
            add_label(label_obj, container, message)
        return True
    return False


def is_tow_endpoint_operation(ctx):
    """
    Identify a towing/movement notice that publishes only two endpoints of an
    operation, not a navigable route geometry.

    A plain "BETWEEN" clause is intentionally different from explicit
    trackline wording such as "BETWEEN THE POINTS"; the latter is handled by
    handle_trackline when the source actually describes line geometry.
    """
    if len(ctx["coords"]) != 2:
        return False
    if has_area_pattern(ctx["block"]):
        return False

    upper = ctx["upper"]
    if re.search(
        rf"\b(?:{BUOY_WORD}|LIGHT{BUOY_WORD}|BEACONS?|MARKS?|AIDS\s+TO\s+NAVIGATION)\b",
        upper,
    ):
        return False

    is_towing_operation = re.search(
        r"\b(?:TOW(?:ING|ED)?|TUG|BARGE)\b",
        upper,
    )
    is_movable_object = re.search(
        r"\b(?:RIG|JACKET|PLATFORM|FPSO|FSO|JUB|VESSEL|CRAFT)\b",
        upper,
    ) and re.search(
        r"\b(?:MOV(?:E|ED|ES|ING)|RELOCAT(?:E|ED|ING)|"
        r"TRANSFER(?:RED|RING)?|TRANSPORT(?:ED|ING)?)\b",
        upper,
    )
    has_between_endpoints = re.search(r"\bBETWEEN\b", upper) is not None
    has_from_to_endpoints = re.search(
        r"\bFROM\b[\s\S]{0,450}\bTO\b",
        upper,
    ) is not None

    return bool(
        (is_towing_operation or is_movable_object)
        and (has_between_endpoints or has_from_to_endpoints)
    )


def handle_tow_endpoints(ctx, container, message):
    """
    Preserve both published endpoints of an unresolved TOW operation.

    The source does not provide intermediate route points, so this handler
    emits two independent point labels and deliberately does not create a
    straight line between them.
    """
    debug("PROCESS: handle_tow_endpoints")
    if ctx["is_riglist"] or not is_tow_endpoint_operation(ctx):
        return False

    description = (
        f"{ctx['description']}\n"
        "ROUTE GEOMETRY NOT PROVIDED; POINTS ARE TOW ENDPOINTS ONLY."
    )
    for coord in ctx["coords"]:
        label_obj = create_label(
            style=get_point_style(ctx["block"]),
            color=detect_color(ctx["block"]),
            check_danger=detect_check_danger(ctx["block"]),
            text=ctx["label_text"],
            description=description,
            coord=coord,
        )
        add_label(label_obj, container, message)
    return True


def handle_single_point(ctx, container, message):
    debug("PROCESS: handle_single_point")
    if ctx["is_riglist"]:
        return False
    if len(ctx["coords"]) < 1:
        return False
    label_obj = create_label(
        style=get_point_style(ctx["block"]),
        color=detect_color(ctx["block"]),
        check_danger=detect_check_danger(ctx["block"]),
        text=ctx["label_text"],
        description=ctx["description"],
        coord=ctx["coords"][0],
    )
    add_label(label_obj, container, message)
    return True


def handle_fallback(ctx, container, message):
    debug("PROCESS: handle_fallback")
    if ctx["is_riglist"]:
        return False
    if len(ctx["coords"]) < 1:
        return False
    label_obj = create_label(
        style=2,
        color="NINFO",
        check_danger=0,
        text=ctx["label_text"],
        description=ctx["description"],
        coord=ctx["coords"][0],
    )
    add_label(label_obj, container, message)
    return True


def handle_no_anchor(ctx, container, message):
    debug("PROCESS: handle_no_anchor")
    if ctx["is_riglist"]:
        return False
    if "NO ANCHOR" not in ctx["upper"] and "ANCHORING PROHIBITED" not in ctx["upper"]:
        return False
    if len(ctx["coords"]) < 3:
        return False

    area_coords = normalize_area_vertices(ctx["coords"])
    area_obj = create_area(
        name=ctx["label_text"],
        description=ctx["description"],
        coords=area_coords,
        color=detect_color(ctx["block"]),
        check_danger=0,
    )
    add_area(area_obj, container, message)
    return True


# ----------------------------------------------------------------------
# BUOY SEMANTIC LAYER v1
# ----------------------------------------------------------------------

BUOY_SUBTYPE_PATTERNS = [
    (
        "CHANNEL_MARKING",
        re.compile(rf"\bCHANNEL\s+MARKING\s+{BUOY_WORD}\b", re.IGNORECASE),
    ),
    ("CHANNEL", re.compile(rf"\bCHANNEL\s+{BUOY_WORD}\b", re.IGNORECASE)),
    ("FAIRWAY", re.compile(rf"\bFAIRWAY\s+{BUOY_WORD}\b", re.IGNORECASE)),
    (
        "SAFE_WATER",
        re.compile(rf"\bSAFE\s+WATER\s+{BUOY_WORD}\b", re.IGNORECASE),
    ),
    (
        "SPECIAL_MARK",
        re.compile(rf"\bSPECIAL\s+MARK\s+{BUOY_WORD}\b", re.IGNORECASE),
    ),
    ("BUOY_NO", re.compile(rf"\b{BUOY_WORD}\s+NO\b", re.IGNORECASE)),
    ("BUOY_GROUP", re.compile(rf"\b{BUOY_WORD}\s+GROUP\b", re.IGNORECASE)),
    ("LIGHTBUOY", re.compile(rf"\bLIGHT{BUOY_WORD}\b", re.IGNORECASE)),
    (
        "BEACON",
        re.compile(
            r"\b(?:"
            r"BEACONS?"
            r"|BEACONS?\s+TOWERS?"
            r"|TOWERS?\s+BEACONS?"
            r"|PILL(?:AR|ER|E)\s+BEACONS?"
            r"|LATTICE\s+BEACONS?"
            r"|PERCH\s+BEACONS?"
            r"|LIGHT(?:ED|HED)?\s+BEACONS?"
            r"|PIER\s+BEACONS?"
            r"|DAY\s+BEACONS?"
            r")\b",
            re.IGNORECASE,
        ),
    ),
    ("BUOY", re.compile(rf"\b{BUOY_WORD}\b", re.IGNORECASE)),
]

BUOY_DISPLAY_PROFILES = {
    "BUOY": {"style": 4, "active_color": "CHYLW"},
    "BEACON": {"style": 4, "active_color": "CHYLW"},
}

BUOY_STATUS_PATTERNS = [
    ("UNLIT", re.compile(r"\bUNLIT\b", re.IGNORECASE)),
    ("MISSING", re.compile(r"\bMISSING\b", re.IGNORECASE)),
    ("OFF_AIR", re.compile(r"\bOFF\s+AIR\b", re.IGNORECASE)),
    ("REMOVED", re.compile(r"\bREMOVED\b", re.IGNORECASE)),
    ("RETRIEVED", re.compile(r"\bRETRIEVED\b", re.IGNORECASE)),
    ("SHIFTED", re.compile(r"\bSHIFTED\b", re.IGNORECASE)),
]


BUOY_TABLE_COORD_RE = re.compile(
    r"(?P<lat_deg>\d{1,3})[- ]+(?P<lat_min>[\d.]+)\s*"
    r"(?P<lat_hemi>[NS])[\s,]+"
    r"(?P<lon_deg>\d{1,3})[- ]+(?P<lon_min>[\d.]+)\s*"
    r"(?P<lon_hemi>[EW])",
    re.IGNORECASE,
)


def detect_buoy_status(text):
    for name, pattern in BUOY_STATUS_PATTERNS:
        if pattern.search(text.upper()):
            return name
    return "ACTIVE"


def classify_buoy(text):
    upper = text.upper()

    # LIGHT UNLIT / LIGHTHOUSE UNLIT — это AtoN, не buoy
    if (
        "UNLIT" in upper
        and not BUOY_TEXT_RE.search(upper)
        and ("LIGHT" in upper or "LIGHTHOUSE" in upper)
    ):
        return None

    subtype = None
    for name, pattern in BUOY_SUBTYPE_PATTERNS:
        if pattern.search(upper):
            subtype = name
            break

    if subtype is None:
        return None

    status = detect_buoy_status(upper)

    return {
        "has_buoy": True,
        "subtype": subtype,
        "status": status,
    }


def parse_buoy_table_rows(block):
    """Return per-coordinate semantics for a buoy status table."""
    if not (
        re.search(rf"\b{BUOY_WORD}\s+POSITIONS\b", block, re.IGNORECASE)
        and re.search(r"\bTYPE\s+AND\s+ISSUE\b", block, re.IGNORECASE)
    ):
        return []

    matches = list(BUOY_TABLE_COORD_RE.finditer(block))
    rows = []
    for index, match in enumerate(matches):
        lat = dm_to_decimal(
            match.group("lat_deg"),
            match.group("lat_min"),
            match.group("lat_hemi").upper(),
        )
        lon = dm_to_decimal(
            match.group("lon_deg"),
            match.group("lon_min"),
            match.group("lon_hemi").upper(),
        )
        if lat is None or lon is None:
            continue

        row_end = matches[index + 1].start() if index + 1 < len(matches) else len(block)
        row_text = block[match.start() : row_end]
        rows.append(
            {
                "coord": (lat, lon),
                "status": detect_buoy_status(row_text),
                "subtype": "BUOY",
                "check_danger": detect_check_danger(row_text),
            }
        )

    return rows


def buoy_style_color(check_danger, status, subtype=None):
    """
    ÐÐ¾Ð·Ð²ÑÐ°ÑÐ°ÐµÑ (style, color, checkDanger) Ð´Ð»Ñ Ð±ÑÑÐ².

    Style 4 Ð¾Ð±ÑÐ·Ð°ÑÐµÐ»ÐµÐ½ Ð´Ð»Ñ buoy display.

    ACTIVE:
        S52colorcode = CHYLW

    ÐÑÑ Ð¾ÑÑÐ°Ð»ÑÐ½Ð¾Ðµ:
        S52colorcode = NINFO

    ÐÑÐ°ÑÐ½ÑÐ¹ Ð½Ðµ Ð¸ÑÐ¿Ð¾Ð»ÑÐ·ÑÐµÑÑÑ.
    """
    profile = BUOY_DISPLAY_PROFILES.get(
        subtype,
        BUOY_DISPLAY_PROFILES["BUOY"],
    )
    style = profile["style"]

    if check_danger:
        return style, "CHRED", 1
    elif status == "ACTIVE":
        color = profile["active_color"]
    else:
        color = "NINFO"

    return style, color, 0


def build_buoy_label_description(ctx, coord, status):
    # Keep the complete notice context. Coordinates and cancellation timing
    # remain visible in the Description for operator verification.
    status_text = status if status and status != "ACTIVE" else ""
    metadata = ctx.get("metadata") or {}
    return compose_description(
        ctx.get("parent_context", ""),
        metadata.get("semantic_context", ""),
        ctx.get("block", ""),
        status_text,
    )


def _buoy_context_fragments(block, coords):
    """Map each buoy coordinate to its numbered source section when present."""

    section_markers = list(
        re.finditer(
            r"(?:^|\n)\s*(\d+(?:\.\d+)*)\.\s+",
            block,
        )
    )
    if len(section_markers) < 2:
        return [block for _ in coords]

    sections = []
    for index, marker in enumerate(section_markers):
        end = (
            section_markers[index + 1].start()
            if index + 1 < len(section_markers)
            else len(block)
        )
        section = block[marker.start() : end].strip()
        if section:
            sections.append(section)

    fragments = []
    for coord in coords:
        fragments.append(
            next(
                (
                    section
                    for section in sections
                    if coord in extract_coordinates(section)
                ),
                block,
            )
        )
    return fragments


def handle_buoy_semantics(ctx, container, message):
    """
    Buoy Semantic Layer v1.

    ÐÑÐ»Ð¸ ÑÐ¾Ð¾Ð±ÑÐµÐ½Ð¸Ðµ Ð¾Ð¿Ð¸ÑÑÐ²Ð°ÐµÑ Ð±ÑÐ¸ Ð¸ Ð½Ðµ ÑÐ¾Ð´ÐµÑÐ¶Ð¸Ñ ÑÐµÐ°Ð»ÑÐ½ÑÑ line-Ð³ÐµÐ¾Ð¼ÐµÑÑÐ¸Ñ,
    ÑÐ¾Ð·Ð´Ð°ÑÑ Ð¾ÑÐ´ÐµÐ»ÑÐ½ÑÐµ labels Style 4 Ð´Ð»Ñ ÐºÐ°Ð¶Ð´Ð¾Ð¹ ÐºÐ¾Ð¾ÑÐ´Ð¸Ð½Ð°ÑÑ.

    Line geometry Ð´Ð»Ñ buoy-only messages ÐÐ ÑÐ¾Ð·Ð´Ð°ÑÑÑÑ.
    """
    debug("PROCESS: handle_buoy_semantics")

    if ctx["is_riglist"]:
        return False
    upper = ctx["upper"]
    if has_area_pattern(ctx["block"]) and "CHANNEL WIDTH" not in upper:
        return False

    if (
        "UNLIT" in upper
        and not BUOY_TEXT_RE.search(upper)
        and ("LIGHT" in upper or "LIGHTHOUSE" in upper)
    ):
        return False

    buoy = classify_buoy(ctx["block"])
    if not buoy or not buoy.get("has_buoy"):
        return False

    LINE_GEOMETRY_TERMS = ["TRACKLINE", "JOINING", "PIPELINE", "ROUTE"]
    HAZARD_CONTEXT_TERMS = [
        "DERELICT",
        "WRECK",
        "SUNKEN",
        "SUNK",
        "OBSTRUCTION",
        "SUBMERGED",
        "UNMARKED",
    ]

    if any(term in ctx["upper"] for term in HAZARD_CONTEXT_TERMS):
        return False
    has_line_geometry = any(kw in ctx["upper"] for kw in LINE_GEOMETRY_TERMS)

    if has_line_geometry:
        return False

    if len(ctx["coords"]) < 1:
        return False

    table_rows = parse_buoy_table_rows(ctx["block"])
    if table_rows and [row["coord"] for row in table_rows] == ctx["coords"]:
        buoy_rows = table_rows
    else:
        row_contexts = _buoy_context_fragments(ctx["block"], ctx["coords"])
        buoy_rows = [
            {
                "coord": coord,
                "status": detect_buoy_status(row_context),
                "subtype": (classify_buoy(row_context) or buoy)["subtype"],
                "check_danger": detect_check_danger(row_context),
            }
            for coord, row_context in zip(ctx["coords"], row_contexts)
        ]

    for row in buoy_rows:
        style, color, check_danger = buoy_style_color(
            check_danger=row["check_danger"],
            status=row["status"],
            subtype=row["subtype"],
        )
        coord = row["coord"]
        desc = build_buoy_label_description(ctx, coord, row["status"])

        label_obj = create_label(
            style=style,
            color=color,
            check_danger=check_danger,
            text=ctx["label_text"],
            description=desc,
            coord=coord,
        )
        add_label(label_obj, container, message)

    return True


# -------------------- HANDLER REGISTRY --------------------
PROCESS_HANDLERS = [
    handle_ice_report,
    handle_explicit_line_circle,
    handle_mixed_geometry_package,
    handle_platform_multipoint,
    handle_line_with_endpoint_objects,
    handle_implicit_operational_area,
    handle_buoy_semantics,  # NEW
    handle_vessel_list_points,
    handle_facility_list_points,
    handle_structured_sections,
    handle_circle,
    handle_bounding_box,
    handle_area,
    handle_no_anchor,
    handle_trackline,
    handle_sublabels,
    handle_lettered_sections,
    handle_riglist,
    handle_multipoint,
    handle_tow_endpoints,
    handle_single_point,
    handle_fallback,
]


def validate_handler_registry(registry):
    if not registry:
        print("WARNING: Handler registry is empty.")
        return
    if registry[-1].__name__ != "handle_fallback":
        print("WARNING: Last handler in registry should be handle_fallback.")
    try:
        single_idx = [h.__name__ for h in registry].index("handle_single_point")
    except ValueError:
        print("WARNING: handle_single_point not found in registry.")
        return
    geometry_handlers = [
        "handle_area",
        "handle_trackline",
        "handle_circle",
        "handle_bounding_box",
    ]
    for h in geometry_handlers:
        try:
            idx = [h_name for h_name in [fn.__name__ for fn in registry]].index(h)
            if idx > single_idx:
                print(
                    f"WARNING: {h} appears after handle_single_point (order may be incorrect)."
                )
        except ValueError:
            pass


validate_handler_registry(PROCESS_HANDLERS)


# -------------------- PROCESS_BLOCK DISPATCHER --------------------
def process_block(block, message, container, navarea_name, label_text=None, meta=None):
    ctx = build_processing_context(block, navarea_name, label_text, meta)
    object_counts_before = {
        kind: len(container.get(kind, []))
        for kind in ("areas", "lines", "circles", "labels")
    }
    message_counts_before = {
        kind: len(message.get(kind, []))
        for kind in ("areas", "lines", "circles", "labels")
    }
    stage_diagnostics = message.setdefault("stage_diagnostics", [])
    stage_diagnostics.append(
        {
            "stage": "context_built",
            "coordinate_count": len(ctx["coords"]),
            "metadata_partition": (meta or {}).get("partition_type"),
        }
    )
    if DEBUG:
        print(f"DEBUG: processing block with {len(ctx['coords'])} coords")
    for handler in PROCESS_HANDLERS:
        if handler(ctx, container, message):
            for kind in ("areas", "lines", "circles", "labels"):
                container_objects = container.get(kind, [])[
                    object_counts_before[kind] :
                ]
                message_objects = message.get(kind, [])[
                    message_counts_before[kind] :
                ]
                for obj in (*container_objects, *message_objects):
                    if ctx.get("parent_context") or ctx.get("footer_context"):
                        obj["description"] = compose_partition_description(
                            ctx.get("parent_context", ""),
                            obj.get("description", ""),
                            ctx.get("footer_context", ""),
                        )
            handler_name = handler.__name__
            stage_diagnostics.append(
                {
                    "stage": "handler_match",
                    "handler": handler_name,
                    "object_counts": {
                        "areas": len(message.get("areas", [])),
                        "lines": len(message.get("lines", [])),
                        "circles": len(message.get("circles", [])),
                        "labels": len(message.get("labels", [])),
                    },
                }
            )
            if DEBUG:
                print(f"MATCH: {handler_name}")
            return
    stage_diagnostics.append(
        {
            "stage": "handler_match",
            "handler": None,
            "object_counts": {
                "areas": len(message.get("areas", [])),
                "lines": len(message.get("lines", [])),
                "circles": len(message.get("circles", [])),
                "labels": len(message.get("labels", [])),
            },
        }
    )


# -------------------- REACTIVE MONSTER HANDLING --------------------
def create_new_part(base_id, part_num):
    return create_message(
        f"{base_id} (Part {part_num})",
        metadata={"partition_type": "REACTIVE", "partition_id": str(part_num)},
    )


def explode_oversized_messages(messages, limit):
    new_messages = []
    for msg in messages:
        obj_count = count_objects(msg)
        if DEBUG:
            print(f"\nð Message: {msg['id']}")
            print_complexity_report(msg)
        check_geometry_warnings(msg)

        if obj_count <= limit:
            new_messages.append(msg)
            continue

        groups = []
        for area in msg.get("areas", []):
            groups.append(
                {"type": "area", "geometry": copy.deepcopy(area), "labels": []}
            )
        for line in msg.get("lines", []):
            groups.append(
                {"type": "line", "geometry": copy.deepcopy(line), "labels": []}
            )
        for circle in msg.get("circles", []):
            groups.append(
                {"type": "circle", "geometry": copy.deepcopy(circle), "labels": []}
            )
        for label in msg.get("labels", []):
            groups.append(
                {"type": "label", "geometry": None, "labels": [copy.deepcopy(label)]}
            )

        def group_object_count(group):
            cnt = 0
            if group["geometry"] is not None:
                cnt += 1
            cnt += len(group["labels"])
            return cnt

        oversized_groups = [g for g in groups if group_object_count(g) > limit]
        if oversized_groups:
            print(
                f"WARNING: Message {msg['id']} contains groups that exceed the object limit:"
            )
            for g in oversized_groups:
                print(
                    f"  - {g['type']} group with {group_object_count(g)} objects cannot be packed safely."
                )

        parts = []
        part_num = 1
        current_part = create_new_part(msg["id"], part_num)
        current_count = 0

        for group in groups:
            group_count = group_object_count(group)
            if current_count + group_count <= limit:
                if group["type"] == "area":
                    current_part["areas"].append(group["geometry"])
                elif group["type"] == "line":
                    current_part["lines"].append(group["geometry"])
                elif group["type"] == "circle":
                    current_part["circles"].append(group["geometry"])
                for lbl in group["labels"]:
                    current_part["labels"].append(lbl)
                current_count += group_count
            else:
                if current_count > 0:
                    parts.append(current_part)
                part_num += 1
                current_part = create_new_part(msg["id"], part_num)
                if group["type"] == "area":
                    current_part["areas"].append(group["geometry"])
                elif group["type"] == "line":
                    current_part["lines"].append(group["geometry"])
                elif group["type"] == "circle":
                    current_part["circles"].append(group["geometry"])
                for lbl in group["labels"]:
                    current_part["labels"].append(lbl)
                current_count = group_count

        if current_count > 0:
            parts.append(current_part)

        if len(parts) == 1:
            new_messages.append(parts[0])
        else:
            for idx, part in enumerate(parts, start=1):
                part["id"] = f"{msg['id']} (Part {idx})"
            new_messages.extend(parts)
            if DEBUG:
                print(f"   Exploded into {len(parts)} parts:")
                for idx, part in enumerate(parts, start=1):
                    part_objects = count_objects(part)
                    part_vertices = total_vertices_in_message(part)
                    print(
                        f"     Part {idx} â {part_objects} objects, {part_vertices} vertices"
                    )

    return new_messages


# -------------------- SPLITTER --------------------
def split_legacy_messages(messages, limit):
    if not messages:
        return []
    if limit <= 0:
        raise ValueError("Legacy object limit must be positive")

    total_objects = 0
    oversized = []
    for msg in messages:
        cnt = count_objects(msg)
        total_objects += cnt
        if cnt > limit:
            oversized.append(msg["id"])

    if oversized:
        print("WARNING: Some messages exceed legacy object limit:")
        for mid in oversized:
            print(f"  {mid}")

    if total_objects <= limit:
        if DEBUG:
            print(f"Total objects: {total_objects}, Legacy limit: {limit} â single part")
        return [messages]

    parts = []
    current_part = []
    current_count = 0

    for msg in messages:
        cnt = count_objects(msg)
        if cnt > limit:
            if current_part:
                parts.append(current_part)
                current_part = []
                current_count = 0
            parts.append([msg])
            continue

        if current_count + cnt <= limit:
            current_part.append(msg)
            current_count += cnt
        else:
            if current_part:
                parts.append(current_part)
            current_part = [msg]
            current_count = cnt

    if current_part:
        parts.append(current_part)

    if DEBUG:
        print(f"Total objects: {total_objects}, Legacy limit: {limit}")
    for i, part in enumerate(parts, 1):
        part_count = sum(count_objects(m) for m in part)
        print(f"Part {i} = {part_count} objects")

    return parts


# -------------------- XML ATTRIBUTE SANITIZATION & VALIDATION --------------------
def sanitize_xml_attribute(value):
    """
    Normalize XML attribute value for legacy ECDIS compatibility.

    - None -> ""
    - replace CR/LF/TAB with space
    - collapse repeated whitespace
    - trim leading/trailing whitespace
    """
    if value is None:
        return ""
    text = str(value)
    text = text.replace("\r", " ")
    text = text.replace("\n", " ")
    text = text.replace("\t", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def sanitize_ecdis_description(value):
    """
    Keep the message, operational meaning, and verification coordinates in
    the ECDIS Description.

    Coordinates are intentionally duplicated in the object's position
    vertices and Description: the vertices drive ECDIS geometry, while the
    text lets an operator verify the published position. Cancellation
    information also remains in the Description so an operator can compare
    the planned passage time with the warning's end time. The application
    does not schedule self-deletion of the object.
    """
    text = unescape(sanitize_xml_attribute(value))
    text = re.sub(r"\s+([.,;])", r"\1", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def xml_attr(value):
    """
    Sanitize whitespace and escape XML special characters.
    Use for manual f-string XML exports.
    """
    return escape(sanitize_xml_attribute(value))


XML_ATTR_RE = re.compile(r'([A-Za-z_][A-Za-z0-9_.:-]*)\s*=\s*"([^"]*)"')


def validate_xml_attributes(xml_text, context="XML"):
    """
    ÐÑÐ¾Ð²ÐµÑÑÐµÑ ÐÐ¡Ð XML-Ð°ÑÑÐ¸Ð±ÑÑÑ Ð½Ð° Ð½Ð°Ð»Ð¸ÑÐ¸Ðµ CR/LF/TAB.

    Returns True if no unsafe attributes found.
    """
    attrs = XML_ATTR_RE.findall(xml_text)
    unsafe = []

    for attr_name, attr_value in attrs:
        if any(ch in attr_value for ch in ("\r", "\n", "\t")):
            unsafe.append((attr_name, attr_value))

    print(f"\n{context} VALIDATION")
    print(f"Attributes checked : {len(attrs)}")
    print(f"Unsafe attributes  : {len(unsafe)}")

    for attr_name, attr_value in unsafe:
        preview = attr_value[:120].encode("unicode_escape").decode()
        print(f"  UNSAFE attribute : {attr_name}")
        print(f"  Offending value  : {preview}")

    return len(unsafe) == 0


# -------------------- LEGACY XML GENERATORS --------------------
def generate_legacy_xml_from_messages(nav_id, part_messages, part_index, total_parts):
    combined = {"areas": [], "lines": [], "circles": [], "labels": []}
    for msg in part_messages:
        combined["areas"].extend(msg.get("areas", []))
        combined["lines"].extend(msg.get("lines", []))
        combined["circles"].extend(msg.get("circles", []))
        combined["labels"].extend(msg.get("labels", []))

    if total_parts > 1:
        name_suffix = f"(Part {part_index})"
    else:
        name_suffix = None

    return generate_legacy_xml(nav_id, combined, name_suffix=name_suffix)


def generate_legacy_xml(nav_id, data, name_suffix=None):
    base_name = f"NAVAREA {nav_id}"
    full_name = f"{base_name} {name_suffix}" if name_suffix else base_name
    full_name = sanitize_xml_attribute(full_name)

    root = ET.Element("userchart", name=full_name, description="", version="1.0")

    def get_attrs(obj_type, obj_data):
        raw_name = obj_data.get("name") or obj_data.get("text") or "UNKNOWN"

        if obj_type == "area":
            name = obj_data.get("name", f"NAV {nav_id}")
            desc = sanitize_ecdis_description(obj_data.get("description", ""))
        elif obj_type == "label":
            name = obj_data.get("text", f"NAV {nav_id}")
            desc = sanitize_ecdis_description(obj_data.get("description", name))
        else:  # line, circle, clearingLine
            name = obj_data.get("name", "")
            desc = sanitize_ecdis_description(obj_data.get("description", ""))

        name = sanitize_xml_attribute(name)
        desc = sanitize_xml_attribute(desc)

        if len(desc) > LEGACY_MAX_DESC:
            print(f"DESC TRUNCATED [{obj_type}]")
            print(f"OBJECT: {sanitize_xml_attribute(raw_name)}")
            print(f"LENGTH: {len(desc)} -> {LEGACY_MAX_DESC}")
            desc = desc[:LEGACY_MAX_DESC]

        return name, desc

    # LINES
    if data.get("lines"):
        lines_elem = ET.SubElement(root, "lines")
        for line in data["lines"]:
            name, desc = get_attrs("line", line)
            line_elem = ET.SubElement(lines_elem, "line", name=name, description=desc)
            pos = ET.SubElement(line_elem, "position")
            for idx, (lat, lon) in enumerate(line["coords"], start=1):
                ET.SubElement(
                    pos,
                    "vertex",
                    id=str(idx),
                    latitude=f"{lat:.6f}",
                    longitude=f"{lon:.6f}",
                )
            ET.SubElement(line_elem, "attribute", lineType=str(line.get("lineType", 2)))
            ET.SubElement(
                line_elem,
                "type",
                checkDanger=str(line.get("checkDanger", 0)),
                displayRadar="0",
                hasNotes="0",
                rangeOfNotes="1.000000",
            )

    # CLEARING LINES
    if data.get("clearingLines"):
        clearing_elem = ET.SubElement(root, "clearingLines")
        for cl in data["clearingLines"]:
            name, desc = get_attrs("line", cl)
            cl_elem = ET.SubElement(
                clearing_elem, "clearingLine", name=name, description=desc
            )
            pos = ET.SubElement(cl_elem, "position")
            for idx, (lat, lon) in enumerate(cl["coords"], start=1):
                ET.SubElement(
                    pos,
                    "vertex",
                    id=str(idx),
                    latitude=f"{lat:.6f}",
                    longitude=f"{lon:.6f}",
                )
            ET.SubElement(cl_elem, "attribute", lineType=str(cl.get("lineType", 1)))
            ET.SubElement(cl_elem, "type", isDanger=str(cl.get("isDanger", 0)))

    # AREAS
    if data.get("areas"):
        areas_elem = ET.SubElement(root, "areas")
        for area in data["areas"]:
            name, desc = get_attrs("area", area)
            area_elem = ET.SubElement(areas_elem, "area", name=name, description=desc)
            pos = ET.SubElement(area_elem, "position")
            for idx, (lat, lon) in enumerate(
                area_vertices_for_xml(area["coords"]), start=1
            ):
                ET.SubElement(
                    pos,
                    "vertex",
                    id=str(idx),
                    latitude=f"{lat:.6f}",
                    longitude=f"{lon:.6f}",
                )
            ET.SubElement(
                area_elem,
                "type",
                checkDanger=str(area.get("checkDanger", 0)),
                displayRadar="0",
                hasNotes="0",
                notesType="0",
            )

    # LABELS
    if data.get("labels"):
        labels_elem = ET.SubElement(root, "labels")
        for label in data["labels"]:
            name, desc = get_attrs("label", label)
            label_elem = ET.SubElement(
                labels_elem, "label", name=name, description=desc
            )
            pos = ET.SubElement(label_elem, "position")
            lat, lon = label["coord"]
            ET.SubElement(
                pos, "vertex", id="1", latitude=f"{lat:.6f}", longitude=f"{lon:.6f}"
            )

            label_text = sanitize_xml_attribute(label.get("text", f"NAV {nav_id}"))
            ET.SubElement(label_elem, "attribute", labelStyle="2", labelText=label_text)
            ET.SubElement(
                label_elem,
                "type",
                checkDanger=str(label.get("checkDanger", 0)),
                displayRadar="0",
            )

    # CIRCLES
    if data.get("circles"):
        circles_elem = ET.SubElement(root, "circles")
        for circle in data["circles"]:
            name, desc = get_attrs("circle", circle)
            circle_elem = ET.SubElement(
                circles_elem, "circle", name=name, description=desc
            )
            pos = ET.SubElement(circle_elem, "position")
            lat, lon = circle["coord"]
            ET.SubElement(
                pos, "vertex", id="1", latitude=f"{lat:.6f}", longitude=f"{lon:.6f}"
            )

            range_val = circle.get("range", 0.0)
            if range_val > LEGACY_MAX_CIRCLE_RANGE:
                print(
                    f"WARNING: Circle range {range_val} exceeds legacy limit (50). Will be reduced to 50."
                )
                range_val = LEGACY_MAX_CIRCLE_RANGE

            ET.SubElement(circle_elem, "attribute", range=f"{range_val:.6f}")
            ET.SubElement(
                circle_elem,
                "type",
                checkDanger=str(circle.get("checkDanger", 0)),
                displayRadar="0",
                hasNotes="0",
                notesType="0",
            )

    rough_string = ET.tostring(root, encoding="unicode")
    reparsed = minidom.parseString(rough_string)

    root_node = reparsed.documentElement
    section_tags = ["lines", "clearingLines", "areas", "labels", "circles"]
    comment_map = {
        "lines": "userchart line",
        "clearingLines": "userchart clearingLine",
        "areas": "userchart area",
        "labels": "userchart label",
        "circles": "userchart circle",
    }
    for tag in section_tags:
        elem = root_node.getElementsByTagName(tag)
        if elem:
            elem = elem[0]
            comment = reparsed.createComment(comment_map.get(tag, tag))
            root_node.insertBefore(comment, elem)

    xml_str = reparsed.toprettyxml(indent="  ")
    lines = xml_str.splitlines()
    if lines and lines[0].startswith("<?xml"):
        lines = lines[1:]
    xml_str = "\n".join(
        ['<?xml version="1.0" encoding="UTF-8"?>', "<!--userchart node-->", *lines]
    )
    return xml_str


# -------------------- EXPORT ADAPTERS --------------------
def export_furuno_modern(nav_id, container):
    xml = []
    xml.append('<?xml version="1.0" encoding="UTF-8"?>')
    xml.append(
        f'<userchart name="{xml_attr(f"NAVAREA {nav_id} IMPORT")}" description="" version="1.3">'
    )

    if container.get("lines"):
        xml.append("<lines>")
        for line in container["lines"]:
            xml.append(
                f'<line name="{xml_attr(line["name"])}" '
                f'description="{xml_attr(sanitize_ecdis_description(line["description"]))}">'
            )
            xml.append("<position>")
            for idx, (lat, lon) in enumerate(line["coords"], start=1):
                xml.append(
                    f'<vertex id="{idx}" latitude="{lat:.6f}" longitude="{lon:.6f}"/>'
                )
            xml.append("</position>")
            xml.append(
                f'<attribute lineType="{line.get("lineType", 2)}" linkedDocument=""/>'
            )
            xml.append(
                f'<type checkDanger="{line["checkDanger"]}" displayRadar="0" hasNotes="0" rangeOfNotes="1.000000"/>'
            )
            xml.append(f'<display S52colorcode="{line["color"]}" lineWidth="3"/>')
            xml.append("</line>")
        xml.append("</lines>")

    if container.get("areas"):
        xml.append("<areas>")
        for area in container["areas"]:
            xml.append(
                f'<area name="{xml_attr(area["name"])}" '
                f'description="{xml_attr(sanitize_ecdis_description(area["description"]))}">'
            )
            xml.append("<position>")
            for idx, (lat, lon) in enumerate(
                area_vertices_for_xml(area["coords"]), start=1
            ):
                xml.append(
                    f'<vertex id="{idx}" latitude="{lat:.6f}" longitude="{lon:.6f}"/>'
                )
            xml.append("</position>")
            xml.append('<attribute linkedDocument=""/>')
            xml.append(
                f'<type checkDanger="{area["checkDanger"]}" displayRadar="0" hasNotes="0" notesType="0"/>'
            )
            xml.append(
                f'<display S52colorcode="{area["color"]}" lineWidth="2" density="25"/>'
            )
            xml.append("</area>")
        xml.append("</areas>")

    if container.get("circles"):
        xml.append("<circles>")
        for circle in container["circles"]:
            xml.append(
                f'<circle name="{xml_attr(circle["name"])}" '
                f'description="{xml_attr(sanitize_ecdis_description(circle["description"]))}">'
            )
            lat, lon = circle["coord"]
            xml.append("<position>")
            xml.append(f'<vertex id="1" latitude="{lat:.6f}" longitude="{lon:.6f}"/>')
            xml.append("</position>")
            xml.append(f'<attribute range="{circle["range"]:.6f}" linkedDocument=""/>')
            xml.append(
                f'<type checkDanger="{circle["checkDanger"]}" displayRadar="0" hasNotes="0" notesType="0"/>'
            )
            xml.append(
                f'<display S52colorcode="{circle["color"]}" lineWidth="2" density="25"/>'
            )
            xml.append("</circle>")
        xml.append("</circles>")

    if container.get("labels"):
        xml.append("<labels>")
        for label in container["labels"]:
            xml.append(
                f'<label name="{xml_attr(label["text"])}" '
                f'description="{xml_attr(sanitize_ecdis_description(label["description"]))}">'
            )
            lat, lon = label["coord"]
            xml.append("<position>")
            xml.append(f'<vertex id="1" latitude="{lat:.6f}" longitude="{lon:.6f}"/>')
            xml.append("</position>")
            xml.append(
                f'<attribute labelStyle="{label["style"]}" '
                f'labelText="{xml_attr(label["text"])}" linkedDocument=""/>'
            )
            xml.append(f'<type checkDanger="{label["checkDanger"]}" displayRadar="0"/>')
            xml.append(f'<display S52colorcode="{label["color"]}"/>')
            xml.append("</label>")
        xml.append("</labels>")

    # Keep the UserChart presentation grouped by geometry: areas first,
    # followed by lines, circles and point objects (labels). The individual
    # builders above stay unchanged so production object semantics are not
    # altered by the presentation order.
    section_markers = {
        "<areas>": ("areas", "Areas: closed zones with boundaries"),
        "<lines>": ("lines", "Lines: paths between points"),
        "<circles>": ("circles", "Circles: radius around one point"),
        "<labels>": ("labels", "Point objects: one position"),
    }
    sections = {}
    current_section = None
    for item in xml[2:]:
        marker = section_markers.get(item)
        if marker:
            current_section = marker[0]
            sections[current_section] = [f"<!-- {marker[1]} -->", item]
        elif current_section:
            sections[current_section].append(item)

    ordered_xml = xml[:2]
    for section_name in ("areas", "lines", "circles", "labels"):
        ordered_xml.extend(sections.get(section_name, []))

    xml = ordered_xml
    xml.append("</userchart>")
    return "\n".join(xml)


def export_furuno_legacy(nav_id, container):
    messages = container.get("messages", [])
    non_empty_messages = [m for m in messages if count_objects(m) > 0]
    output = []

    if non_empty_messages:
        exploded = explode_oversized_messages(non_empty_messages, LEGACY_MAX_OBJECTS)
        parts = split_legacy_messages(exploded, LEGACY_MAX_OBJECTS)
        for idx, part in enumerate(parts, start=1):
            part_comp = analyze_part_complexity(part)
            print(
                f"   Legacy Part {idx}: {part_comp['message_count']} messages, {part_comp['total_objects']} objects, {part_comp['total_vertices']} vertices, Risk: {part_comp['risk']}"
            )
            xml_str = generate_legacy_xml_from_messages(nav_id, part, idx, len(parts))
            if len(parts) > 1:
                filename = f"output_NAVAREA_{nav_id}_legacy_Part{idx}.xml"
            else:
                filename = f"output_NAVAREA_{nav_id}_legacy.xml"
            output.append((filename, xml_str))
    else:
        xml_str = generate_legacy_xml(nav_id, container)
        filename = f"output_NAVAREA_{nav_id}_legacy.xml"
        output.append((filename, xml_str))

    return output


# -------------------- EXPORT MANAGER --------------------
def export_navarea(nav_id, container):
    comp = analyze_container_complexity(container)
    stats = {
        "nav_id": nav_id,
        "message_count": comp["message_count"],
        "total_objects": comp["total_objects"],
        "total_vertices": comp["total_vertices"],
        "risk": comp["risk"],
        "modern_success": False,
        "legacy_parts": 0,
        "legacy_files": [],
    }

    # Modern export
    try:
        modern_xml = export_furuno_modern(nav_id, container)
        filename = f"output_NAVAREA_{nav_id}.xml"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(modern_xml)
        stats["modern_success"] = True
        print(
            f"Wrote {filename}: Areas={len(container['areas'])}, Lines={len(container['lines'])}, Circles={len(container['circles'])}, Labels={len(container['labels'])}"
        )
    except Exception as e:
        print(f"Failed to write modern export for {nav_id}: {e}")

    # Legacy export
    legacy_outputs = export_furuno_legacy(nav_id, container)
    for filename, xml_str in legacy_outputs:
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(xml_str)
            stats["legacy_files"].append(filename)
        except Exception as e:
            print(f"Failed to write {filename}: {e}")
    stats["legacy_parts"] = len(legacy_outputs)

    if DEBUG:
        print(f"\nð Container: {nav_id}")
        print(f"   Messages: {comp['message_count']}")
        print(f"   Objects: {comp['total_objects']}")
        print(f"   Vertices: {comp['total_vertices']}")
        print(f"   Risk: {comp['risk']}")
        if stats["modern_success"]:
            print("   Modern Export: Success")
        else:
            print("   Modern Export: Failed")
        print(f"   Legacy Export: {stats['legacy_parts']} part(s)")

    return stats


# -------------------- REGRESSION TEST FRAMEWORK --------------------
def run_regression_tests():
    test_dir = "tests"
    if not os.path.isdir(test_dir):
        print("No test directory found, skipping regression tests.")
        return

    test_files = sorted(glob.glob(os.path.join(test_dir, "*.txt")))
    if not test_files:
        print("No test files found in tests/")
        return

    passed = 0
    failed = 0

    for tf in test_files:
        print(f"Running test: {os.path.basename(tf)}")
        try:
            navs = {}
            with open(tf, "r", encoding="utf-8") as f:
                test_text = f.read()

            test_stats = NormalizerStats()
            test_text = normalize_input(test_text, test_stats)

            blocks = split_navarea_blocks(test_text)

            for block in blocks:
                block = block.strip()
                if not block:
                    continue
                nav_match = NAVAREA_HEADER_RE.search(block)
                if not nav_match:
                    continue
                navarea_name = nav_match.group(1)
                m_code = re.search(
                    r"NAVAREA\s+([A-Z0-9]+)\s+(\d+/\d+)",
                    navarea_name,
                    re.IGNORECASE,
                )
                if m_code:
                    nav_code = m_code.group(1).upper()
                else:
                    nav_code = re.sub(r"[^A-Z0-9]", "_", navarea_name.upper())

                if nav_code not in navs:
                    navs[nav_code] = create_container(nav_code)
                container = navs[nav_code]

                predict_complexity(block)
                partitioned = partition_navarea_block(block, navarea_name)

                if (
                    len(partitioned) == 1
                    and partitioned[0][1]["partition_type"] == "NONE"
                ):
                    msg_id = navarea_name
                    message = create_message(msg_id, metadata=partitioned[0][1])
                    container["messages"].append(message)
                    label_text = build_navarea_label(navarea_name)
                    process_block(
                        block, message, container, navarea_name, label_text, meta=None
                    )
                else:
                    for sub_block, meta in partitioned:
                        if meta["partition_type"] == "SECTION_NUMBER":
                            msg_id = f"{navarea_name} [Section {meta['partition_id']}]"
                        elif meta["partition_type"] == "LETTER":
                            msg_id = f"{navarea_name} [{meta['partition_id']}]"
                        elif meta["partition_type"] == "RIGLIST":
                            msg_id = f"{navarea_name} [RIG {meta['partition_id']}]"
                        else:
                            msg_id = navarea_name
                        message = create_message(msg_id, metadata=meta)
                        container["messages"].append(message)
                        label_text = build_navarea_label(navarea_name)
                        process_block(
                            sub_block,
                            message,
                            container,
                            navarea_name,
                            label_text,
                            meta=meta,
                        )

            total_objects = sum(
                len(m.get("areas", []))
                + len(m.get("lines", []))
                + len(m.get("circles", []))
                + len(m.get("labels", []))
                for nav in navs.values()
                for m in nav.get("messages", [])
            )
            if total_objects == 0:
                raise Exception("No objects generated")

            for nav_id, container in navs.items():
                export_furuno_modern(nav_id, container)
                export_furuno_legacy(nav_id, container)

            print(f"â Test passed: {os.path.basename(tf)}")
            passed += 1
        except Exception as e:
            print(f"â Test failed: {os.path.basename(tf)} - {e}")
            failed += 1

    print(f"\nRegression tests: {passed} passed, {failed} failed")


# -------------------- ARCHITECTURE SELF-CHECK --------------------
def run_architecture_checks():
    print("\nArchitecture self-check:")
    for factory in [
        create_container,
        create_message,
        create_area,
        create_line,
        create_circle,
        create_label,
    ]:
        print(f"  {factory.__name__}: {'OK' if callable(factory) else 'MISSING'}")
    print(f"  PROCESS_HANDLERS: {'OK' if PROCESS_HANDLERS else 'EMPTY'}")
    for adapter in [export_furuno_modern, export_furuno_legacy]:
        print(f"  {adapter.__name__}: {'OK' if callable(adapter) else 'MISSING'}")
    print("")


# -------------------- CONSOLE PROGRESS --------------------
class ConsoleProgress:
    """Small, Windows-safe progress indicator for normal CLI runs."""

    FRAMES = ("|", "/", "-", "\\")
    NON_TTY_INTERVAL = 25
    MIN_VISIBLE_SECONDS = 12.0
    ANIMATION_INTERVAL_SECONDS = 0.12
    FINISHING_STAGES = (
        "validating output",
        "preparing XML",
        "writing files",
        "readying console",
    )
    FINISHING_STAGE_SECONDS = 2.4

    def __init__(self, total):
        self.total = total
        self.current = 0
        self.interactive = sys.stdout.isatty()
        self.enabled = not DEBUG and total > 0
        self.last_width = 0
        self.last_stage = "starting"
        self.last_label = "starting"
        self.frame_index = 0
        self.started_at = time.monotonic() if self.enabled and self.interactive else None

    def update(self, current, label):
        if not self.enabled:
            return

        self.current = current
        self.last_stage = "reading"
        self.last_label = label
        self._render()

        if not self.interactive and (
            current == 1 or current == self.total or current % self.NON_TTY_INTERVAL == 0
        ):
            print(self._text(), flush=True)

    def stage(self, stage_name):
        if not self.enabled:
            return

        self.last_stage = stage_name
        self._render()

    def _text(self):
        return (
            f"{self.FRAMES[self.frame_index]} {self.last_stage} "
            f"[{self.current}/{self.total}] {self.last_label}"
        )

    def _render(self):
        text = self._text()
        if self.interactive:
            padded = text.ljust(self.last_width)
            print(f"\r{padded}", end="", flush=True)
            self.last_width = max(self.last_width, len(text))
        self.frame_index = (self.frame_index + 1) % len(self.FRAMES)

    def finish(self):
        if not self.enabled:
            return

        if self.interactive and self.started_at is not None:
            stage_index = 0
            stage_started_at = time.monotonic()
            self.last_stage = self.FINISHING_STAGES[stage_index]
            self._render()
            remaining = self.MIN_VISIBLE_SECONDS - (time.monotonic() - self.started_at)
            while remaining > 0:
                time.sleep(min(self.ANIMATION_INTERVAL_SECONDS, remaining))
                elapsed_stage_seconds = time.monotonic() - stage_started_at
                next_stage_index = min(
                    len(self.FINISHING_STAGES) - 1,
                    int(elapsed_stage_seconds / self.FINISHING_STAGE_SECONDS),
                )
                if next_stage_index != stage_index:
                    stage_index = next_stage_index
                    self.last_stage = self.FINISHING_STAGES[stage_index]
                self._render()
                remaining = self.MIN_VISIBLE_SECONDS - (
                    time.monotonic() - self.started_at
                )

        completed = f"Completed {self.current}/{self.total} NAVAREA messages."
        if self.interactive:
            print(f"\r{completed.ljust(self.last_width)}")
        elif self.current:
            print(completed)


# -------------------- MAIN ORCHESTRATION --------------------
def main():
    if "--test" in sys.argv:
        run_regression_tests()
        return
    if "--check-arch" in sys.argv:
        run_architecture_checks()
        return
    print()
    print("=" * 60)
    print(f" {APP_NAME} v{APP_VERSION}")
    print()
    print(" NAVAREA to Furuno UserChart Converter")
    print()
    print(f" Author : {APP_AUTHOR}")
    print("=" * 60)
    print()

    if len(sys.argv) > 1:
        sources = [arg for arg in sys.argv[1:] if not arg.startswith("--")]
    else:
        sources = sorted(glob.glob("*.txt"))

    if not sources:
        if os.path.isfile("input.txt"):
            sources = ["input.txt"]

    print("\n=== SOURCE DISCOVERY ===")
    print("SOURCES =", sources)
    print("========================\n")
  

    from source_intake import load_sources, combine_texts, report_summary

    reports = load_sources(sources)
    print(report_summary(reports))
    text = combine_texts(reports)

    if not text:
        print("[WARNING] No text loaded from sources. Export will be empty.")

    stats = NormalizerStats()
    text = normalize_input(text, stats)

    blocks = split_navarea_blocks(text)

    if DEBUG:
        print("\n========== XV DIAGNOSTICS ==========")
        print(f"[DIAG] SOURCE FILE: {sources}")
        print(f"[DIAG] TEXT LENGTH: {len(text)}")
        print(f"[DIAG] BLOCKS FOUND: {len(blocks)}")

        for i, block in enumerate(blocks[:20]):
            if block.strip():
                preview = block[:120].replace("\n", "\n")
                print(f"[DIAG] BLOCK {i}: {preview}")

                m = NAVAREA_HEADER_RE.search(block)

                if m:
                    print(
                        f"[DIAG] MESSAGE FOUND: NAVAREA {m.group(1)} {m.group(2)}"
                    )

        print("====================================\n")

    blocks = split_navarea_blocks(text)

    navs = {}
    total_work_blocks = sum(
        1
        for candidate in blocks
        if re.search(
            r"(NAVAREA\s+[A-ZIVXLC]+\s+\d+/\d+)",
            candidate,
            re.IGNORECASE,
        )
    )
    progress = ConsoleProgress(total_work_blocks)
    processed_blocks = 0

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        nav_match = NAVAREA_HEADER_RE.search(block)
        if not nav_match:
            continue

        navarea_name = nav_match.group(1)
        processed_blocks += 1
        progress.update(processed_blocks, navarea_name)
        m_code = re.search(
            r"NAVAREA\s+([A-Z0-9]+)\s+(\d+/\d+)", navarea_name, re.IGNORECASE
        )
        if m_code:
            nav_code = m_code.group(1).upper()
        else:
            nav_code = re.sub(r"[^A-Z0-9]", "_", navarea_name.upper())

        if nav_code not in navs:
            navs[nav_code] = create_container(nav_code)
        container = navs[nav_code]

        progress.stage("analyzing")
        predict_complexity(block)
        progress.stage("partitioning")
        partitioned = partition_navarea_block(block, navarea_name)

        progress.stage("building geometry")
        if len(partitioned) == 1 and partitioned[0][1]["partition_type"] == "NONE":
            msg_id = navarea_name
            message = create_message(msg_id, metadata=partitioned[0][1])
            container["messages"].append(message)
            label_text = build_navarea_label(navarea_name)
            process_block(
                block, message, container, navarea_name, label_text, meta=None
            )
        else:
            for sub_block, meta in partitioned:
                if meta["partition_type"] == "SECTION_NUMBER":
                    msg_id = f"{navarea_name} [Section {meta['partition_id']}]"
                elif meta["partition_type"] == "LETTER":
                    msg_id = f"{navarea_name} [{meta['partition_id']}]"
                elif meta["partition_type"] == "RIGLIST":
                    msg_id = f"{navarea_name} [RIG {meta['partition_id']}]"
                else:
                    msg_id = navarea_name

                message = create_message(msg_id, metadata=meta)
                container["messages"].append(message)
                label_text = build_navarea_label(navarea_name)
                process_block(
                    sub_block, message, container, navarea_name, label_text, meta=meta
                )

    if "--show-normalizer" in sys.argv:
        stats.report()

    progress.stage("exporting XML")
    all_stats = []
    for nav_id in sorted(navs.keys()):
        stats = export_navarea(nav_id, navs[nav_id])
        all_stats.append(stats)

    progress.stage("summarizing results")
    total_areas = total_lines = total_circles = total_labels = 0
    for nav_id, container in navs.items():
        total_areas += len(container["areas"])
        total_lines += len(container["lines"])
        total_circles += len(container["circles"])
        total_labels += len(container["labels"])

    progress.finish()

    print()
    print("===== TOTAL SUMMARY =====")
    print(f"Areas   : {total_areas}")
    print(f"Lines   : {total_lines}")
    print(f"Circles : {total_circles}")
    print(f"Labels  : {total_labels}")
    print(f"Objects : {total_areas + total_lines + total_circles + total_labels}")
    print()
    print("Conversion completed successfully.")
    print()
    print("Copyright (C) 2026 NAVAREA2UC. All Rights Reserved.")
    print()
    if getattr(sys, "frozen", False):
        input("\nPress ENTER to exit...")


if __name__ == "__main__":
    main()
