import json
import re
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import main
from source_intake import load_source


ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = ROOT / "tests" / "fixtures" / "rc1_superboss_baseline.json"


def load_case_block(filename, navarea_name):
    report = load_source(str(ROOT / filename))
    if report.text is None:
        raise AssertionError(f"Could not decode {filename}: {report.error}")
    source = report.text
    normalized = main.normalize_input(source, main.NormalizerStats())
    blocks = main.split_navarea_blocks(normalized)
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

    def run_source_case(self, source, navarea_name):
        message = main.create_message(navarea_name)
        container = main.create_container(navarea_name.split()[1])
        block = load_case_block(source, f"NAVAREA {navarea_name}")
        main.process_block(
            block,
            message,
            container,
            navarea_name.split()[1],
            label_text=main.build_navarea_label(f"NAVAREA {navarea_name}"),
        )
        return message, container

    def run_partitioned_source_case(self, source, navarea_name):
        block = load_case_block(source, f"NAVAREA {navarea_name}")
        messages = []
        for sub_block, metadata in main.partition_navarea_block(
            block, f"NAVAREA {navarea_name}"
        ):
            message = main.create_message(navarea_name, metadata=dict(metadata))
            container = main.create_container(navarea_name.split()[0])
            main.process_block(
                sub_block,
                message,
                container,
                navarea_name,
                label_text=main.build_navarea_label(f"NAVAREA {navarea_name}"),
                meta=dict(metadata),
            )
            messages.append((sub_block, metadata, message, container))
        return messages

    def assert_counts(self, message, expected):
        for object_type in ("areas", "lines", "circles", "labels"):
            self.assertEqual(
                len(message[object_type]),
                expected[object_type],
                f"{object_type} count mismatch",
            )

    def test_iii_92_preserves_all_lettered_areas(self):
        message, _ = self.run_case("III 92/22")
        expected = self.baseline["cases"]["III 92/22"]["after"]
        self.assert_counts(message, expected)
        self.assertEqual(len(message["areas"]), 7)
        self.assertNotIn("GEOMETRY_SELF_INTERSECTION", diagnostic_codes(message))
        self.assertFalse(any(main.has_self_intersection(a["coords"]) for a in message["areas"]))
        self.assert_stage_match(message, "handle_area")

    def test_iii_124_preserves_line_without_area(self):
        message, _ = self.run_case("III 124/22")
        self.assert_counts(message, self.baseline["cases"]["III 124/22"]["after"])
        self.assertEqual(len(message["lines"][0]["coords"]), 3)
        self.assertFalse(message["areas"])
        self.assert_stage_match(message, "handle_structured_sections")

    def test_iii_34_preserves_waiting_areas_and_routes(self):
        message, _ = self.run_case("III 34/24")
        expected = self.baseline["cases"]["III 34/24"]["after"]
        self.assert_counts(message, expected)
        self.assertEqual(len(message["areas"]), 2)
        self.assertNotIn("GEOMETRY_SELF_INTERSECTION", diagnostic_codes(message))
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

    def test_facility_lists_keep_shared_header_and_local_codes(self):
        cases = (
            ("NAVAREA IV - USA.txt", "IV 616/2025", 5, "BOSTON (F)"),
            ("NAVAREA IV - USA.txt", "IV 653/2026", 6, "BOSTON"),
            ("NAVAREA XII - USA.txt", "XII 354/2025", 5, "CAMBRIA (Q)"),
        )
        for source, navarea_name, expected_count, last_name in cases:
            with self.subTest(navarea=navarea_name):
                message, container = self.run_source_case(source, navarea_name)
                self.assert_counts(
                    message,
                    {
                        "areas": 0,
                        "lines": 0,
                        "circles": 0,
                        "labels": expected_count,
                    },
                )
                self.assert_stage_match(message, "handle_facility_list_points")
                descriptions = [label["description"] for label in message["labels"]]
                self.assertTrue(
                    all("REMOTE COMMUNICATION FACILITIES" in description for description in descriptions)
                )
                self.assertTrue(any(last_name in description for description in descriptions))
                self.assertFalse(
                    any(
                        re.search(r"(?m)^\([A-Z]\)\s+\d", description)
                        for description in descriptions
                    )
                )
                modern = ET.fromstring(
                    main.export_furuno_modern(navarea_name.split()[0], container)
                )
                xml_descriptions = [
                    node.attrib["description"]
                    for node in modern.findall("./labels/label")
                ]
                self.assertTrue(any(last_name in description for description in xml_descriptions))
                self.assertFalse(
                    any(
                        "--------------------------------------------------------------------------------" in description
                        for description in xml_descriptions
                    )
                )

    def test_ix_208_partitioned_descriptions_are_section_scoped(self):
        messages = self.run_partitioned_source_case(
            "NAVAREA IX - PAKISTAN.txt", "IX 208/2026"
        )
        section8 = next(item for item in messages if item[1].get("partition_id") == "8")
        section9 = next(item for item in messages if item[1].get("partition_id") == "9")

        circle_description = section8[2]["circles"][0]["description"]
        self.assertIn("SULTANATE OF OMAN HAS ISSUED FOLLOWING ADVISORY", circle_description)
        self.assertIn("8.", circle_description)
        self.assertNotIn("9. UPON ARRIVAL", circle_description)

        for object_type in ("lines", "labels"):
            description = section9[2][object_type][0]["description"]
            self.assertIn("SULTANATE OF OMAN HAS ISSUED FOLLOWING ADVISORY", description)
            self.assertIn("9.", description)
            self.assertNotIn("8. UPON RECEIPT", description)

        modern = ET.fromstring(main.export_furuno_modern("IX", section9[3]))
        legacy = ET.fromstring(
            main.generate_legacy_xml_from_messages("IX", [section9[2]], 1, 1)
        )
        modern_descriptions = [
            node.attrib["description"] for node in modern.findall("./lines/line")
        ] + [
            node.attrib["description"] for node in modern.findall("./labels/label")
        ]
        legacy_descriptions = [
            node.attrib["description"] for node in legacy.findall("./lines/line")
        ] + [
            node.attrib["description"] for node in legacy.findall("./labels/label")
        ]
        self.assertEqual(len(modern_descriptions), len(legacy_descriptions))
        for modern_description, legacy_description in zip(
            modern_descriptions, legacy_descriptions
        ):
            self.assertLessEqual(len(modern_description), main.LEGACY_MAX_DESC)
            self.assertEqual(legacy_description, modern_description)

    def test_v_470_preserves_area_radius_warning_without_inferred_circle(self):
        message = main.create_message("NAVAREA V 470/26")
        container = main.create_container("V")
        block = load_case_block("NAVAREA V - BRAZIL.txt", "NAVAREA V 470/26")

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

    def test_v_tow_between_preserves_two_endpoints_without_route(self):
        expected_cases = {
            "V 527/26": [
                (-22.818333, -43.110333),
                (-21.8575, -41.013833),
            ],
            "V 528/26": [
                (-22.818333, -43.110333),
                (-20.322833, -40.337833),
            ],
            "V 589/25": [
                (-22.8965, -43.207333),
                (-22.381, -41.765833),
            ],
            "V 593/25": [
                (-22.8965, -43.207333),
                (-22.381, -41.765833),
            ],
        }
        for navarea_name, expected_coords in expected_cases.items():
            message, _ = self.run_source_case(
                "NAVAREA V - BRAZIL.txt",
                navarea_name,
            )
            self.assert_counts(
                message,
                {"areas": 0, "lines": 0, "circles": 0, "labels": 2},
            )
            self.assertEqual(
                [label["coord"] for label in message["labels"]],
                expected_coords,
                navarea_name,
            )
            self.assertTrue(
                all(
                    "ROUTE GEOMETRY NOT PROVIDED" in label["description"]
                    for label in message["labels"]
                ),
                navarea_name,
            )
            self.assert_stage_match(message, "handle_tow_endpoints")

    def test_ix_moved_or_towed_objects_preserve_endpoints_without_route(self):
        expected_cases = {
            "IX 75/2026": [
                (26.672667, 52.014167),
                (26.585667, 51.926333),
            ],
            "IX 76/2026": [
                (26.7505, 51.838333),
                (26.5435, 51.836833),
            ],
            "IX 295/2026": [
                (26.585667, 51.926333),
                (26.672833, 52.014),
            ],
        }
        for navarea_name, expected_coords in expected_cases.items():
            message, _ = self.run_source_case(
                "NAVAREA IX - PAKISTAN.txt",
                navarea_name,
            )
            self.assert_counts(
                message,
                {"areas": 0, "lines": 0, "circles": 0, "labels": 2},
            )
            self.assertEqual(
                [label["coord"] for label in message["labels"]],
                expected_coords,
                navarea_name,
            )
            self.assertTrue(
                all(
                    "ROUTE GEOMETRY NOT PROVIDED" in label["description"]
                    for label in message["labels"]
                ),
                navarea_name,
            )
            self.assert_stage_match(message, "handle_tow_endpoints")

    def test_ix_157_emits_buoy_labels_without_line(self):
        message, _ = self.run_source_case(
            "NAVAREA IX - PAKISTAN.txt", "IX 157/2026"
        )

        self.assertFalse(message["areas"])
        self.assertFalse(message["lines"])
        self.assertFalse(message["circles"])
        self.assertEqual(len(message["labels"]), 5)
        self.assertTrue(all(label["style"] == 4 for label in message["labels"]))
        self.assertTrue(
            all(
                "YELLOW MARKER BUOYS" in label["description"].upper()
                for label in message["labels"]
            )
        )

    def test_ix_102_section_3_recovers_bouy_typo_in_modern_and_legacy_xml(self):
        navarea_name = "IX 102/2022"
        partitioned = self.run_partitioned_source_case(
            "NAVAREA IX - PAKISTAN.txt", navarea_name
        )
        self.assertEqual(len(partitioned), 1)
        _, metadata, message, container = partitioned[0]
        self.assertEqual(metadata["partition_type"], "NONE")

        self.assert_counts(
            message,
            {"areas": 0, "lines": 0, "circles": 0, "labels": 2},
        )
        self.assert_stage_match(message, "handle_buoy_semantics")

        label = message["labels"][1]
        self.assertEqual(label["coord"], (24.578, 67.067833))
        self.assertEqual(label["style"], 4)
        self.assertEqual(label["color"], "CHYLW")
        self.assertEqual(label["checkDanger"], 0)
        self.assertIn("NEW BOUY NO-3", label["description"])

        modern_xml = main.export_furuno_modern("IX", container)
        legacy_xml = main.generate_legacy_xml_from_messages(
            "IX", [message], 1, 1
        )
        for xml in (modern_xml, legacy_xml):
            root = ET.fromstring(xml)
            self.assertIsNone(root.find("./areas"))
            self.assertIsNone(root.find("./lines"))
            self.assertIsNone(root.find("./circles"))
            labels = root.findall("./labels/label")
            self.assertEqual(len(labels), 2)
            xml_label = next(
                item
                for item in labels
                if item.find("./position/vertex").attrib["latitude"] == "24.578000"
            )
            vertex = xml_label.find("./position/vertex")
            self.assertEqual(vertex.attrib["latitude"], "24.578000")
            self.assertEqual(vertex.attrib["longitude"], "67.067833")
            self.assertEqual(xml_label.find("./type").attrib["checkDanger"], "0")
            self.assertIn("NEW BOUY NO-3", xml_label.attrib["description"])

        modern_root = ET.fromstring(modern_xml)
        modern_label = modern_root.find("./labels/label")
        self.assertEqual(modern_label.find("./attribute").attrib["labelStyle"], "4")
        self.assertEqual(modern_label.find("./display").attrib["S52colorcode"], "CHYLW")

    def test_ix_58_emits_three_independent_safety_zone_circles(self):
        message, container = self.run_source_case(
            "NAVAREA IX - PAKISTAN.txt", "IX 58/2023"
        )

        self.assertFalse(message["areas"])
        self.assertFalse(message["lines"])
        self.assertEqual(len(message["circles"]), 3)
        self.assertFalse(message["labels"])
        self.assertTrue(
            all(circle["color"] == "NINFO" for circle in message["circles"])
        )
        self.assertTrue(
            all(circle["checkDanger"] == 0 for circle in message["circles"])
        )
        self.assertTrue(
            all(abs(circle["range"] - (1500 / 1852)) < 1e-12
                for circle in message["circles"])
        )
        self.assertEqual(
            [circle["coord"] for circle in message["circles"]],
            [
                (26.5916, 52.0331),
                (26.6468, 51.8916),
                (26.672917, 51.898267),
            ],
        )
        self.assert_stage_match(message, "handle_circle")

        for xml in (
            main.export_furuno_modern("IX", container),
            main.generate_legacy_xml_from_messages("IX", [message], 1, 1),
        ):
            root = ET.fromstring(xml)
            circles = root.findall("./circles/circle")
            self.assertEqual(len(circles), 3)
            self.assertIsNone(root.find("./lines"))
            self.assertEqual(
                [
                    (
                        float(circle.find("./position/vertex").attrib["latitude"]),
                        float(circle.find("./position/vertex").attrib["longitude"]),
                    )
                    for circle in circles
                ],
                [
                    (26.5916, 52.0331),
                    (26.6468, 51.8916),
                    (26.672917, 51.898267),
                ],
            )
            self.assertTrue(
                all(
                    abs(
                        float(circle.find("./attribute").attrib["range"])
                        - (1500 / 1852)
                    )
                    < 1e-6
                    for circle in circles
                )
            )

    def test_ix_7_emits_pipeline_line_and_two_endpoint_yellow_buoys(self):
        message, container = self.run_source_case(
            "NAVAREA IX - PAKISTAN.txt", "IX 7/2026"
        )

        self.assertFalse(message["areas"])
        self.assertFalse(message["circles"])
        self.assertEqual(len(message["lines"]), 1)
        self.assertEqual(
            message["lines"][0]["coords"],
            [
                (24.206, 52.636),
                (24.197833, 52.631),
            ],
        )
        self.assertEqual(len(message["labels"]), 2)
        self.assertEqual(
            [label["coord"] for label in message["labels"]],
            [
                (24.206, 52.636),
                (24.197833, 52.631),
            ],
        )
        self.assertTrue(all(label["style"] == 4 for label in message["labels"]))
        self.assertTrue(
            all(label["color"] == "CHYLW" for label in message["labels"])
        )
        self.assertTrue(
            all(label["checkDanger"] == 0 for label in message["labels"])
        )
        self.assert_stage_match(message, "handle_line_with_endpoint_objects")

        for xml in (
            main.export_furuno_modern("IX", container),
            main.generate_legacy_xml_from_messages("IX", [message], 1, 1),
        ):
            root = ET.fromstring(xml)
            self.assertEqual(len(root.findall("./lines/line")), 1)
            self.assertEqual(len(root.findall("./labels/label")), 2)
            self.assertIsNone(root.find("./circles"))
            self.assertIsNone(root.find("./areas"))

    def test_composite_line_with_tower_endpoints_is_not_buoy_specific(self):
        block = (
            "1. DISPOSAL PIPELINE IS MARKED BY TWO TOWERS IN POSITIONS:\n"
            "(A) 24-12.36N 052-38.16E\n"
            "(B) 24-11.87N 052-37.86E"
        )
        message = main.create_message("TEST")
        container = main.create_container("IX")
        main.process_block(block, message, container, "TEST", label_text="TEST")

        self.assertEqual(len(message["lines"]), 1)
        self.assertEqual(len(message["labels"]), 2)
        self.assertFalse(message["areas"])
        self.assertFalse(message["circles"])
        self.assertEqual(
            [label["coord"] for label in message["labels"]],
            [
                (24.206, 52.636),
                (24.197833, 52.631),
            ],
        )
        self.assert_stage_match(message, "handle_line_with_endpoint_objects")

    def test_viii_895_maps_undivided_survey_vicinity_to_area(self):
        message, _ = self.run_source_case(
            "NAVAREA VIII - INDIA.txt", "VIII 895/26"
        )

        expected = [
            (22.414167, 67.511),
            (22.366667, 68.066667),
            (21.898333, 68.1125),
            (21.621, 68.175833),
        ]
        self.assertEqual(len(message["areas"]), 1)
        self.assertFalse(message["lines"])
        self.assertFalse(message["circles"])
        self.assertFalse(message["labels"])
        self.assertEqual(message["areas"][0]["coords"], expected + [expected[0]])
        self.assertEqual(message["areas"][0]["color"], "NINFO")
        self.assertEqual(message["areas"][0]["checkDanger"], 0)
        self.assert_stage_match(message, "handle_implicit_operational_area")

    def test_bouy_variants_keep_buoy_semantics_without_source_normalization(self):
        variants = (
            ("BOUY IN POSITION 24-00N 067-00E", "BUOY"),
            ("BOUYS IN POSITION 24-00N 067-00E", "BUOY"),
            ("SPECIAL MARK BOUYS IN POSITION 24-00N 067-00E", "SPECIAL_MARK"),
            ("LIGHTBOUY IN POSITION 24-00N 067-00E", "LIGHTBUOY"),
        )
        for text, expected_subtype in variants:
            with self.subTest(text=text):
                classified = main.classify_buoy(text)
                self.assertIsNotNone(classified)
                self.assertEqual(classified["subtype"], expected_subtype)
                self.assertIn("BOUY", text)

    def test_bouy_negative_contexts_do_not_override_specialized_handlers(self):
        cases = (
            (
                "WRECK BOUY IN POSITION 24-00N 067-00E",
                "handle_single_point",
            ),
            (
                "TOWED RIG FROM 24-00N 067-00E TO 25-00N 068-00E",
                "handle_tow_endpoints",
            ),
            (
                "TRACKLINE JOINING BOUY A TO BOUY B: "
                "24-00N 067-00E TO 25-00N 068-00E",
                "handle_trackline",
            ),
        )
        for text, expected_handler in cases:
            with self.subTest(text=text):
                message = main.create_message("TEST")
                container = main.create_container("IX")
                main.process_block(
                    text,
                    message,
                    container,
                    "IX",
                    label_text="TEST",
                )
                self.assert_stage_match(message, expected_handler)
                self.assertFalse(message["areas"])

    def test_ix_246_emits_platform_point_labels_without_line(self):
        message, _ = self.run_source_case(
            "NAVAREA IX - PAKISTAN.txt", "IX 246/2026"
        )

        self.assertFalse(message["areas"])
        self.assertFalse(message["lines"])
        self.assertFalse(message["circles"])
        self.assertEqual(len(message["labels"]), 2)
        self.assertTrue(all(label["style"] == 5 for label in message["labels"]))

    def test_vii_217_preserves_named_vessel_positions_without_false_line(self):
        message, container = self.run_source_case(
            "NAVAREA VII - SOUTH AFRICA.txt", "VII 217/2026"
        )

        expected_coords = [
            (-28.710667, 15.945),
            (-28.385, 15.7705),
            (-28.636833, 16.022167),
            (-28.718333, 15.908333),
            (-28.344333, 15.822167),
            (-28.698333, 15.983333),
        ]
        self.assertFalse(message["areas"])
        self.assertFalse(message["lines"])
        self.assertFalse(message["circles"])
        self.assertEqual(len(message["labels"]), 6)
        self.assertTrue(all(label["color"] == "RESBL" for label in message["labels"]))
        self.assertEqual(
            [label["coord"] for label in message["labels"]],
            expected_coords,
        )

        descriptions = [label["description"] for label in message["labels"]]
        self.assertEqual(
            [description.split()[0] for description in descriptions],
            ["(A)", "(B)", "(C)", "(D)", "(E)", "(F)"],
        )
        for vessel_name in (
            "M/V BENGUELA GEM",
            "M/V SS MUJOMA",
            "M/V DEBMAR ATLANTIC",
            "M/V MAFUTA",
            "M/V GARIEP",
            "M/V DEBMAR PACIFIC",
        ):
            self.assertTrue(
                any(vessel_name in description for description in descriptions),
                vessel_name,
            )
        self.assertIn("ON DP", descriptions[0])
        self.assertIn("ON DP", descriptions[1])
        self.assertIn("4 ANCHOR SPREAD", descriptions[2])
        self.assertIn("4 ANCHOR SPREAD", descriptions[3])
        self.assertIn("4 ANCHOR SPREAD", descriptions[4])
        self.assertIn("3 ANCHOR SPREAD", descriptions[5])
        self.assert_stage_match(message, "handle_vessel_list_points")

        modern_xml = main.export_furuno_modern("VII", container)
        legacy_xml = main.generate_legacy_xml_from_messages("VII", [message], 1, 1)
        for xml in (modern_xml, legacy_xml):
            root = ET.fromstring(xml)
            self.assertIsNone(root.find("./lines"))
            self.assertEqual(len(root.findall("./labels/label")), 6)
            self.assertIn("M/V BENGUELA GEM", xml)
            self.assertIn("4 ANCHOR SPREAD", xml)

        modern_root = ET.fromstring(modern_xml)
        self.assertTrue(
            all(
                label.find("./display").attrib["S52colorcode"] == "RESBL"
                for label in modern_root.findall("./labels/label")
            )
        )

    def test_xvi_58_preserves_lateral_buoy_context(self):
        message, _ = self.run_source_case(
            "NAVAREA XVI - PERU.txt", "XVI 58/26"
        )

        self.assertEqual(len(message["labels"]), 3)
        self.assertTrue(all(label["style"] == 4 for label in message["labels"]))
        self.assertTrue(
            all("LATERAL BUOY LIGHTS" in label["description"].upper()
                for label in message["labels"])
        )

    def test_v_502_reconstructs_one_track_and_preserves_raw_provenance(self):
        message, _ = self.run_source_case(
            "NAVAREA V - BRAZIL.txt", "V 502/26"
        )

        self.assertFalse(message["areas"])
        self.assertFalse(message["circles"])
        self.assertEqual(len(message["lines"]), 1)
        self.assertEqual(len(message["lines"][0]["coords"]), 11)
        self.assertEqual(
            message["lines"][0]["coords"],
            [
                (6.132667, -50.199667),
                (5.710833, -48.181333),
                (4.147, -46.417667),
                (2.4695, -45.100167),
                (2.180333, -44.783),
                (0.727667, -43.211333),
                (-0.307333, -42.184833),
                (-1.129667, -40.973667),
                (-1.804667, -38.958167),
                (-2.245667, -37.610833),
                (-2.189167, -36.907),
            ],
        )
        self.assertIn("GEOMETRY_LINE_ORDER_REPAIRED", diagnostic_codes(message))
        self.assertFalse(
            message["lines"][0]["geometry_order_review"]["source_order_preserved"]
        )
        self.assertEqual(
            message["lines"][0]["raw_coords"],
            [
                (-0.307333, -42.184833),
                (-2.189167, -36.907),
                (2.180333, -44.783),
                (6.132667, -50.199667),
                (5.710833, -48.181333),
                (2.4695, -45.100167),
                (4.147, -46.417667),
                (0.727667, -43.211333),
                (-1.129667, -40.973667),
                (-1.804667, -38.958167),
                (-2.245667, -37.610833),
            ],
        )
        self.assertEqual(len(message["labels"]), 1)
        self.assertEqual(message["labels"][0]["style"], 6)

    def test_line_order_handling_is_generic_and_preserves_source_provenance(self):
        crossing = [(0.0, 0.0), (1.0, 1.0), (0.0, 1.0), (1.0, 0.0)]
        long_jump = [(0.0, 0.0), (0.1, 0.1), (0.2, 0.2), (10.0, 10.0)]

        crossing_issues = main.line_traversal_review(crossing)
        long_jump_issues = main.line_traversal_review(long_jump)

        self.assertIn(
            "NON_ADJACENT_SEGMENT_CROSSING",
            {issue["kind"] for issue in crossing_issues},
        )
        self.assertIn(
            "SUSPICIOUS_LONG_LEG",
            {issue["kind"] for issue in long_jump_issues},
        )

        message = main.create_message("SYNTHETIC LINE REVIEW")
        container = main.create_container("TEST")
        line = main.create_line(
            "TEST",
            "Published source order must remain unchanged.",
            crossing,
            "NINFO",
            0,
        )
        main.add_line(line, container, message)

        self.assertNotEqual(message["lines"][0]["coords"], crossing)
        self.assertEqual(message["lines"][0]["raw_coords"], crossing)
        self.assertEqual(message["lines"][0]["geometry_order_status"], "REPAIRED")
        self.assertIn("GEOMETRY_LINE_ORDER_REPAIRED", diagnostic_codes(message))
        self.assertFalse(
            main._line_crossing_segments(message["lines"][0]["coords"])
        )

    def test_disconnected_tracks_split_without_message_loss(self):
        coords = [
            (0.0, 0.0),
            (0.0, 1.0),
            (20.0, 20.0),
            (20.0, 21.0),
        ]
        message = main.create_message("SYNTHETIC DISCONNECTED TRACKS")
        container = main.create_container("TEST")
        line = main.create_line("TEST", "Two published tracks.", coords, "NINFO", 0)

        parts = main.add_line(line, container, message)

        self.assertEqual(len(parts), 2)
        self.assertEqual(
            sorted(coord for part in parts for coord in part["coords"]),
            sorted(coords),
        )
        self.assertTrue(all(len(part["coords"]) == 2 for part in parts))
        self.assertIn("GEOMETRY_LINE_TRACKS_SPLIT", diagnostic_codes(message))
        self.assertFalse(message.get("geometry_rejected", False))

    def test_iv_789_preserves_source_trackline_order(self):
        message, _ = self.run_source_case(
            "NAVAREA IV - USA.txt", "IV 789/2026"
        )

        self.assertFalse(message["areas"])
        self.assertFalse(message["circles"])
        self.assertEqual(len(message["lines"]), 1)
        self.assertEqual(
            message["lines"][0]["coords"],
            [
                (6.132667, -50.199667),
                (5.710833, -48.181333),
                (4.147, -46.417667),
                (2.4695, -45.100167),
                (2.180333, -44.783),
                (0.727667, -43.211333),
                (-0.307333, -42.184833),
                (-1.129667, -40.973667),
                (-1.804667, -38.958167),
                (-2.245667, -37.610833),
                (-2.189167, -36.907),
            ],
        )
        self.assertEqual(len(message["labels"]), 1)
        self.assertEqual(message["labels"][0]["style"], 6)

    def test_ii_307_matches_furuno_point_label_reference(self):
        message, _ = self.run_source_case(
            "NAVAREA II - FRANCE.txt", "II 307/2026"
        )

        self.assertFalse(message["areas"])
        self.assertFalse(message["lines"])
        self.assertFalse(message["circles"])
        self.assertEqual(len(message["labels"]), 1)
        self.assertEqual(message["labels"][0]["coord"], (23.116667, -17.2))
        self.assertEqual(message["labels"][0]["style"], 2)
        self.assertEqual(message["labels"][0]["color"], "CHRED")
        self.assertEqual(message["labels"][0]["checkDanger"], 1)
        self.assertIn("CAP BLANC", message["labels"][0]["description"])
        self.assertIn("MV HORIZON JADE", message["labels"][0]["description"])

    def test_viii_789_aground_is_dangerous_wreck_point(self):
        message, _ = self.run_source_case(
            "NAVAREA VIII - INDIA.txt", "VIII 789/26"
        )

        self.assertFalse(message["areas"])
        self.assertFalse(message["lines"])
        self.assertFalse(message["circles"])
        self.assertEqual(len(message["labels"]), 1)
        label = message["labels"][0]
        self.assertEqual(label["style"], 3)
        self.assertEqual(label["color"], "CHRED")
        self.assertEqual(label["checkDanger"], 1)
        self.assertEqual(label["coord"], (19.191667, 72.773333))
        self.assertIn("AL JAFZIA UNMANNED", label["description"])
        self.assertIn("REPORTED AGROUND", label["description"])

    def test_v_522_splits_repeated_unlabelled_area_boundaries(self):
        message, _ = self.run_source_case(
            "NAVAREA V - BRAZIL.txt",
            "V 522/26",
        )

        self.assert_counts(
            message,
            {"areas": 4, "lines": 0, "circles": 0, "labels": 0},
        )
        self.assert_stage_match(message, "handle_area")
        self.assertNotIn("GEOMETRY_SELF_INTERSECTION", diagnostic_codes(message))

        expected_first_coordinates = [
            "03-05.00N 028-43.00W",
            "05-35.00N 048-53.00W",
            "05-19.00N 047-01.00W",
            "02-45.00N 028-25.00W",
        ]
        for area, first_coordinate in zip(
            message["areas"], expected_first_coordinates
        ):
            self.assertEqual(len(area["coords"]), 5)
            self.assertEqual(area["coords"][0], area["coords"][-1])
            self.assertIn(first_coordinate, area["description"])
            self.assertFalse(main.has_self_intersection(area["coords"]))

    def test_iii_122_accepts_descriptive_header_without_splitting_cancellation(self):
        source = "tests/fixtures/navarea_iii_spain_122_26.txt"
        raw = (ROOT / source).read_text(encoding="utf-8")
        normalized = main.normalize_input(raw, main.NormalizerStats())
        blocks = [block.strip() for block in main.split_navarea_blocks(normalized)
                  if block.strip()]

        self.assertEqual(len(blocks), 1)
        self.assertTrue(blocks[0].startswith("NAVAREA III 122/26"))
        self.assertIn("CANCEL NAVAREA III 0114/26", blocks[0])

        message = main.create_message("III 122/26")
        container = main.create_container("III")
        container["messages"].append(message)
        main.process_block(
            blocks[0],
            message,
            container,
            "III 122/26",
            label_text=main.build_navarea_label("NAVAREA III 122/26"),
        )

        self.assertEqual(len(message["areas"]), 1)
        self.assertEqual(len(message["areas"][0]["coords"]), 5)
        self.assertEqual(message["areas"][0]["coords"][0],
                         message["areas"][0]["coords"][-1])
        self.assertIn("DRILLING OPERATIONS", message["areas"][0]["description"])
        self.assertIn("ABDULHAMID HAN RIG", message["areas"][0]["description"])
        self.assertEqual(len(container["messages"]), 1)

        xml = main.export_furuno_modern("III", container)
        ET.fromstring(xml)
        self.assertIn('name="NAV III 122/26"', xml)
        self.assertIn("NAVAREA III 122/26 BLACK SEA", xml)

    def test_iii_122_ecdis_description_keeps_operation_and_coordinates(self):
        source = "tests/fixtures/navarea_iii_spain_122_26.txt"
        block = load_case_block(source, "NAVAREA III 122/26")
        message = main.create_message("III 122/26")
        container = main.create_container("III")
        main.process_block(
            block,
            message,
            container,
            "III 122/26",
            label_text=main.build_navarea_label("NAVAREA III 122/26"),
        )

        xml = main.export_furuno_modern("III", container)
        root = ET.fromstring(xml)
        area = root.find("./areas/area")
        self.assertIsNotNone(area)
        description = area.attrib["description"]
        self.assertIn("BLACK SEA", description)
        self.assertIn("DRILLING OPERATIONS BY ABDULHAMID HAN RIG", description)
        self.assertIn("031-36.52E", description)
        self.assertIn("CANCEL NAVAREA", description.upper())

    def test_description_contract_preserves_context_for_specialized_handlers(self):
        cases = (
            (
                "NAVAREA IV - USA.txt",
                "IV 616/2025",
                ("NAVAREA IV 616/2025", "MESSAGING SERVICES UNAVAILABLE"),
            ),
            (
                "NAVAREA IV - USA.txt",
                "IV 653/2026",
                ("NAVAREA IV 653/2026", "SERVICES UNRELIABLE"),
            ),
            (
                "NAVAREA VII - SOUTH AFRICA.txt",
                "VII 124/2026",
                ("NAVAREA VII 124/2026", "CAPRICORNUS 1A", "2NM WIDE BERTH"),
            ),
            (
                "NAVAREA VII - SOUTH AFRICA.txt",
                "VII 154/2026",
                ("NAVAREA VII 154/2026", "NOT UNDER COMMAND AND ADRIFT"),
            ),
            (
                "NAVAREA VII - SOUTH AFRICA.txt",
                "VII 210/2026",
                ("NAVAREA VII 210/2026", "TOWING FPSO", "DESTINATION GUYANA"),
            ),
            (
                "NAVAREA VII - SOUTH AFRICA.txt",
                "VII 221/2026",
                ("NAVAREA VII 221/2026", "SPECIAL MARK CHARACTERISTICS", "NAVIGATE WITH CAUTION"),
            ),
            (
                "NAVAREA VII - SOUTH AFRICA.txt",
                "VII 217/2026",
                ("NAVAREA VII 217/2026", "MINING/AMPLING/EXPLORATION VESSELS LIST"),
            ),
            (
                "NAVAREA VIII - INDIA.txt",
                "VIII 806/26",
                ("NAVAREA VIII 806/26", "GRANDI I", "ST. GEORGE"),
            ),
        )

        for source, navarea_name, required_phrases in cases:
            with self.subTest(navarea=navarea_name):
                message, container = self.run_source_case(source, navarea_name)
                modern_root = ET.fromstring(
                    main.export_furuno_modern(navarea_name.split()[0], container)
                )
                legacy_root = ET.fromstring(
                    main.generate_legacy_xml_from_messages(
                        navarea_name.split()[0], [message], 1, 1
                    )
                )
                modern_descriptions = [
                    node.attrib["description"]
                    for kind in ("area", "line", "circle", "label")
                    for node in modern_root.findall(f"./{kind}s/{kind}")
                ]
                legacy_descriptions = [
                    node.attrib["description"]
                    for kind in ("area", "line", "circle", "label")
                    for node in legacy_root.findall(f"./{kind}s/{kind}")
                ]
                self.assertEqual(modern_descriptions, legacy_descriptions)
                self.assertTrue(modern_descriptions)
                for phrase in required_phrases:
                    self.assertTrue(
                        any(phrase.upper() in description.upper()
                            for description in modern_descriptions),
                        f"{navarea_name}: missing {phrase}",
                    )

    def test_iii_122_ecdis_area_exports_unique_boundary_vertices(self):
        source = "tests/fixtures/navarea_iii_spain_122_26.txt"
        block = load_case_block(source, "NAVAREA III 122/26")
        message = main.create_message("III 122/26")
        container = main.create_container("III")
        main.process_block(
            block,
            message,
            container,
            "III 122/26",
            label_text=main.build_navarea_label("NAVAREA III 122/26"),
        )

        expected = [
            (43.083833, 31.608667),
            (43.083833, 31.665833),
            (43.043833, 31.665833),
            (43.043833, 31.608667),
        ]
        for xml in (
            main.export_furuno_modern("III", container),
            main.generate_legacy_xml_from_messages("III", [message], 1, 1),
        ):
            root = ET.fromstring(xml)
            vertices = [
                (
                    float(vertex.attrib["latitude"]),
                    float(vertex.attrib["longitude"]),
                )
                for vertex in root.findall("./areas/area/position/vertex")
            ]
            self.assertEqual(vertices, expected)
            self.assertEqual(len(vertices), len(set(vertices)))

    def test_viii_729_depth_reports_are_independent_points(self):
        message, _ = self.run_source_case(
            "NAVAREA VIII - INDIA.txt", "VIII 729/26"
        )

        self.assertFalse(message["areas"])
        self.assertFalse(message["lines"])
        self.assertFalse(message["circles"])
        self.assertEqual(len(message["labels"]), 2)
        self.assertTrue(all(label["style"] == 2 for label in message["labels"]))
        self.assertTrue(
            all(label["color"] == "NINFO" for label in message["labels"])
        )
        self.assertTrue(
            all(label["checkDanger"] == 0 for label in message["labels"])
        )
        self.assertEqual(
            [label["coord"] for label in message["labels"]],
            [
                (18.295333, 72.919667),
                (18.296167, 72.932),
            ],
        )
        self.assert_stage_match(message, "handle_multipoint")

    def test_i_181_explicit_miles_circle_and_ecdis_description(self):
        source = "tests/fixtures/navarea_i_uk_181_26.txt"
        block = load_case_block(source, "NAVAREA I 181/26")
        message = main.create_message("I 181/26")
        container = main.create_container("I")
        main.process_block(
            block,
            message,
            container,
            "I 181/26",
            label_text=main.build_navarea_label("NAVAREA I 181/26"),
        )

        circle_spec = main.extract_circle_spec(block)
        self.assertEqual(circle_spec["center"], (55.083333, -19.0))
        self.assertEqual(circle_spec["radius"], 41.0)
        self.assertEqual(circle_spec["unit"], "MILES")
        self.assertEqual(len(message["circles"]), 1)
        self.assertFalse(message["areas"])
        self.assertFalse(message["lines"])

        xml = main.export_furuno_modern("I", container)
        root = ET.fromstring(xml)
        circle = root.find("./circles/circle")
        self.assertIsNotNone(circle)
        description = circle.attrib["description"]
        self.assertIn("NAVAL EXERCISE INCLUDING LIVE WEAPONS FIRING", description)
        self.assertIn("CONTACT ON SATCOM +494631942056268", description)
        self.assertIn("WITHIN 41 MILES OF 55-05N 019-00W", description)
        self.assertIn("55-05N 019-00W", description)
        self.assertIn("CANCEL THIS MSG", description.upper())

    def test_i_181_partition_keeps_contact_with_circle(self):
        messages = self.run_partitioned_source_case(
            "tests/fixtures/navarea_i_uk_181_26.txt",
            "I 181/26",
        )
        circle_messages = [item for item in messages if item[2]["circles"]]

        self.assertEqual(len(circle_messages), 1)
        _, metadata, message, container = circle_messages[0]
        self.assertEqual(metadata["partition_type"], "NONE")
        self.assertEqual(len(message["circles"]), 1)

        xml = main.export_furuno_modern("I", container)
        description = ET.fromstring(xml).find("./circles/circle").attrib[
            "description"
        ]
        self.assertIn("NAVAL EXERCISE INCLUDING LIVE WEAPONS FIRING", description)
        self.assertIn("CONTACT ON SATCOM +494631942056268", description)
        self.assertEqual(description.upper().count("NAVAREA I 181/26"), 1)
        self.assertIn("CANCEL THIS MSG", description.upper())

    def test_i_181_legacy_circle_range_uses_50_limit(self):
        block = load_case_block(
            "tests/fixtures/navarea_i_uk_181_26.txt",
            "NAVAREA I 181/26",
        )
        message = main.create_message("I 181/26")
        container = main.create_container("I")
        main.process_block(
            block,
            message,
            container,
            "I 181/26",
            label_text=main.build_navarea_label("NAVAREA I 181/26"),
        )

        legacy_xml = main.generate_legacy_xml_from_messages("I", [message], 1, 1)
        circle = ET.fromstring(legacy_xml).find("./circles/circle")
        self.assertIsNotNone(circle)
        self.assertEqual(
            float(circle.find("./attribute").attrib["range"]),
            41.0,
        )

        for requested, expected in ((49.0, 49.0), (50.0, 50.0), (51.0, 50.0)):
            data = {
                "areas": [],
                "lines": [],
                "labels": [],
                "circles": [
                    {
                        "name": "NAV I 181/26",
                        "description": "NAVAL EXERCISE",
                        "coord": (55.083333, -19.0),
                        "range": requested,
                    }
                ],
            }
            root = ET.fromstring(main.generate_legacy_xml("I", data))
            exported = float(root.find("./circles/circle/attribute").attrib["range"])
            self.assertEqual(exported, expected)

    def test_multiple_incomplete_area_boundaries_are_rejected_explicitly(self):
        block = """NAVAREA V 999/26
IN AREA BOUND BY
03-05.00N 028-43.00W
03-39.00N 028-39.00W
04-07.00N 032-44.00W
IN AREA BOUND BY
05-35.00N 048-53.00W
05-45.00N 048-54.00W
CANCEL THIS WARNING 010000 UTC SEP 26."""
        message = main.create_message("V 999/26")
        container = main.create_container("V")

        main.process_block(
            block,
            message,
            container,
            "V 999/26",
            label_text=main.build_navarea_label("NAVAREA V 999/26"),
        )

        self.assertFalse(message["areas"])
        self.assertIn("GEOMETRY_UNPARSED_AREA_GROUPS", diagnostic_codes(message))
        self.assertTrue(message["geometry_rejected"])

    def test_v_449_preserves_named_operational_groups(self):
        message, _ = self.run_source_case(
            "NAVAREA V - BRAZIL.txt", "V 449/26"
        )

        self.assertFalse(message["areas"])
        self.assertFalse(message["lines"])
        self.assertFalse(message["circles"])
        self.assertEqual(len(message["labels"]), 3)
        descriptions = [label["description"].upper() for label in message["labels"]]
        for group_name in ("AREA ALFA", "AREA BRAVO", "AREA CHARLIE"):
            self.assertTrue(any(group_name in description for description in descriptions))
        self.assertTrue(all(label["color"] == "RESBL" for label in message["labels"]))
        self.assertTrue(all(label["checkDanger"] == 0 for label in message["labels"]))
        self.assertNotIn("GEOMETRY_SELF_INTERSECTION", diagnostic_codes(message))

    def test_partition_parent_context_is_shared_without_legacy_truncation(self):
        block = load_case_block(
            "NAVAREA IX - PAKISTAN.txt", "NAVAREA IX 208/2026"
        )
        parts = main.partition_navarea_block(block, "NAVAREA IX 208/2026")
        section = next(
            (entry, metadata)
            for entry, metadata in parts
            if metadata["partition_type"] == "SECTION_NUMBER"
            and metadata["partition_id"] == "9"
        )
        message = main.create_message("IX 208/2026", metadata=section[1])
        container = main.create_container("IX")
        main.process_block(
            section[0],
            message,
            container,
            "IX 208/2026",
            label_text=main.build_navarea_label("NAVAREA IX 208/2026"),
            meta=section[1],
        )

        modern_xml = main.export_furuno_modern("IX", container)
        legacy_xml = main.generate_legacy_xml_from_messages("IX", [message], 1, 1)
        modern_root = ET.fromstring(modern_xml)
        legacy_root = ET.fromstring(legacy_xml)
        modern_description = modern_root.find("./lines/line").attrib["description"]
        legacy_description = legacy_root.find("./lines/line").attrib["description"]
        self.assertIn("PERSIAN GULF", modern_description)
        self.assertIn("PERSIAN GULF", legacy_description)
        self.assertLessEqual(len(modern_description), main.LEGACY_MAX_DESC)
        self.assertEqual(
            legacy_description,
            modern_description,
        )

    def test_closed_operational_area_is_not_rejected_as_self_intersecting(self):
        navarea_name = "NAVAREA I 133/26"
        block = load_case_block(
            "tests/fixtures/legacy_regression_cases.txt", navarea_name
        )
        message = main.create_message(navarea_name)
        container = main.create_container("I")

        main.process_block(
            block,
            message,
            container,
            "I 133/26",
            label_text=main.build_navarea_label(navarea_name),
        )

        self.assertEqual(len(message["areas"]), 1)
        self.assertNotIn("GEOMETRY_SELF_INTERSECTION", diagnostic_codes(message))
        self.assertFalse(main.has_self_intersection(message["areas"][0]["coords"][:-1]))

    def test_arc_defined_area_survives_closed_ring_validation(self):
        navarea_name = "NAVAREA VIII 809/26"
        block = load_case_block(
            "tests/fixtures/legacy_regression_cases.txt", navarea_name
        )
        parts = main.partition_navarea_block(block, navarea_name)
        section, section_metadata = parts[0]
        self.assertEqual(section_metadata["partition_type"], "NONE")
        message = main.create_message(f"{navarea_name} [Section 1]")
        container = main.create_container("VIII")

        main.process_block(
            section,
            message,
            container,
            "VIII 809/26",
            label_text=main.build_navarea_label(navarea_name),
            meta=section_metadata,
        )

        self.assertEqual(len(message["areas"]), 1)
        self.assertGreater(len(message["areas"][0]["coords"]), 10)
        self.assertNotIn("GEOMETRY_SELF_INTERSECTION", diagnostic_codes(message))

    def test_ix_507_classifies_cardinal_beacon_and_danger_lightbuoy(self):
        navarea_name = "NAVAREA IX 507/2022"
        block = load_case_block(
            "tests/fixtures/legacy_regression_cases.txt", navarea_name
        )
        parts = main.partition_navarea_block(block, navarea_name)

        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0][1]["partition_type"], "NONE")

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
        self.assertEqual(len(point_messages), 1)

        danger_label = messages[0]["labels"][0]
        self.assertEqual(danger_label["style"], 4)
        self.assertEqual(danger_label["color"], "CHRED")
        self.assertEqual(danger_label["coord"], (27.11, 56.099333))

        cardinal_label = messages[0]["labels"][1]
        self.assertEqual(cardinal_label["style"], 4)
        self.assertEqual(cardinal_label["color"], "CHYLW")
        self.assertEqual(cardinal_label["coord"], (27.114333, 56.107667))

    def test_security_class_is_red_style_five_and_not_pilot_boarding(self):
        security_text = (
            "SECURITY INCIDENT IN POSITION 26-05.11N 056-35.40E"
        )
        self.assertTrue(main.detect_security_incident(security_text))
        self.assertEqual(main.get_point_style(security_text), 5)
        self.assertEqual(main.detect_color(security_text), "CHRED")
        self.assertEqual(main.detect_check_danger(security_text), 1)
        self.assertFalse(
            main.detect_security_incident(
                "PILOT BOARDING STATION IS DESIGNATED "
                "IN POSITION 26-05.11N 056-35.40E"
            )
        )

    def test_ix_432_classifies_beacon_tower_as_buoy_triangle(self):
        navarea_name = "NAVAREA IX 432/2024"
        block = load_case_block(
            "tests/fixtures/legacy_regression_cases.txt", navarea_name
        )
        message = main.create_message(navarea_name)
        container = main.create_container("IX")

        main.process_block(
            block,
            message,
            container,
            "IX 432/2024",
            label_text=main.build_navarea_label(navarea_name),
        )

        self.assertEqual(len(message["labels"]), 4)
        self.assertTrue(
            all(label["style"] == 4 for label in message["labels"])
        )
        self.assertTrue(
            all(label["color"] == "CHYLW" for label in message["labels"])
        )
        self.assertEqual(
            [label["coord"] for label in message["labels"]],
            [
                (26.967333, 56.046167),
                (26.967333, 56.045167),
                (26.507333, 54.6655),
                (26.508, 54.664167),
            ],
        )

    def test_beacon_aliases_share_beacon_subtype(self):
        aliases = (
            "BEACON",
            "BEACON TOWER",
            "PILLAR BEACON",
            "PILLER BEACON",
            "PILE BEACON",
            "LATTICE BEACON",
            "PERCH BEACON",
            "LIGHTED BEACON",
            "PIER BEACON",
            "DAY BEACON",
            "NORTH CARDINAL BEACON",
        )
        for alias in aliases:
            classified = main.classify_buoy(f"{alias} IN POSITION 26-00N 056-00E")
            self.assertIsNotNone(classified, alias)
            self.assertEqual(classified["subtype"], "BEACON", alias)

        self.assertIsNone(
            main.classify_buoy("LIGHTHOUSE IN POSITION 26-00N 056-00E")
        )

    def test_buoy_display_uses_color_for_status_not_subtype(self):
        self.assertEqual(
            main.buoy_style_color(False, "ACTIVE", "BEACON"),
            (4, "CHYLW", 0),
        )
        self.assertEqual(
            main.buoy_style_color(False, "MISSING", "BEACON"),
            (4, "NINFO", 0),
        )
        self.assertEqual(
            main.buoy_style_color(True, "ACTIVE", "BEACON"),
            (4, "CHRED", 1),
        )

    def test_ix_115_keeps_deployed_buoys_triangle_yellow(self):
        navarea_name = "NAVAREA IX 115/2026"
        block = load_case_block(
            "tests/fixtures/legacy_regression_cases.txt", navarea_name
        )
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
        self.assertEqual(
            [label["coord"] for label in message["labels"]],
            [
                (28.657, 48.393167),
                (28.657333, 48.392167),
                (28.657833, 48.392333),
                (28.653667, 48.382333),
                (28.653833, 48.381833),
            ],
        )

    def test_ix_34_isolates_buoy_status_per_table_row_in_both_xml_formats(self):
        navarea_name = "IX 34/2023"
        message, container = self.run_source_case(
            "NAVAREA IX - PAKISTAN.txt", navarea_name
        )

        self.assert_counts(
            message,
            {"areas": 0, "lines": 0, "circles": 0, "labels": 39},
        )
        labels_by_coord = {label["coord"]: label for label in message["labels"]}

        unlit_buoy = labels_by_coord[(16.945167, 41.314)]
        self.assertEqual(unlit_buoy["style"], 4)
        self.assertEqual(unlit_buoy["color"], "NINFO")
        self.assertEqual(unlit_buoy["checkDanger"], 0)

        danger_buoy = labels_by_coord[(16.995333, 41.321333)]
        self.assertEqual(danger_buoy["style"], 4)
        self.assertEqual(danger_buoy["color"], "CHRED")
        self.assertEqual(danger_buoy["checkDanger"], 1)
        self.assertEqual(
            sum(label["checkDanger"] for label in message["labels"]),
            1,
        )

        nav_id = navarea_name.removeprefix("NAVAREA ").split()[0]
        modern_xml = main.export_furuno_modern(nav_id, container)
        legacy_xml = main.generate_legacy_xml_from_messages(
            nav_id, [message], 1, 1
        )

        for xml in (modern_xml, legacy_xml):
            root = ET.fromstring(xml)
            self.assertIsNone(root.find("./areas"))
            self.assertIsNone(root.find("./lines"))
            self.assertIsNone(root.find("./circles"))
            labels = root.findall("./labels/label")
            self.assertEqual(len(labels), 39)

            labels_by_position = {
                (
                    label.find("./position/vertex").attrib["latitude"],
                    label.find("./position/vertex").attrib["longitude"],
                ): label
                for label in labels
            }
            xml_unlit = labels_by_position[("16.945167", "41.314000")]
            xml_danger = labels_by_position[("16.995333", "41.321333")]
            self.assertEqual(
                xml_unlit.find("./type").attrib["checkDanger"], "0"
            )
            self.assertEqual(
                xml_danger.find("./type").attrib["checkDanger"], "1"
            )

        modern_root = ET.fromstring(modern_xml)
        modern_unlit = next(
            label
            for label in modern_root.findall("./labels/label")
            if label.find("./position/vertex").attrib["latitude"] == "16.945167"
        )
        modern_danger = next(
            label
            for label in modern_root.findall("./labels/label")
            if label.find("./position/vertex").attrib["latitude"] == "16.995333"
        )
        self.assertEqual(
            modern_unlit.find("./attribute").attrib["labelStyle"], "4"
        )
        self.assertEqual(
            modern_unlit.find("./display").attrib["S52colorcode"], "NINFO"
        )
        self.assertEqual(
            modern_danger.find("./attribute").attrib["labelStyle"], "4"
        )
        self.assertEqual(
            modern_danger.find("./display").attrib["S52colorcode"], "CHRED"
        )

    def test_iv_834_iceberg_tracklines_and_labels_are_red_danger(self):
        navarea_name = "NAVAREA IV 834/2026"
        block = load_case_block(
            "tests/fixtures/navarea_iv_834_2026.txt",
            navarea_name,
        )
        message = main.create_message(navarea_name)
        container = main.create_container("IV")

        main.process_block(
            block,
            message,
            container,
            "IV 834/2026",
            label_text=main.build_navarea_label(navarea_name),
        )

        self.assertFalse(message["areas"])
        self.assertFalse(message["circles"])
        self.assertEqual(
            [len(line["coords"]) for line in message["lines"]],
            [3, 6, 2],
        )
        self.assertTrue(
            all(
                line["color"] == "CHRED" and line["checkDanger"] == 1
                for line in message["lines"]
            )
        )
        self.assertEqual(len(message["labels"]), 3)
        self.assertTrue(
            all(
                label["style"] == 6
                and label["color"] == "CHRED"
                and label["checkDanger"] == 1
                for label in message["labels"]
            )
        )
        self.assert_stage_match(message, "handle_structured_sections")

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