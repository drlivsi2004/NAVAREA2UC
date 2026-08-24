# source_intake/models.py
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, Any, List, Optional


class SourceType(Enum):
    FILE = auto()
    EMAIL = auto()
    PDF = auto()
    WEB = auto()
    CLIPBOARD = auto()
    NAVSTATION = auto()
    SAFETYNET = auto()
    OTHER = auto()


class Status(Enum):
    SUCCESS = "SUCCESS"
    FALLBACK = "FALLBACK"
    FAILED = "FAILED"


@dataclass
class SourceDescriptor:
    id: str
    source_type: SourceType
    original_size: int
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IntakeReport:
    descriptor: SourceDescriptor
    status: Status
    encoding: str                     # used_encoding (final)
    detected_encoding: str            # encoding detected before fallback
    confidence: float
    replacement_count: int            # number of replacement chars inserted
    text: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    error: Optional[str] = None
    fallback_used: bool = False