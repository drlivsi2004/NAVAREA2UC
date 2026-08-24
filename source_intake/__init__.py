# source_intake/__init__.py
from .models import SourceType, Status, SourceDescriptor, IntakeReport
from .loader import (
    decode_source,
    load_source,
    load_sources,
    combine_texts,
    report_summary
)

__all__ = [
    "SourceType",
    "Status",
    "SourceDescriptor",
    "IntakeReport",
    "decode_source",
    "load_source",
    "load_sources",
    "combine_texts",
    "report_summary"
]