import re
import unittest
from pathlib import Path

import main
from source_intake import load_source


ROOT = Path(__file__).resolve().parents[1]


def navarea_block(path, navarea):
    report = load_source(str(path))
    if report.text is None:
        raise AssertionError(f"Could not decode {path}: {report.error}")
    text = report.text
    start = re.search(r"(?im)^" + re.escape(navarea) + r"\b", text)
    if not start:
        raise AssertionError(f"Missing {navarea}")
    next_header = re.search(r"(?im)^NAVAREA\s+[^\n]+", text[start.end() :])
    end = start.end() + next_header.start() if next_header else len(text)
    return text[start.start() : end]


class RiglistPairingTests(unittest.TestCase):
    def _entries(self, filename, navarea):
        raw = navarea_block(ROOT / filename, navarea)
        normalized = main.normalize_input(raw, main.NormalizerStats())
        return main.extract_riglist_entries(normalized)

    def test_large_coordinate_first_riglist_keeps_names_clean(self):
        entries = self._entries(
            "tests/fixtures/legacy_regression_cases.txt", "NAVAREA I 169/26"
        )

        self.assertEqual(len(entries), 43)
        self.assertIn("VALARIS NORWAY ACP CYGNUS GAS FIELD", entries[10])
        self.assertNotIn("NORTH SEA:", entries[10])
        self.assertIn("NOBLE INTEGRATOR ACP HUGIN A", entries[27])
        self.assertNotIn("NORWEGIAN SEA:", entries[27])
        self.assertNotIn("NOTES", entries[-1].upper())
        self.assertNotIn("CANCEL", entries[-1].upper())

    def test_lettered_riglist_does_not_absorb_following_item_numbers(self):
        entries = self._entries(
            "NAVAREA VII - SOUTH AFRICA.txt", "NAVAREA VII 233/2026"
        )

        self.assertEqual(len(entries), 12)
        self.assertEqual(
            entries[0],
            "22 - 00.80 S 014 - 00.55 E DEEPWATER ORION",
        )
        self.assertEqual(
            entries[1],
            "22 - 00.85 S 014 - 00.45 E WEST ECLIPSE",
        )
        self.assertEqual(
            entries[-1],
            "29 - 19.2 S 014 - 07.2 E SAIPEM 12000",
        )
        self.assertNotIn("4NM", entries[-1].upper())

    def test_each_riglist_label_uses_its_partition_coordinate(self):
        raw = navarea_block(
            ROOT / "tests/fixtures/legacy_regression_cases.txt",
            "NAVAREA IV 735/2026",
        )
        normalized = main.normalize_input(raw, main.NormalizerStats())
        parts = main.partition_navarea_block(normalized, "NAVAREA IV 735/2026")

        self.assertEqual(len(parts), 94)
        for entry, metadata in parts:
            message = main.create_message(
                f"NAVAREA IV 735/2026 [RIG {metadata['partition_id']}]"
            )
            container = main.create_container("IV")
            main.process_block(
                entry,
                message,
                container,
                "NAVAREA IV 735/2026",
                "NAV IV 735/2026",
                metadata,
            )

            self.assertEqual(len(message["labels"]), 1)
            label = message["labels"][0]
            self.assertEqual(label["coord"], main.extract_coordinates(entry)[0])
            self.assertNotIn("NOTES", label["description"].upper())
            self.assertNotIn("CANCEL", label["description"].upper())
            self.assertNotIn("TO REPORT", label["description"].upper())

    def test_riglist_description_keeps_shared_preamble_per_entry(self):
        raw = navarea_block(
            ROOT / "tests/fixtures/legacy_regression_cases.txt",
            "NAVAREA I 169/26",
        )
        normalized = main.normalize_input(raw, main.NormalizerStats())
        parts = main.partition_navarea_block(normalized, "NAVAREA I 169/26")
        entry, metadata = parts[0]
        message = main.create_message(
            "NAVAREA I 169/26 [RIG 1]", metadata=metadata
        )
        container = main.create_container("I")

        main.process_block(
            entry,
            message,
            container,
            "NAVAREA I 169/26",
            "NAV I 169/26",
            metadata,
        )

        description = message["labels"][0]["description"].upper()
        self.assertIn("RIGLIST", description)
        self.assertIn("CORRECT AT 100430 UTC AUG 2026", description)
        self.assertIn("VALARIS 123 ACP P18-A", description)
        self.assertNotIn("SHELF DRILLING WINNER", description)
        self.assertNotIn("NOTES", description)
        self.assertNotIn("CANCEL", description)


if __name__ == "__main__":
    unittest.main()