import unittest
from pathlib import Path

from corpus_differential import build_corpus_report


ROOT = Path(__file__).resolve().parents[1]


class CorpusDifferentialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = build_corpus_report(ROOT)

    def test_all_available_navarea_sources_are_processed(self):
        self.assertEqual(self.report["source_file_count"], 21)
        self.assertGreaterEqual(self.report["navarea_block_count"], 600)
        self.assertEqual(self.report["error_count"], 0)
        self.assertGreater(
            self.report["processed_message_count"],
            self.report["navarea_block_count"],
        )

    def test_report_separates_geometry_and_operation_outcomes(self):
        self.assertIn("CONFIRMED", self.report["geometry_status_counts"])
        self.assertIn("REFERENCE_ONLY", self.report["geometry_status_counts"])
        self.assertIn("UNKNOWN", self.report["geometry_status_counts"])
        self.assertIn("EXPLICIT", self.report["geometry_basis_counts"])
        self.assertGreater(self.report["operation_only_count"], 0)

    def test_mixed_geometry_findings_have_source_references(self):
        self.assertGreater(self.report["multiple_explicit_geometry_count"], 0)
        ix_findings = [
            finding
            for finding in self.report["component_loss_findings"]
            if finding["navarea"].upper() == "NAVAREA IX 208/2026"
        ]
        self.assertTrue(ix_findings)
        self.assertIn("line", ix_findings[0]["missing_explicit_components"])
        self.assertEqual(ix_findings[0]["source_file"], "NAV-IX.txt")


if __name__ == "__main__":
    unittest.main()