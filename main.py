from normalizer import normalize_input, NormalizerStats
import re
import sys
import glob
import os
import copy
import math
import xml.etree.ElementTree as ET
from xml.dom import minidom
from xml.sax.saxutils import escape

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

print("PROJECT_DIR =", PROJECT_DIR)

os.chdir(PROJECT_DIR)

print("NEW CWD =", os.getcwd())
print("PROJECT FILES =", os.listdir())


APP_NAME = "NAVAREA2UC"
APP_VERSION = "1.3.0"
APP_AUTHOR = "dr_livsi2004"

# -------------------- CONSTANTS --------------------
LEGACY_MAX_OBJECTS = 150
LEGACY_MAX_DESC = 999
LEGACY_MAX_CIRCLE_RANGE = 100.0
RISK_LOW_MAX = 500
RISK_MEDIUM_MAX = 2000
RISK_HIGH_MAX = 5000
MAX_VERTICES_PER_OBJECT = None
MAX_VERTICES_PER_MESSAGE = None
STYLE_SECURITY = 5

DEBUG = True


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
        r"(\d{1,3})[- ]+([\d.]+)\s*([NS])[\s,]+(\d{1,3})[- ]+([\d.]+)\s*([EW])",
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
    fallback = r"([+-]?\d+)-([\d.]+)([NS])\s+([+-]?\d+)-([\d.]+)([EW])"
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


def extract_sublabels(block):
    markers = list(
        re.finditer(r"(?:^|\n)\s*(?:\(([A-Z]{1,4})\)|([A-Z]{1,4})\.)\s*", block)
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
    if any(
        x in upper
        for x in [
            "WRECK",
            "SANK",
            "SUNK",
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
            "ROCKET LAUNCHING",
            "ICEBERG",
            "ICEBERGS",
        ]
    ):
        return "CHRED"
    if any(
        x in upper
        for x in ["FPSO", "FSO", "MODU", "RIG", "PLATFORM", "DRILL", "DRILLSHIP"]
    ):
        return "RESBL"
    return "NINFO"


def detect_check_danger(block):
    upper = block.upper()
    if any(
        x in upper
        for x in [
            "WAR RISK AREA",
            "MINE DANGER",
            "FIRING PRACTICE",
            "FIRING",
            "NAVAL OPERATIONS",
            "HAZARDOUS OPERATIONS",
            "ROCKET LAUNCHING",
            "ICEBERG",
            "ICEBERGS",
            "SUBMERGED WELLHEAD",
            "SUBMERGED OBJECT",
            "UNMARKED SUBMERGED WELLHEAD",
            "WRECK",
            "SANK",
            "SUNK",
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
            "BUOY",
            "LIGHT",
            "SPECIAL MARK",
            "SPECIAL-MARK",
            "MOORING",
            "MOORING BUOY",
            "MOORING BUOYS",
        ]
    ):
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
        "MESSAGING SERVICES UNAVAILABLE",
        "REMOVAL OF SUBMERGED LINES",
        "CHANNEL MARKING BUOY",
    ]
    return any(x in upper for x in triggers)


def is_buoy_group(text):
    return "BUOY GROUP" in text.upper()


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
    if not re.search(r"(?:^|\n)\s*\d+\.\s*", block):
        return None

    parts = re.split(r"\n\s*(\d+)\.\s*", block)
    sections = []
    for i in range(1, len(parts), 2):
        num = parts[i]
        text = parts[i + 1].strip()
        if not text:
            continue

        lines = text.split("\n")
        title = lines[0].strip()
        desc_lines = []
        for ln in lines:
            if re.search(r"\d{1,3}[- ]\d+[NS]", ln):
                break
            desc_lines.append(ln)

        description = " ".join(desc_lines).strip()
        if not description:
            description = title

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
def extract_riglist_entries(block):
    upper = block.upper()
    if not any(
        x in upper
        for x in ["RIGLIST", "RIG LIST", "MODU LIST", "MOBILE OFFSHORE DRILLING UNITS"]
    ):
        return None

    entries = re.split(r"\n\s*\d+.\s+", block)

    entries = [
        e.strip()
        for e in entries
        if e.strip()
        and re.search(
            r"\d{1,3}-\d+(?:.\d+)?[NS]\s+\d{1,3}-\d+(?:.\d+)?[EW]",
            e,
            re.I,
        )
    ]

    if len(entries) > 10:
        return entries

    rig_block = re.sub(r"\s+", " ", block)
    coord_pattern = re.compile(r"\d{1,3}-[\d.]+[NS]\s+\d{1,3}-[\d.]+[EW]", re.I)
    matches = list(coord_pattern.finditer(rig_block))
    if not matches:
        return [block.strip()]

    entries = []
    for i, m in enumerate(matches):
        start = m.start()
        next_start = matches[i + 1].start() if i + 1 < len(matches) else len(rig_block)
        notes_pos = rig_block.find("NOTES:", m.end())
        if notes_pos == -1:
            end = next_start
        else:
            end = min(next_start, notes_pos)
        if end < 0:
            end = len(rig_block)
        entry = rig_block[start:end].strip()
        if entry:
            entries.append(entry)

    return entries


def process_riglist_entry(entry_text, label_text, container, message):
    coord_pattern = re.compile(r"\d{1,3}-[\d.]+[NS]\s+\d{1,3}-[\d.]+[EW]", re.I)
    matches = list(coord_pattern.finditer(entry_text))
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

    obj = {
        "style": 5,
        "color": "RESBL",
        "checkDanger": 0,
        "text": label_text,
        "description": f"{rig_name} | {coord_text}",
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
    }


def create_area(name, description, coords, color, check_danger):
    return {
        "name": name,
        "description": description,
        "coords": coords,
        "color": color,
        "checkDanger": check_danger,
    }


def create_line(name, description, coords, color, check_danger):
    return {
        "name": name,
        "description": description,
        "coords": coords,
        "color": color,
        "checkDanger": check_danger,
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
def add_area(area_obj, container, message):
    container["areas"].append(area_obj)
    message["areas"].append(area_obj.copy())


def add_line(line_obj, container, message):
    container["lines"].append(line_obj)
    message["lines"].append(line_obj.copy())


def add_circle(circle_obj, container, message):
    container["circles"].append(circle_obj)
    message["circles"].append(circle_obj.copy())


def add_label(label_obj, container, message):
    container["labels"].append(label_obj)
    message["labels"].append(label_obj.copy())


# -------------------- CONTEXT & PARTITIONING --------------------
def build_partition_context(source_navarea, partition_type, partition_id, sub_block):
    return {
        "source_navarea": source_navarea,
        "partition_type": partition_type,
        "partition_id": partition_id,
        "context_id": f"{source_navarea}|{partition_type}|{partition_id}",
    }


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
        parts.append((entry, meta))
    return parts


def partition_navarea_block(block, navarea_name):
    if DEBUG:
        print(f"DEBUG: partition input block starts with: {block[:100]}")
    # RIGLIST
    rig_parts = partition_riglist(block, navarea_name)
    if rig_parts:
        return rig_parts

    # Numbered sections
    numbered_markers = list(re.finditer(r"(?:^|\n)\s*(\d+)\.\s*", block))
    if len(numbered_markers) > 1:
        parts = []
        for i, m in enumerate(numbered_markers):
            start = m.start()
            end = (
                numbered_markers[i + 1].start()
                if i + 1 < len(numbered_markers)
                else len(block)
            )
            sub_block = block[start:end].strip()
            if sub_block:
                meta = build_partition_context(
                    source_navarea=navarea_name,
                    partition_type="SECTION_NUMBER",
                    partition_id=m.group(1),
                    sub_block=sub_block,
                )
                parts.append((sub_block, meta))
        return parts

    # Lettered sections
    letter_markers = list(re.finditer(r"(?:^|\n)\s*([A-Z]{1,4})\.\s+", block))
    if len(letter_markers) > 1:
        parts = []
        for i, m in enumerate(letter_markers):
            start = m.start()
            end = (
                letter_markers[i + 1].start()
                if i + 1 < len(letter_markers)
                else len(block)
            )
            sub_block = block[start:end].strip()
            if sub_block:
                meta = build_partition_context(
                    source_navarea=navarea_name,
                    partition_type="LETTER",
                    partition_id=m.group(1),
                    sub_block=sub_block,
                )
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
    upper = block.upper()
    coords = extract_coordinates(block)
    clean_block = re.sub(r"-{5,}", " ", block)
    clean_block = re.sub(r"\s+", " ", clean_block)
    description = escape(clean_block.replace('"', "'").strip())
    if label_text is None:
        label_text = build_navarea_label(navarea_name)
    is_riglist = metadata and metadata.get("partition_type") == "RIGLIST"
    is_letter_partition = metadata and metadata.get("partition_type") == "LETTER"
    return {
        "block": block,
        "upper": upper,
        "coords": coords,
        "description": description,
        "navarea_name": navarea_name,
        "label_text": label_text,
        "metadata": metadata,
        "is_riglist": is_riglist,
        "is_letter_partition": is_letter_partition,
    }


# -------------------- SUBLABEL HELPER --------------------
def emit_sublabel_points(
    sublabels, ctx, container, message, style, color, check_danger
):
    for s in sublabels:
        if not s["coords"]:
            continue
        desc = escape(s["text"])
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
    "BOARDING",
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

LINE_PATTERNS = [
    "ALONG TRACKLINE",
    "TRACKLINE JOINING",
]


def has_area_pattern(text):
    normalized = re.sub(r"\s+", " ", text.upper())
    return any(pattern in normalized for pattern in AREA_PATTERNS)


def has_line_pattern(text):
    upper = text.upper()
    return any(pattern in upper for pattern in LINE_PATTERNS)


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

    any_processed = False
    for header, text in sections:
        coords = extract_coordinates(text)
        if not coords:
            continue

        upper_header = header.upper()

        if "ROUTE NO" in upper_header:
            if len(coords) >= 2:
                obj_name = f"{label_text} {header}"
                line_obj = create_line(
                    name=obj_name,
                    description=header,
                    coords=coords,
                    color=detect_color(ctx["block"]),
                    check_danger=detect_check_danger(ctx["block"]),
                )
                add_line(line_obj, container, message)
                mid = len(coords) // 2
                label_obj = create_label(
                    style=6,
                    color=detect_color(ctx["block"]),
                    check_danger=detect_check_danger(ctx["block"]),
                    text=obj_name,
                    description=header,
                    coord=coords[mid],
                )
                add_label(label_obj, container, message)
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
                    description="SOUTHERN WAITING AREA",
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
                    description="WAITING AREA NORTH AR 354",
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
                    description=header,
                    coords=coords,
                    color=detect_color(ctx["block"]),
                    check_danger=detect_check_danger(ctx["block"]),
                )
                add_line(line_obj, container, message)
                mid = len(coords) // 2
                label_obj = create_label(
                    style=6,
                    color=detect_color(ctx["block"]),
                    check_danger=detect_check_danger(ctx["block"]),
                    text=obj_name,
                    description=header,
                    coord=coords[mid],
                )
                add_label(label_obj, container, message)
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
    print("DEBUG: ICE SECTION DETECTED")

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
            add_line(line_obj, container, message)

            mid = len(coords) // 2
            label_obj = create_label(
                style=6,
                color="NINFO",
                check_danger=0,
                text=label,
                description="SEA ICE LIMIT",
                coord=coords[mid],
            )
            add_label(label_obj, container, message)
        return True

    if "ICEBERGS GREATER" in upper:
        normalized_block = _normalize_ice_coordinate_spacing(block)

        matches = list(ICEBERG_ENTRY_RE.finditer(normalized_block))

        print(f"DEBUG: ICE MATCH COUNT = {len(matches)}")

        for match in matches:
            print(
                "DEBUG: ICEBERG "
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
        if obj["type"] == "area":
            area_obj = create_area(
                name=ctx["label_text"],
                description=obj["description"],
                coords=obj["coords"],
                color=detect_color(ctx["block"]),
                check_danger=detect_check_danger(ctx["block"]),
            )
            add_area(area_obj, container, message)
        elif obj["type"] == "line":
            line_obj = create_line(
                name=ctx["label_text"],
                description=obj["description"],
                coords=obj["coords"],
                color=detect_color(ctx["block"]),
                check_danger=detect_check_danger(ctx["block"]),
            )
            add_line(line_obj, container, message)
            mid = len(obj["coords"]) // 2
            label_obj = create_label(
                style=6,
                color=detect_color(ctx["block"]),
                check_danger=detect_check_danger(ctx["block"]),
                text=ctx["label_text"],
                description=obj["description"],
                coord=obj["coords"][mid],
            )
            add_label(label_obj, container, message)
        elif obj["type"] == "label":
            label_obj = create_label(
                style=6,
                color=detect_color(ctx["block"]),
                check_danger=detect_check_danger(ctx["block"]),
                text=ctx["label_text"],
                description=obj["description"],
                coord=obj["coord"],
            )
            add_label(label_obj, container, message)

    return True


def handle_circle(ctx, container, message):
    debug("PROCESS: handle_circle")
    if ctx["is_riglist"]:
        return False
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

    # ------------------------------------------------------------------
    # 1. Grouped Areas / Named Areas
    # ------------------------------------------------------------------
    area_groups = extract_area_group_sections(ctx["block"])

    if len(area_groups) > 1:
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
    if not (
        "AREA BOUND BY" in ctx["upper"]
        or "BOUNDED BY" in ctx["upper"]
        or "AREA BOUNDED" in ctx["upper"]
        or "AREAS BOUNDED" in ctx["upper"]
        or "AREAS BOUND BY" in ctx["upper"]
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
    if has_area_pattern(ctx["block"]):
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

    LINE_GEOMETRY_TERMS = ["TRACKLINE", "JOINING", "PIPELINE", "CABLE", "ROUTE"]

    has_line_geometry = any(kw in ctx["upper"] for kw in LINE_GEOMETRY_TERMS)

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
        "CHANNEL",
        "TRACK LINE",
        "TRACK LINE JOINING",
    ]

    if not any(kw in ctx["upper"] for kw in ROUTE_KEYWORDS + TRACK_KEYWORDS):
        return False

    if len(ctx["coords"]) < 2:
        return False

    line_obj = create_line(
        name=ctx["label_text"],
        description=ctx["description"],
        coords=ctx["coords"],
        color=detect_color(ctx["block"]),
        check_danger=detect_check_danger(ctx["block"]),
    )
    add_line(line_obj, container, message)

    mid = len(ctx["coords"]) // 2
    label_obj = create_label(
        style=6,
        color=detect_color(ctx["block"]),
        check_danger=detect_check_danger(ctx["block"]),
        text=ctx["label_text"],
        description=ctx["description"],
        coord=ctx["coords"][mid],
    )
    add_label(label_obj, container, message)

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
                    description=escape(s["text"]),
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
    ("CHANNEL_MARKING", re.compile(r"\bCHANNEL\s+MARKING\s+BUOYS?\b", re.IGNORECASE)),
    ("CHANNEL", re.compile(r"\bCHANNEL\s+BUOYS?\b", re.IGNORECASE)),
    ("FAIRWAY", re.compile(r"\bFAIRWAY\s+BUOYS?\b", re.IGNORECASE)),
    ("SAFE_WATER", re.compile(r"\bSAFE\s+WATER\s+BUOYS?\b", re.IGNORECASE)),
    ("SPECIAL_MARK", re.compile(r"\bSPECIAL\s+MARK\s+BUOYS?\b", re.IGNORECASE)),
    ("BUOY_NO", re.compile(r"\bBUOY\s+NO\b", re.IGNORECASE)),
    ("BUOY_GROUP", re.compile(r"\bBUOY\s+GROUP\b", re.IGNORECASE)),
    ("BUOY", re.compile(r"\bBUOYS?\b", re.IGNORECASE)),
]

BUOY_STATUS_PATTERNS = [
    ("UNLIT", re.compile(r"\bUNLIT\b", re.IGNORECASE)),
    ("MISSING", re.compile(r"\bMISSING\b", re.IGNORECASE)),
    ("OFF_AIR", re.compile(r"\bOFF\s+AIR\b", re.IGNORECASE)),
    ("REMOVED", re.compile(r"\bREMOVED\b", re.IGNORECASE)),
    ("RETRIEVED", re.compile(r"\bRETRIEVED\b", re.IGNORECASE)),
    ("SHIFTED", re.compile(r"\bSHIFTED\b", re.IGNORECASE)),
]


def classify_buoy(text):
    upper = text.upper()

    # LIGHT UNLIT / LIGHTHOUSE UNLIT — это AtoN, не buoy
    if (
        "UNLIT" in upper
        and "BUOY" not in upper
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

    status = "ACTIVE"
    for name, pattern in BUOY_STATUS_PATTERNS:
        if pattern.search(upper):
            status = name
            break

    return {
        "has_buoy": True,
        "subtype": subtype,
        "status": status,
    }


def buoy_style_color(check_danger, status):
    """
    ÐÐ¾Ð·Ð²ÑÐ°ÑÐ°ÐµÑ (style, color, checkDanger) Ð´Ð»Ñ Ð±ÑÑÐ².

    Style 4 Ð¾Ð±ÑÐ·Ð°ÑÐµÐ»ÐµÐ½ Ð´Ð»Ñ buoy display.

    ACTIVE:
        S52colorcode = CHYLW

    ÐÑÑ Ð¾ÑÑÐ°Ð»ÑÐ½Ð¾Ðµ:
        S52colorcode = CHBRN

    ÐÑÐ°ÑÐ½ÑÐ¹ Ð½Ðµ Ð¸ÑÐ¿Ð¾Ð»ÑÐ·ÑÐµÑÑÑ.
    """
    style = 4

    if status == "ACTIVE":
        color = "CHYLW"
    else:
        color = "CHBRN"

    return style, color, 0


def build_buoy_label_description(ctx, coord, status):
    nav_summary = sanitize_xml_attribute(ctx.get("description", ""))

    # ÐÑÐµÐ¼ Ð¿ÐµÑÐ²ÑÑ ÐºÐ¾Ð¾ÑÐ´Ð¸Ð½Ð°ÑÑ Ð¸ Ð¾Ð±ÑÐµÐ·Ð°ÐµÐ¼ ÑÐµÐºÑÑ Ð´Ð¾ Ð½ÐµÑ
    coord_pattern = re.compile(
        r"\d{1,3}-\d{1,2}(?:\.\d+)?[NS]\s+\d{1,3}-\d{1,2}(?:\.\d+)?[EW]", re.IGNORECASE
    )
    m = coord_pattern.search(nav_summary)

    if m:
        nav_summary = nav_summary[: m.start()].rstrip()
        nav_summary = re.sub(r"[(\[\s,;:-]+$", "", nav_summary)

    if not nav_summary:
        nav_summary = sanitize_xml_attribute(ctx.get("navarea_name", ""))

    # ÐÑÐ»Ð¸ Ð±ÑÐ¹ Ð´ÐµÐ³ÑÐ°Ð´Ð¸ÑÐ¾Ð²Ð°Ð», Ð´Ð¾Ð±Ð°Ð²Ð»ÑÐµÐ¼ ÑÑÐ°ÑÑÑ, Ð¿Ð¾ÑÐ¾Ð¼Ñ ÑÑÐ¾ Ð² Ð¸ÑÑÐ¾Ð´Ð½Ð¾Ð¼
    # ÑÐµÐºÑÑÐµ Ð¾Ð½ Ð¾Ð±ÑÑÐ½Ð¾ Ð½Ð°ÑÐ¾Ð´Ð¸ÑÑÑ Ð¿Ð¾ÑÐ»Ðµ ÐºÐ¾Ð¾ÑÐ´Ð¸Ð½Ð°ÑÑ Ð¸ Ð±ÑÐ» Ð¾Ð±ÑÐµÐ·Ð°Ð½.
    if status and status != "ACTIVE":
        nav_summary = f"{nav_summary} {status}"

    coord_text = f"{coord[0]:.6f} {coord[1]:.6f}"
    return f"{nav_summary} | {coord_text}"


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

    if (
        "UNLIT" in upper
        and "BUOY" not in upper
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

    style, color, check_danger = buoy_style_color(
        check_danger=detect_check_danger(ctx["block"]),
        status=buoy["status"],
    )

    for coord in ctx["coords"]:
        desc = build_buoy_label_description(ctx, coord, buoy["status"])

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
    handle_mixed_geometry_package,
    handle_structured_sections,
    handle_circle,
    handle_bounding_box,
    handle_area,
    handle_no_anchor,
    handle_buoy_semantics,  # NEW
    handle_trackline,
    handle_sublabels,
    handle_lettered_sections,
    handle_riglist,
    handle_multipoint,
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
    if DEBUG:
        print(f"DEBUG: processing block with {len(ctx['coords'])} coords")
    for handler in PROCESS_HANDLERS:
        if handler(ctx, container, message):
            handler_name = handler.__name__
            print(f"MATCH: {handler_name}")
            return


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
            desc = obj_data.get("description", "")
        elif obj_type == "label":
            name = obj_data.get("text", f"NAV {nav_id}")
            desc = obj_data.get("description", name)
        else:  # line, circle, clearingLine
            name = obj_data.get("name", "")
            desc = obj_data.get("description", "")

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
            for idx, (lat, lon) in enumerate(area["coords"], start=1):
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
                    f"WARNING: Circle range {range_val} NM exceeds legacy limit (100 NM). Will be reduced to 100 NM."
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
                f'description="{xml_attr(line["description"])}">'
            )
            xml.append("<position>")
            for idx, (lat, lon) in enumerate(line["coords"], start=1):
                xml.append(
                    f'<vertex id="{idx}" latitude="{lat:.6f}" longitude="{lon:.6f}"/>'
                )
            xml.append("</position>")
            xml.append('<attribute lineType="2" linkedDocument=""/>')
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
                f'description="{xml_attr(area["description"])}">'
            )
            xml.append("<position>")
            for idx, (lat, lon) in enumerate(area["coords"], start=1):
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
                f'description="{xml_attr(circle["description"])}">'
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
                f'description="{xml_attr(label["description"])}">'
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

    # Container diagnostics
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

            blocks = re.split(
                r"(?=NAVAREA\s+[A-ZIVXLC]+\s+\d+/\d+)", test_text, flags=re.IGNORECASE
            )

            for block in blocks:
                block = block.strip()
                if not block:
                    continue
                nav_match = re.search(
                    r"(NAVAREA\s+[A-ZIVXLC]+\s+\d+/\d+)", block, re.IGNORECASE
                )
                if not nav_match:
                    continue
                navarea_name = nav_match.group(1)
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
        sources = sys.argv[1:]
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

    print("\n========== XV DIAGNOSTICS ==========")
    print(f"[DIAG] SOURCE FILE: {sources}")

    print(f"[DIAG] TEXT LENGTH: {len(text)}")

    blocks = re.split(r"(?=NAVAREA\s+[A-ZIVXLC]+\s+\d+/\d+)", text, flags=re.IGNORECASE)

    print(f"[DIAG] BLOCKS FOUND: {len(blocks)}")

    for i, block in enumerate(blocks[:20]):
        if block.strip():
            preview = block[:120].replace("\n", "\n")
            print(f"[DIAG] BLOCK {i}: {preview}")

            m = re.search(
                r"NAVAREA\s+([A-ZIVXLC]+)\s+(\d+/\d+)", block, flags=re.IGNORECASE
            )

            if m:
                print(f"[DIAG] MESSAGE FOUND: NAVAREA {m.group(1)} {m.group(2)}")

    print("====================================\n")

    blocks = re.split(r"(?=NAVAREA\s+[A-ZIVXLC]+\s+\d+/\d+)", text, flags=re.IGNORECASE)

    navs = {}

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        nav_match = re.search(
            r"(NAVAREA\s+[A-ZIVXLC]+\s+\d+/\d+)", block, re.IGNORECASE
        )
        if not nav_match:
            continue

        navarea_name = nav_match.group(1)
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

        predict_complexity(block)
        partitioned = partition_navarea_block(block, navarea_name)

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

    all_stats = []
    for nav_id in sorted(navs.keys()):
        stats = export_navarea(nav_id, navs[nav_id])
        all_stats.append(stats)

    total_areas = total_lines = total_circles = total_labels = 0
    for nav_id, container in navs.items():
        total_areas += len(container["areas"])
        total_lines += len(container["lines"])
        total_circles += len(container["circles"])
        total_labels += len(container["labels"])

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
    print("Copyright Â© 2026 All Rights Reserved.")
    print()
    if getattr(sys, "frozen", False):
        input("\nPress ENTER to exit...")


if __name__ == "__main__":
    main()
