import json
import re
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import main


ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = ROOT / "tests" / "fixtures" / "rc1_superboss_baseline.json"


def load_case_block(filename, navarea_name):
    source = (ROOT / filename).read_text(encoding="utf-8")
    normalized = main.normalize_input(source, main.NormalizerStats())
    blocks = re.split(
        r"(?=NAVAREA\s+[A-ZIVXLC]+\s+\d+/\d+)",
        normalized,
        flags=re.IGNORECASE,
    )
    for block in blocks:
        if block.lstrip().upper().startswith(navarea_name.upper()):
            return block.strip()
    raise AssertionError(f"Could not find {navarea_name} in {filename}")


class Rc1SuperbossControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))

    def run_case(self, navarea_name):
        case = self.baseline["cases"][navarea_name]
        message = main.create_message(navarea_name)
        container = main.create_container(navarea_name.split()[1])
        block = load_case_block(case["source"], f"NAVAREA {navarea_name}")
        main.process_block(
            block,
            message,
            container,
            navarea_name.split()[1],
            label_text=main.build_navarea_label(f"NAVAREA {navarea_name}"),
        )
        return message, container

    def assert_counts(self, message, expected):
        for object_type in ("areas", "lines", "circles", "labels"):
            self.assertEqual(
                len(message[object_type]),
                expected[object_type],
                f"{object_type} count mismatch",
            )

    def test_iii_92_rejects_invalid_area(self):
        message, _ = self.run_case("III 92/22")
        expected = self.baseline["cases"]["III 92/22"]["after"]
        self.assert_counts(message, expected)
        self.assertIn(expected["required_diagnostic"], diagnostic_codes(message))
        self.assertFalse(any(main.has_self_intersection(a["coords"]) for a in message["areas"]))
        self.assert_stage_match(message, "handle_area")

    def test_iii_124_preserves_line_without_area(self):
        message, _ = self.run_case("III 124/22")
        self.assert_counts(message, self.baseline["cases"]["III 124/22"]["after"])
        self.assertEqual(len(message["lines"][0]["coords"]), 3)
        self.assertFalse(message["areas"])
        self.assert_stage_match(message, "handle_structured_sections")

    def test_iii_34_rejects_invalid_areas_but_keeps_routes(self):
        message, _ = self.run_case("III 34/24")
        expected = self.baseline["cases"]["III 34/24"]["after"]
        self.assert_counts(message, expected)
        self.assertIn(expected["required_diagnostic"], diagnostic_codes(message))
        self.assertFalse(any(main.has_self_intersection(a["coords"]) for a in message["areas"]))
        self.assert_stage_match(message, "handle_mixed_geometry_package")

    def test_ix_208_emits_explicit_line_and_circle(self):
        message, container = self.run_case("IX 208/2026")
        expected = self.baseline["cases"]["IX 208/2026"]["after"]
        self.assert_counts(message, expected)
        self.assertEqual(len(message["lines"][0]["coords"]), expected["line_vertices"])
        self.assertEqual(message["circles"][0]["coord"], tuple(expected["circle_center"]))
        self.assertEqual(message["circles"][0]["range"], expected["circle_radius"])
        self.assertFalse(message["areas"])
        self.assert_stage_match(message, "handle_explicit_line_circle")

        modern_xml = main.export_furuno_modern("IX", container)
        legacy_xml = main.generate_legacy_xml_from_messages("IX", [message], 1, 1)
        self.assertEqual(ET.fromstring(modern_xml).tag, "userchart")
        self.assertEqual(ET.fromstring(legacy_xml).tag, "userchart")

    def test_v_470_preserves_area_radius_warning_without_inferred_circle(self):
        message = main.create_message("NAVAREA V 470/26")
        container = main.create_container("V")
        block = load_case_block("NAV-V.txt", "NAVAREA V 470/26")

        main.process_block(
            block,
            message,
            container,
            "V 470/26",
            label_text=main.build_navarea_label("NAVAREA V 470/26"),
        )

        self.assertEqual(len(message["areas"]), 1)
        self.assertFalse(message["lines"])
        self.assertFalse(message["circles"])
        self.assertIn(
            "RADIUS OF 1.5 NAUTICAL MILES",
            message["areas"][0]["description"].upper(),
        )
        self.assertNotIn(
            "GEOMETRY_SELF_INTERSECTION",
            diagnostic_codes(message),
        )

        modern_xml = main.export_furuno_modern("V", container)
        legacy_xml = main.generate_legacy_xml_from_messages("V", [message], 1, 1)
        for xml in (modern_xml, legacy_xml):
            ET.fromstring(xml)
            self.assertIn("RADIUS OF 1.5 NAUTICAL MILES", xml.upper())

    def test_ix_507_classifies_cardinal_beacon_and_danger_lightbuoy(self):
        navarea_name = "NAVAREA IX 507/2022"
        block = load_case_block("NAV-IX.txt", navarea_name)
        parts = main.partition_navarea_block(block, navarea_name)

        self.assertEqual(
            [meta["partition_id"] for _, meta in parts],
            ["2", "3", "4"],
        )

        messages = []
        container = main.create_container("IX")
        for sub_block, meta in parts:
            message = main.create_message(
                f"{navarea_name} [Section {meta['partition_id']}]",
                metadata=meta,
            )
            main.process_block(
                sub_block,
                message,
                container,
                "IX 507/2022",
                label_text=main.build_navarea_label(navarea_name),
                meta=meta,
            )
            messages.append(message)

        point_messages = [message for message in messages if message["labels"]]
        self.assertEqual(len(point_messages), 2)

        danger_label = messages[0]["labels"][0]
        self.assertEqual(danger_label["style"], 4)
        self.assertEqual(danger_label["color"], "CHRED")
        self.assertEqual(danger_label["coord"], (27.11, 56.099333))

        cardinal_label = messages[1]["labels"][0]
        self.assertEqual(cardinal_label["style"], 4)
        self.assertEqual(cardinal_label["color"], "CHYLW")
        self.assertEqual(cardinal_label["coord"], (27.114333, 56.107667))

    def test_ix_115_keeps_deployed_buoys_triangle_yellow(self):
        navarea_name = "NAVAREA IX 115/2026"
        block = load_case_block("NAV-IX.txt", navarea_name)
        message = main.create_message(navarea_name)
        container = main.create_container("IX")

        main.process_block(
            block,
            message,
            container,
            "IX 115/2026",
            label_text=main.build_navarea_label(navarea_name),
        )

        self.assertEqual(len(message["labels"]), 5)
        self.assertTrue(
            all(label["style"] == 4 for label in message["labels"])
        )
        self.assertTrue(
            all(label["color"] == "CHYLW" for label in message["labels"])
        )

    def assert_stage_match(self, message, handler_name):
        matches = [
            stage
            for stage in message.get("stage_diagnostics", [])
            if stage["stage"] == "handler_match"
        ]
        self.assertTrue(matches)
        self.assertEqual(matches[-1]["handler"], handler_name)


def diagnostic_codes(message):
    return {diagnostic["code"] for diagnostic in message.get("diagnostics", [])}


if __name__ == "__main__":
    unittest.main()