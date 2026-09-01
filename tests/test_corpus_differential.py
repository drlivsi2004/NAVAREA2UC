import unittest
import tempfile
from pathlib import Path

from corpus_runner import review_warning_duplicates
from tests.corpus_differential import build_corpus_report


ROOT = Path(__file__).resolve().parents[1]


class CorpusDifferentialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = build_corpus_report(ROOT)

    def test_all_available_navarea_sources_are_processed(self):
        self.assertEqual(self.report["source_file_count"], 21)
        self.assertGreater(self.report["navarea_block_count"], 0)
        self.assertEqual(self.report["error_count"], 0)
        self.assertGreater(
            self.report["processed_message_count"],
            self.report["navarea_block_count"],
        )

    def test_future_coastal_sources_can_be_enabled_explicitly(self):
        report = build_corpus_report(ROOT, include_future_coastal=True)
        self.assertEqual(report["source_file_count"], 69)
        self.assertGreaterEqual(report["navarea_block_count"], 600)
        self.assertEqual(report["error_count"], 0)

    def test_coastal_duplicate_review_is_separate_and_auditable(self):
        review = self.report["duplicate_review"]
        self.assertEqual(review["source_file_count"], 69)
        self.assertGreater(review["intentional_repeat_count"], 0)
        self.assertEqual(review["true_duplicate_count"], 2)
        self.assertEqual(review["status"], "REVIEW_REQUIRED")
        self.assertTrue(
            all(
                finding["source_references"]
                for finding in review["intentional_repeats"]
            )
        )
        self.assertTrue(
            all(
                finding["source_references"]
                for finding in review["true_duplicates"]
            )
        )

    def test_report_separates_geometry_and_operation_outcomes(self):
        self.assertIn("CONFIRMED", self.report["geometry_status_counts"])
        self.assertIn("REFERENCE_ONLY", self.report["geometry_status_counts"])
        self.assertIn("UNKNOWN", self.report["geometry_status_counts"])
        self.assertIn("EXPLICIT", self.report["geometry_basis_counts"])
        self.assertGreater(self.report["operation_only_count"], 0)

    def test_mixed_geometry_findings_have_source_references(self):
        self.assertGreater(self.report["multiple_explicit_geometry_count"], 0)
        ix_records = [
            record
            for record in self.report["multiple_explicit_geometry"]
            if record["navarea"].upper() == "NAVAREA IX 208/2026"
        ]
        self.assertTrue(ix_records)
        self.assertEqual(ix_records[0]["missing_explicit_components"], [])

        remaining_findings = [
            finding
            for finding in self.report["component_loss_findings"]
        ]
        self.assertEqual(remaining_findings, [])

    def test_review_scan_distinguishes_cross_stream_repeat_from_true_duplicate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            primary = root / "primary.txt"
            coastal = root / "NAVAREA TEST - COASTAL.txt"
            primary.write_text(
                """NAVAREA TEST 7/2026
POINT AT 10-00.0N 020-00.0E.
""",
                encoding="utf-8",
            )
            coastal.write_text(
                """AVINAV 7/2026
POINT AT 11-00.0N 021-00.0E.
""",
                encoding="utf-8",
            )

            reviewed = review_warning_duplicates(
                root,
                [primary, coastal],
                {
                    "primary.txt": "primary",
                    "NAVAREA TEST - COASTAL.txt": "coastal",
                },
            )

            self.assertEqual(reviewed["true_duplicate_count"], 0)
            self.assertEqual(reviewed["intentional_repeat_count"], 1)
            repeat = reviewed["intentional_repeats"][0]
            self.assertEqual(repeat["warning_identity"]["number"], 7)
            self.assertEqual(
                {item["source"] for item in repeat["source_references"]},
                {"primary.txt", "NAVAREA TEST - COASTAL.txt"},
            )

            primary.write_text(
                """NAVAREA TEST 7/2026
POINT AT 10-00.0N 020-00.0E.

NAVAREA TEST 7/2026
POINT AT 12-00.0N 022-00.0E.
""",
                encoding="utf-8",
            )
            reviewed = review_warning_duplicates(
                root,
                [primary],
                {"primary.txt": "primary"},
            )
            self.assertEqual(reviewed["intentional_repeat_count"], 0)
            self.assertEqual(reviewed["true_duplicate_count"], 1)
            duplicate = reviewed["true_duplicates"][0]
            self.assertEqual(
                duplicate["source_references"][0]["source"],
                "primary.txt",
            )

    def test_review_scan_does_not_count_summary_references_as_duplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            coastal = root / "coastal.txt"
            coastal.write_text(
                """NEW WARNINGS: AVINAV 7/2026.

AVINAV 7/2026
POINT AT 10-00.0N 020-00.0E.
""",
                encoding="utf-8",
            )
            reviewed = review_warning_duplicates(
                root,
                [coastal],
                {"coastal.txt": "coastal"},
            )
            self.assertEqual(reviewed["true_duplicate_count"], 0)


if __name__ == "__main__":
    unittest.main()