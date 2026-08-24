# source_intake/encoding.py
import logging
from typing import Tuple, List, Optional

logger = logging.getLogger(__name__)

try:
    import chardet
    HAS_CHARDET = True
except ImportError:
    HAS_CHARDET = False


DEFAULT_FALLBACK_CHAIN = [
    "utf-8",
    "utf-8-sig",
    "windows-1252",
    "cp1251",
    "iso-8859-2",
    # UTF-16 only attempted after heuristic check
]


class EncodingIntelligence:

    @staticmethod
    def detect_bom(data: bytes) -> Optional[str]:
        if data.startswith(b'\xEF\xBB\xBF'):
            return "utf-8-sig"
        if data.startswith(b'\xFF\xFE'):
            return "utf-16-le"
        if data.startswith(b'\xFE\xFF'):
            return "utf-16-be"
        return None

    @staticmethod
    def is_likely_utf16(data: bytes) -> bool:
        if data.startswith((b'\xFF\xFE', b'\xFE\xFF')):
            return True
        if len(data) < 4:
            return False
        null_ratio = data.count(0) / len(data)
        return null_ratio > 0.15

    @staticmethod
    def detect_encoding(data: bytes) -> Tuple[str, float]:
        bom_enc = EncodingIntelligence.detect_bom(data)
        if bom_enc:
            return bom_enc, 1.0

        if HAS_CHARDET:
            result = chardet.detect(data)
            enc = result.get('encoding')
            conf = result.get('confidence', 0.0)
            if enc and conf > 0.5:
                # Normalize common names
                enc_lower = enc.lower()
                if enc_lower == 'utf-8':
                    return "utf-8", conf
                if enc_lower == 'windows-1252':
                    return "windows-1252", conf
                if enc_lower == 'iso-8859-1':
                    return "latin-1", conf
                return enc, conf

        # Fallback heuristic: try utf-8 strict
        try:
            data.decode('utf-8', errors='strict')
            return "utf-8", 0.9
        except UnicodeDecodeError:
            pass

        return "utf-8", 0.0  # safe default

    @staticmethod
    def decode_with_fallback(
        data: bytes,
        detected_enc: Optional[str] = None,
        confidence: float = 0.0,
        fallback_chain: List[str] = None
    ) -> Tuple[str, str, str, float, bool, int, List[str]]:
        """
        Returns:
            text, used_encoding, detected_encoding, confidence,
            fallback_used, replacement_count, warnings
        """
        if fallback_chain is None:
            fallback_chain = DEFAULT_FALLBACK_CHAIN.copy()

        warnings = []
        replacement_count = 0

        # 1. Try detected encoding with strict
        if detected_enc:
            try:
                text = data.decode(detected_enc, errors='strict')
                return text, detected_enc, detected_enc, confidence, False, 0, warnings
            except UnicodeDecodeError:
                warnings.append(f"strict decode with {detected_enc} failed")

        # 2. Try fallback chain (strict), excluding Latin-1
        for enc in fallback_chain:
            if enc == "latin-1":
                continue
            try:
                text = data.decode(enc, errors='strict')
                return text, enc, detected_enc, 0.5, True, 0, warnings
            except UnicodeDecodeError:
                warnings.append(f"strict decode with {enc} failed")

        # 3. UTF-16 heuristic
        if EncodingIntelligence.is_likely_utf16(data):
            for enc in ("utf-16-le", "utf-16-be"):
                try:
                    text = data.decode(enc, errors='strict')
                    return text, enc, detected_enc, 0.6, True, 0, warnings
                except UnicodeDecodeError:
                    continue

        # 4. Last resort: Latin-1 with replace (never fails)
        text = data.decode('latin-1', errors='replace')
        replacement_count = text.count('\uFFFD')
        if replacement_count:
            warnings.append(f"{replacement_count} replacement characters inserted")
        return text, "latin-1", detected_enc, 0.1, True, replacement_count, warnings