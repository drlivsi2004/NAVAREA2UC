import unittest

import main


class RecommendedRouteSemanticsTests(unittest.TestCase):
    def test_recommended_route_uses_confirmed_furuno_presentation(self):
        block = (
            "RECOMMENDED ROUTE FROM 46-00.0N 031-00.0E "
            "TO 46-10.0N 031-10.0E"
        )
        ctx = main.build_processing_context(
            block,
            "NAVAREA III 1/2026",
        )
        container = main.create_container("III")
        message = main.create_message("NAVAREA III 1/2026")

        self.assertTrue(main.handle_trackline(ctx, container, message))
        self.assertEqual(len(container["lines"]), 1)

        line = container["lines"][0]
        self.assertEqual(line["color"], "NINFO")
        self.assertEqual(line["lineType"], 1)
        self.assertEqual(line["checkDanger"], 0)
        self.assertEqual(container["labels"][0]["color"], "NINFO")

        xml = main.export_furuno_modern("III", container)
        self.assertIn('<attribute lineType="1" linkedDocument=""/>', xml)
        self.assertIn('<display S52colorcode="NINFO" lineWidth="3"/>', xml)

    def test_unrelated_route_keeps_default_line_type(self):
        block = "TRANSIT ROUTE FROM 46-00.0N 031-00.0E TO 46-10.0N 031-10.0E"
        ctx = main.build_processing_context(block, "NAVAREA III 2/2026")
        container = main.create_container("III")
        message = main.create_message("NAVAREA III 2/2026")

        self.assertTrue(main.handle_trackline(ctx, container, message))
        self.assertEqual(container["lines"][0]["lineType"], 2)


if __name__ == "__main__":
    unittest.main()