import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import corpus_runner


ROOT = Path(__file__).resolve().parents[1]
WINDOWS_WORKFLOW = ROOT / ".github" / "workflows" / "build-windows.yml"


def _workflow_step_text(workflow_path, step_name):
    """Return one workflow step without requiring a YAML parser dependency."""

    workflow = workflow_path.read_text(encoding="utf-8")
    marker = f"    - name: {step_name}\n"
    start = workflow.index(marker)
    end = workflow.find("\n    - name:", start + len(marker))
    if end == -1:
        end = len(workflow)
    return workflow[start:end]


class CorpusRunnerTests(unittest.TestCase):
    def test_description_audit_records_source_handler_modern_and_legacy(self):
        report = corpus_runner.run_corpus(
            ROOT,
            [ROOT / "NAVAREA IV - USA.txt", ROOT / "NAVAREA XII - USA.txt"],
        )
        records = {
            message["id"]: message
            for message in report["messages"]
            if message["id"] in {
                "NAVAREA IV 616/2025",
                "NAVAREA IV 653/2026",
                "NAVAREA XII 354/2025",
            }
        }

        self.assertEqual(len(records), 3)
        self.assertEqual(report["description_audit"]["messages"], 284)
        self.assertEqual(report["description_audit"]["source_files"], 2)
        for message in records.values():
            audit = message["description_audit"]
            self.assertIn("source_expectation", audit)
            self.assertTrue(audit["source_section"])
            self.assertEqual(len(audit["objects"]), message["object_counts"]["object_count"])
            for obj in audit["objects"]:
                self.assertTrue(obj["handler_description"])
                self.assertTrue(obj["modern_description"])
                self.assertEqual(
                    obj["modern_description"], obj["legacy_description"]
                )
                self.assertEqual(
                    obj["mismatch_classification"]["modern_to_legacy"], "MATCH"
                )
                self.assertNotEqual(
                    obj["mismatch_classification"]["overall"], "MODERN_MISMATCH"
                )
                self.assertNotEqual(
                    obj["mismatch_classification"]["overall"], "LEGACY_MISMATCH"
                )

        summary = report["summary"]["description_audit"]
        self.assertEqual(summary["messages"], len(report["messages"]))
        self.assertGreater(summary["objects"], 0)

    def test_full_corpus_description_audit_requires_semantic_context(self):
        report = corpus_runner.run_corpus(ROOT)
        audit_summary = report["summary"]["description_audit"]

        self.assertEqual(audit_summary["messages"], 983)
        self.assertGreater(audit_summary["objects"], 0)
        self.assertEqual(
            audit_summary["semantic_context_statuses"],
            {"PRESENT": audit_summary["objects"]},
        )
        for message in report["messages"]:
            for obj in message["description_audit"]["objects"]:
                self.assertEqual(
                    obj["semantic_context"]["status"],
                    "PRESENT",
                    msg=f"{message['id']} object {obj['object_index']}",
                )
        validation = corpus_runner.validate_report(report)
        self.assertEqual(validation["semantic_context_missing_count"], 0)
        self.assertEqual(validation["status"], "PASS")

    def test_windows_workflow_captures_preview_and_gates_on_boolean_match(self):
        step = _workflow_step_text(
            WINDOWS_WORKFLOW,
            "Preview reviewed corpus baseline",
        )
        self.assertIn("shell: pwsh", step)
        self.assertIn("$previewPath = \"reports/corpus_baseline_preview.json\"", step)

        # Keep the Windows-only wiring covered on POSIX runners. The order is
        # important: capture the Python status before parsing the captured JSON,
        # and reject a stale report before honoring that status.
        required_fragments = (
            "python corpus_runner.py",
            "--preview-baseline reports/corpus_baseline.json",
            "--source-report reports/corpus_differential_latest.json",
            "--json > $previewPath",
            "$previewStatus = $LASTEXITCODE",
            "if (-not (Test-Path $previewPath))",
            "Get-Content -Raw $previewPath | ConvertFrom-Json",
            "if ($preview.reviewed_report_matches_current -ne $true)",
            "if ($previewStatus -ne 0)",
        )
        positions = []
        for fragment in required_fragments:
            position = step.find(fragment)
            self.assertNotEqual(
                position,
                -1,
                msg=f"Windows baseline preview step is missing: {fragment}",
            )
            positions.append(position)
        self.assertEqual(positions, sorted(positions))
        self.assertIn("exit $previewStatus", step)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "NAV-TEST.txt"
            source.write_text(
                """NAVAREA TEST 1/2026
AREA BOUNDED BY 10-00.0N 020-00.0E, 10-00.0N 021-00.0E,
11-00.0N 021-00.0E, 11-00.0N 020-00.0E.
""",
                encoding="utf-8",
            )
            current_report = corpus_runner.run_corpus(root, [source])
            source_report = root / "reviewed-full-report.json"
            baseline = root / "compact-baseline.json"
            preview_path = root / "corpus_baseline_preview.json"

            def run_captured_preview():
                with preview_path.open("w", encoding="utf-8") as preview_file:
                    return subprocess.run(
                        [
                            sys.executable,
                            str(ROOT / "corpus_runner.py"),
                            "--root",
                            str(root),
                            "--source",
                            str(source),
                            "--preview-baseline",
                            str(baseline),
                            "--source-report",
                            str(source_report),
                            "--json",
                        ],
                        cwd=ROOT,
                        stdout=preview_file,
                        stderr=subprocess.PIPE,
                        text=True,
                        check=False,
                    )

            source_report.write_text(
                json.dumps(current_report),
                encoding="utf-8",
            )
            matching_result = run_captured_preview()
            self.assertEqual(matching_result.returncode, 0)
            self.assertTrue(preview_path.is_file())
            matching_preview = json.loads(preview_path.read_text(encoding="utf-8"))
            self.assertIs(matching_preview["reviewed_report_matches_current"], True)
            self.assertTrue(
                matching_preview["reviewed_report_matches_current"]
                and matching_result.returncode == 0
            )

            stale_report = json.loads(source_report.read_text(encoding="utf-8"))
            stale_report["messages"][0]["id"] = "NAVAREA TEST 99/2026"
            source_report.write_text(json.dumps(stale_report), encoding="utf-8")
            stale_result = run_captured_preview()
            self.assertEqual(stale_result.returncode, 1)
            self.assertTrue(preview_path.is_file())
            stale_preview = json.loads(preview_path.read_text(encoding="utf-8"))
            self.assertIs(
                stale_preview["reviewed_report_matches_current"],
                False,
            )
            self.assertFalse(
                stale_preview["reviewed_report_matches_current"]
                and stale_result.returncode == 0
            )

    def test_windows_workflow_has_isolated_native_preview_smoke_gate(self):
        smoke_step = _workflow_step_text(
            WINDOWS_WORKFLOW,
            "Smoke test captured baseline approval path",
        )
        self.assertIn("shell: pwsh", smoke_step)
        required_fragments = (
            "$previewPath = Join-Path $env:RUNNER_TEMP",
            "python corpus_runner.py",
            "--output $sourceReportPath",
            "function Assert-BaselinePreviewApproval",
            "--preview-baseline reports/corpus_baseline.json",
            "--source-report $ExpectedSourceReport",
            "$previewOutput = python corpus_runner.py",
            "$previewStatus = $LASTEXITCODE",
            "$previewOutput | Set-Content -Path $previewPath -Encoding utf8NoBOM",
            "Get-Content -Raw $previewPath | ConvertFrom-Json",
            "$preview.reviewed_report_matches_current -eq $true",
            "Assert-BaselinePreviewApproval $sourceReportPath $true",
            '$staleReport.messages[0].id = "NAVAREA WINDOWS SMOKE 99/2026"',
            "Assert-BaselinePreviewApproval $sourceReportPath $false",
        )
        for fragment in required_fragments:
            self.assertIn(
                fragment,
                smoke_step,
                msg=f"Windows native preview smoke step is missing: {fragment}",
            )

        workflow = WINDOWS_WORKFLOW.read_text(encoding="utf-8")
        build_job = workflow[workflow.index("  build:") :]
        self.assertIn("      - validate-windows-preview", build_job)

    @unittest.skipUnless(
        os.name == "posix",
        "direct shell-wrapper launch is covered on POSIX checkouts",
    )
    def test_release_validation_wrapper_launches_from_clean_checkout(self):
        with tempfile.TemporaryDirectory() as directory:
            checkout = Path(directory) / "checkout"
            clone = subprocess.run(
                ["git", "clone", "--quiet", "--no-local", str(ROOT), str(checkout)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(
                clone.returncode,
                0,
                msg=f"clean checkout failed:\n{clone.stderr}",
            )

            environment = os.environ.copy()
            environment["CORPUS_REPORT_PATH"] = str(
                Path(directory) / "release-corpus.json"
            )
            wrapper = checkout / "scripts" / "release-validation.sh"

            try:
                result = subprocess.run(
                    [str(wrapper)],
                    cwd=checkout,
                    env=environment,
                    capture_output=True,
                    text=True,
                    check=False,
                )
            except OSError as error:
                self.fail(
                    "release validation wrapper could not be launched "
                    f"from a clean checkout: {error}"
                )

        self.assertEqual(
            result.returncode,
            0,
            msg=f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )
        self.assertIn("Release validation: PASS", result.stdout)

    def test_release_validation_command_starts_and_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            environment = os.environ.copy()
            environment["CORPUS_REPORT_PATH"] = str(
                Path(directory) / "release-corpus.json"
            )

            result = subprocess.run(
                ["bash", str(ROOT / "scripts" / "release-validation.sh")],
                cwd=ROOT,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(
            result.returncode,
            0,
            msg=f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )
        self.assertIn("Release validation: PASS", result.stdout)

    def test_update_baseline_derives_metadata_and_preserves_reviewed_findings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "NAV-TEST.txt"
            source.write_text(
                """NAVAREA TEST 1/2026
AREA BOUNDED BY 10-00.0N 020-00.0E, 10-00.0N 021-00.0E,
11-00.0N 021-00.0E, 11-00.0N 020-00.0E.
""",
                encoding="utf-8",
            )
            full_report = corpus_runner.run_corpus(root, [source])
            source_report_path = root / "reviewed-full-report.json"
            source_report_path.write_text(
                json.dumps(full_report), encoding="utf-8"
            )
            baseline_path = root / "compact-baseline.json"
            baseline_path.write_text(
                json.dumps(
                    {
                        "baseline_messages": 999,
                        "reviewed_component_losses": [
                            {"id": "reviewed", "kind": "line"}
                        ],
                    }
                ),
                encoding="utf-8",
            )

            status = corpus_runner.main_cli(
                [
                    "--root",
                    str(root),
                    "--source",
                    str(source),
                    "--update-baseline",
                    str(baseline_path),
                    "--source-report",
                    str(source_report_path),
                ]
            )

            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
            self.assertEqual(status, 0)
            self.assertEqual(baseline["baseline_messages"], 1)
            self.assertEqual(
                baseline["report_sha256"],
                corpus_runner._report_fingerprint(full_report),
            )
            self.assertEqual(baseline["source_report"], "reviewed-full-report.json")
            self.assertEqual(
                baseline["reviewed_component_losses"],
                [{"id": "reviewed", "kind": "line"}],
            )

    def test_update_baseline_rejects_stale_source_fingerprint_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "NAV-TEST.txt"
            source.write_text(
                """NAVAREA TEST 1/2026
POINT AT 10-00.0N 020-00.0E.
""",
                encoding="utf-8",
            )
            current_report = corpus_runner.run_corpus(root, [source])
            reviewed_report = json.loads(json.dumps(current_report))
            reviewed_report["messages"][0]["id"] = "NAVAREA TEST 99/2026"
            source_report_path = root / "reviewed-full-report.json"
            source_report_path.write_text(
                json.dumps(reviewed_report), encoding="utf-8"
            )
            baseline_path = root / "compact-baseline.json"
            original_baseline = {
                "baseline_messages": 7,
                "report_sha256": "a" * 64,
                "reviewed_component_losses": [{"id": "reviewed"}],
            }
            baseline_path.write_text(
                json.dumps(original_baseline), encoding="utf-8"
            )
            stderr = io.StringIO()

            with redirect_stderr(stderr):
                status = corpus_runner.main_cli(
                    [
                        "--root",
                        str(root),
                        "--source",
                        str(source),
                        "--update-baseline",
                        str(baseline_path),
                        "--source-report",
                        str(source_report_path),
                    ]
                )

            self.assertEqual(status, 1)
            self.assertIn("fingerprint", stderr.getvalue())
            self.assertEqual(
                json.loads(baseline_path.read_text(encoding="utf-8")),
                original_baseline,
            )

    def test_update_baseline_rejects_inconsistent_source_message_count(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "NAV-TEST.txt"
            source.write_text(
                """NAVAREA TEST 1/2026
POINT AT 10-00.0N 020-00.0E.
""",
                encoding="utf-8",
            )
            reviewed_report = corpus_runner.run_corpus(root, [source])
            reviewed_report["summary"]["messages"] = 2
            source_report_path = root / "reviewed-full-report.json"
            source_report_path.write_text(
                json.dumps(reviewed_report), encoding="utf-8"
            )
            baseline_path = root / "compact-baseline.json"
            original_baseline = {
                "baseline_messages": 1,
                "report_sha256": "b" * 64,
            }
            baseline_path.write_text(
                json.dumps(original_baseline), encoding="utf-8"
            )
            stderr = io.StringIO()

            with redirect_stderr(stderr):
                status = corpus_runner.main_cli(
                    [
                        "--root",
                        str(root),
                        "--source",
                        str(source),
                        "--update-baseline",
                        str(baseline_path),
                        "--source-report",
                        str(source_report_path),
                    ]
                )

            self.assertEqual(status, 1)
            self.assertIn("message count", stderr.getvalue())
            self.assertEqual(
                json.loads(baseline_path.read_text(encoding="utf-8")),
                original_baseline,
            )

    def test_preview_baseline_shows_derived_metadata_and_preserves_review_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "NAV-TEST.txt"
            source.write_text(
                """NAVAREA TEST 1/2026
AREA BOUNDED BY 10-00.0N 020-00.0E, 10-00.0N 021-00.0E,
11-00.0N 021-00.0E, 11-00.0N 020-00.0E.
""",
                encoding="utf-8",
            )
            current_report = corpus_runner.run_corpus(root, [source])
            source_report_path = root / "reviewed-full-report.json"
            source_report_path.write_text(
                json.dumps(current_report), encoding="utf-8"
            )
            baseline_path = root / "compact-baseline.json"
            original_baseline = {
                "baseline_messages": 99,
                "report_sha256": "a" * 64,
                "reviewed_component_losses": [{"id": "reviewed", "kind": "line"}],
            }
            baseline_path.write_text(json.dumps(original_baseline), encoding="utf-8")
            stdout = io.StringIO()

            with redirect_stdout(stdout):
                status = corpus_runner.main_cli(
                    [
                        "--root",
                        str(root),
                        "--source",
                        str(source),
                        "--preview-baseline",
                        str(baseline_path),
                        "--source-report",
                        str(source_report_path),
                    ]
                )

            self.assertEqual(status, 0)
            output = stdout.getvalue()
            self.assertIn("Compact baseline preview (read-only)", output)
            self.assertIn("Derived message count: 1", output)
            self.assertIn(
                f"Derived fingerprint: {corpus_runner._report_fingerprint(current_report)}",
                output,
            )
            self.assertIn(
                "Reviewed report matches current corpus: YES",
                output,
            )
            self.assertIn("Preserved review metadata:", output)
            self.assertIn('"id": "reviewed"', output)
            self.assertEqual(
                json.loads(baseline_path.read_text(encoding="utf-8")),
                original_baseline,
            )

    def test_preview_baseline_reports_stale_review_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "NAV-TEST.txt"
            source.write_text(
                """NAVAREA TEST 1/2026
POINT AT 10-00.0N 020-00.0E.
""",
                encoding="utf-8",
            )
            reviewed_report = corpus_runner.run_corpus(root, [source])
            reviewed_report["messages"][0]["id"] = "NAVAREA TEST 99/2026"
            source_report_path = root / "reviewed-full-report.json"
            source_report_path.write_text(
                json.dumps(reviewed_report), encoding="utf-8"
            )
            baseline_path = root / "compact-baseline.json"
            original_baseline = {
                "baseline_messages": 1,
                "report_sha256": "b" * 64,
                "reviewed_component_losses": [{"id": "reviewed"}],
            }
            baseline_path.write_text(json.dumps(original_baseline), encoding="utf-8")
            stdout = io.StringIO()

            with redirect_stdout(stdout):
                status = corpus_runner.main_cli(
                    [
                        "--root",
                        str(root),
                        "--source",
                        str(source),
                        "--preview-baseline",
                        str(baseline_path),
                        "--source-report",
                        str(source_report_path),
                    ]
                )

            self.assertEqual(status, 1)
            self.assertIn(
                "Reviewed report matches current corpus: NO",
                stdout.getvalue(),
            )
            self.assertEqual(
                json.loads(baseline_path.read_text(encoding="utf-8")),
                original_baseline,
            )

    def test_preview_baseline_json_outputs_structured_result_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "NAV-TEST.txt"
            source.write_text(
                """NAVAREA TEST 1/2026
AREA BOUNDED BY 10-00.0N 020-00.0E, 10-00.0N 021-00.0E,
11-00.0N 021-00.0E, 11-00.0N 020-00.0E.
""",
                encoding="utf-8",
            )
            current_report = corpus_runner.run_corpus(root, [source])
            source_report_path = root / "reviewed-full-report.json"
            source_report_path.write_text(
                json.dumps(current_report), encoding="utf-8"
            )
            baseline_path = root / "compact-baseline.json"
            original_baseline = {
                "baseline_messages": 99,
                "report_sha256": "a" * 64,
                "reviewed_component_losses": [{"id": "reviewed", "kind": "line"}],
            }
            baseline_path.write_text(json.dumps(original_baseline), encoding="utf-8")
            stdout = io.StringIO()

            with redirect_stdout(stdout):
                status = corpus_runner.main_cli(
                    [
                        "--root",
                        str(root),
                        "--source",
                        str(source),
                        "--preview-baseline",
                        str(baseline_path),
                        "--source-report",
                        str(source_report_path),
                        "--json",
                    ]
                )

            structured = json.loads(stdout.getvalue())
            self.assertEqual(status, 0)
            self.assertEqual(structured["reviewed_report_messages"], 1)
            self.assertEqual(
                structured["reviewed_report_sha256"],
                corpus_runner._report_fingerprint(current_report),
            )
            self.assertEqual(structured["current_messages"], 1)
            self.assertEqual(
                structured["current_report_sha256"],
                corpus_runner._report_fingerprint(current_report),
            )
            self.assertTrue(structured["reviewed_report_matches_current"])
            self.assertEqual(
                structured["review_metadata"],
                {"reviewed_component_losses": [{"id": "reviewed", "kind": "line"}]},
            )
            self.assertEqual(
                structured["proposed_baseline"]["reviewed_component_losses"],
                original_baseline["reviewed_component_losses"],
            )
            self.assertEqual(
                json.loads(baseline_path.read_text(encoding="utf-8")),
                original_baseline,
            )

    def test_preview_baseline_json_outputs_stale_result_and_nonzero_status(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "NAV-TEST.txt"
            source.write_text(
                """NAVAREA TEST 1/2026
POINT AT 10-00.0N 020-00.0E.
""",
                encoding="utf-8",
            )
            reviewed_report = corpus_runner.run_corpus(root, [source])
            reviewed_report["messages"][0]["id"] = "NAVAREA TEST 99/2026"
            source_report_path = root / "reviewed-full-report.json"
            source_report_path.write_text(
                json.dumps(reviewed_report), encoding="utf-8"
            )
            baseline_path = root / "compact-baseline.json"
            stdout = io.StringIO()

            with redirect_stdout(stdout):
                status = corpus_runner.main_cli(
                    [
                        "--root",
                        str(root),
                        "--source",
                        str(source),
                        "--preview-baseline",
                        str(baseline_path),
                        "--source-report",
                        str(source_report_path),
                        "--preview-baseline-json",
                    ]
                )

            structured = json.loads(stdout.getvalue())
            self.assertEqual(status, 1)
            self.assertFalse(structured["reviewed_report_matches_current"])
            self.assertEqual(structured["reviewed_report_messages"], 1)
            self.assertEqual(structured["current_messages"], 1)

    def test_discovers_primary_navarea_sources_and_reports_geometry(self):
        sources = corpus_runner.discover_sources(ROOT)
        self.assertEqual(len(sources), 21)
        self.assertEqual(
            {path.name for path in sources},
            {
                line.strip()
                for line in (
                    ROOT / corpus_runner.PRIMARY_SOURCE_MANIFEST
                ).read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.lstrip().startswith("#")
            },
        )

        report = corpus_runner.run_corpus(ROOT)

        self.assertEqual(report["summary"]["source_files"], 21)
        self.assertGreater(report["summary"]["source_blocks"], 0)
        self.assertEqual(report["summary"]["intake_errors"], 0)
        self.assertEqual(report["summary"]["processing_errors"], 0)
        self.assertEqual(len(report["blocks"]), report["summary"]["source_blocks"])
        self.assertGreaterEqual(len(report["messages"]), len(report["blocks"]))
        self.assertIn(
            "CONFIRMED_GEOMETRY",
            report["summary"]["geometry_status_counts"],
        )
        self.assertIn(
            "REFERENCE_ONLY_COORDINATES",
            report["summary"]["geometry_status_counts"],
        )
        self.assertNotIn(
            "REJECTED_INVALID_AREA",
            report["summary"]["geometry_status_counts"],
        )
        self.assertIn(
            "OPERATION_ONLY",
            report["summary"]["geometry_status_counts"],
        )

    def test_future_coastal_sources_are_retained_as_an_opt_in_set(self):
        primary = corpus_runner.discover_sources(ROOT)
        all_sources = corpus_runner.discover_sources(
            ROOT,
            include_future_coastal=True,
        )
        future_manifest = {
            line.strip()
            for line in (
                ROOT / corpus_runner.FUTURE_COASTAL_MANIFEST
            ).read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }

        self.assertEqual(len(all_sources), 69)
        self.assertEqual(len(future_manifest), 48)
        self.assertEqual(
            {path.name for path in all_sources} - {path.name for path in primary},
            future_manifest,
        )

    def test_mixed_geometry_report_keeps_statement_references_and_loss_signal(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "NAV-TEST.txt"
            source.write_text(
                """NAVAREA TEST 1/2026
ROUTE NO. 1:
A 10-00.0N 020-00.0E
B 11-00.0N 021-00.0E
WAITING AREA BOUNDED BY 12-00.0N 022-00.0E, 13-00.0N 022-00.0E,
14-00.0N 023-00.0E.
""",
                encoding="utf-8",
            )

            report = corpus_runner.run_corpus(Path(directory), [source])
            self.assertEqual(report["summary"]["source_blocks"], 1)
            self.assertEqual(
                report["summary"]["multiple_explicit_geometry_blocks"], 1
            )

            message = report["messages"][0]
            self.assertTrue(message["multiple_explicit_geometry"])
            self.assertTrue(message["source_block_multiple_explicit_geometry"])
            self.assertEqual(
                {item["kind"] for item in message["explicit_geometry_statements"]},
                {"area", "line"},
            )
            self.assertTrue(
                all(
                    item["source_reference"].startswith("NAV-TEST.txt:")
                    for item in message["explicit_geometry_statements"]
                )
            )
            self.assertEqual(message["geometry_status"], "CONFIRMED_GEOMETRY")
            self.assertEqual(
                message["missing_geometry_components"][0]["kind"], "area"
            )

    def test_radius_warning_without_center_is_not_missing_circle(self):
        report = corpus_runner.run_corpus(
            ROOT, [ROOT / "NAVAREA V - BRAZIL.txt"]
        )
        targets = [
            message
            for message in report["messages"]
            if message["navarea"] == "NAVAREA V 470/26"
        ]
        self.assertEqual(len(targets), 1)
        target = targets[0]
        self.assertEqual(target["object_counts"]["areas"], 1)
        self.assertEqual(target["object_counts"]["circles"], 0)
        self.assertFalse(target["missing_geometry_components"])

    def test_differential_report_classifies_geometry_change(self):
        before = {
            "messages": [
                {
                    "source": "NAV-I.txt",
                    "source_block_index": 1,
                    "id": "NAVAREA I 1/2026",
                    "selected_handler": "handle_area",
                    "object_counts": {
                        "areas": 1,
                        "lines": 0,
                        "circles": 0,
                        "labels": 0,
                        "object_count": 1,
                    },
                    "geometry_statuses": ["CONFIRMED_GEOMETRY"],
                    "diagnostic_codes": [],
                }
            ]
        }
        after = json.loads(json.dumps(before))
        after["messages"][0]["selected_handler"] = "handle_single_point"
        after["messages"][0]["object_counts"] = {
            "areas": 0,
            "lines": 0,
            "circles": 0,
            "labels": 1,
            "object_count": 1,
        }
        after["messages"][0]["geometry_statuses"] = ["REFERENCE_ONLY_COORDINATES"]

        differential = corpus_runner.compare_reports(before, after)
        self.assertEqual(differential["changed_messages"], 1)
        self.assertEqual(differential["unexpected_changes"], 1)
        self.assertEqual(differential["changes"][0]["severity"], "ERROR")

    def test_fail_on_loss_gate_passes_without_component_loss(self):
        status = corpus_runner.main_cli(
            [
                "--root",
                str(ROOT),
                "--source",
                str(ROOT / "NAVAREA IX - PAKISTAN.txt"),
                "--fail-on-loss",
            ]
        )
        self.assertEqual(status, 0)

    def test_validation_allows_reviewed_loss_but_blocks_new_loss(self):
        report = {
            "summary": {"intake_errors": 0, "processing_errors": 0},
            "messages": [
                {
                    "id": "NAVAREA TEST 1/2026",
                    "source": "NAV-TEST.txt",
                    "source_block_index": 1,
                    "source_reference": "NAV-TEST.txt:1",
                    "missing_geometry_components": ["line"],
                }
            ],
        }
        baseline = {
            "reviewed_component_losses": [
                {
                    "id": "NAVAREA TEST 1/2026",
                    "kind": "line",
                    "source": "NAV-TEST.txt",
                    "source_block_index": 1,
                }
            ]
        }

        reviewed = corpus_runner.validate_report(report, baseline=baseline)
        self.assertEqual(reviewed["status"], "PASS")
        self.assertEqual(reviewed["unreviewed_component_loss_count"], 0)

        report["messages"][0]["missing_geometry_components"] = ["circle"]
        unreviewed = corpus_runner.validate_report(report, baseline=baseline)
        self.assertEqual(unreviewed["status"], "FAIL")
        self.assertEqual(unreviewed["unreviewed_component_loss_count"], 1)

    def test_fingerprint_baseline_detects_unexpected_report_change(self):
        before = {"report_sha256": "not-the-current-report"}
        after = {"messages": [], "summary": {}}

        differential = corpus_runner.compare_reports(before, after)
        self.assertEqual(differential["unexpected_changes"], 1)
        self.assertEqual(differential["changes"][0]["classification"], "UNEXPECTED")

    def test_matching_report_rejects_stale_compact_baseline_message_count(self):
        after = {
            "messages": [{"id": "NAVAREA TEST 1/2026"}],
            "summary": {"messages": 1},
        }
        baseline = {
            "baseline_messages": 0,
            "report_sha256": corpus_runner._report_fingerprint(after),
        }

        differential = corpus_runner.compare_reports(baseline, after)

        self.assertFalse(differential["baseline_messages_consistent"])
        self.assertEqual(differential["baseline_messages"], 1)
        self.assertEqual(differential["declared_baseline_messages"], 0)
        self.assertEqual(
            differential["baseline_message_count_source"],
            "matching current report",
        )
        self.assertIn("declares 0 messages", differential["baseline_messages_error"])
        self.assertIn("contains 1 message", differential["baseline_messages_error"])
        self.assertEqual(differential["unexpected_changes"], 1)
        self.assertEqual(differential["changes"][0]["message"], "COMPACT_BASELINE")

        rendered = corpus_runner.render_github_summary(
            {"summary": {}, "differential": differential}
        )
        self.assertIn("### Baseline metadata error", rendered)
        self.assertIn("declares 0 messages", rendered)

    def test_matching_source_report_rejects_stale_compact_baseline_message_count(
        self,
    ):
        source_report = {
            "messages": [{"id": "NAVAREA TEST 1/2026"}],
            "summary": {"messages": 1},
        }
        baseline = {
            "baseline_messages": 2,
            "report_sha256": corpus_runner._report_fingerprint(source_report),
        }
        after = {"messages": [], "summary": {}}

        differential = corpus_runner.compare_reports(
            baseline, after, source_comparison=source_report
        )

        self.assertTrue(differential["source_comparison_available"])
        self.assertFalse(differential["baseline_messages_consistent"])
        self.assertEqual(differential["baseline_messages"], 1)
        self.assertEqual(differential["declared_baseline_messages"], 2)
        self.assertEqual(
            differential["baseline_message_count_source"],
            "matching source report",
        )
        self.assertIn("declares 2 messages", differential["baseline_messages_error"])
        self.assertIn("contains 1 message", differential["baseline_messages_error"])
        self.assertEqual(differential["unexpected_changes"], 2)
        self.assertEqual(
            differential["changes"][-1]["message"], "COMPACT_BASELINE"
        )

    def test_cli_fails_and_reports_stale_compact_baseline_message_count(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "NAV-TEST.txt"
            source.write_text(
                """NAVAREA TEST 1/2026
AREA BOUNDED BY 10-00.0N 020-00.0E, 10-00.0N 021-00.0E,
11-00.0N 021-00.0E, 11-00.0N 020-00.0E.
""",
                encoding="utf-8",
            )
            source_report = corpus_runner.run_corpus(root, [source])
            source_report_path = root / "full-report.json"
            source_report_path.write_text(
                json.dumps(source_report), encoding="utf-8"
            )
            baseline_path = root / "compact-baseline.json"
            baseline_path.write_text(
                json.dumps(
                    {
                        "baseline_messages": 0,
                        "report_sha256": corpus_runner._report_fingerprint(
                            source_report
                        ),
                        "source_report": source_report_path.name,
                    }
                ),
                encoding="utf-8",
            )
            output_path = root / "after.json"
            summary_path = root / "summary.md"
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                status = corpus_runner.main_cli(
                    [
                        "--root",
                        str(root),
                        "--baseline",
                        str(baseline_path),
                        "--output",
                        str(output_path),
                        "--github-summary",
                        str(summary_path),
                    ]
                )

            report = json.loads(output_path.read_text(encoding="utf-8"))
            differential = report["differential"]
            self.assertEqual(status, 1)
            self.assertFalse(differential["baseline_messages_consistent"])
            self.assertEqual(differential["baseline_messages"], 1)
            self.assertIn("declares 0 messages", stdout.getvalue())
            self.assertIn(
                "Baseline message count: ERROR", stdout.getvalue()
            )
            self.assertIn(
                "compact baseline declares 0 messages",
                summary_path.read_text(encoding="utf-8"),
            )

    def test_fingerprint_drift_uses_matching_source_report_for_message_findings(self):
        source_report = {
            "messages": [
                {
                    "source": "NAV-TEST.txt",
                    "source_block_index": 4,
                    "id": "NAVAREA TEST 4/2026",
                    "source_reference": "NAV-TEST.txt:40-44",
                    "selected_handler": "handle_area",
                    "object_counts": {
                        "areas": 1,
                        "lines": 0,
                        "circles": 0,
                        "labels": 0,
                        "object_count": 1,
                    },
                    "geometry_statuses": ["CONFIRMED_GEOMETRY"],
                    "diagnostic_codes": [],
                }
            ]
        }
        baseline_fingerprint = corpus_runner._report_fingerprint(source_report)
        source_report["report_sha256"] = baseline_fingerprint
        after = json.loads(json.dumps(source_report))
        after["messages"][0]["selected_handler"] = "handle_single_point"
        after["messages"][0]["object_counts"] = {
            "areas": 0,
            "lines": 0,
            "circles": 0,
            "labels": 1,
            "object_count": 1,
        }
        after["messages"][0]["geometry_statuses"] = ["REFERENCE_ONLY_COORDINATES"]
        after.pop("report_sha256")

        differential = corpus_runner.compare_reports(
            {
                "baseline_messages": 1,
                "report_sha256": baseline_fingerprint,
            },
            after,
            source_comparison=source_report,
        )

        self.assertTrue(differential["source_comparison_available"])
        self.assertEqual(differential["changed_messages"], 1)
        self.assertEqual(differential["unexpected_changes"], 1)
        self.assertEqual(differential["changes"][0]["message"], "NAVAREA TEST 4/2026")
        self.assertEqual(
            differential["changes"][0]["source_reference"],
            "NAV-TEST.txt:40-44",
        )
        self.assertNotEqual(
            differential["changes"][0]["message"],
            "CORPUS_REPORT",
        )

    def test_cli_loads_source_report_pointer_for_message_level_findings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "NAV-TEST.txt"
            source.write_text(
                """NAVAREA TEST 1/2026
AREA BOUNDED BY 10-00.0N 020-00.0E, 10-00.0N 021-00.0E,
11-00.0N 021-00.0E, 11-00.0N 020-00.0E.
""",
                encoding="utf-8",
            )
            source_report = corpus_runner.run_corpus(root, [source])
            source_report_path = root / "baseline" / "full-report.json"
            source_report_path.parent.mkdir()
            source_report_path.write_text(
                json.dumps(source_report), encoding="utf-8"
            )
            baseline_path = source_report_path.parent / "compact-baseline.json"
            baseline_path.write_text(
                json.dumps(
                    {
                        "baseline_messages": len(source_report["messages"]),
                        "report_sha256": corpus_runner._report_fingerprint(
                            source_report
                        ),
                        "source_report": "full-report.json",
                    }
                ),
                encoding="utf-8",
            )

            source.write_text(
                """NAVAREA TEST 1/2026
POINT AT 10-00.0N 020-00.0E.
""",
                encoding="utf-8",
            )
            output_path = root / "after.json"
            summary_path = root / "summary.md"
            status = corpus_runner.main_cli(
                [
                    "--root",
                    str(root),
                    "--baseline",
                    str(baseline_path),
                    "--output",
                    str(output_path),
                    "--github-summary",
                    str(summary_path),
                ]
            )

            report = json.loads(output_path.read_text(encoding="utf-8"))
            differential = report["differential"]
            self.assertEqual(status, 1)
            self.assertTrue(differential["source_comparison_available"])
            self.assertEqual(differential["changed_messages"], 1)
            self.assertEqual(
                differential["changes"][0]["message"], "NAVAREA TEST 1/2026"
            )
            self.assertEqual(
                differential["changes"][0]["source_reference"],
                "NAV-TEST.txt:1-2",
            )
            summary = summary_path.read_text(encoding="utf-8")
            self.assertIn("NAVAREA TEST 1/2026", summary)
            self.assertIn("NAV-TEST.txt:1-2", summary)

    def test_cli_falls_back_to_corpus_finding_for_unavailable_source_report(self):
        for source_report_name, expected_reason in (
            ("missing-full-report.json", "not found"),
            ("stale-full-report.json", "fingerprint"),
            ("malformed-full-report.json", "invalid JSON"),
            ("invalid-utf8-full-report.json", "not valid UTF-8"),
            ("non-object-full-report.json", "must contain a JSON object"),
        ):
            with self.subTest(source_report_name=source_report_name):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    source = root / "NAV-TEST.txt"
                    source.write_text(
                        """NAVAREA TEST 1/2026
AREA BOUNDED BY 10-00.0N 020-00.0E, 10-00.0N 021-00.0E,
11-00.0N 021-00.0E, 11-00.0N 020-00.0E.
""",
                        encoding="utf-8",
                    )
                    source_report = corpus_runner.run_corpus(root, [source])
                    baseline_path = root / "compact-baseline.json"
                    baseline_path.write_text(
                        json.dumps(
                            {
                                "baseline_messages": len(
                                    source_report["messages"]
                                ),
                                "report_sha256": corpus_runner._report_fingerprint(
                                    source_report
                                ),
                                "source_report": source_report_name,
                            }
                        ),
                        encoding="utf-8",
                    )
                    if source_report_name.startswith("stale"):
                        stale_report = dict(source_report)
                        stale_report["stale_marker"] = True
                        Path(directory, source_report_name).write_text(
                            json.dumps(stale_report), encoding="utf-8"
                        )
                    elif source_report_name.startswith("malformed"):
                        Path(directory, source_report_name).write_text(
                            '{"messages":', encoding="utf-8"
                        )
                    elif source_report_name.startswith("invalid-utf8"):
                        Path(directory, source_report_name).write_bytes(
                            b"\xff\xfe\xfa"
                        )
                    elif source_report_name.startswith("non-object"):
                        Path(directory, source_report_name).write_text(
                            "[]", encoding="utf-8"
                        )

                    source.write_text(
                        """NAVAREA TEST 1/2026
POINT AT 10-00.0N 020-00.0E.
""",
                        encoding="utf-8",
                    )
                    output_path = root / "after.json"
                    summary_path = root / "summary.md"
                    status = corpus_runner.main_cli(
                        [
                            "--root",
                            str(root),
                            "--baseline",
                            str(baseline_path),
                            "--output",
                            str(output_path),
                            "--github-summary",
                            str(summary_path),
                        ]
                    )

                    report = json.loads(output_path.read_text(encoding="utf-8"))
                    differential = report["differential"]
                    self.assertEqual(status, 1)
                    self.assertFalse(
                        differential["source_comparison_available"]
                    )
                    self.assertEqual(
                        differential["changes"][0]["message"], "CORPUS_REPORT"
                    )
                    self.assertIsNone(
                        differential["changes"][0]["source_reference"]
                    )
                    reason = differential["source_comparison_unavailable_reason"]
                    self.assertIn(expected_reason, reason)
                    summary = summary_path.read_text(encoding="utf-8")
                    self.assertIn("`CORPUS_REPORT`", summary)
                    self.assertIn("source unavailable", summary)
                    self.assertIn("Source-level comparison unavailable", summary)
                    self.assertIn(reason, summary)

    def test_cli_reports_source_read_failure_in_json_and_markdown(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "NAV-TEST.txt"
            source.write_text(
                """NAVAREA TEST 1/2026
AREA BOUNDED BY 10-00.0N 020-00.0E, 10-00.0N 021-00.0E,
11-00.0N 021-00.0E, 11-00.0N 020-00.0E.
""",
                encoding="utf-8",
            )
            source_report_path = root / "full-report.json"
            source_report_path.write_text(
                json.dumps(corpus_runner.run_corpus(root, [source])),
                encoding="utf-8",
            )
            baseline_path = root / "compact-baseline.json"
            baseline_path.write_text(
                json.dumps(
                    {
                        "baseline_messages": 1,
                        "report_sha256": "a" * 64,
                        "source_report": source_report_path.name,
                    }
                ),
                encoding="utf-8",
            )
            source.write_text(
                """NAVAREA TEST 1/2026
POINT AT 10-00.0N 020-00.0E.
""",
                encoding="utf-8",
            )
            output_path = root / "after.json"
            summary_path = root / "summary.md"
            original_read_text = Path.read_text

            def read_text_with_failure(path, *args, **kwargs):
                if path == source_report_path:
                    raise OSError("permission denied")
                return original_read_text(path, *args, **kwargs)

            with patch.object(Path, "read_text", new=read_text_with_failure):
                status = corpus_runner.main_cli(
                    [
                        "--root",
                        str(root),
                        "--baseline",
                        str(baseline_path),
                        "--output",
                        str(output_path),
                        "--github-summary",
                        str(summary_path),
                    ]
                )

            report = json.loads(output_path.read_text(encoding="utf-8"))
            differential = report["differential"]
            reason = differential["source_comparison_unavailable_reason"]
            self.assertEqual(status, 1)
            self.assertFalse(differential["source_comparison_available"])
            self.assertEqual(differential["changes"][0]["message"], "CORPUS_REPORT")
            self.assertIsNone(differential["changes"][0]["source_reference"])
            self.assertIn("source report could not be read (permission denied)", reason)
            summary = summary_path.read_text(encoding="utf-8")
            self.assertIn("`CORPUS_REPORT`", summary)
            self.assertIn(reason, summary)

    def test_cli_reports_compact_baseline_read_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "NAV-TEST.txt"
            source.write_text(
                """NAVAREA TEST 1/2026
AREA BOUNDED BY 10-00.0N 020-00.0E, 10-00.0N 021-00.0E,
11-00.0N 021-00.0E, 11-00.0N 020-00.0E.
""",
                encoding="utf-8",
            )
            baseline_path = root / "compact-baseline.json"
            baseline_path.write_text("{}", encoding="utf-8")
            original_read_text = Path.read_text

            def read_text_with_failure(path, *args, **kwargs):
                if path == baseline_path:
                    raise OSError("permission denied")
                return original_read_text(path, *args, **kwargs)

            diagnostics = io.StringIO()
            with patch.object(Path, "read_text", new=read_text_with_failure):
                with redirect_stderr(diagnostics):
                    status = corpus_runner.main_cli(
                        [
                            "--root",
                            str(root),
                            "--baseline",
                            str(baseline_path),
                        ]
                    )

            self.assertEqual(status, 1)
            self.assertIn(
                "compact baseline could not be read (permission denied)",
                diagnostics.getvalue(),
            )
            self.assertIn(str(baseline_path), diagnostics.getvalue())

    def test_cli_reports_malformed_compact_baseline(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "NAV-TEST.txt"
            source.write_text(
                """NAVAREA TEST 1/2026
AREA BOUNDED BY 10-00.0N 020-00.0E, 10-00.0N 021-00.0E,
11-00.0N 021-00.0E, 11-00.0N 020-00.0E.
""",
                encoding="utf-8",
            )
            baseline_path = root / "compact-baseline.json"
            baseline_path.write_text('{"baseline_messages":', encoding="utf-8")

            diagnostics = io.StringIO()
            with redirect_stderr(diagnostics):
                status = corpus_runner.main_cli(
                    [
                        "--root",
                        str(root),
                        "--baseline",
                        str(baseline_path),
                    ]
                )

            self.assertEqual(status, 1)
            self.assertIn(
                "compact baseline contains invalid JSON",
                diagnostics.getvalue(),
            )
            self.assertIn(str(baseline_path), diagnostics.getvalue())

    def test_cli_reports_non_object_compact_baseline(self):
        for baseline_value in ("[]", '"baseline"'):
            with self.subTest(baseline_value=baseline_value):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    source = root / "NAV-TEST.txt"
                    source.write_text(
                        """NAVAREA TEST 1/2026
AREA BOUNDED BY 10-00.0N 020-00.0E, 10-00.0N 021-00.0E,
11-00.0N 021-00.0E, 11-00.0N 020-00.0E.
""",
                        encoding="utf-8",
                    )
                    baseline_path = root / "compact-baseline.json"
                    baseline_path.write_text(baseline_value, encoding="utf-8")

                    diagnostics = io.StringIO()
                    with redirect_stderr(diagnostics):
                        status = corpus_runner.main_cli(
                            [
                                "--root",
                                str(root),
                                "--baseline",
                                str(baseline_path),
                            ]
                        )

                    self.assertEqual(status, 1)
                    self.assertIn(
                        "compact baseline must contain a JSON object",
                        diagnostics.getvalue(),
                    )
                    self.assertIn(str(baseline_path), diagnostics.getvalue())

    def test_cli_reports_missing_compact_baseline_metadata(self):
        for baseline_value, missing_metadata in (
            ({}, {"baseline_messages", "report_sha256"}),
            ({"baseline_messages": 1}, {"report_sha256"}),
            ({"report_sha256": "baseline"}, {"baseline_messages"}),
        ):
            with self.subTest(baseline_value=baseline_value):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    source = root / "NAV-TEST.txt"
                    source.write_text(
                        """NAVAREA TEST 1/2026
AREA BOUNDED BY 10-00.0N 020-00.0E, 10-00.0N 021-00.0E,
11-00.0N 021-00.0E, 11-00.0N 020-00.0E.
""",
                        encoding="utf-8",
                    )
                    baseline_path = root / "compact-baseline.json"
                    baseline_path.write_text(
                        json.dumps(baseline_value), encoding="utf-8"
                    )

                    diagnostics = io.StringIO()
                    with redirect_stderr(diagnostics):
                        with patch.object(
                            corpus_runner,
                            "compare_reports",
                            side_effect=AssertionError(
                                "comparison should not run"
                            ),
                        ):
                            status = corpus_runner.main_cli(
                                [
                                    "--root",
                                    str(root),
                                    "--baseline",
                                    str(baseline_path),
                                ]
                            )

                    diagnostic = diagnostics.getvalue()
                    self.assertEqual(status, 1)
                    self.assertIn(
                        "compact baseline is missing required metadata",
                        diagnostic,
                    )
                    self.assertIn(str(baseline_path), diagnostic)
                    for metadata in missing_metadata:
                        self.assertIn(metadata, diagnostic)

    def test_cli_reports_invalid_compact_baseline_metadata(self):
        valid_fingerprint = "a" * 64
        for baseline_value, invalid_metadata in (
            (
                {"baseline_messages": -1, "report_sha256": valid_fingerprint},
                {"baseline_messages"},
            ),
            (
                {"baseline_messages": 1.5, "report_sha256": valid_fingerprint},
                {"baseline_messages"},
            ),
            (
                {"baseline_messages": True, "report_sha256": valid_fingerprint},
                {"baseline_messages"},
            ),
            (
                {"baseline_messages": 1, "report_sha256": ""},
                {"report_sha256"},
            ),
            (
                {"baseline_messages": 1, "report_sha256": "not-a-sha256"},
                {"report_sha256"},
            ),
            (
                {"baseline_messages": "1", "report_sha256": None},
                {"baseline_messages", "report_sha256"},
            ),
        ):
            with self.subTest(baseline_value=baseline_value):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    source = root / "NAV-TEST.txt"
                    source.write_text(
                        """NAVAREA TEST 1/2026
AREA BOUNDED BY 10-00.0N 020-00.0E, 10-00.0N 021-00.0E,
11-00.0N 021-00.0E, 11-00.0N 020-00.0E.
""",
                        encoding="utf-8",
                    )
                    baseline_path = root / "compact-baseline.json"
                    baseline_path.write_text(
                        json.dumps(baseline_value), encoding="utf-8"
                    )

                    diagnostics = io.StringIO()
                    with redirect_stderr(diagnostics):
                        with patch.object(
                            corpus_runner,
                            "compare_reports",
                            side_effect=AssertionError(
                                "comparison should not run"
                            ),
                        ):
                            status = corpus_runner.main_cli(
                                [
                                    "--root",
                                    str(root),
                                    "--baseline",
                                    str(baseline_path),
                                ]
                            )

                    diagnostic = diagnostics.getvalue()
                    self.assertEqual(status, 1)
                    self.assertIn(
                        "compact baseline has invalid metadata",
                        diagnostic,
                    )
                    self.assertIn(str(baseline_path), diagnostic)
                    for metadata in invalid_metadata:
                        self.assertIn(metadata, diagnostic)

    def test_cli_reports_invalid_utf8_compact_baseline(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "NAV-TEST.txt"
            source.write_text(
                """NAVAREA TEST 1/2026
AREA BOUNDED BY 10-00.0N 020-00.0E, 10-00.0N 021-00.0E,
11-00.0N 021-00.0E, 11-00.0N 020-00.0E.
""",
                encoding="utf-8",
            )
            baseline_path = root / "compact-baseline.json"
            baseline_path.write_bytes(b'{"baseline_messages":\xff}')

            diagnostics = io.StringIO()
            with redirect_stderr(diagnostics):
                status = corpus_runner.main_cli(
                    [
                        "--root",
                        str(root),
                        "--baseline",
                        str(baseline_path),
                    ]
                )

            self.assertEqual(status, 1)
            self.assertIn(
                "compact baseline is not valid UTF-8",
                diagnostics.getvalue(),
            )
            self.assertIn(str(baseline_path), diagnostics.getvalue())

    def test_github_summary_includes_counts_and_finding_references(self):
        report = {
            "summary": {
                "source_files": 2,
                "source_blocks": 3,
                "messages": 4,
                "geometry_status_counts": {"CONFIRMED_GEOMETRY": 3},
            },
            "differential": {
                "source_comparison_available": True,
                "changes": [
                    {
                        "message": "NAVAREA TEST 1/2026",
                        "severity": "ERROR",
                        "expected": False,
                        "source_reference": "NAV-TEST.txt:12-15",
                    }
                ]
            },
            "validation": {
                "status": "FAIL",
                "intake_errors": 0,
                "processing_errors": 1,
                "unexpected_differential_changes": 1,
                "reviewed_component_loss_count": 2,
                "unreviewed_component_loss_count": 1,
                "unreviewed_component_losses": [
                    {
                        "id": "NAVAREA TEST 2/2026",
                        "source_reference": "NAV-TEST.txt:20",
                        "missing_geometry_components": [{"kind": "line"}],
                    }
                ],
            },
        }

        rendered = corpus_runner.render_github_summary(report)

        self.assertIn("**Status: `FAIL`**", rendered)
        self.assertIn("| Processing errors | 1 |", rendered)
        self.assertIn("| Unreviewed component losses | 1 |", rendered)
        self.assertIn("### Changed messages", rendered)
        self.assertIn("NAV-TEST.txt:12-15", rendered)
        self.assertIn("NAV-TEST.txt:20", rendered)
        self.assertIn("NAVAREA-corpus-validation", rendered)

    def test_github_summary_handles_findings_without_source_references(self):
        report = {
            "summary": {},
            "differential": {
                "changes": [
                    {"message": "CORPUS_REPORT", "expected": False}
                ]
            },
            "validation": {
                "status": "FAIL",
                "unreviewed_component_losses": [
                    {
                        "id": "NAVAREA TEST 1/2026",
                        "missing_geometry_components": ["area"],
                    }
                ],
            },
        }

        rendered = corpus_runner.render_github_summary(report)

        self.assertEqual(rendered.count("source unavailable"), 2)
