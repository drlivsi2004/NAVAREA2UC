import argparse
import contextlib
import io
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import main
from corpus_runner import discover_sources, review_warning_duplicates
from source_intake import load_source


NAVAREA_PATTERN = re.compile(
    r"(?im)(?=^[ \t]*NAVAREA\s+[A-Z0-9]+\s+\d+/\d+\b)"
)
NAVAREA_HEADER_PATTERN = re.compile(
    r"(?im)^[ \t]*(NAVAREA\s+([A-Z0-9]+)\s+(\d+/\d+))\b"
)
OPERATION_PATTERN = re.compile(
    r"\b(?:EXERCISE|DRILL|FIRING|GUNNERY|MISSILE|WEAPONS?|"
    r"SUBMARINE|MILITARY|NAVAL\s+OPERATION|AIRCRAFT|UNMANNED)\b",
    flags=re.IGNORECASE,
)
AREA_EXPLICIT_PATTERN = re.compile(
    r"\b(?:DANGER\s+)?AREAS?\s+"
    r"(?:BOUND(?:ED)?\s+BY|DELIMITED\s+BY)\b",
    flags=re.IGNORECASE,
)
LINE_EXPLICIT_PATTERN = re.compile(
    r"\b(?:TRACKLINE|LINE\s+JOINING|CENTERLINE\s+COORDINATES|"
    r"NORTH(?:ERN)?\s+OF\s+LINE)\b",
    flags=re.IGNORECASE,
)
SHORE_BOUNDARY_LINE_PATTERN = re.compile(
    r"\bAREAS?\s+BOUND(?:ED)?\s+BY\b[\s\S]{0,800}?"
    r"\bLINE\s+JOINING\b[\s\S]{0,800}?\bAND\s+BY\s+SHORE\b",
    flags=re.IGNORECASE,
)


def discover_source_files(root, include_future_coastal=False):
    return discover_sources(
        root,
        include_future_coastal=include_future_coastal,
    )


def iter_navarea_blocks(path):
    report = load_source(str(path))
    if report.text is None:
        raise AssertionError(f"Could not decode {path}: {report.error}")
    raw_text = report.text
    stats = main.NormalizerStats()
    normalized = main.normalize_input(raw_text, stats)
    for block in NAVAREA_PATTERN.split(normalized):
        block = block.strip()
        if not block:
            continue
        match = NAVAREA_HEADER_PATTERN.search(block)
        if match:
            yield match.group(1), match.group(2), match.group(3), block, stats


def explicit_geometry_kinds(block):
    kinds = []
    route_points = main.extract_explicit_route_waypoints(block)
    line_is_area_boundary = SHORE_BOUNDARY_LINE_PATTERN.search(block)
    if (len(route_points) >= 2 or LINE_EXPLICIT_PATTERN.search(block)) and not line_is_area_boundary:
        kinds.append("line")
    circle_spec = main.extract_circle_spec(block)
    if circle_spec:
        kinds.append("circle")
    is_arc_circle = circle_spec and re.search(
        r"\bARC\s+OF\s+RADIUS\b", block, re.IGNORECASE
    )
    if (
        (AREA_EXPLICIT_PATTERN.search(block) and not is_arc_circle)
        or main.extract_area_group_sections(block)
    ):
        kinds.append("area")
    return kinds


def nav_code(region):
    return region.upper()


def process_source_block(block, navarea_name, region):
    container = main.create_container(nav_code(region))
    partitioned = main.partition_navarea_block(block, navarea_name)
    messages = []
    label_text = main.build_navarea_label(navarea_name)

    for sub_block, meta in partitioned:
        if len(partitioned) == 1 and meta["partition_type"] == "NONE":
            message_id = navarea_name
            process_meta = None
            process_block = block
        else:
            message_id = f"{navarea_name} [{meta['partition_id']}]"
            process_meta = meta
            process_block = sub_block

        message = main.create_message(message_id, metadata=meta)
        container["messages"].append(message)
        main.process_block(
            process_block,
            message,
            container,
            navarea_name,
            label_text=label_text,
            meta=process_meta,
        )
        messages.append(message)

    handlers = [
        stage["handler"]
        for message in messages
        for stage in message.get("stage_diagnostics", [])
        if stage["stage"] == "handler_match" and stage["handler"]
    ]
    diagnostic_codes = [
        diagnostic["code"]
        for message in messages
        for diagnostic in message.get("diagnostics", [])
    ]
    actual_counts = {
        object_type: len(container[object_type])
        for object_type in ("areas", "lines", "circles", "labels")
    }
    rejected_area_count = sum(
        1 for code in diagnostic_codes if code.startswith("GEOMETRY_")
    )
    source_coordinate_count = len(main.extract_coordinates(block))
    explicit_kinds = explicit_geometry_kinds(block)
    has_geometry = any(
        actual_counts[object_type] for object_type in ("areas", "lines", "circles")
    )

    if has_geometry:
        geometry_status = "CONFIRMED"
    elif source_coordinate_count:
        geometry_status = "REFERENCE_ONLY"
    else:
        geometry_status = "UNKNOWN"

    geometry_basis = (
        "EXPLICIT"
        if explicit_kinds
        else "NONE"
        if source_coordinate_count
        else "UNKNOWN"
    )
    operation_only = not has_geometry and bool(OPERATION_PATTERN.search(block))
    operational_group_labels = (
        "LAUNCH OF" in block.upper()
        and "ANCHORAGE LINES" in block.upper()
        and actual_counts["labels"] >= len(main.extract_area_group_sections(block))
    )
    missing_components = [
        kind
        for kind in explicit_kinds
        if actual_counts[f"{kind}s"] == 0
        and not (
            kind == "area"
            and (rejected_area_count or operational_group_labels)
        )
    ]

    return {
        "source_file": None,
        "navarea": navarea_name,
        "region": region,
        "partition_count": len(partitioned),
        "processed_message_count": len(messages),
        "source_coordinate_count": source_coordinate_count,
        "explicit_geometry_kinds": explicit_kinds,
        "multiple_explicit_geometry": len(explicit_kinds) > 1,
        "object_counts": actual_counts,
        "selected_handlers": dict(Counter(handlers)),
        "diagnostic_codes": dict(Counter(diagnostic_codes)),
        "rejected_area_count": rejected_area_count,
        "geometry_status": geometry_status,
        "geometry_basis": geometry_basis,
        "operation_only": operation_only,
        "missing_explicit_components": missing_components,
        "error": None,
    }


def build_corpus_report(root, include_future_coastal=False):
    records = []
    source_files = discover_source_files(root, include_future_coastal)
    normalization_totals = Counter()

    for path in source_files:
        for navarea_name, region, _number, block, stats in iter_navarea_blocks(path):
            normalization_totals.update(
                {
                    key: value
                    for key, value in vars(stats).items()
                    if isinstance(value, int)
                }
            )
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    record = process_source_block(block, navarea_name, region)
            except Exception as error:
                record = {
                    "source_file": path.name,
                    "navarea": navarea_name,
                    "region": region,
                    "partition_count": 0,
                    "processed_message_count": 0,
                    "source_coordinate_count": len(main.extract_coordinates(block)),
                    "explicit_geometry_kinds": explicit_geometry_kinds(block),
                    "multiple_explicit_geometry": False,
                    "object_counts": {
                        "areas": 0,
                        "lines": 0,
                        "circles": 0,
                        "labels": 0,
                    },
                    "selected_handlers": {},
                    "diagnostic_codes": {},
                    "rejected_area_count": 0,
                    "geometry_status": "UNKNOWN",
                    "geometry_basis": "UNKNOWN",
                    "operation_only": False,
                    "missing_explicit_components": [],
                    "error": f"{type(error).__name__}: {error}",
                }
            record["source_file"] = path.name
            records.append(record)

    object_totals = Counter()
    for record in records:
        object_totals.update(record["object_counts"])

    multiple_geometry_records = [
        {
            "source_file": record["source_file"],
            "navarea": record["navarea"],
            "explicit_geometry_kinds": record["explicit_geometry_kinds"],
            "object_counts": record["object_counts"],
            "missing_explicit_components": record["missing_explicit_components"],
        }
        for record in records
        if record["multiple_explicit_geometry"]
    ]
    component_loss_records = [
        {
            "source_file": record["source_file"],
            "navarea": record["navarea"],
            "explicit_geometry_kinds": record["explicit_geometry_kinds"],
            "object_counts": record["object_counts"],
            "missing_explicit_components": record["missing_explicit_components"],
        }
        for record in records
        if record["missing_explicit_components"]
    ]

    duplicate_sources = (
        source_files
        if include_future_coastal
        else discover_source_files(root, include_future_coastal=True)
    )
    return {
        "runner": "NAVAREA corpus differential",
        "runner_version": 1,
        "source_files": [path.name for path in source_files],
        "source_file_count": len(source_files),
        "navarea_block_count": len(records),
        "processed_message_count": sum(
            record["processed_message_count"] for record in records
        ),
        "partition_count": sum(record["partition_count"] for record in records),
        "object_totals": dict(object_totals),
        "geometry_status_counts": dict(
            Counter(record["geometry_status"] for record in records)
        ),
        "geometry_basis_counts": dict(
            Counter(record["geometry_basis"] for record in records)
        ),
        "operation_only_count": sum(record["operation_only"] for record in records),
        "rejected_area_count": sum(
            record["rejected_area_count"] for record in records
        ),
        "multiple_explicit_geometry_count": len(multiple_geometry_records),
        "component_loss_count": len(component_loss_records),
        "error_count": sum(record["error"] is not None for record in records),
        "normalization_totals": dict(normalization_totals),
        "multiple_explicit_geometry": multiple_geometry_records,
        "component_loss_findings": component_loss_records,
        "duplicate_review": review_warning_duplicates(root, duplicate_sources),
        "records": records,
    }


def main_cli():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Workspace root containing NAVAREA*.txt or NAV-*.txt files",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional JSON report path",
    )
    parser.add_argument(
        "--include-future-coastal",
        action="store_true",
        help="Include retained coastal and other regional sources",
    )
    args = parser.parse_args()
    with contextlib.redirect_stdout(io.StringIO()):
        report = build_corpus_report(
            args.root,
            include_future_coastal=args.include_future_coastal,
        )

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "source_file_count",
                    "navarea_block_count",
                    "processed_message_count",
                    "partition_count",
                    "geometry_status_counts",
                    "geometry_basis_counts",
                    "operation_only_count",
                    "rejected_area_count",
                    "multiple_explicit_geometry_count",
                    "component_loss_count",
                    "error_count",
                )
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report["error_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main_cli())