from pathlib import Path


PAGE_W, PAGE_H = 595.28, 841.89
OUTPUT = Path(__file__).resolve().parents[1] / "public" / "NAVAREA2UC-ECDIS-Quick-Reference.pdf"

ROWS = [
    ("i", "Information / status notice", "Orange", "Warning", "Light unlit, reported depths, moorings, communication or service notices.", "information"),
    ("i", "Drifting hazard", "Red", "Danger", "Drifting objects or hazards, shown with the separate (i) symbol.", "drifting"),
    ("i", "Offshore activity / deployment", "Blue", "Non-danger", "An offshore operation or deployment notice shown as an information symbol.", "offshore"),
    ("triangle", "Active / established navigation buoy", "Yellow", "Non-danger", "An active, established navigation buoy or other aid at one position.", "buoy"),
    ("triangle", "Degraded / missing navigation aid", "Orange", "Warning", "A navigation aid reported degraded, missing, unlit or otherwise changed from its established state.", "degraded"),
    ("triangle", "Isolated danger buoy", "Red", "Danger", "A red isolated-danger mark at a hazard position.", "isolated-danger"),
    ("diamond", "Offshore structure", "Blue", "Non-danger", "FPSO, FSO, MODU, offshore rig, platform or drillship.", "platform"),
    ("diamond", "Pilot station", "Magenta", "Non-danger", "A pilot station shown with a magenta diamond.", "pilot"),
    ("diamond", "Security incident", "Red", "Danger", "Piracy, armed robbery or another security incident at a reported position.", "security"),
    ("point", "Danger point", "Red", "Danger", "Wreck, obstruction, aground vessel, derelict, submerged object or iceberg marker.", "danger"),
    ("Line", "Navigation or operational line", "Orange", "Warning", "Recommended route, trackline, cable, pipeline, channel or survey line.", "line"),
    ("Line", "Danger line", "Red", "Danger", "An iceberg danger trackline or another explicitly dangerous operational line.", "iceberg"),
    ("Area", "Non-danger area", "Orange", "Warning", "Survey, work, anchorage, waiting, holding, temporary-stay or no-anchoring area.", "area"),
    ("Area", "Danger area", "Red", "Danger", "War-risk, mine-danger, firing, military, prohibited, exclusion or other hazard area.", "firing"),
    ("Circle", "Scientific / survey radius", "Orange", "Warning", "Scientific or survey activity with a published centre and distance.", "survey-circle"),
    ("Circle", "Radius warning", "Red", "Danger", "A warning, rocket-launch or explosives radius with a published centre and distance.", "circle"),
]

COLORS = {
    "navy": (0.05, 0.13, 0.25),
    "navy2": (0.08, 0.21, 0.33),
    "ink": (0.08, 0.16, 0.23),
    "muted": (0.29, 0.40, 0.47),
    "line": (0.83, 0.88, 0.91),
    "panel": (0.97, 0.985, 0.99),
    "rule": (0.93, 0.95, 0.96),
    "yellow": (0.90, 0.67, 0.15),
    "orange": (0.82, 0.48, 0.08),
    "red": (0.78, 0.13, 0.19),
    "blue": (0.18, 0.42, 0.67),
    "magenta": (0.67, 0.20, 0.57),
    "white": (1, 1, 1),
}


def escaped(value):
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def paint(color, stroke=False):
    r, g, b = COLORS[color]
    return f"{r:.3f} {g:.3f} {b:.3f} {'RG' if stroke else 'rg'}"


def text(x, y, value, size, color="ink", bold=False):
    font = "F2" if bold else "F1"
    return f"{paint(color)} BT /{font} {size} Tf {x:.2f} {y:.2f} Td ({escaped(value)}) Tj ET"


def rectangle(x, y, width, height, fill=None, stroke=None, line_width=1):
    commands = []
    if fill:
        commands.append(paint(fill))
    if stroke:
        commands.extend((paint(stroke, True), f"{line_width:.2f} w"))
    operator = "B" if fill and stroke else "f" if fill else "S"
    commands.append(f"{x:.2f} {y:.2f} {width:.2f} {height:.2f} re {operator}")
    return "\n".join(commands)


def rule(x1, y1, x2, y2, color="line", width=0.7, dash=None):
    commands = [paint(color, True), f"{width:.2f} w"]
    if dash:
        commands.append(f"[{dash[0]} {dash[1]}] 0 d")
    commands.append(f"{x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S")
    commands.append("[] 0 d")
    return "\n".join(commands)


def circle_path(cx, cy, radius, color, width=1.5, filled=False):
    k = 0.5522848 * radius
    commands = [paint(color, not filled), f"{width:.2f} w"]
    commands.extend(
        (
            f"{cx + radius:.2f} {cy:.2f} m",
            f"{cx + radius:.2f} {cy + k:.2f} {cx + k:.2f} {cy + radius:.2f} {cx:.2f} {cy + radius:.2f} c",
            f"{cx - k:.2f} {cy + radius:.2f} {cx - radius:.2f} {cy + k:.2f} {cx - radius:.2f} {cy:.2f} c",
            f"{cx - radius:.2f} {cy - k:.2f} {cx - k:.2f} {cy - radius:.2f} {cx:.2f} {cy - radius:.2f} c",
            f"{cx + k:.2f} {cy - radius:.2f} {cx + radius:.2f} {cy - k:.2f} {cx + radius:.2f} {cy:.2f} c",
            "f" if filled else "S",
        )
    )
    return "\n".join(commands)


def marker(kind, cx, cy, color):
    commands = [paint(color, True), "1.15 w"]
    if kind in ("information", "drifting", "offshore"):
        commands.extend((f"{cx - 7:.2f} {cy - 7:.2f} 14 14 re S", text(cx - 2.7, cy - 4.1, "i", 10, color)))
    elif kind in ("buoy", "degraded", "isolated-danger"):
        commands.append(paint(color))
        commands.append(f"{cx:.2f} {cy + 8:.2f} m {cx - 8:.2f} {cy - 7:.2f} l {cx + 8:.2f} {cy - 7:.2f} l h f")
    elif kind in ("platform", "pilot", "security"):
        commands.append(paint(color))
        commands.append(f"{cx:.2f} {cy + 9:.2f} m {cx + 9:.2f} {cy:.2f} l {cx:.2f} {cy - 9:.2f} l {cx - 9:.2f} {cy:.2f} l h f")
    elif kind == "danger":
        commands.append(circle_path(cx, cy, 5, color, filled=True))
    elif kind in ("line", "iceberg"):
        commands.extend((f"[{4 if kind == 'line' else 2} 2] 0 d", f"{cx - 9:.2f} {cy:.2f} m {cx + 9:.2f} {cy:.2f} l S", "[] 0 d"))
    elif kind in ("area", "firing"):
        commands.extend((f"[{3 if kind == 'area' else 2} 2] 0 d", f"{cx - 8:.2f} {cy - 7:.2f} 16 14 re S", "[] 0 d"))
    elif kind in ("survey-circle", "circle"):
        commands.append(circle_path(cx, cy, 8, color))
    return "\n".join(commands)


def build_content():
    commands = [rectangle(0, 0, PAGE_W, PAGE_H, fill="white")]
    commands.extend(
        (
            text(36, PAGE_H - 54, "NAVAREA", 25, "navy", True),
            text(161, PAGE_H - 53.5, "2", 25, "yellow", True),
            text(174, PAGE_H - 54, "UC", 25, "navy", True),
            text(36, PAGE_H - 76, "ECDIS USERCHART / VISUAL QUICK REFERENCE / V1.3.0", 7.5, "blue", True),
            text(407, PAGE_H - 54, "PRINT EDITION", 7.5, "muted", True),
            rule(36, PAGE_H - 91, PAGE_W - 36, PAGE_H - 91, "yellow", 2.2),
            text(36, PAGE_H - 115, "Read the chart at a glance.", 17, "ink", True),
            text(36, PAGE_H - 132, "Symbols, colours and shapes used by the NAVAREA2UC export.", 8.5, "muted"),
        )
    )

    panel_x, panel_y, panel_w, panel_h = 36, 60, PAGE_W - 72, 660
    commands.extend(
        (
            rectangle(panel_x, panel_y, panel_w, panel_h, fill="panel", stroke="line", line_width=0.8),
            rectangle(panel_x, panel_y + panel_h - 36, panel_w, 36, fill="navy"),
            text(panel_x + 15, panel_y + panel_h - 15, "ENGINE OUTPUT QUICK REFERENCE", 9, "white", True),
            text(panel_x + panel_w - 126, panel_y + panel_h - 15, "REVIEWABLE BY DESIGN", 6.6, "yellow", True),
        )
    )

    row_top = panel_y + panel_h - 36
    row_height = 33.5
    for index, (element, name, color_name, status, meaning, kind) in enumerate(ROWS):
        top = row_top - index * row_height
        bottom = top - row_height
        center = bottom + row_height / 2 + 1
        color = color_name.lower()
        commands.extend(
            (
                marker(kind, panel_x + 25, center, color),
                text(panel_x + 49, top - 13, f"Element ({element})", 8.4, "ink", True),
                text(panel_x + 127, top - 13, name, 8.4, "navy2", True),
                text(panel_x + 127, top - 25, meaning, 6.7, "muted"),
                text(panel_x + panel_w - 111, top - 13, color_name, 7.0, color, True),
                text(panel_x + panel_w - 45, top - 13, status.upper(), 5.9, "red" if status == "Danger" else "orange" if status == "Warning" else "blue", True),
            )
        )
        if index < len(ROWS) - 1:
            commands.append(rule(panel_x + 12, bottom, panel_x + panel_w - 12, bottom, "line", 0.5))

    rules_y = panel_y + 13
    commands.extend(
        (
            rectangle(panel_x + 12, panel_y, panel_w - 24, 59, fill="rule"),
            text(panel_x + 24, panel_y + 45, "SAFETY RULES", 7.2, "orange", True),
            text(panel_x + 24, panel_y + 33, "Circle only when the source publishes both a centre and a radius. FROM / TO movement stays as separate points.", 6.8, "muted"),
            text(panel_x + 24, panel_y + 21, "Operation-only text without usable geometry creates no chart object.", 6.8, "muted"),
            text(panel_x + 24, panel_y + 9, "Colours and styles shown are the author's default settings; users can change the colour code and styles at their discretion.", 6.8, "muted"),
            text(36, 31, "NAVAREA2UC  |  Any Source. Any Format. Any ECDIS.", 7, "muted"),
            text(PAGE_W - 145, 31, "A4 / PRINT READY", 7, "blue", True),
        )
    )
    return ("\n".join(commands) + "\n").encode("latin-1")


def write_pdf(content):
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_W:.2f} {PAGE_H:.2f}] /Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 6 0 R >>".encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"endstream",
    ]
    pdf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(pdf))
        pdf.extend(f"{number} 0 obj\n".encode())
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")
    xref = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode())
    pdf.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(pdf)


if __name__ == "__main__":
    write_pdf(build_content())
    print(f"created={OUTPUT}")
    print(f"bytes={OUTPUT.stat().st_size}")