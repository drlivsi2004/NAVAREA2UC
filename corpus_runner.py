"""Repeatable corpus validation for NAVAREA geometry dispatch.

The runner deliberately sits beside ``main.py`` instead of changing parser
handlers.  It uses the same intake, normalization, partitioning, and dispatch
functions as the application, then records an auditable JSON result.

Examples:

    python corpus_runner.py --output reports/navarea-corpus.json
    python corpus_runner.py --baseline reports/before.json --output reports/after.json
    python corpus_runner.py --fail-on-loss
    python corpus_runner.py --github-summary "$GITHUB_STEP_SUMMARY"
"""

from __future__ import annotations

import argparse
from bisect import bisect_right
import contextlib
import hashlib
import io
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Iterable, Iterator, Mapping, Sequence
from xml.etree import ElementTree as ET

import main
from source_intake import load_source


REPORT_SCHEMA_VERSION = "1.1"
COMPACT_BASELINE_METADATA = ("baseline_messages", "report_sha256")
SHA256_FINGERPRINT_RE = re.compile(r"^[0-9a-fA-F]{64}$")
NAVAREA_HEADER_RE = re.compile(
    r"(?im)^NAVAREA\s+([A-Z0-9]+)\s+(\d+/\d+)\b"
)
WARNING_REFERENCE_RE = re.compile(
    r"(?<![A-Z0-9])(?P<issuer>"
    r"NAVAREA\s+(?P<navarea_region>[A-Z0-9]+)|"
    r"NSR\s*-\s*(?:WEST|EAST)\s+COASTAL|"
    r"TAIWAN\s+NTM|"
    r"AVINAV|AVURNAV|AVLOCAL|NAVWARN|NAVTEX|COASTAL|INW|NTM|"
    r"HB|TJ|LYG|ZJ|GD|P|M|C|A|S|E|"
    r"[A-Z][A-Z0-9-]{0,15}"
    r")\s+(?P<number>\d{1,5})/(?P<year>\d{2}|\d{4})\b",
    re.IGNORECASE,
)
NON_WARNING_REFERENCE_ISSUERS = {
    "AND",
    "CANCEL",
    "CHART",
    "FROM",
    "IN",
    "NEW",
    "NOTICE",
    "OF",
    "ON",
    "ORDER",
    "PREVIOUS",
    "REF",
    "SECTION",
    "SERIES",
    "SUMMARY",
    "TO",
    "BY",
    "AT",
    "FOR",
    "THE",
    "WEST",
    "EAST",
    "NORTH",
    "SOUTH",
    "WARNING",
    "WARNINGS",
}
OBJECT_TYPES = ("areas", "lines", "circles", "labels")
GEOMETRY_TYPES = ("area", "line", "circle")
DESCRIPTION_SEMANTIC_STOPWORDS = {
    "ABOUT",
    "AREA",
    "AREAS",
    "AT",
    "BE",
    "BOUND",
    "BOUNDED",
    "BY",
    "CANCEL",
    "CHART",
    "CHARTS",
    "COORDINATES",
    "IN",
    "NAVAREA",
    "OF",
    "ON",
    "POSITION",
    "THE",
    "TO",
    "UTC",
    "UNTIL",
}
SHORE_BOUNDARY_LINE_RE = re.compile(
    r"\bAREAS?\s+BOUND(?:ED)?\s+BY\b[\s\S]{0,800}?"
    r"\bLINE\s+JOINING\b[\s\S]{0,800}?\bAND\s+BY\s+SHORE\b",
    re.IGNORECASE,
)

# These patterns identify explicit geometry statements, not every occurrence
# of a geometry-related word.  The order keeps specific phrases from being
# counted again by a broader phrase such as ROUTE.
GEOMETRY_STATEMENT_PATTERNS = (
    (
        "area",
        re.compile(
            r"\b(?:AREAS?|ZONES?)\s+"
            r"(?:BOUND(?:ED)?\s+BY|DELIMITED\s+BY|BOUNDED\s+WITHIN)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "area",
        re.compile(
            r"\b(?:WAITING|HOLDING|ANCHORAGE|TEMPORARY\s+STAY)\s+AREA\b",
            re.IGNORECASE,
        ),
    ),
    (
        "line",
        re.compile(
            r"\bROUTE\s+NO\.?\s*[A-Z0-9]+(?:\.[A-Z0-9]+)*\s*:",
            re.IGNORECASE,
        ),
    ),
    (
        "line",
        re.compile(
            r"\b(?:TRACKLINE(?:\s+JOINING)?|LINE\s+JOINING|"
            r"ROUTE\s+CENTERLINE|CENTERLINE\s+COORDINATES)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "circle",
        re.compile(
            r"\b(?:CIRCLE|RADIUS\s+OF|WITHIN\s+"
            r"\d+(?:\.\d+)?\s*(?:NM|MILES?|MI)\s+RADIUS)\b",
            re.IGNORECASE,
        ),
    ),
)

OPERATION_TERMS = (
    "OPERATION",
    "OPERATIONS",
    "SEISMIC",
    "SURVEY",
    "TOWING",
    "TOWED",
    "DREDGING",
    "DRILLING",
    "HEAVY LIFT",
    "CONSTRUCTION",
    "MAINTENANCE",
    "INSTALLATION",
    "MOORING",
    "SALVAGE",
    "EXERCISE",
    "FIRING PRACTICE",
    "WORKS",
)

PRIMARY_SOURCE_MANIFEST = Path("corpus_manifests/navarea_primary.txt")
FUTURE_COASTAL_MANIFEST = Path("corpus_manifests/coastal_future.txt")


def _read_source_manifest(root: Path, manifest: Path) -> set[str] | None:
    manifest_path = root / manifest
    if not manifest_path.is_file():
        return None

    entries = [
        line.strip()
        for line in manifest_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    names = set(entries)
    if len(entries) != len(names):
        raise ValueError(f"duplicate source in manifest: {manifest_path}")
    return names


def discover_sources(
    root: Path,
    include_future_coastal: bool = False,
) -> list[Path]:
    """Return the selected NAVAREA source set under *root*.

    The tracked primary manifest contains one source for each of the 21
    global NAVAREA regions.  Coastal and other regional feeds stay in the
    repository, but are opt-in until their duplicate/review policy is ready.
    """

    sources = {
        path
        for pattern in ("NAVAREA*.txt", "NAV-*.txt")
        for path in root.glob(pattern)
        if path.is_file()
    }
    if not include_future_coastal:
        primary_names = _read_source_manifest(root, PRIMARY_SOURCE_MANIFEST)
        if primary_names is not None:
            available_names = {path.name for path in sources}
            missing_names = sorted(primary_names - available_names)
            if missing_names:
                raise FileNotFoundError(
                    "primary NAVAREA manifest references missing sources: "
                    + ", ".join(missing_names)
                )
            sources = {path for path in sources if path.name in primary_names}
    return sorted(
        sources,
        key=lambda path: path.name.casefold(),
    )


def _relative_source(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def iter_navarea_blocks(text: str) -> Iterator[tuple[int, re.Match[str], str]]:
    """Yield ``(index, header_match, block)`` for every NAVAREA block."""

    matches = []
    for match in NAVAREA_HEADER_RE.finditer(text):
        line_start = text.rfind("\n", 0, match.start()) + 1
        line_end = text.find("\n", match.end())
        line_end = len(text) if line_end < 0 else line_end
        line_text = text[line_start:line_end]
        preceding = text[max(0, line_start - 240) : line_start]
        # A few source files list the cancelled warning on its own line after
        # "CANCEL".  It is a reference, not another NAVAREA warning block.
        if re.search(r"\bCANCEL\b", line_text, re.IGNORECASE) or re.search(
            r"\bCANCEL\b[^\n]*\n\s*$", preceding, re.IGNORECASE
        ):
            continue
        matches.append(match)

    for index, match in enumerate(matches, start=1):
        end = matches[index].start() if index < len(matches) else len(text)
        block = text[match.start() : end].strip()
        if block:
            yield index, match, block


def _line_at(text: str, offset: int, first_line: int = 1) -> int:
    return first_line + text.count("\n", 0, max(0, offset))


def _source_reference(source: str, line: int, end_line: int | None = None) -> str:
    if end_line is None or end_line == line:
        return f"{source}:{line}"
    return f"{source}:{line}-{end_line}"


def _warning_year(value: str) -> int:
    year = int(value)
    return year + 2000 if len(value) == 2 else year


def _warning_region(source: str, issuer_region: str | None) -> str | None:
    match = re.search(r"\bNAVAREA\s+([A-Z0-9]+)\b", source, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return issuer_region.upper() if issuer_region else None


def _warning_scope_sets(root: Path) -> tuple[set[str], set[str]]:
    primary = _read_source_manifest(root, PRIMARY_SOURCE_MANIFEST) or set()
    coastal = _read_source_manifest(root, FUTURE_COASTAL_MANIFEST) or set()
    return primary, coastal


def _warning_source_scope(
    source: str,
    root: Path,
    source_scopes: Mapping[str, str] | None,
) -> str:
    name = Path(source).name
    if source_scopes:
        explicit = source_scopes.get(source) or source_scopes.get(name)
        if explicit:
            return explicit
    primary, coastal = _warning_scope_sets(root)
    if name in primary:
        return "primary"
    if name in coastal:
        return "coastal"
    return "unknown"


def _navarea_source_ranges(
    text: str,
) -> list[tuple[int, int, int]]:
    """Return raw line ranges for real NAVAREA blocks in *text*."""

    headers = []
    for match in NAVAREA_HEADER_RE.finditer(text):
        line_start = text.rfind("\n", 0, match.start()) + 1
        line_end = text.find("\n", match.end())
        line_end = len(text) if line_end < 0 else line_end
        line_text = text[line_start:line_end]
        preceding = text[max(0, line_start - 240) : line_start]
        # Primary feeds repeat the warning number inside the detail body as
        # NAVAREA IV 144/21(28).  That is a source reference, not a second
        # warning block.
        if re.search(
            r"\bNAVAREA\s+[A-Z0-9]+\s+\d+/\d+\s*\(",
            line_text,
            re.IGNORECASE,
        ):
            continue
        if re.search(r"\bCANCEL\b", line_text, re.IGNORECASE) or re.search(
            r"\bCANCEL\b[^\n]*\n\s*$", preceding, re.IGNORECASE
        ):
            continue
        headers.append(_line_at(text, match.start()))

    return [
        (
            index,
            start_line,
            headers[index] - 1 if index < len(headers) else text.count("\n") + 1,
        )
        for index, start_line in enumerate(headers, start=1)
    ]


def _warning_reference_kind(line_text: str) -> str:
    upper = line_text.upper()
    if re.search(
        r"\b(?:NEW|CANCEL(?:LED|ED)?|SUMMARY|IN FORCE|CURRENT|"
        r"PREVIOUS|WARNINGS IN FORCE)\b",
        upper,
    ):
        return "summary_or_status"
    return "detail"


def _warning_record_key(
    line_number: int,
    line_text: str,
    source_scope: str,
    navarea_ranges: Sequence[tuple[int, int, int]],
    anchor_state: list[int],
    reference_kind: str | None = None,
    coastal_section: int | None = None,
) -> tuple[str, int]:
    if source_scope == "primary":
        for block_index, start_line, end_line in navarea_ranges:
            if start_line <= line_number <= end_line:
                return ("NAVAREA_BLOCK", block_index)
        return ("UNBOUND", 0)

    if coastal_section is not None:
        return ("COASTAL_SECTION", coastal_section)

    stripped = line_text.strip()
    anchor_match = WARNING_REFERENCE_RE.match(stripped)
    is_anchor = bool(
        anchor_match
        and anchor_match.group("issuer").upper()
        not in NON_WARNING_REFERENCE_ISSUERS
    )
    if is_anchor and (reference_kind or _warning_reference_kind(line_text)) == "detail":
        anchor_state[0] += 1
        return ("DETAIL_RECORD", anchor_state[0])
    return ("SUMMARY", 0)


def review_warning_duplicates(
    root: Path | str = ".",
    sources: Iterable[Path | str] | None = None,
    source_scopes: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """Review repeated warning identities across primary and coastal feeds.

    A warning identity is the normalized NAVAREA region, number, and year.
    This intentionally ignores the local stream prefix (for example AVINAV
    or INW) when comparing different source files: those prefixes are agency
    delivery streams, not globally unique warning identities.  Repeated
    detail records inside one source remain true-duplicate candidates.
    Summary/status lists are retained as evidence but never create a
    same-source duplicate by themselves.
    """

    root = Path(root).resolve()
    source_paths = (
        [Path(source).resolve() for source in sources]
        if sources is not None
        else discover_sources(root, include_future_coastal=True)
    )
    references: list[dict[str, object]] = []
    intake_errors: list[dict[str, object]] = []

    for source_path in source_paths:
        source = _relative_source(source_path, root)
        intake = load_source(str(source_path))
        if intake.text is None:
            intake_errors.append(
                {"source": source, "error": intake.error or "source could not be decoded"}
            )
            continue
        source_scope = _warning_source_scope(source, root, source_scopes)
        ranges = _navarea_source_ranges(intake.text)
        anchor_state = [0]
        separator_lines = [
            line_number
            for line_number, line_text in enumerate(
                intake.text.splitlines(), start=1
            )
            if re.fullmatch(r"-{10,}", line_text.strip())
        ]
        summary_mode = False
        for line_number, line_text in enumerate(
            intake.text.splitlines(), start=1
        ):
            line_kind = _warning_reference_kind(line_text)
            if re.search(
                r"\b(?:NEW|CANCEL(?:LED|ED)?|SUMMARY|WARNINGS IN FORCE)\b",
                line_text,
                re.IGNORECASE,
            ):
                summary_mode = True
            if not line_text.strip() and summary_mode:
                summary_mode = False
            if summary_mode:
                line_kind = "summary_or_status"
            coastal_section = (
                bisect_right(separator_lines, line_number)
                if separator_lines
                else None
            )
            record_key = _warning_record_key(
                line_number,
                line_text,
                source_scope,
                ranges,
                anchor_state,
                line_kind,
                coastal_section,
            )
            for match in WARNING_REFERENCE_RE.finditer(line_text):
                region = _warning_region(
                    source,
                    match.group("navarea_region"),
                )
                if region is None:
                    continue
                issuer = re.sub(r"\s+", " ", match.group("issuer").upper()).strip()
                if issuer in NON_WARNING_REFERENCE_ISSUERS:
                    continue
                number = int(match.group("number"))
                year = _warning_year(match.group("year"))
                reference_kind = line_kind
                if (
                    reference_kind == "detail"
                    and not line_text.lstrip().startswith(match.group(0))
                ):
                    reference_kind = "embedded_reference"
                references.append(
                    {
                        "source": source,
                        "scope": source_scope,
                        "source_reference": _source_reference(source, line_number),
                        "line": line_number,
                        "raw_reference": match.group(0),
                        "issuer": issuer,
                        "identity": {
                            "region": region,
                            "number": number,
                            "year": year,
                        },
                        "stream_identity": (
                            region,
                            issuer,
                            number,
                            year,
                        ),
                        "record_key": record_key,
                        "reference_kind": reference_kind,
                    }
                )

    by_identity: dict[tuple[str, int, int], list[dict[str, object]]] = {}
    for reference in references:
        identity = reference["identity"]
        assert isinstance(identity, Mapping)
        key = (
            str(identity["region"]),
            int(identity["number"]),
            int(identity["year"]),
        )
        by_identity.setdefault(key, []).append(reference)

    intentional_repeats: list[dict[str, object]] = []
    true_duplicates: list[dict[str, object]] = []
    for identity_key, identity_references in sorted(by_identity.items()):
        source_names = sorted(
            {str(reference["source"]) for reference in identity_references}
        )
        if len(source_names) > 1:
            intentional_repeats.append(
                {
                    "classification": "INTENTIONAL_REPEAT",
                    "reason": (
                        "same normalized NAVAREA region, warning number, and "
                        "year is published by multiple source streams"
                    ),
                    "warning_identity": {
                        "region": identity_key[0],
                        "number": identity_key[1],
                        "year": identity_key[2],
                    },
                    "sources": source_names,
                    "scopes": sorted(
                        {str(reference["scope"]) for reference in identity_references}
                    ),
                    "source_references": identity_references,
                }
            )

        by_stream: dict[tuple[str, str], list[dict[str, object]]] = {}
        for reference in identity_references:
            by_stream.setdefault(
                (str(reference["source"]), str(reference["issuer"])),
                [],
            ).append(reference)
        for (source, issuer), stream_references in sorted(by_stream.items()):
            detail_references = [
                reference
                for reference in stream_references
                if reference["reference_kind"] == "detail"
            ]
            record_keys = sorted(
                {
                    tuple(reference["record_key"])
                    for reference in detail_references
                }
            )
            if len(record_keys) > 1:
                true_duplicates.append(
                    {
                        "classification": "TRUE_DUPLICATE",
                        "reason": (
                            "the same warning stream identity occurs in "
                            "multiple detail records within one source"
                        ),
                        "warning_identity": {
                            "region": identity_key[0],
                            "number": identity_key[1],
                            "year": identity_key[2],
                        },
                        "source": source,
                        "issuer": issuer,
                        "record_keys": [list(key) for key in record_keys],
                        "source_references": detail_references,
                    }
                )

    findings = [*true_duplicates, *intentional_repeats]
    return {
        "reviewed": True,
        "method": "normalized_region_number_year_with_source_record_review",
        "source_file_count": len(source_paths),
        "reference_count": len(references),
        "identity_count": len(by_identity),
        "intentional_repeat_count": len(intentional_repeats),
        "true_duplicate_count": len(true_duplicates),
        "intake_error_count": len(intake_errors),
        "status": (
            "ERROR"
            if intake_errors
            else (
                "REVIEW_REQUIRED"
                if true_duplicates
                else "PASS_WITH_INTENTIONAL_REPEATS"
            )
        ),
        "intake_errors": intake_errors,
        "true_duplicates": true_duplicates,
        "intentional_repeats": intentional_repeats,
        "findings": findings,
    }


def extract_geometry_statements(
    block: str, source: str, first_line: int
) -> list[dict[str, object]]:
    """Return explicit geometry statements with source line references."""

    matches: list[tuple[int, int, str, re.Match[str]]] = []
    for kind, pattern in GEOMETRY_STATEMENT_PATTERNS:
        for match in pattern.finditer(block):
            matches.append((match.start(), match.end(), kind, match))

    statements: list[dict[str, object]] = []
    occupied: list[tuple[int, int]] = []
    for start, end, kind, match in sorted(matches, key=lambda item: (item[0], item[1])):
        if any(start < occupied_end and end > occupied_start for occupied_start, occupied_end in occupied):
            continue
        if kind == "line" and SHORE_BOUNDARY_LINE_RE.search(block):
            # "AREA BOUND BY LINE JOINING ... AND BY SHORE" describes one
            # polygonal area whose first boundary is a line segment.  The
            # line phrase is not a separate chart Line component.
            continue
        next_section = re.search(
            r"\n\s*(?:\d+(?:\.\d+)*|[A-Z])\.\s+", block[end:], re.IGNORECASE
        )
        scope_start = block.rfind("\n", 0, start) + 1
        scope_end = end + next_section.start() if next_section else len(block)
        scope = block[scope_start:scope_end]
        if kind == "circle" and not _has_explicit_circle_center(block):
            # A radius warning can qualify a polygon without defining a
            # separate Circle object.  Do not turn "radius" into a missing
            # geometry component unless the source also supplies a center.
            continue
        if kind == "area" and re.search(
            r"\bARC\s+OF\s+RADIUS\b", scope, re.IGNORECASE
        ):
            # An arc with an explicit center is a Circle, not a polygonal
            # Area.  The surrounding warning text may still contain
            # "AREA BOUNDED BY".
            continue
        if kind == "area" and len(main.extract_coordinates(scope)) < 3:
            # A parent section can introduce child areas whose coordinates
            # are listed under later numbered/lettered sections.  The parent
            # text itself is not a missing Area component.
            continue
        if kind == "area" and re.match(
            r"(?:WAITING|HOLDING|ANCHORAGE|TEMPORARY\s+STAY)\s+AREA\b",
            match.group(0),
            re.IGNORECASE,
        ):
            # A waiting area described only as a radius/reference is not a
            # polygonal area statement.  Require the local section to carry
            # enough coordinates for an area.
            if re.search(
                r"\bWITHIN\s+(?:\d+(?:\.\d+)?\s*)?"
                r"(?:NM|MILES?|MI)\s+RADIUS\b",
                scope,
                re.IGNORECASE,
            ) or re.search(r"\bCHANNEL\s+WIDTH\b", scope, re.IGNORECASE):
                continue
            if re.search(
                r"\bROUTES?\s+THAT\s+HAVE\s+BEEN\s+AUTHORIZED\b",
                scope,
                re.IGNORECASE,
            ):
                continue
        line = _line_at(block, start, first_line)
        line_start = block.rfind("\n", 0, start) + 1
        line_end_offset = block.find("\n", end)
        line_end_offset = len(block) if line_end_offset < 0 else line_end_offset
        line_text = " ".join(block[line_start:line_end_offset].split())
        statements.append(
            {
                "kind": kind,
                "text": match.group(0),
                "source_reference": _source_reference(source, line),
                "source_line": line,
                "line_text": line_text[:240],
            }
        )
        occupied.append((start, end))
    return statements


def _has_explicit_circle_center(block: str) -> bool:
    """Return whether a radius/circle statement names a center or position."""

    if main.extract_circle_spec(block):
        return True
    return bool(
        re.search(
            r"\b(?:CIRCLE|RADIUS)\b[\s\S]{0,160}\b"
            r"(?:CENTER|CENTRE|POSITION)\b",
            block,
            re.IGNORECASE,
        )
    )


def _partition_id(message: Mapping[str, object]) -> str:
    metadata = message.get("metadata") or {}
    partition_type = metadata.get("partition_type")
    partition_id = metadata.get("partition_id")
    if partition_type == "SECTION_NUMBER":
        return f"Section {partition_id}"
    if partition_type == "LETTER":
        return str(partition_id)
    if partition_type == "RIGLIST":
        return f"RIG {partition_id}"
    if partition_type and partition_type != "NONE":
        return f"{partition_type} {partition_id}"
    return "NONE"


def _message_id(navarea_name: str, metadata: Mapping[str, object]) -> str:
    partition_type = metadata.get("partition_type")
    partition_id = metadata.get("partition_id")
    if partition_type == "SECTION_NUMBER":
        return f"{navarea_name} [Section {partition_id}]"
    if partition_type == "LETTER":
        return f"{navarea_name} [{partition_id}]"
    if partition_type == "RIGLIST":
        return f"{navarea_name} [RIG {partition_id}]"
    return navarea_name


def _selected_handler(message: Mapping[str, object]) -> str | None:
    matches = [
        stage.get("handler")
        for stage in message.get("stage_diagnostics", [])
        if stage.get("stage") == "handler_match"
    ]
    return matches[-1] if matches else None


def _object_counts(message: Mapping[str, object]) -> dict[str, int]:
    counts = {object_type: len(message.get(object_type, [])) for object_type in OBJECT_TYPES}
    counts["object_count"] = sum(counts.values())
    return counts


def _diagnostic_codes(message: Mapping[str, object]) -> list[str]:
    return sorted(
        {
            str(diagnostic.get("code"))
            for diagnostic in message.get("diagnostics", [])
            if diagnostic.get("code")
        }
    )


def _geometry_status(
    message: Mapping[str, object], block: str
) -> tuple[str, list[str], str]:
    counts = _object_counts(message)
    emitted = any(
        counts[f"{object_type}s"] for object_type in GEOMETRY_TYPES
    )
    rejected = bool(message.get("geometry_rejected")) or any(
        code.startswith("GEOMETRY_")
        and not code.endswith("_REPAIRED")
        and code
        not in {"GEOMETRY_LINE_ORDER_REVIEW", "GEOMETRY_LINE_TRACKS_SPLIT"}
        for code in _diagnostic_codes(message)
    )
    diagnostic_codes = _diagnostic_codes(message)
    coordinate_reference_fallback = (
        "COORDINATE_REFERENCE_FALLBACK" in diagnostic_codes
    )
    line_order_review = "GEOMETRY_LINE_ORDER_REVIEW" in diagnostic_codes
    line_tracks_split = "GEOMETRY_LINE_TRACKS_SPLIT" in diagnostic_codes
    operation = any(term in block.upper() for term in OPERATION_TERMS)
    coordinates = bool(main.extract_coordinates(block))

    statuses: list[str] = []
    if emitted:
        statuses.append("CONFIRMED_GEOMETRY")
    if line_order_review:
        statuses.append("GEOMETRY_ORDER_REVIEW")
    if line_tracks_split:
        statuses.append("GEOMETRY_TRACKS_SPLIT")
    if rejected:
        statuses.append("REJECTED_INVALID_AREA")
    if not emitted and not rejected and operation:
        statuses.append("OPERATION_ONLY")
    if coordinate_reference_fallback or (
        not emitted and not rejected and not operation and coordinates
    ):
        if "REFERENCE_ONLY_COORDINATES" not in statuses:
            statuses.append("REFERENCE_ONLY_COORDINATES")
    if not statuses:
        statuses.append("NO_GEOMETRY")

    # The first status is the primary status; the complete list preserves
    # mixed outcomes such as a valid route alongside a rejected area.
    basis = {
        "CONFIRMED_GEOMETRY": "emitted_chart_geometry",
        "GEOMETRY_ORDER_REVIEW": "line_source_order_preserved_for_review",
        "GEOMETRY_TRACKS_SPLIT": "independent_line_tracks_split",
        "REJECTED_INVALID_AREA": "invalid_area_diagnostic",
        "OPERATION_ONLY": "operation_semantics_without_chart_geometry",
        "REFERENCE_ONLY_COORDINATES": "source_coordinates_without_chart_geometry",
        "NO_GEOMETRY": "no_coordinates_or_chart_geometry",
    }[statuses[0]]
    return statuses[0], statuses, basis


def _missing_components(
    statements: Sequence[Mapping[str, object]],
    message: Mapping[str, object],
    statuses: Sequence[str],
) -> list[dict[str, object]]:
    expected = Counter(str(statement["kind"]) for statement in statements)
    counts = _object_counts(message)
    emitted = {
        "area": counts["areas"],
        "line": counts["lines"],
        "circle": counts["circles"],
    }
    missing: list[dict[str, object]] = []
    for kind in GEOMETRY_TYPES:
        expected_count = expected.get(kind, 0)
        emitted_count = emitted[kind]
        # A rejected area is an explicit, diagnosed outcome rather than a
        # silent component loss.  Keep it in the status and diagnostics.
        if kind == "area" and "REJECTED_INVALID_AREA" in statuses:
            continue
        if "REFERENCE_ONLY_COORDINATES" in statuses:
            continue
        if expected_count and not emitted_count:
            missing.append(
                {
                    "kind": kind,
                    "expected_statements": expected_count,
                    "emitted_objects": emitted_count,
                }
            )
    return missing


def _xml_descriptions(xml_text: str) -> dict[str, list[str]]:
    """Read serialized descriptions grouped by the runner's object names."""

    try:
        root = ET.fromstring(xml_text)
    except (ET.ParseError, TypeError):
        return {object_type: [] for object_type in OBJECT_TYPES}

    section_to_element = {
        "areas": ("areas", "area"),
        "lines": ("lines", "line"),
        "circles": ("circles", "circle"),
        "labels": ("labels", "label"),
    }
    descriptions: dict[str, list[str]] = {}
    for object_type, (section, element_name) in section_to_element.items():
        descriptions[object_type] = [
            element.attrib.get("description", "")
            for element in root.findall(f"./{section}/{element_name}")
        ]
    return descriptions


def _description_mismatch(
    handler_description: str,
    modern_description: str,
    legacy_description: str,
) -> dict[str, object]:
    """Classify intentional XML sanitization separately from defects."""

    sanitized_handler = main.sanitize_ecdis_description(handler_description)
    handler_to_modern = (
        "MATCH"
        if handler_description == modern_description
        else (
            "SERIALIZER_SANITIZED"
            if sanitized_handler == modern_description
            else "MODERN_MISMATCH"
        )
    )
    legacy_capped = len(modern_description) > main.LEGACY_MAX_DESC
    legacy_to_modern = (
        "LEGACY_CAP"
        if legacy_capped and legacy_description == modern_description[: main.LEGACY_MAX_DESC]
        else "MATCH"
        if modern_description == legacy_description
        else "LEGACY_MISMATCH"
    )
    if legacy_to_modern == "LEGACY_MISMATCH":
        overall = "LEGACY_MISMATCH"
    elif handler_to_modern == "MODERN_MISMATCH":
        overall = "MODERN_MISMATCH"
    elif legacy_to_modern == "LEGACY_CAP":
        overall = "LEGACY_CAPPED"
    elif handler_to_modern == "SERIALIZER_SANITIZED":
        overall = "HANDLER_TO_MODERN_SANITIZED"
    else:
        overall = "MATCH"
    return {
        "handler_to_modern": handler_to_modern,
        "modern_to_legacy": legacy_to_modern,
        "overall": overall,
    }


def _description_fingerprint(value: str) -> str:
    """Compare descriptions by meaning-preserving whitespace normalization."""

    return " ".join(main.sanitize_ecdis_description(value).split()).casefold()


def _description_contract_audit(
    obj: Mapping[str, object],
    modern_description: str,
    legacy_description: str,
    source_text: str | None = None,
) -> dict[str, object]:
    """Validate the dispatcher-owned Description assembly contract.

    This is intentionally separate from Modern/Legacy parity.  XML parity can
    pass even when a handler supplied an incomplete or overly broad string.
    """

    evidence = obj.get("_description_evidence")
    if not isinstance(evidence, Mapping):
        return {
            "status": "MISSING_CONTRACT",
            "required_fragments": [],
            "missing_fragments": [],
            "expected_description": "",
            "modern_matches_expected": False,
            "legacy_cap_stage": "",
        }

    expected = str(evidence.get("assembled_description", ""))
    fragments = [
        str(fragment)
        for fragment in evidence.get("included_fragments", [])
        if str(fragment).strip()
    ]
    source_fragments = [
        str(fragment)
        for fragment in evidence.get("source_required_fragments", [])
        if str(fragment).strip()
    ]
    fragment_references = [
        reference
        for reference in evidence.get("fragment_references", [])
        if isinstance(reference, Mapping)
    ]
    selected_ids = [str(reference.get("id", "")) for reference in fragment_references]
    selected_orders = [
        reference.get("source_order") for reference in fragment_references
    ]
    object_coordinates = {
        tuple(coord) for coord in main._description_object_coordinates(obj)
    }
    referenced_coordinates = {
        tuple(coord)
        for reference in fragment_references
        for coord in reference.get("coordinates", [])
    }
    traceability_issues = []
    if not fragment_references:
        traceability_issues.append("FRAGMENT_TRACE_MISSING")
    if len(selected_ids) != len(set(selected_ids)):
        traceability_issues.append("FRAGMENT_TRACE_DUPLICATE")
    spans = [
        (
            reference.get("source_span", {}).get("start"),
            reference.get("source_span", {}).get("end"),
        )
        for reference in fragment_references
        if isinstance(reference.get("source_span"), Mapping)
    ]
    malformed_references = [
        reference
        for reference in fragment_references
        if not str(reference.get("id", "")).strip()
        or not isinstance(reference.get("source_order"), int)
        or not isinstance(reference.get("source_span"), Mapping)
        or not isinstance(reference.get("source_span", {}).get("start"), int)
        or not isinstance(reference.get("source_span", {}).get("end"), int)
        or reference.get("source_span", {}).get("start")
        >= reference.get("source_span", {}).get("end")
    ]
    if malformed_references:
        traceability_issues.append("FRAGMENT_TRACE_MISSING")
    if len(spans) != len(set(spans)):
        traceability_issues.append("FRAGMENT_TRACE_DUPLICATE")
    if selected_orders != sorted(
        order for order in selected_orders if isinstance(order, int)
    ) or any(order is None for order in selected_orders):
        traceability_issues.append("FRAGMENT_TRACE_REORDERED")
    if referenced_coordinates - object_coordinates:
        traceability_issues.append("FRAGMENT_TRACE_CONTAMINATED")
    excluded_ids = {
        str(fragment_id)
        for fragment_id in evidence.get("excluded_sibling_fragments", [])
    }
    if set(selected_ids) & excluded_ids:
        traceability_issues.append("FRAGMENT_TRACE_CONTAMINATED")
    owner = evidence.get("owner")
    valid_owner = (
        isinstance(owner, Mapping)
        and str(owner.get("object_type", "")).strip() in {
            "area",
            "line",
            "circle",
            "label",
        }
        and isinstance(owner.get("object_index"), int)
        and owner.get("object_index") >= 0
    )
    if not valid_owner:
        traceability_issues.append("FRAGMENT_TRACE_OWNER_INVALID")
    if any(reference.get("owner") != owner for reference in fragment_references):
        traceability_issues.append("FRAGMENT_TRACE_OWNER_MISMATCH")
    if source_text is not None:
        traceability_issues.extend(
            main.validate_description_fragment_references(
                {"block": source_text},
                fragment_references,
            )
        )
    traceability_issues = list(dict.fromkeys(traceability_issues))
    modern_fingerprint = _description_fingerprint(modern_description)
    missing_fragments = []
    for fragment in (*fragments, *source_fragments):
        fragment_fingerprint = _description_fingerprint(fragment)
        if fragment_fingerprint and fragment_fingerprint not in modern_fingerprint:
            missing_fragments.append(fragment)
    expected_fingerprint = _description_fingerprint(expected)
    modern_matches_expected = modern_fingerprint == expected_fingerprint
    expected_length = len(main.sanitize_ecdis_description(expected))
    modern_length = len(modern_description)
    legacy_length = len(legacy_description)

    if traceability_issues:
        status = traceability_issues[0]
    elif missing_fragments:
        status = "MISSING_REQUIRED_FRAGMENT"
    elif not modern_matches_expected:
        status = "ASSEMBLY_MISMATCH"
    elif expected_length > main.LEGACY_MAX_DESC and modern_length <= main.LEGACY_MAX_DESC:
        status = "PREMATURE_CAP"
    elif expected_length > main.LEGACY_MAX_DESC:
        status = "COMPLETE_LEGACY_CAP_EXPECTED"
    else:
        status = "COMPLETE"

    legacy_cap_valid = (
        legacy_length == main.LEGACY_MAX_DESC
        if modern_length > main.LEGACY_MAX_DESC
        else legacy_length == modern_length
    )
    if not legacy_cap_valid:
        status = "LEGACY_CAP_MISMATCH"
    return {
        "status": status,
        "required_fragments": fragments,
        "source_required_fragments": source_fragments,
        "source_scope": str(evidence.get("source_scope", "UNSCOPED")),
        "source_sections": evidence.get("source_sections", []),
        "owner": owner,
        "fragment_references": fragment_references,
        "excluded_sibling_fragments": list(
            evidence.get("excluded_sibling_fragments", [])
        ),
        "source_order": selected_orders,
        "source_spans": [
            reference.get("source_span", {}) for reference in fragment_references
        ],
        "fragment_origin": str(evidence.get("fragment_origin", "")),
        "traceability_issues": traceability_issues,
        "missing_fragments": missing_fragments,
        "expected_description": expected,
        "modern_matches_expected": modern_matches_expected,
        "legacy_cap_stage": str(evidence.get("legacy_cap_stage", "")),
        "legacy_cap_valid": legacy_cap_valid,
        "expected_length": expected_length,
        "modern_length": modern_length,
        "legacy_length": legacy_length,
    }


def _description_semantic_context(
    source_text: str, modern_description: str
) -> dict[str, object]:
    """Check that export retains at least one source-derived semantic anchor."""

    def terms(value: str) -> set[str]:
        normalized = main.sanitize_ecdis_description(value).upper()
        return {
            token
            for token in re.findall(r"[A-Z][A-Z0-9/-]{4,}", normalized)
            if token not in DESCRIPTION_SEMANTIC_STOPWORDS
        }

    source_terms = terms(source_text)
    description_terms = terms(modern_description)
    matched = sorted(source_terms & description_terms)
    return {
        "status": "PRESENT" if matched else "MISSING",
        "source_terms": sorted(source_terms),
        "matched_terms": matched,
    }


def _description_audit(
    sub_block: str,
    navarea_name: str,
    metadata: Mapping[str, object],
    message: Mapping[str, object],
    container: Mapping[str, object],
) -> dict[str, object]:
    """Capture source, handler, Modern XML, and Legacy XML descriptions."""

    with contextlib.redirect_stdout(io.StringIO()):
        modern_xml = main.export_furuno_modern(navarea_name.split()[1], container)
        legacy_xml = main.generate_legacy_xml_from_messages(
            navarea_name.split()[1], [message], 1, 1
        )
    modern_descriptions = _xml_descriptions(modern_xml)
    legacy_descriptions = _xml_descriptions(legacy_xml)
    parent_context = str(metadata.get("parent_context") or "")
    partition_semantic_context = str(metadata.get("semantic_context") or "")
    footer_context = str(metadata.get("footer_context") or "")
    semantic_source = " ".join(
        part
        for part in (
            parent_context,
            partition_semantic_context,
            sub_block,
            footer_context,
        )
        if part
    )

    objects: list[dict[str, object]] = []
    for object_type in OBJECT_TYPES:
        for index, obj in enumerate(message.get(object_type, [])):
            handler_description = str(obj.get("description", ""))
            modern_description = modern_descriptions[object_type][index] if index < len(
                modern_descriptions[object_type]
            ) else ""
            legacy_description = legacy_descriptions[object_type][index] if index < len(
                legacy_descriptions[object_type]
            ) else ""
            mismatch = _description_mismatch(
                handler_description, modern_description, legacy_description
            )
            contract = _description_contract_audit(
                obj,
                modern_description,
                legacy_description,
                source_text=sub_block,
            )
            semantic_context = _description_semantic_context(
                semantic_source, modern_description
            )
            objects.append(
                {
                    "object_type": object_type.removesuffix("s"),
                    "object_index": index,
                    "handler_description": handler_description,
                    "modern_description": modern_description,
                    "legacy_description": legacy_description,
                    "handler_length": len(handler_description),
                    "modern_length": len(modern_description),
                    "legacy_length": len(legacy_description),
                    "legacy_cap": len(modern_description) > main.LEGACY_MAX_DESC,
                    "mismatch_classification": mismatch,
                    "description_contract": contract,
                    "semantic_context": semantic_context,
                }
            )

    normalized_source = " ".join(sub_block.split())
    normalized_parent = " ".join(parent_context.split())
    return {
        "schema_version": "1.0",
        "source_expectation": {
            "parent_context": parent_context,
            "footer_context": footer_context,
            "section": sub_block,
            "relevant_fragment": sub_block,
        },
        "source_section": sub_block,
        "source_section_normalized": normalized_source,
        "parent_context": parent_context,
        "parent_context_normalized": normalized_parent,
        "footer_context": footer_context,
        "relevant_source": " ".join(
            part
            for part in (
                normalized_parent,
                normalized_source,
                " ".join(footer_context.split()),
            )
            if part
        ),
        "objects": objects,
    }


def _run_message(
    sub_block: str,
    navarea_name: str,
    metadata: Mapping[str, object],
    source: str,
    source_block_index: int,
    source_line: int,
) -> dict[str, object]:
    message = main.create_message(
        _message_id(navarea_name, metadata), metadata=dict(metadata)
    )
    container = main.create_container(navarea_name.split()[1])
    label_text = main.build_navarea_label(navarea_name)

    # The application prints handler traces unconditionally.  A corpus report
    # should be machine-readable and deterministic, so capture that noise.
    with contextlib.redirect_stdout(io.StringIO()):
        main.process_block(
            sub_block,
            message,
            container,
            navarea_name,
            label_text=label_text,
            meta=dict(metadata),
        )

    statements = extract_geometry_statements(sub_block, source, source_line)
    geometry_status, geometry_statuses, geometry_basis = _geometry_status(
        message, sub_block
    )
    diagnostics = list(message.get("diagnostics", []))
    counts = _object_counts(message)
    missing = _missing_components(statements, message, geometry_statuses)
    end_line = _line_at(sub_block, len(sub_block), source_line)
    description_audit = _description_audit(
        sub_block, navarea_name, metadata, message, container
    )

    result = {
        "id": message["id"],
        "source": source,
        "source_reference": _source_reference(source, source_line, end_line),
        "source_block_index": source_block_index,
        "navarea": navarea_name,
        "partition": _partition_id(message),
        "selected_handler": _selected_handler(message),
        "object_counts": counts,
        "coordinate_count": len(main.extract_coordinates(sub_block)),
        "geometry_status": geometry_status,
        "geometry_statuses": geometry_statuses,
        "geometry_basis": geometry_basis,
        "explicit_geometry_statements": statements,
        "multiple_explicit_geometry": len(statements) > 1,
        "missing_geometry_components": missing,
        "diagnostic_codes": _diagnostic_codes(message),
        "diagnostics": diagnostics,
        "stage_diagnostics": list(message.get("stage_diagnostics", [])),
        "processing_error": None,
        "description_audit": description_audit,
    }
    if message.get("geometry_audit"):
        result["geometry_audit"] = list(message["geometry_audit"])
    return result


def _run_block(
    normalized_text: str,
    source: str,
    source_block_index: int,
    header_match: re.Match[str],
    block: str,
    source_line: int,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    navarea_name = f"NAVAREA {header_match.group(1).upper()} {header_match.group(2)}"
    block_statements = extract_geometry_statements(block, source, source_line)

    with contextlib.redirect_stdout(io.StringIO()):
        partitions = main.partition_navarea_block(block, navarea_name)

    messages: list[dict[str, object]] = []
    for sub_block, metadata in partitions:
        try:
            messages.append(
                _run_message(
                    sub_block,
                    navarea_name,
                    metadata,
                    source,
                    source_block_index,
                    source_line + block[: block.find(sub_block)].count("\n"),
                )
            )
        except Exception as exc:  # Keep one malformed block from hiding others.
            messages.append(
                {
                    "id": _message_id(navarea_name, metadata),
                    "source": source,
                    "source_reference": _source_reference(source, source_line),
                    "source_block_index": source_block_index,
                    "navarea": navarea_name,
                    "partition": _partition_id({"metadata": metadata}),
                    "selected_handler": None,
                    "object_counts": {**{key: 0 for key in OBJECT_TYPES}, "object_count": 0},
                    "coordinate_count": len(main.extract_coordinates(sub_block)),
                    "geometry_status": "PROCESSING_ERROR",
                    "geometry_statuses": ["PROCESSING_ERROR"],
                    "geometry_basis": "runner_processing_error",
                    "explicit_geometry_statements": extract_geometry_statements(
                        sub_block, source, source_line
                    ),
                    "multiple_explicit_geometry": False,
                    "missing_geometry_components": [],
                    "diagnostic_codes": [],
                    "diagnostics": [],
                    "stage_diagnostics": [],
                    "processing_error": f"{type(exc).__name__}: {exc}",
                }
            )

    for message in messages:
        message["source_block_multiple_explicit_geometry"] = (
            len(block_statements) > 1
        )
        message["source_block_explicit_geometry_statements"] = block_statements

    block_record = {
        "source": source,
        "source_block_index": source_block_index,
        "navarea": navarea_name,
        "source_reference": _source_reference(
            source,
            source_line,
            source_line + block.count("\n"),
        ),
        "explicit_geometry_statements": block_statements,
        "multiple_explicit_geometry": len(block_statements) > 1,
        "message_ids": [message["id"] for message in messages],
        "component_loss_messages": [
            {
                "id": message["id"],
                "source_reference": message["source_reference"],
                "selected_handler": message["selected_handler"],
                "geometry_status": message["geometry_status"],
                "missing_geometry_components": message[
                    "missing_geometry_components"
                ],
            }
            for message in messages
            if message["missing_geometry_components"]
        ],
    }
    return block_record, messages


def _summary(
    sources: Sequence[Mapping[str, object]],
    blocks: Sequence[Mapping[str, object]],
    messages: Sequence[Mapping[str, object]],
    intake_errors: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    status_counts: Counter[str] = Counter()
    status_flag_counts: Counter[str] = Counter()
    handler_counts: Counter[str] = Counter()
    object_totals: Counter[str] = Counter()
    description_counts: Counter[str] = Counter()
    description_contract_counts: Counter[str] = Counter()
    description_traceability_counts: Counter[str] = Counter()
    description_objects = 0
    semantic_context_counts: Counter[str] = Counter()
    for message in messages:
        status_counts[str(message["geometry_status"])] += 1
        status_flag_counts.update(str(status) for status in message["geometry_statuses"])
        handler_counts[str(message["selected_handler"] or "NONE")] += 1
        object_totals.update(message["object_counts"])
        audit = message.get("description_audit", {})
        for obj in audit.get("objects", []) if isinstance(audit, Mapping) else []:
            description_objects += 1
            semantic = obj.get("semantic_context", {})
            if isinstance(semantic, Mapping):
                semantic_context_counts[str(semantic.get("status", "UNKNOWN"))] += 1
            mismatch = obj.get("mismatch_classification", {})
            overall = (
                mismatch.get("overall")
                if isinstance(mismatch, Mapping)
                else "UNKNOWN"
            )
            description_counts[str(overall)] += 1
            contract = obj.get("description_contract", {})
            contract_status = (
                contract.get("status")
                if isinstance(contract, Mapping)
                else "UNKNOWN"
            )
            description_contract_counts[str(contract_status)] += 1
            if isinstance(contract, Mapping):
                description_traceability_counts.update(
                    str(issue)
                    for issue in contract.get("traceability_issues", [])
                )

    return {
        "source_files": len(sources),
        "source_blocks": len(blocks),
        "messages": len(messages),
        "intake_errors": len(intake_errors),
        "processing_errors": sum(
            1 for message in messages if message.get("processing_error")
        ),
        "multiple_explicit_geometry_blocks": sum(
            1 for block in blocks if block["multiple_explicit_geometry"]
        ),
        "mixed_geometry_source_messages": sum(
            1
            for message in messages
            if message["source_block_multiple_explicit_geometry"]
        ),
        "mixed_geometry_component_losses": sum(
            1 for message in messages if message["missing_geometry_components"]
        ),
        "geometry_status_counts": dict(sorted(status_counts.items())),
        "geometry_status_flag_counts": dict(sorted(status_flag_counts.items())),
        "handler_counts": dict(sorted(handler_counts.items())),
        "object_totals": dict(sorted(object_totals.items())),
        "description_audit": {
            "messages": len(messages),
            "objects": description_objects,
            "mismatch_classifications": dict(sorted(description_counts.items())),
            "semantic_context_statuses": dict(
                sorted(semantic_context_counts.items())
            ),
            "contract_statuses": dict(
                sorted(description_contract_counts.items())
            ),
            "traceability_issues": dict(
                sorted(description_traceability_counts.items())
            ),
        },
    }


def run_corpus(
    root: Path | str = ".",
    sources: Iterable[Path | str] | None = None,
    include_future_coastal: bool = False,
) -> dict[str, object]:
    """Run the current parser against every selected NAVAREA source."""

    root = Path(root).resolve()
    source_paths = (
        [Path(source).resolve() for source in sources]
        if sources is not None
        else discover_sources(root, include_future_coastal=include_future_coastal)
    )
    source_records: list[dict[str, object]] = []
    blocks: list[dict[str, object]] = []
    messages: list[dict[str, object]] = []
    intake_errors: list[dict[str, object]] = []

    for source_path in source_paths:
        source = _relative_source(source_path, root)
        intake = load_source(str(source_path))
        if intake.text is None:
            intake_errors.append(
                {"source": source, "error": intake.error or "source could not be decoded"}
            )
            source_records.append(
                {
                    "source": source,
                    "status": intake.status.value,
                    "encoding": intake.encoding,
                    "error": intake.error,
                }
            )
            continue

        # Boundary discovery intentionally uses decoded source text.  The
        # normalizer may join lines in a way that makes cancellation
        # references look like fresh NAVAREA headers.
        normalized = intake.text
        source_records.append(
            {
                "source": source,
                "status": intake.status.value,
                "encoding": intake.encoding,
                "detected_encoding": intake.detected_encoding,
                "fallback_used": intake.fallback_used,
                "replacement_count": intake.replacement_count,
                "warnings": list(intake.warnings),
            }
        )
        for block_index, header_match, block in iter_navarea_blocks(normalized):
            # Keep the source boundary and line number from the decoded
            # source.  Normalize only inside that block so cancellation
            # references cannot become new parser blocks.
            raw_block = block
            normalized_block = main.normalize_input(
                raw_block, main.NormalizerStats()
            )
            normalized_header = NAVAREA_HEADER_RE.search(normalized_block)
            if normalized_header is None:
                intake_errors.append(
                    {
                        "source": source,
                        "error": "NAVAREA header disappeared during normalization",
                        "source_line": _line_at(normalized, header_match.start()),
                    }
                )
                continue
            block_record, block_messages = _run_block(
                normalized_block,
                source,
                block_index,
                normalized_header,
                normalized_block,
                _line_at(normalized, header_match.start()),
            )
            blocks.append(block_record)
            messages.extend(block_messages)

    # Keep the duplicate review separate from parser output.  The default
    # release corpus remains the 21 primary files, while this review also
    # inspects the retained coastal manifest so a clean parser baseline cannot
    # accidentally imply that coastal sources were reviewed.
    duplicate_sources = (
        source_paths
        if sources is not None
        else discover_sources(root, include_future_coastal=True)
    )
    summary = _summary(source_records, blocks, messages, intake_errors)
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "runner": "corpus_runner",
        "sources": source_records,
        "blocks": blocks,
        "messages": messages,
        "summary": summary,
        "description_audit": {
            "schema_version": "1.0",
            "scope": "all selected source messages and emitted objects",
            "source_files": len(source_records),
            "source_blocks": len(blocks),
            "messages": len(messages),
            "objects": summary["description_audit"]["objects"],
            "mismatch_classifications": summary["description_audit"][
                "mismatch_classifications"
            ],
            "semantic_context_statuses": summary["description_audit"][
                "semantic_context_statuses"
            ],
            "traceability_issues": summary["description_audit"][
                "traceability_issues"
            ],
            "records": "messages[].description_audit",
        },
        "intake_errors": intake_errors,
        "duplicate_review": review_warning_duplicates(root, duplicate_sources),
    }
    return report


def _record_key(record: Mapping[str, object]) -> tuple[object, ...]:
    return (
        record.get("source"),
        record.get("source_block_index"),
        record.get("id"),
    )

def _component_loss_key(
    record: Mapping[str, object], kind: str
) -> tuple[object, ...]:
    return (*_record_key(record), kind)


def _report_fingerprint(report: Mapping[str, object]) -> str:
    """Return a stable fingerprint for a report before validation metadata."""

    canonical = json.dumps(report, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _report_for_baseline_fingerprint(
    report: Mapping[str, object],
) -> dict[str, object]:
    """Remove metadata added after a corpus report was generated."""

    content = dict(report)
    for metadata_key in ("differential", "report_sha256", "validation"):
        content.pop(metadata_key, None)
    return content


def _load_json_object(path: Path, description: str) -> Mapping[str, object]:
    """Load a JSON object and give baseline operations actionable errors."""

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"{description} was not found: {path}") from exc
    except UnicodeError as exc:
        raise ValueError(f"{description} is not valid UTF-8: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"{description} contains invalid JSON: {path}") from exc
    except OSError as exc:
        raise ValueError(f"{description} could not be read ({exc}): {path}") from exc
    if not isinstance(value, Mapping):
        raise ValueError(f"{description} must contain a JSON object: {path}")
    return value


def update_compact_baseline(
    baseline_path: Path | str,
    source_report_path: Path | str,
    current_report: Mapping[str, object],
) -> dict[str, object]:
    """Write compact metadata only after verifying a reviewed full report.

    The current report is generated from the working corpus immediately
    before this function is called.  The reviewed report must describe that
    exact corpus, so neither its message count nor its fingerprint can be
    supplied independently.
    """

    preview = preview_compact_baseline(
        baseline_path,
        source_report_path,
        current_report,
    )
    if not preview["reviewed_report_matches_current"]:
        if preview["reviewed_report_messages"] != preview["current_messages"]:
            raise ValueError(
                "source report message count does not match the current corpus"
            )
        raise ValueError("source report fingerprint does not match the current corpus")

    baseline_path = Path(baseline_path)
    compact_baseline = dict(preview["proposed_baseline"])

    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = baseline_path.with_name(
        f".{baseline_path.name}.tmp"
    )
    try:
        temporary_path.write_text(
            json.dumps(compact_baseline, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary_path.replace(baseline_path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()
    return compact_baseline


def preview_compact_baseline(
    baseline_path: Path | str,
    source_report_path: Path | str,
    current_report: Mapping[str, object],
) -> dict[str, object]:
    """Derive a compact baseline without changing any files.

    The returned preview includes the proposed baseline, the fingerprints and
    message counts used for approval, and any metadata that would be carried
    forward from an existing compact baseline.
    """

    baseline_path = Path(baseline_path)
    source_report_path = Path(source_report_path)
    source_report = _load_json_object(source_report_path, "source report")

    source_messages = source_report.get("messages")
    if not isinstance(source_messages, list):
        raise ValueError(
            f"source report must contain a messages list: {source_report_path}"
        )
    source_summary = source_report.get("summary")
    if not isinstance(source_summary, Mapping):
        raise ValueError(
            f"source report must contain a summary object: {source_report_path}"
        )
    source_summary_count = source_summary.get("messages")
    if (
        isinstance(source_summary_count, bool)
        or not isinstance(source_summary_count, int)
        or source_summary_count != len(source_messages)
    ):
        raise ValueError(
            "source report message count does not match its messages list: "
            f"{source_report_path}"
        )

    current_messages = current_report.get("messages")
    current_summary = current_report.get("summary")
    if not isinstance(current_messages, list) or not isinstance(
        current_summary, Mapping
    ):
        raise ValueError("current corpus report is missing messages or summary data")
    if current_summary.get("messages") != len(current_messages):
        raise ValueError("current corpus report has inconsistent message count")
    source_fingerprint = _report_fingerprint(
        _report_for_baseline_fingerprint(source_report)
    )
    current_fingerprint = _report_fingerprint(current_report)
    declared_source_fingerprint = source_report.get("report_sha256")
    if (
        declared_source_fingerprint is not None
        and declared_source_fingerprint != source_fingerprint
    ):
        raise ValueError(
            "source report fingerprint metadata does not match its contents"
        )
    if source_fingerprint != current_fingerprint:
        reviewed_report_matches_current = False
    else:
        reviewed_report_matches_current = True

    existing: dict[str, object] = {}
    if baseline_path.exists():
        existing = dict(
            _load_json_object(baseline_path, "compact baseline")
        )
    source_reference = os.path.relpath(
        source_report_path.resolve(), baseline_path.resolve().parent
    )
    compact_baseline = {
        **existing,
        "baseline_messages": len(source_messages),
        "report_sha256": source_fingerprint,
        "source_report": source_reference,
    }
    review_metadata = {
        key: value
        for key, value in existing.items()
        if key not in {"baseline_messages", "report_sha256", "source_report"}
    }
    return {
        "proposed_baseline": compact_baseline,
        "reviewed_report_messages": len(source_messages),
        "reviewed_report_sha256": source_fingerprint,
        "current_messages": len(current_messages),
        "current_report_sha256": current_fingerprint,
        "reviewed_report_matches_current": (
            reviewed_report_matches_current
            and source_summary_count == len(current_messages)
        ),
        "review_metadata": review_metadata,
    }


def _compact_baseline_source(
    baseline: Mapping[str, object],
    source_comparison: Mapping[str, object] | None,
) -> Mapping[str, object] | None:
    if source_comparison is not None:
        return source_comparison
    for candidate_key in ("source_comparison", "source_report"):
        candidate = baseline.get(candidate_key)
        if isinstance(candidate, Mapping):
            return candidate
    return None


def _baseline_message_count_finding(
    declared_count: object,
    established_count: int | None,
    count_source: str | None,
) -> tuple[bool | None, str | None]:
    """Check compact count metadata when a trusted count is available."""

    if established_count is None:
        return None, None
    if declared_count == established_count:
        return True, None
    declared_label = (
        f"{declared_count} message"
        if declared_count == 1
        else f"{declared_count} messages"
    )
    established_label = (
        f"{established_count} message"
        if established_count == 1
        else f"{established_count} messages"
    )
    return (
        False,
        "compact baseline declares "
        f"{declared_label}, but {count_source} contains {established_label}",
    )


def compare_reports(
    before: Mapping[str, object],
    after: Mapping[str, object],
    expected_ids: Iterable[str] = (),
    source_comparison: Mapping[str, object] | None = None,
    source_comparison_unavailable_reason: str | None = None,
) -> dict[str, object]:
    """Compare two runner reports without comparing volatile descriptions."""

    # Release baselines use a compact fingerprint rather than checking a
    # multi-megabyte report into the repository.  If a matching full report is
    # available, use it to identify the message-level changes while retaining
    # the compact fingerprint as the release gate.
    baseline_fingerprint = before.get("report_sha256")
    if baseline_fingerprint:
        source_report = _compact_baseline_source(before, source_comparison)
        source_report_messages = (
            source_report.get("messages")
            if isinstance(source_report, Mapping)
            else None
        )
        source_report_fingerprint = None
        if isinstance(source_report, Mapping) and isinstance(
            source_report_messages, list
        ):
            source_report_fingerprint = source_report.get("report_sha256")
            if source_report_fingerprint is None:
                source_report_fingerprint = _report_fingerprint(source_report)
        source_report_matches_baseline = (
            isinstance(source_report_messages, list)
            and source_report_fingerprint == baseline_fingerprint
        )
        fingerprint_matches = _report_fingerprint(after) == baseline_fingerprint
        if fingerprint_matches:
            changes = []
            source_comparison_available = False
            source_comparison_unavailable_reason = None
            established_count = (
                len(source_report_messages)
                if source_report_matches_baseline
                else (
                    len(after.get("messages", []))
                    if isinstance(after.get("messages"), list)
                    else None
                )
            )
            count_source = (
                "matching source report"
                if source_report_matches_baseline
                else "matching current report"
            )
        else:
            if source_report is not None:
                if not isinstance(source_report_messages, list):
                    source_comparison_unavailable_reason = (
                        source_comparison_unavailable_reason
                        or "source report does not contain any messages"
                    )
            source_comparison_available = bool(
                source_report_matches_baseline
            )
            if source_report is not None and not source_comparison_available:
                source_comparison_unavailable_reason = (
                    source_comparison_unavailable_reason
                    or "source report fingerprint does not match baseline fingerprint"
                )
            elif source_report is None:
                source_comparison_unavailable_reason = (
                    source_comparison_unavailable_reason
                    or "referenced source report was not available"
                )
            if source_comparison_available:
                # Ignore a source report's own fingerprint here.  The compact
                # baseline has already been checked above; this pass compares
                # the source-level message records directly.
                source_before = dict(source_report)
                source_before.pop("report_sha256", None)
                source_differential = _compare_message_reports(
                    source_before, after, expected_ids
                )
                changes = source_differential["changes"]
                established_count = len(source_report_messages)
                count_source = "matching source report"
            else:
                changes = [
                    {
                        "message": "CORPUS_REPORT",
                        "source_reference": None,
                        "classification": "UNEXPECTED",
                        "expected": False,
                        "severity": "ERROR",
                        "changed_fields": ["report_sha256"],
                        "before": {"report_sha256": baseline_fingerprint},
                        "after": {
                            "report_sha256": _report_fingerprint(after)
                        },
                    }
                ]
                established_count = None
                count_source = None

        baseline_messages_consistent, baseline_messages_error = (
            _baseline_message_count_finding(
                before.get("baseline_messages"),
                established_count,
                count_source,
            )
        )
        if baseline_messages_error:
            changes.append(
                {
                    "message": "COMPACT_BASELINE",
                    "source_reference": None,
                    "classification": "UNEXPECTED",
                    "expected": False,
                    "severity": "ERROR",
                    "changed_fields": ["baseline_messages"],
                    "before": {
                        "baseline_messages": before.get("baseline_messages")
                    },
                    "after": {"baseline_messages": established_count},
                }
            )
        reported_baseline_messages = (
            established_count
            if established_count is not None
            else before.get("baseline_messages")
        )

        if source_comparison_available:
            return {
                "baseline_messages": reported_baseline_messages,
                "declared_baseline_messages": before.get("baseline_messages"),
                "current_messages": len(after.get("messages", [])),
                "compared_messages": source_differential["compared_messages"],
                "changed_messages": len(changes),
                "unexpected_changes": sum(
                    1 for change in changes if not change["expected"]
                ),
                "critical_changes": sum(
                    1 for change in changes if change["severity"] == "CRITICAL"
                ),
                "baseline_messages_consistent": baseline_messages_consistent,
                "baseline_messages_error": baseline_messages_error,
                "baseline_message_count_source": count_source,
                "source_comparison_available": True,
                "source_comparison_unavailable_reason": None,
                "changes": changes,
            }

        return {
            "baseline_messages": reported_baseline_messages,
            "declared_baseline_messages": before.get("baseline_messages"),
            "current_messages": len(after.get("messages", [])),
            "compared_messages": len(after.get("messages", [])),
            "changed_messages": len(changes),
            "unexpected_changes": len(changes),
            "critical_changes": sum(
                1 for change in changes if change["severity"] == "CRITICAL"
            ),
            "baseline_messages_consistent": baseline_messages_consistent,
            "baseline_messages_error": baseline_messages_error,
            "baseline_message_count_source": count_source,
            "source_comparison_available": False,
            "source_comparison_unavailable_reason": (
                source_comparison_unavailable_reason
            ),
            "changes": changes,
        }

    return _compare_message_reports(before, after, expected_ids)


def _compare_message_reports(
    before: Mapping[str, object],
    after: Mapping[str, object],
    expected_ids: Iterable[str] = (),
) -> dict[str, object]:
    """Compare message records from two full source-level reports."""

    expected_ids = set(expected_ids)
    before_by_key = {
        _record_key(record): record for record in before.get("messages", [])
    }
    changes: list[dict[str, object]] = []
    compared = 0

    fields = ("selected_handler", "object_counts", "geometry_statuses", "diagnostic_codes")
    for after_record in after.get("messages", []):
        key = _record_key(after_record)
        before_record = before_by_key.get(key)
        if before_record is None:
            changes.append(
                {
                    "message": after_record.get("id"),
                    "source_reference": after_record.get("source_reference"),
                    "classification": "ADDED",
                    "expected": after_record.get("id") in expected_ids,
                    "severity": "WARNING",
                    "before": None,
                    "after": {field: after_record.get(field) for field in fields},
                }
            )
            continue
        compared += 1
        changed_fields = [
            field
            for field in fields
            if before_record.get(field) != after_record.get(field)
        ]
        if not changed_fields:
            continue
        has_loss = bool(after_record.get("missing_geometry_components"))
        geometry_changed = any(
            field in changed_fields for field in ("object_counts", "geometry_statuses")
        )
        severity = "CRITICAL" if has_loss else "ERROR" if geometry_changed else "WARNING"
        changes.append(
            {
                "message": after_record.get("id"),
                "source_reference": (
                    after_record.get("source_reference")
                    or before_record.get("source_reference")
                ),
                "classification": "EXPECTED" if after_record.get("id") in expected_ids else "UNEXPECTED",
                "expected": after_record.get("id") in expected_ids,
                "severity": severity,
                "changed_fields": changed_fields,
                "before": {field: before_record.get(field) for field in fields},
                "after": {field: after_record.get(field) for field in fields},
            }
        )

    after_keys = {_record_key(record) for record in after.get("messages", [])}
    for before_record in before.get("messages", []):
        if _record_key(before_record) not in after_keys:
            changes.append(
                {
                    "message": before_record.get("id"),
                    "source_reference": before_record.get("source_reference"),
                    "classification": "REMOVED",
                    "expected": before_record.get("id") in expected_ids,
                    "severity": "CRITICAL",
                    "before": {field: before_record.get(field) for field in fields},
                    "after": None,
                }
            )

    return {
        "baseline_messages": len(before.get("messages", [])),
        "current_messages": len(after.get("messages", [])),
        "compared_messages": compared,
        "changed_messages": len(changes),
        "unexpected_changes": sum(1 for change in changes if not change["expected"]),
        "critical_changes": sum(
            1 for change in changes if change["severity"] == "CRITICAL"
        ),
        "changes": changes,
    }

def _reviewed_component_loss_keys(
    baseline: Mapping[str, object] | None,
    reviewed_loss_ids: Iterable[str],
) -> set[tuple[object, ...]]:
    """Read reviewed loss entries from a baseline and CLI message allowlist."""

    reviewed: set[tuple[object, ...]] = set()
    reviewed_ids = set(reviewed_loss_ids)
    if baseline:
        for finding in baseline.get("reviewed_component_losses", []):
            if not isinstance(finding, Mapping):
                continue
            source = finding.get("source")
            source_block_index = finding.get("source_block_index")
            message_id = finding.get("id")
            kind = finding.get("kind")
            if (
                source is not None
                and source_block_index is not None
                and message_id is not None
                and kind is not None
            ):
                reviewed.add((source, source_block_index, message_id, kind))

    return reviewed | {
        ("*", "*", message_id, "*") for message_id in reviewed_ids
    }


def _summary_value(value: object) -> str:
    """Return a compact, safe value for a GitHub Markdown summary."""

    return str(value).replace("|", r"\|").replace("\n", " ")


def _finding_source_reference(finding: Mapping[str, object]) -> str:
    reference = finding.get("source_reference")
    return _summary_value(reference) if reference else "source unavailable"


def render_github_summary(report: Mapping[str, object]) -> str:
    """Render the concise report that GitHub Actions shows in a job summary."""

    summary = report.get("summary") or {}
    validation = report.get("validation") or {}
    differential = report.get("differential") or {}
    status = validation.get("status", "UNKNOWN")
    baseline_count_line = (
        [
            "| Baseline messages | "
            f"{_summary_value(differential['baseline_messages'])} |"
        ]
        if "baseline_messages" in differential
        else []
    )

    lines = [
        "## NAVAREA geometry validation",
        "",
        f"**Status: `{_summary_value(status)}`**",
        "",
        "| Metric | Count |",
        "| --- | ---: |",
        f"| Source files | {_summary_value(summary.get('source_files', 0))} |",
        f"| NAVAREA blocks | {_summary_value(summary.get('source_blocks', 0))} |",
        f"| Messages | {_summary_value(summary.get('messages', 0))} |",
        *baseline_count_line,
        f"| Intake errors | {_summary_value(validation.get('intake_errors', summary.get('intake_errors', 0)))} |",
        f"| Processing errors | {_summary_value(validation.get('processing_errors', summary.get('processing_errors', 0)))} |",
        f"| Unexpected changes | {_summary_value(validation.get('unexpected_differential_changes', differential.get('unexpected_changes', 0)))} |",
        f"| Reviewed component losses | {_summary_value(validation.get('reviewed_component_loss_count', 0))} |",
        f"| Unreviewed component losses | {_summary_value(validation.get('unreviewed_component_loss_count', 0))} |",
    ]

    status_counts = summary.get("geometry_status_counts") or {}
    if status_counts:
        lines.extend(
            [
                "",
                "### Geometry outcomes",
                "",
                "| Outcome | Count |",
                "| --- | ---: |",
            ]
        )
        lines.extend(
            f"| `{_summary_value(status_name)}` | {_summary_value(count)} |"
            for status_name, count in sorted(status_counts.items())
        )

    changes = differential.get("changes", [])
    if differential.get("source_comparison_available"):
        displayed_changes = list(changes)
        changes_heading = "### Changed messages"
    else:
        displayed_changes = [
            change for change in changes if not change.get("expected")
        ]
        changes_heading = "### Unexpected changes"
    if displayed_changes:
        lines.extend(["", changes_heading, ""])
        for change in displayed_changes:
            message = _summary_value(change.get("message", "unknown message"))
            severity = _summary_value(change.get("severity", "UNKNOWN"))
            reference = _finding_source_reference(change)
            lines.append(f"- `{severity}` `{message}` — `{reference}`")

    baseline_messages_error = differential.get("baseline_messages_error")
    if baseline_messages_error:
        lines.extend(
            [
                "",
                "### Baseline metadata error",
                "",
                _summary_value(baseline_messages_error) + ".",
            ]
        )

    source_comparison_reason = differential.get(
        "source_comparison_unavailable_reason"
    )
    if source_comparison_reason:
        lines.extend(
            [
                "",
                "### Source-level comparison unavailable",
                "",
                "The referenced source report could not be used for the "
                "source-level comparison: "
                f"{_summary_value(source_comparison_reason)}.",
            ]
        )

    unreviewed_losses = validation.get("unreviewed_component_losses") or []
    if unreviewed_losses:
        lines.extend(["", "### Unreviewed component losses", ""])
        for finding in unreviewed_losses:
            message = _summary_value(finding.get("id", "unknown message"))
            missing = finding.get("missing_geometry_components") or []
            kinds = []
            for component in missing:
                if isinstance(component, Mapping):
                    kinds.append(str(component.get("kind", "unknown")))
                else:
                    kinds.append(str(component))
            component_text = ", ".join(_summary_value(kind) for kind in kinds) or "unknown"
            reference = _finding_source_reference(finding)
            lines.append(
                f"- `{message}` — missing `{component_text}` — `{reference}`"
            )

    lines.extend(
        [
            "",
            "The full JSON report is available in the "
            "`NAVAREA-corpus-validation` workflow artifact.",
            "",
        ]
    )
    return "\n".join(lines)


def write_github_summary(
    report: Mapping[str, object], summary_path: Path | str
) -> None:
    """Write a report summary to the GitHub Actions step-summary file."""

    path = Path(summary_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_github_summary(report), encoding="utf-8")


def _load_source_comparison(
    path: Path,
) -> tuple[Mapping[str, object] | None, str | None]:
    """Load a source report and explain why it cannot be used when possible."""

    try:
        source_comparison = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, f"referenced source report was not found: {path}"
    except UnicodeError:
        return None, f"source report is not valid UTF-8: {path}"
    except json.JSONDecodeError:
        return None, f"source report contains invalid JSON: {path}"
    except OSError as exc:
        return None, f"source report could not be read ({exc}): {path}"
    if not isinstance(source_comparison, Mapping):
        return None, f"source report must contain a JSON object: {path}"
    return source_comparison, None


def _missing_compact_baseline_metadata(
    baseline: Mapping[str, object],
) -> list[str]:
    """Return required compact-baseline keys that are absent."""

    return [
        key for key in COMPACT_BASELINE_METADATA if key not in baseline
    ]


def _invalid_compact_baseline_metadata(
    baseline: Mapping[str, object],
) -> list[str]:
    """Return compact-baseline metadata keys whose values are malformed."""

    invalid: list[str] = []
    baseline_messages = baseline.get("baseline_messages")
    if (
        isinstance(baseline_messages, bool)
        or not isinstance(baseline_messages, int)
        or baseline_messages < 0
    ):
        invalid.append("baseline_messages")

    report_sha256 = baseline.get("report_sha256")
    if (
        not isinstance(report_sha256, str)
        or SHA256_FINGERPRINT_RE.fullmatch(report_sha256) is None
    ):
        invalid.append("report_sha256")

    return invalid


def _print_summary(report: Mapping[str, object]) -> None:
    summary = report["summary"]
    print(
        "Corpus: "
        f"{summary['source_blocks']} blocks, {summary['messages']} messages, "
        f"{summary['source_files']} source files"
    )
    print(
        "Geometry statuses: "
        + json.dumps(summary["geometry_status_counts"], sort_keys=True)
    )
    print(
        "Mixed geometry: "
        f"{summary['multiple_explicit_geometry_blocks']} blocks, "
        f"{summary['mixed_geometry_component_losses']} component-loss records"
    )
    if report.get("validation"):
        validation = report["validation"]
        print(
            "Release validation: "
            f"{validation['status']} "
            f"({validation['unreviewed_component_loss_count']} unreviewed losses)"
        )
    if report.get("differential"):
        differential = report["differential"]
        print(
            "Differential: "
            f"{differential['changed_messages']} changed, "
            f"{differential['unexpected_changes']} unexpected"
        )
        if "baseline_messages" in differential:
            print(f"Baseline messages: {differential['baseline_messages']}")
        if differential.get("baseline_messages_error"):
            print(
                "Baseline message count: ERROR "
                f"({differential['baseline_messages_error']})"
            )


def main_cli(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--source",
        action="append",
        type=Path,
        help=(
            "source file to run (repeatable; defaults to the 21 primary "
            "NAVAREA sources)"
        ),
    )
    parser.add_argument(
        "--include-future-coastal",
        action="store_true",
        help=(
            "include the retained coastal and other regional sources in "
            "addition to the 21 primary NAVAREA sources"
        ),
    )
    parser.add_argument("--baseline", type=Path, help="prior JSON report to compare")
    parser.add_argument(
        "--update-baseline",
        type=Path,
        help="write a compact baseline to this path from a verified full report",
    )
    parser.add_argument(
        "--preview-baseline",
        type=Path,
        help=(
            "preview a compact baseline without changing files; use with "
            "--source-report"
        ),
    )
    parser.add_argument(
        "--json",
        "--preview-baseline-json",
        dest="preview_baseline_json",
        action="store_true",
        help=(
            "emit the --preview-baseline result as machine-readable JSON "
            "instead of text"
        ),
    )
    parser.add_argument(
        "--source-report",
        type=Path,
        help=(
            "reviewed full report used with --update-baseline or "
            "--preview-baseline; its fingerprint and message count are checked "
            "against the current corpus"
        ),
    )
    parser.add_argument(
        "--source-baseline",
        type=Path,
        help=(
            "optional full report to use for message-level comparison when "
            "the compact baseline fingerprint drifts"
        ),
    )
    parser.add_argument("--output", type=Path, help="write the JSON report to this path")
    parser.add_argument(
        "--github-summary",
        type=Path,
        help="write a Markdown summary to a GitHub Actions step-summary path",
    )
    parser.add_argument(
        "--expected-id",
        action="append",
        default=[],
        help="message id allowed to change in a baseline comparison (repeatable)",
    )
    parser.add_argument(
        "--reviewed-loss-id",
        action="append",
        default=[],
        help="message id whose existing component loss has been reviewed (repeatable)",
    )
    parser.add_argument(
        "--fail-on-loss",
        action="store_true",
        help="return status 2 when an explicit geometry component is missing",
    )
    args = parser.parse_args(argv)

    baseline_command = args.update_baseline or args.preview_baseline
    if args.update_baseline and args.preview_baseline:
        print(
            "--update-baseline and --preview-baseline cannot be used together",
            file=sys.stderr,
        )
        return 2
    if bool(baseline_command) != bool(args.source_report):
        print(
            "--update-baseline or --preview-baseline and --source-report "
            "must be provided together",
            file=sys.stderr,
        )
        return 2
    if args.preview_baseline_json and not args.preview_baseline:
        print(
            "--json can only be used with --preview-baseline",
            file=sys.stderr,
        )
        return 2

    report = run_corpus(
        args.root,
        args.source,
        include_future_coastal=args.include_future_coastal,
    )
    if args.update_baseline:
        try:
            compact_baseline = update_compact_baseline(
                args.update_baseline,
                args.source_report,
                report,
            )
        except (OSError, ValueError) as exc:
            print(f"compact baseline was not updated: {exc}", file=sys.stderr)
            return 1
        print(
            "Updated compact baseline: "
            f"{args.update_baseline} "
            f"({compact_baseline['baseline_messages']} messages)"
        )
        return 0

    if args.preview_baseline:
        try:
            preview = preview_compact_baseline(
                args.preview_baseline,
                args.source_report,
                report,
            )
        except (OSError, ValueError) as exc:
            print(f"compact baseline preview failed: {exc}", file=sys.stderr)
            return 1
        matches = preview["reviewed_report_matches_current"]
        if args.preview_baseline_json:
            print(json.dumps(preview, indent=2, sort_keys=True))
            return 0 if matches else 1
        print("Compact baseline preview (read-only)")
        print(f"Baseline path: {args.preview_baseline}")
        print(f"Derived message count: {preview['reviewed_report_messages']}")
        print(f"Derived fingerprint: {preview['reviewed_report_sha256']}")
        print(
            "Current corpus: "
            f"{preview['current_messages']} messages, "
            f"fingerprint {preview['current_report_sha256']}"
        )
        print(
            "Reviewed report matches current corpus: "
            f"{'YES' if matches else 'NO'}"
        )
        review_metadata = preview["review_metadata"]
        if review_metadata:
            print(
                "Preserved review metadata: "
                + json.dumps(review_metadata, sort_keys=True)
            )
        else:
            print("Preserved review metadata: none")
        return 0 if matches else 1

    baseline = None
    if args.baseline:
        try:
            baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
        except OSError as exc:
            print(
                f"compact baseline could not be read ({exc}): {args.baseline}",
                file=sys.stderr,
            )
            return 1
        except UnicodeError:
            print(
                f"compact baseline is not valid UTF-8: {args.baseline}",
                file=sys.stderr,
            )
            return 1
        except json.JSONDecodeError:
            print(
                f"compact baseline contains invalid JSON: {args.baseline}",
                file=sys.stderr,
            )
            return 1
        if not isinstance(baseline, Mapping):
            print(
                f"compact baseline must contain a JSON object: {args.baseline}",
                file=sys.stderr,
            )
            return 1
        missing_metadata = _missing_compact_baseline_metadata(baseline)
        if missing_metadata:
            print(
                "compact baseline is missing required metadata "
                f"({', '.join(missing_metadata)}): {args.baseline}",
                file=sys.stderr,
            )
            return 1
        invalid_metadata = _invalid_compact_baseline_metadata(baseline)
        if invalid_metadata:
            print(
                "compact baseline has invalid metadata "
                f"({', '.join(invalid_metadata)}): {args.baseline}",
                file=sys.stderr,
            )
            return 1
        source_comparison = None
        source_comparison_unavailable_reason = None
        source_baseline_path = args.source_baseline
        if source_baseline_path is None:
            source_report_value = baseline.get("source_report")
            if isinstance(source_report_value, str):
                candidate_paths = [
                    Path(source_report_value),
                    args.root / source_report_value,
                    args.baseline.parent / source_report_value,
                ]
                source_baseline_path = next(
                    (
                        path
                        for path in candidate_paths
                        if path.is_file()
                    ),
                    None,
                )
                if source_baseline_path is None:
                    source_comparison_unavailable_reason = (
                        "referenced source report was not found: "
                        f"{source_report_value}"
                    )
        if source_baseline_path is not None:
            (
                source_comparison,
                source_comparison_unavailable_reason,
            ) = _load_source_comparison(source_baseline_path)
        report["differential"] = compare_reports(
            baseline,
            report,
            args.expected_id,
            source_comparison,
            source_comparison_unavailable_reason,
        )
    report["validation"] = validate_report(
        report,
        report.get("differential"),
        baseline,
        args.reviewed_loss_id,
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"Wrote corpus report: {args.output}")
    if args.github_summary:
        write_github_summary(report, args.github_summary)
    _print_summary(report)

    if (
        report["summary"]["intake_errors"]
        or report["summary"]["processing_errors"]
    ):
        return 1
    if report.get("differential", {}).get("unexpected_changes"):
        return 1
    if report["validation"].get("semantic_context_missing_count"):
        return 1
    if (
        args.fail_on_loss
        and report["validation"]["unreviewed_component_loss_count"]
    ):
        return 2
    return 0


def _component_loss_keys(
    report: Mapping[str, object],
) -> set[tuple[object, ...]]:
    return {
        _component_loss_key(
            message,
            str(kind.get("kind") if isinstance(kind, Mapping) else kind),
        )
        for message in report.get("messages", [])
        for kind in message.get("missing_geometry_components", [])
    }

def validate_report(
    report: Mapping[str, object],
    differential: Mapping[str, object] | None = None,
    baseline: Mapping[str, object] | None = None,
    reviewed_loss_ids: Iterable[str] = (),
) -> dict[str, object]:
    """Summarize release-blocking findings in a machine-readable form."""

    reviewed_keys = _reviewed_component_loss_keys(baseline, reviewed_loss_ids)
    losses = _component_loss_keys(report)
    unreviewed_loss_keys = {
        loss
        for loss in losses
        if loss not in reviewed_keys
        and ("*", "*", loss[2], "*") not in reviewed_keys
    }
    unreviewed_losses = [
        message
        for message in report.get("messages", [])
        if any(
            _component_loss_key(
                message,
                str(kind.get("kind") if isinstance(kind, Mapping) else kind),
            )
            in unreviewed_loss_keys
            for kind in message.get("missing_geometry_components", [])
        )
    ]
    processing_errors = int(report["summary"].get("processing_errors", 0))
    intake_errors = int(report["summary"].get("intake_errors", 0))
    unexpected_changes = int(
        (differential or {}).get("unexpected_changes", 0)
    )
    baseline_messages_consistent = (differential or {}).get(
        "baseline_messages_consistent"
    )
    baseline_messages_error = (differential or {}).get(
        "baseline_messages_error"
    )
    semantic_context_missing = [
        {
            "id": message["id"],
            "source_reference": message["source_reference"],
            "object_type": obj["object_type"],
            "object_index": obj["object_index"],
        }
        for message in report.get("messages", [])
        for obj in message.get("description_audit", {}).get("objects", [])
        if obj.get("semantic_context", {}).get("status") == "MISSING"
    ]
    description_contract_issues = [
        {
            "id": message["id"],
            "source_reference": message["source_reference"],
            "object_type": obj["object_type"],
            "object_index": obj["object_index"],
            "status": obj.get("description_contract", {}).get("status", "UNKNOWN"),
            "missing_fragments": obj.get("description_contract", {}).get(
                "missing_fragments", []
            ),
            "traceability_issues": obj.get("description_contract", {}).get(
                "traceability_issues", []
            ),
        }
        for message in report.get("messages", [])
        for obj in message.get("description_audit", {}).get("objects", [])
        if obj.get("description_contract", {}).get("status")
        not in {"COMPLETE", "COMPLETE_LEGACY_CAP_EXPECTED"}
    ]

    return {
        "status": "PASS"
        if not (
            processing_errors
            or intake_errors
            or unexpected_changes
            or unreviewed_losses
            or semantic_context_missing
            or description_contract_issues
        )
        else "FAIL",
        "processing_errors": processing_errors,
        "intake_errors": intake_errors,
        "unexpected_differential_changes": unexpected_changes,
        "baseline_messages_consistent": baseline_messages_consistent,
        "baseline_messages_error": baseline_messages_error,
        "reviewed_component_loss_count": len(losses) - len(unreviewed_loss_keys),
        "unreviewed_component_loss_count": len(unreviewed_loss_keys),
        "semantic_context_missing_count": len(semantic_context_missing),
        "semantic_context_missing": semantic_context_missing,
        "description_contract_issue_count": len(description_contract_issues),
        "description_contract_issues": description_contract_issues,
        "unreviewed_component_losses": [
            {
                "id": message["id"],
                "source_reference": message["source_reference"],
                "missing_geometry_components": message[
                    "missing_geometry_components"
                ],
            }
            for message in unreviewed_losses
        ],
    }


if __name__ == "__main__":
    sys.exit(main_cli())
