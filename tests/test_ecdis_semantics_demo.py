import xml.etree.ElementTree as ET
import unittest
from pathlib import Path

from examples.generate_ecdis_semantics_demo import (
    DEMO_NAV_ID,
    OUTPUT_PATH,
    build_demo_container,
    render_demo_xml,
)


ROOT = Path(__file__).resolve().parents[1]


class EcdisSemanticsDemoTests(unittest.TestCase):
    def test_demo_container_has_expected_semantic_object_counts(self):
        container = build_demo_container()

        self.assertEqual(len(container["lines"]), 4)
        self.assertEqual(len(container["areas"]), 3)
        self.assertEqual(len(container["circles"]), 1)
        self.assertEqual(len(container["labels"]), 13)
        self.assertEqual(
            len(container["lines"])
            + len(container["areas"])
            + len(container["circles"])
            + len(container["labels"]),
            21,
        )

    def test_demo_xml_has_all_modern_furuno_sections_and_semantics(self):
        xml = render_demo_xml()
        root = ET.fromstring(xml)

        self.assertEqual(root.tag, "userchart")
        self.assertEqual(root.attrib["name"], f"NAVAREA {DEMO_NAV_ID} IMPORT")
        self.assertEqual(root.attrib["version"], "1.3")
        self.assertIn("<!-- Areas: closed zones with boundaries -->", xml)
        self.assertIn("<!-- Lines: paths between points -->", xml)
        self.assertIn("<!-- Circles: radius around one point -->", xml)
        self.assertIn("<!-- Point objects: one position -->", xml)
        section_tags = [
            child.tag
            for child in root
            if child.tag in {"areas", "lines", "circles", "labels"}
        ]
        self.assertEqual(section_tags, ["areas", "lines", "circles", "labels"])
        self.assertIsNotNone(root.find("lines"))
        self.assertIsNotNone(root.find("areas"))
        self.assertIsNotNone(root.find("circles"))
        self.assertIsNotNone(root.find("labels"))

        labels = root.findall("./labels/label")
        descriptions = [label.attrib["description"] for label in labels]
        names = [label.attrib["name"] for label in labels]

        self.assertEqual(
            [name for name in names if "BUOY" in name],
            [
                "SPECIAL MARK BUOY - YELLOW",
                "ISOLATED DANGER BUOY",
                "DEGRADED BUOY",
            ],
        )
        self.assertIn("SECURITY INCIDENT", names)
        self.assertIn("ICEBERG TRACKLINE", names)
        self.assertIn("LIGHTHOUSE", names)
        self.assertIn("LEADING LIGHT - FRONT", names)
        self.assertIn("LEADING LIGHT - REAR", names)
        self.assertIn("DRIFTING OBJECTS - DANGER", names)
        self.assertIn("WRECK - DANGER POINT", names)
        self.assertIn("AREA - FIRING EXERCISE DANGER ZONE", [
            area.attrib["name"] for area in root.findall("./areas/area")
        ])
        self.assertIn("POINT | special mark buoy | yellow class | DANGER=NO", descriptions)
        self.assertIn("POINT | isolated danger buoy | DANGER=YES", descriptions)
        self.assertIn("POINT | degraded buoy | STATUS=DEGRADED", descriptions)
        self.assertIn("POINT | lighthouse | fixed light", descriptions)
        self.assertIn("POINT | leading light | front", descriptions)
        self.assertIn("POINT | leading light | rear", descriptions)
        self.assertTrue(any("drifting objects" in text for text in descriptions))
        self.assertTrue(any("DANGER=YES" in text for text in descriptions))

        dangerous_types = [
            *root.findall("./areas/area"),
            *root.findall("./circles/circle"),
            *root.findall("./labels/label"),
        ]
        danger_values = [
            element.find("type").attrib["checkDanger"] for element in dangerous_types
        ]
        self.assertIn("1", danger_values)
        self.assertIn("0", danger_values)

        for vertex in root.findall(".//vertex"):
            latitude = float(vertex.attrib["latitude"])
            longitude = float(vertex.attrib["longitude"])
            self.assertGreaterEqual(latitude, 45.5)
            self.assertLessEqual(latitude, 46.3)
            self.assertGreaterEqual(longitude, 30.8)
            self.assertLessEqual(longitude, 31.9)

    def test_checked_in_fixture_matches_reproducible_export(self):
        fixture = (ROOT / OUTPUT_PATH).read_text(encoding="utf-8")
        self.assertEqual(fixture, render_demo_xml())