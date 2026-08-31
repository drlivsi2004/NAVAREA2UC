# source_intake/__init__.py
from .models import SourceType, Status, SourceDescriptor, IntakeReport
from .encoding import (
    AmbiguousEncodingError,
    EncodingDecodeError,
    LowConfidenceEncodingError,
    MIN_DECODING_CONFIDENCE,
)
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
    "AmbiguousEncodingError",
    "EncodingDecodeError",
    "LowConfidenceEncodingError",
    "MIN_DECODING_CONFIDENCE",
    "decode_source",
    "load_source",
    "load_sources",
    "combine_texts",
    "report_summary"
]