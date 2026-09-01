import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import main
from source_intake import load_source


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "NAVAREA IX - PAKISTAN.txt"


def load_navarea_block(source_path, navarea_name):
    report = load_source(str(source_path))
    if report.text is None:
        raise AssertionError(f"Could not decode {source_path}: {report.error}")
    normalized = main.normalize_input(report.text, main.NormalizerStats())
    for block in main.split_navarea_blocks(normalized):
        if block.lstrip().upper().startswith(navarea_name.upper()):
            return block.strip()
    raise AssertionError(f"Could not find {navarea_name}")


def process_case(source_path, navarea_name, section=None):
    block = load_navarea_block(source_path, navarea_name)
    parts = main.partition_navarea_block(block, navarea_name)
    if section is not None:
        selected = [
            (sub_block, metadata)
            for sub_block, metadata in parts
            if metadata["partition_type"] == "SECTION_NUMBER"
            and metadata["partition_id"] == section
        ]
        if not selected:
            raise AssertionError(f"Could not find Section {section} in {navarea_name}")
        parts = selected
    elif len(parts) != 1:
        raise AssertionError(
            f"{navarea_name} requires an explicit section in this regression"
        )

    nav_id = navarea_name.removeprefix("NAVAREA ")
    container = main.create_container(nav_id.split()[0])
    messages = []
    for sub_block, metadata in parts:
        message_id = navarea_name
        if metadata["partition_type"] == "SECTION_NUMBER":
            message_id = f"{navarea_name} [Section {metadata['partition_id']}]"
        message = main.create_message(message_id, metadata=metadata)
        main.process_block(
            sub_block,
            message,
            container,
            nav_id,
            label_text=main.build_navarea_label(navarea_name),
            meta=metadata,
        )
        messages.append(message)
    return messages, container


def xml_area_snapshot(xml_text):
    root = ET.fromstring(xml_text)
    areas = root.findall("./areas/area")
    lines = root.findall("./lines/line")
    area_vertices = []
    if areas:
        area_vertices = [
            (
                float(vertex.attrib["latitude"]),
                float(vertex.attrib["longitude"]),
            )
            for vertex in areas[0].findall("./position/vertex")
        ]
    area_type = areas[0].find("./type") if areas else None
    area_display = areas[0].find("./display") if areas else None
    return {
        "area_count": len(areas),
        "line_count": len(lines),
        "vertices": area_vertices,
        "checkDanger": (
            int(area_type.attrib["checkDanger"]) if area_type is not None else None
        ),
        "color": (
            area_display.attrib["S52colorcode"]
            if area_display is not None
            else None
        ),
    }


class BoundedAreaExpectationRealityTests(unittest.TestCase):
    def assert_bounded_area_case(
        self,
        source_name,
        navarea_name,
        section,
        expected_unique_vertices,
        expected_coords,
    ):
        messages, container = process_case(ROOT / source_name, navarea_name, section)
        message = messages[0]

        self.assertEqual(len(message["areas"]), 1, navarea_name)
        self.assertEqual(len(message["lines"]), 0, navarea_name)
        self.assertEqual(len(message["circles"]), 0, navarea_name)
        self.assertEqual(len(message["labels"]), 0, navarea_name)

        area = message["areas"][0]
        self.assertEqual(area["color"], "NINFO", navarea_name)
        self.assertEqual(area["checkDanger"], 0, navarea_name)
        self.assertEqual(area["coords"][:-1], expected_coords, navarea_name)
        self.assertEqual(
            len(area["coords"]) - 1,
            expected_unique_vertices,
            navarea_name,
        )
        self.assertEqual(area["coords"][0], area["coords"][-1], navarea_name)

        nav_id = navarea_name.removeprefix("NAVAREA ").split()[0]
        modern = xml_area_snapshot(main.export_furuno_modern(nav_id, container))
        legacy = xml_area_snapshot(
            main.generate_legacy_xml_from_messages(
                nav_id, messages, part_index=1, total_parts=1
            )
        )
        for snapshot in (modern, legacy):
            self.assertEqual(snapshot["area_count"], 1, navarea_name)
            self.assertEqual(snapshot["line_count"], 0, navarea_name)
            self.assertEqual(snapshot["vertices"], expected_coords)
            self.assertEqual(len(snapshot["vertices"]), expected_unique_vertices)
            self.assertEqual(len(snapshot["vertices"]), len(set(snapshot["vertices"])))
            self.assertEqual(snapshot["checkDanger"], 0, navarea_name)
        self.assertEqual(modern["color"], "NINFO", navarea_name)
        # Furuno legacy v1.0 carries area color in the canonical object model
        # and checkDanger in <type>; unlike modern v1.3 it has no <display>
        # element for areas.
        self.assertIsNone(legacy["color"], navarea_name)

    def test_ix_299_explicit_following_bounded_area_wins_over_section_route(self):
        expected = [
            (26.167167, 50.6595),
            (26.1675, 50.662),
            (26.167833, 50.666667),
            (26.166333, 50.671333),
            (26.162833, 50.673667),
            (26.162167, 50.672833),
            (26.166667, 50.665),
            (26.165833, 50.662),
            (26.164667, 50.659667),
            (26.165833, 50.659167),
        ]
        self.assert_bounded_area_case(
            "NAVAREA IX - PAKISTAN.txt",
            "NAVAREA IX 299/2024",
            "1",
            10,
            expected,
        )

    def test_ix_246_bounded_area_wins_over_single_point_fallback(self):
        expected = [
            (26.699833, 51.887667),
            (26.699, 52.0125),
            (26.6275, 52.012),
            (26.628333, 51.887167),
        ]
        self.assert_bounded_area_case(
            "NAVAREA IX - PAKISTAN.txt",
            "NAVAREA IX 246/2025",
            None,
            4,
            expected,
        )

    def test_ix_379_restricted_bounded_area_wins_over_sublabels(self):
        expected = [
            (25.133167, 55.1795),
            (25.138167, 55.177167),
            (25.149667, 55.187),
            (25.1485, 55.189667),
        ]
        self.assert_bounded_area_case(
            "NAVAREA IX - PAKISTAN.txt",
            "NAVAREA IX 379/2025",
            "1",
            4,
            expected,
        )

    def test_ix_48_implicit_routes_bounded_by_remains_area_control(self):
        expected = [
            (26.201, 50.660167),
            (26.185833, 50.654),
            (26.168333, 50.653333),
            (26.163167, 50.652333),
        ]
        self.assert_bounded_area_case(
            "NAVAREA IX - PAKISTAN.txt",
            "NAVAREA IX 48/2024",
            "1",
            4,
            expected,
        )

    def test_self_intersecting_area_cases_are_repaired_without_losing_geometry(self):
        cases = [
            ("NAVAREA IX - PAKISTAN.txt", "NAVAREA IX 94/2024", None),
            ("NAVAREA IX - PAKISTAN.txt", "NAVAREA IX 289/2024", None),
            ("NAVAREA IX - PAKISTAN.txt", "NAVAREA IX 254/2026", "1"),
            ("NAVAREA XIII - RUSSIA.txt", "NAVAREA XIII 42/2026", None),
            ("NAVAREA XVIII - CANADA.txt", "NAVAREA XVIII 87/2026", "1"),
        ]

        for source_name, navarea_name, section in cases:
            messages, container = process_case(
                ROOT / source_name, navarea_name, section
            )
            message = messages[0]
            diagnostics = {
                entry.get("code") for entry in message.get("diagnostics", [])
            }
            self.assertIn("GEOMETRY_ORDER_REPAIRED", diagnostics, navarea_name)
            self.assertNotIn("GEOMETRY_SELF_INTERSECTION", diagnostics, navarea_name)
            self.assertFalse(message.get("geometry_rejected"), navarea_name)
            self.assertEqual(len(message["areas"]), 1, navarea_name)
            self.assertFalse(message["lines"], navarea_name)
            self.assertFalse(message["circles"], navarea_name)
            area_coords = message["areas"][0]["coords"]
            self.assertEqual(area_coords[0], area_coords[-1], navarea_name)
            area = message["areas"][0]
            self.assertTrue(area["geometry_repaired"], navarea_name)
            self.assertEqual(area["repair_method"], "centroid_angle", navarea_name)
            raw_coords = area["raw_coords"]
            self.assertEqual(
                message["diagnostics"][0]["raw_coords"],
                raw_coords,
                navarea_name,
            )
            self.assertEqual(
                set(raw_coords[:-1]),
                set(area_coords[:-1]),
                navarea_name,
            )
            self.assertEqual(
                message["geometry_audit"][0]["event"],
                "area_geometry_repaired",
                navarea_name,
            )
            self.assertEqual(
                message["geometry_audit"][0]["raw_coords"],
                raw_coords,
                navarea_name,
            )
            self.assertEqual(
                message["geometry_audit"][0]["repaired_coords"],
                area_coords,
                navarea_name,
            )
            self.assertFalse(
                main.has_self_intersection(area_coords),
                navarea_name,
            )
            expected_xml_vertices = [
                (round(latitude, 6), round(longitude, 6))
                for latitude, longitude in area_coords[:-1]
            ]
            nav_id = navarea_name.removeprefix("NAVAREA ").split()[0]
            for xml in (
                main.export_furuno_modern(nav_id, container),
                main.generate_legacy_xml_from_messages(
                    nav_id, messages, part_index=1, total_parts=1
                ),
            ):
                snapshot = xml_area_snapshot(xml)
                self.assertEqual(snapshot["area_count"], 1, navarea_name)
                self.assertEqual(snapshot["line_count"], 0, navarea_name)
                self.assertEqual(
                    snapshot["vertices"],
                    expected_xml_vertices,
                    navarea_name,
                )
                self.assertEqual(
                    len(snapshot["vertices"]),
                    len(set(snapshot["vertices"])),
                    navarea_name,
                )
                self.assertEqual(snapshot["checkDanger"], 0, navarea_name)

    def test_failed_area_repair_keeps_vertices_as_unconnected_review_points(self):
        message = main.create_message("TEST 1/2026")
        container = main.create_container("TEST")
        area = main.create_area(
            name="NAV TEST 1/2026",
            description="AREA BOUND BY",
            coords=[(1.0, 2.0), (1.5, 2.5)],
            color="CHRED",
            check_danger=1,
        )

        self.assertFalse(main.add_area(area, container, message))
        self.assertFalse(message["areas"])
        self.assertFalse(message["lines"])
        self.assertFalse(message["circles"])
        self.assertEqual(
            [label["coord"] for label in message["labels"]],
            [(1.0, 2.0), (1.5, 2.5)],
        )
        self.assertTrue(message["geometry_rejected"])
        self.assertIn(
            "GEOMETRY_TOO_FEW_VERTICES",
            {entry["code"] for entry in message["diagnostics"]},
        )
        self.assertEqual(
            message["diagnostics"][0]["fallback"],
            "REFERENCE_POINTS",
        )
        self.assertEqual(
            message["geometry_audit"][0]["event"],
            "area_geometry_review_fallback",
        )
