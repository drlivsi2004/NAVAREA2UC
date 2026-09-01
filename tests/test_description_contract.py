import unittest
import xml.etree.ElementTree as ET

import main


def process_partition(sub_block, metadata):
    message = main.create_message("TEST", metadata=metadata)
    container = main.create_container("TEST")
    main.process_block(
        sub_block,
        message,
        container,
        "TEST",
        label_text="NAV TEST 1/2026",
        meta=metadata,
    )
    return message, container


class DescriptionContractTests(unittest.TestCase):
    def test_short_message_stays_intact_and_modern_legacy_match(self):
        block = """NAVAREA TEST 1/2026
TEST NOTICE
WITHIN 5 NM OF POSITION 10-00N 020-00E.
CANCEL THIS WARNING 010000 UTC SEP 26."""

        parts = main.partition_navarea_block(block, "NAVAREA TEST 1/2026")
        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0][1]["partition_type"], "NONE")

        message, container = process_partition(*parts[0])
        self.assertEqual(len(message["circles"]), 1)
        description = main.unescape(message["circles"][0]["description"])
        expected = main._description_plain_text(
            main.build_processing_context(block, "NAVAREA TEST 1/2026")[
                "description"
            ]
        )
        self.assertEqual(description, expected)
        self.assertLessEqual(len(description), main.LEGACY_MAX_DESC)

        modern = ET.fromstring(main.export_furuno_modern("TEST", container))
        legacy = ET.fromstring(
            main.generate_legacy_xml_from_messages("TEST", [message], 1, 1)
        )
        modern_description = modern.find("./circles/circle").attrib["description"]
        legacy_description = legacy.find("./circles/circle").attrib["description"]
        self.assertEqual(modern_description, legacy_description)

    def test_description_exactly_at_legacy_limit_is_not_cut(self):
        prefix = (
            "NAVAREA TEST 2/2026 NOTICE "
            "WITHIN 5 NM OF POSITION 10-00N 020-00E. "
        )
        block = prefix + ("X" * (main.LEGACY_MAX_DESC - len(prefix)))
        self.assertEqual(main._partition_description_length(block), 999)

        parts = main.partition_navarea_block(block, "NAVAREA TEST 2/2026")
        self.assertEqual(len(parts), 1)
        message, container = process_partition(*parts[0])
        description = main.unescape(message["circles"][0]["description"])
        self.assertEqual(len(description), main.LEGACY_MAX_DESC)

        modern = ET.fromstring(main.export_furuno_modern("TEST", container))
        legacy = ET.fromstring(
            main.generate_legacy_xml_from_messages("TEST", [message], 1, 1)
        )
        self.assertEqual(
            modern.find("./circles/circle").attrib["description"],
            legacy.find("./circles/circle").attrib["description"],
        )

    def test_long_sections_use_header_object_section_and_footer_once(self):
        block = (
            """NAVAREA TEST 3/2026
HEADER OPERATING NOTICE
1. AREA BOUNDED BY 10-00N 020-00E, 10-10N 020-00E, 10-10N 020-10E, 10-00N 020-10E.
2. WAITING AREA WITHIN 5 NM OF POSITION 11-00N 021-00E.
3. """
            + ("IMPORTANT INFORMATION " * 45)
            + """
CANCEL THIS WARNING 010000 UTC SEP 26."""
        )
        self.assertGreater(
            main._partition_description_length(block),
            main.LEGACY_MAX_DESC,
        )

        parts = main.partition_navarea_block(block, "NAVAREA TEST 3/2026")
        self.assertEqual(
            [metadata["partition_id"] for _, metadata in parts],
            ["1", "2", "3"],
        )

        section_messages = {}
        for sub_block, metadata in parts:
            message, _ = process_partition(sub_block, metadata)
            if message["areas"] or message["circles"]:
                objects = message["areas"] + message["circles"]
                section_messages[metadata["partition_id"]] = objects[0]

        area_description = main.unescape(section_messages["1"]["description"])
        circle_description = main.unescape(section_messages["2"]["description"])
        for description, section, foreign_section in (
            (area_description, "1.", "2."),
            (circle_description, "2.", "1."),
        ):
            self.assertIn("NAVAREA TEST 3/2026", description)
            self.assertIn(section, description)
            self.assertNotIn(f"{foreign_section} ", description)
            self.assertEqual(description.count("NAVAREA TEST 3/2026"), 1)
            self.assertLessEqual(len(description), main.LEGACY_MAX_DESC)

        self.assertEqual(area_description.count("CANCEL THIS WARNING"), 1)
        self.assertEqual(circle_description.count("CANCEL THIS WARNING"), 1)

    def test_partition_composition_does_not_duplicate_identical_fragments(self):
        description = main.unescape(
            main.compose_partition_description(
                "HEADER", "OBJECT SECTION", "HEADER"
            )
        )
        self.assertEqual(description, "HEADER\nOBJECT SECTION")


if __name__ == "__main__":
    unittest.main()