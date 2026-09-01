import unittest
from unittest.mock import patch

from source_intake import (
    EncodingDecodeError,
    AmbiguousEncodingError,
    LowConfidenceEncodingError,
    MIN_DECODING_CONFIDENCE,
    Status,
    decode_source,
    report_summary,
)
from source_intake.encoding import EncodingIntelligence


class SourceIntakeEncodingTests(unittest.TestCase):
    def test_confidence_floor_is_explicit(self):
        self.assertEqual(MIN_DECODING_CONFIDENCE, 0.50)

    def test_strict_utf8_is_successful_without_warning(self):
        report = decode_source("NAVAREA TEST\n".encode("utf-8"), source_id="utf8")

        self.assertEqual(report.status, Status.SUCCESS)
        self.assertEqual(report.encoding, "utf-8")
        self.assertEqual(report.confidence, 0.90)
        self.assertEqual(report.text, "NAVAREA TEST\n")
        self.assertEqual(report.warnings, [])

    def test_utf16_without_bom_is_not_misclassified_as_utf8(self):
        report = decode_source(
            "NAVAREA TEST\n".encode("utf-16-le"), source_id="utf16-le"
        )

        self.assertEqual(report.status, Status.SUCCESS)
        self.assertEqual(report.encoding, "utf-16-le")
        self.assertEqual(report.confidence, 0.80)
        self.assertEqual(report.text, "NAVAREA TEST\n")

    def test_strict_fallback_is_imported_with_explicit_warning(self):
        report = decode_source(
            "AVURNAV: été\n".encode("windows-1252"), source_id="cp1252"
        )

        self.assertEqual(report.status, Status.FALLBACK)
        self.assertEqual(report.encoding, "windows-1252")
        self.assertEqual(report.confidence, MIN_DECODING_CONFIDENCE)
        self.assertEqual(report.text, "AVURNAV: été\n")
        self.assertTrue(any("fallback decoding selected" in w for w in report.warnings))

    def test_low_confidence_strict_decode_is_refused(self):
        with self.assertRaises(LowConfidenceEncodingError) as raised:
            EncodingIntelligence.decode_with_fallback(
                b"plain text", "utf-8", MIN_DECODING_CONFIDENCE - 0.01
            )

        self.assertIn("source was not imported", str(raised.exception))
        self.assertTrue(raised.exception.warnings)

        with patch.object(
            EncodingIntelligence,
            "detect_encoding",
            return_value=("utf-8", MIN_DECODING_CONFIDENCE - 0.01),
        ):
            report = decode_source(b"plain text", source_id="low-confidence")

        self.assertEqual(report.status, Status.FAILED)
        self.assertIsNone(report.text)
        self.assertIn("source was not imported", report.error)

    def test_damaged_bom_is_refused_without_single_byte_reinterpretation(self):
        report = decode_source(b"\xff\xfeA", source_id="damaged-utf16")

        self.assertEqual(report.status, Status.FAILED)
        self.assertIsNone(report.text)
        self.assertEqual(report.encoding, "unknown")
        self.assertIn("BOM", report.error)
        self.assertNotIn("windows-1252", report.encoding)
        self.assertIn("source was not imported", report_summary([report]))

    def test_no_strict_decoder_is_refused_instead_of_latin1(self):
        with self.assertRaises(EncodingDecodeError) as raised:
            EncodingIntelligence.decode_with_fallback(
                b"\xff", fallback_chain=[]
            )

        self.assertIn("minimum confidence threshold", str(raised.exception))
        self.assertIn("source was not imported", str(raised.exception))

    def test_ambiguous_short_bytes_are_refused(self):
        report = decode_source(b"\xff", source_id="ambiguous")

        self.assertEqual(report.status, Status.FAILED)
        self.assertIsNone(report.text)
        self.assertIsInstance(report.error, str)
        self.assertIn("unambiguous text", report.error)
        self.assertIn("source was not imported", report.error)


if __name__ == "__main__":
    unittest.main()