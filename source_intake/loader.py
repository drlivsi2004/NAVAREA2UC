# source_intake/loader.py
import os
import logging
from typing import List, Optional, Union

from .models import SourceType, Status, SourceDescriptor, IntakeReport
from .encoding import EncodingIntelligence

logger = logging.getLogger(__name__)


def _create_report_for_data(
    data: bytes,
    source_id: str,
    source_type: SourceType,
    metadata: Optional[dict] = None
) -> IntakeReport:
    if metadata is None:
        metadata = {}

    detected_enc, confidence = EncodingIntelligence.detect_encoding(data)

    try:
        (
            text,
            used_enc,
            detected_enc_final,
            final_conf,
            fallback_used,
            replacement_count,
            warnings
        ) = EncodingIntelligence.decode_with_fallback(
            data, detected_enc, confidence
        )
        status = Status.SUCCESS if not fallback_used else Status.FALLBACK
        error = None
    except Exception as e:
        # Should not happen (Latin-1 always succeeds), but defensive
        status = Status.FAILED
        text = None
        used_enc = "unknown"
        detected_enc_final = detected_enc or "unknown"
        final_conf = 0.0
        replacement_count = 0
        warnings = [str(e)]
        error = str(e)

    descriptor = SourceDescriptor(
        id=source_id,
        source_type=source_type,
        original_size=len(data),
        metadata=metadata
    )

    return IntakeReport(
        descriptor=descriptor,
        status=status,
        encoding=used_enc,
        detected_encoding=detected_enc_final,
        confidence=final_conf,
        replacement_count=replacement_count,
        text=text,
        warnings=warnings,
        error=error,
        fallback_used=fallback_used
    )


def decode_source(
    data: bytes,
    source_id: Optional[str] = None,
    source_type: SourceType = SourceType.FILE,
    metadata: Optional[dict] = None
) -> IntakeReport:
    if source_id is None:
        source_id = f"source_{id(data)}"
    return _create_report_for_data(data, source_id, source_type, metadata)


def load_source(
    path: str,
    source_type: SourceType = SourceType.FILE,
    metadata: Optional[dict] = None
) -> IntakeReport:
    try:
        with open(path, 'rb') as f:
            data = f.read()
    except Exception as e:
        descriptor = SourceDescriptor(
            id=path,
            source_type=source_type,
            original_size=0,
            metadata=metadata or {}
        )
        return IntakeReport(
            descriptor=descriptor,
            status=Status.FAILED,
            encoding="unknown",
            detected_encoding="unknown",
            confidence=0.0,
            replacement_count=0,
            text=None,
            warnings=[],
            error=str(e),
            fallback_used=False
        )

    return _create_report_for_data(data, path, source_type, metadata)


def load_sources(
    sources: List[Union[str, bytes]],
    source_type: SourceType = SourceType.FILE,
) -> List[IntakeReport]:
    reports = []
    for src in sources:
        if isinstance(src, bytes):
            reports.append(decode_source(src, source_type=source_type))
        elif isinstance(src, str):
            reports.append(load_source(src, source_type=source_type))
        else:
            descriptor = SourceDescriptor(
                id=str(src),
                source_type=SourceType.OTHER,
                original_size=0
            )
            reports.append(IntakeReport(
                descriptor=descriptor,
                status=Status.FAILED,
                encoding="unknown",
                detected_encoding="unknown",
                confidence=0.0,
                replacement_count=0,
                text=None,
                warnings=[],
                error=f"Unsupported source type: {type(src)}",
                fallback_used=False
            ))
    return reports


def combine_texts(reports: List[IntakeReport]) -> str:
    texts = []
    for r in reports:
        if r.status in (Status.SUCCESS, Status.FALLBACK) and r.text is not None:
            texts.append(r.text)
    return "\n".join(texts)


def report_summary(reports: List[IntakeReport]) -> str:
    lines = ["[INTAKE SUMMARY]"]
    for r in reports:
        status = r.status.value
        if r.status == Status.FAILED:
            lines.append(f"  {r.descriptor.id}: {status} - {r.error}")
        else:
            fb = " (fallback)" if r.fallback_used else ""
            lines.append(
                f"  {r.descriptor.id}: {status}{fb} "
                f"(used={r.encoding}, detected={r.detected_encoding}, "
                f"conf={r.confidence:.2f}, replacements={r.replacement_count})"
            )
            if r.warnings:
                for w in r.warnings:
                    lines.append(f"    warning: {w}")
    return "\n".join(lines)