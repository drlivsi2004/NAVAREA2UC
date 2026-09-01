# source_intake/encoding.py
import logging
from typing import Tuple, List, Optional

logger = logging.getLogger(__name__)

# A strict fallback candidate is usable at this boundary, but it must remain
# visible to callers as a reviewable warning.  Values below it are never
# accepted as decoded source text.
MIN_DECODING_CONFIDENCE = 0.50
FALLBACK_DECODING_CONFIDENCE = MIN_DECODING_CONFIDENCE


class EncodingDecodeError(UnicodeError):
    """Raised when source bytes cannot be decoded safely."""

    def __init__(self, message: str, warnings: Optional[List[str]] = None):
        super().__init__(message)
        self.warnings = list(warnings or [])


class LowConfidenceEncodingError(EncodingDecodeError):
    """Raised when decoding would require a confidence below the policy floor."""


class AmbiguousEncodingError(EncodingDecodeError):
    """Raised when fallback bytes do not provide enough text evidence."""


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
    def detect_utf16_without_bom(data: bytes) -> Optional[str]:
        """Infer UTF-16 byte order from a strong alternating-NUL pattern."""
        if len(data) < 4:
            return None

        even_bytes = data[0::2]
        odd_bytes = data[1::2]
        even_null_ratio = even_bytes.count(0) / len(even_bytes)
        odd_null_ratio = odd_bytes.count(0) / len(odd_bytes)

        if odd_null_ratio >= 0.30 and odd_null_ratio - even_null_ratio >= 0.20:
            return "utf-16-le"
        if even_null_ratio >= 0.30 and even_null_ratio - odd_null_ratio >= 0.20:
            return "utf-16-be"
        return None

    @staticmethod
    def is_plausible_fallback_text(data: bytes, text: str) -> bool:
        """Reject tiny or binary-looking results from broad single-byte codecs."""
        if not text.strip():
            return False

        control_count = sum(
            1
            for char in text
            if ord(char) < 32 and char not in "\t\n\r\f"
        )
        if control_count > max(1, len(text) // 10):
            return False

        has_non_ascii = any(byte >= 128 for byte in data)
        meaningful_count = sum(
            1 for char in text if not char.isspace() and ord(char) >= 32
        )
        if has_non_ascii and (
            meaningful_count < 4
            or not any(char.isascii() and char.isalnum() for char in text)
        ):
            return False
        return True

    @staticmethod
    def detect_encoding(data: bytes) -> Tuple[str, float]:
        bom_enc = EncodingIntelligence.detect_bom(data)
        if bom_enc:
            return bom_enc, 1.0

        utf16_enc = EncodingIntelligence.detect_utf16_without_bom(data)
        if utf16_enc:
            return utf16_enc, 0.8

        if HAS_CHARDET:
            result = chardet.detect(data)
            enc = result.get('encoding')
            conf = result.get('confidence', 0.0)
            if enc:
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
        bom_enc = EncodingIntelligence.detect_bom(data)
        likely_utf16 = EncodingIntelligence.is_likely_utf16(data)

        # 1. Try detected encoding with strict
        if detected_enc:
            try:
                text = data.decode(detected_enc, errors='strict')
                if confidence < MIN_DECODING_CONFIDENCE:
                    warning = (
                        f"low-confidence encoding detection ({confidence:.2f} < "
                        f"{MIN_DECODING_CONFIDENCE:.2f}) for {detected_enc}; "
                        "source was not imported"
                    )
                    warnings.append(warning)
                    raise LowConfidenceEncodingError(
                        warning, warnings
                    )
                return text, detected_enc, detected_enc, confidence, False, 0, warnings
            except (UnicodeDecodeError, LookupError) as error:
                warnings.append(f"strict decode with {detected_enc} failed")
                if bom_enc == detected_enc:
                    warning = (
                        f"source has a {bom_enc} BOM but strict decoding failed; "
                        "source was not imported"
                    )
                    warnings.append(warning)
                    raise EncodingDecodeError(warning, warnings) from error

        # A likely UTF-16 source must not be reinterpreted as a single-byte
        # encoding if its strict decoders fail.  Otherwise arbitrary bytes
        # containing NULs can become plausible-looking text.
        if likely_utf16:
            for enc in ("utf-16-le", "utf-16-be"):
                try:
                    text = data.decode(enc, errors='strict')
                    if not EncodingIntelligence.is_plausible_fallback_text(
                        data, text
                    ):
                        warnings.append(
                            f"strict decode with {enc} produced ambiguous text"
                        )
                        continue
                    warning = (
                        f"fallback decoding selected {enc} at confidence "
                        f"{FALLBACK_DECODING_CONFIDENCE:.2f}; verify the source "
                        "encoding before processing"
                    )
                    warnings.append(warning)
                    return (
                        text,
                        enc,
                        detected_enc,
                        FALLBACK_DECODING_CONFIDENCE,
                        True,
                        0,
                        warnings,
                    )
                except (UnicodeDecodeError, LookupError):
                    warnings.append(f"strict decode with {enc} failed")

            warning = (
                "source resembles UTF-16 but no strict UTF-16 decoder "
                "succeeded; source was not imported"
            )
            warnings.append(warning)
            raise AmbiguousEncodingError(warning, warnings)

        # 2. Try fallback chain (strict), excluding Latin-1
        for enc in fallback_chain:
            if enc == "latin-1":
                continue
            try:
                text = data.decode(enc, errors='strict')
                if not EncodingIntelligence.is_plausible_fallback_text(data, text):
                    warnings.append(
                        f"strict decode with {enc} produced ambiguous text"
                    )
                    continue
                warning = (
                    f"fallback decoding selected {enc} at confidence "
                    f"{FALLBACK_DECODING_CONFIDENCE:.2f}; verify the source "
                    "encoding before processing"
                )
                warnings.append(warning)
                return (
                    text,
                    enc,
                    detected_enc,
                    FALLBACK_DECODING_CONFIDENCE,
                    True,
                    0,
                    warnings,
                )
            except (UnicodeDecodeError, LookupError):
                warnings.append(f"strict decode with {enc} failed")

        # Latin-1 can decode every byte and therefore cannot establish that
        # the source is text.  Refuse instead of silently importing it.
        warning = (
            "no strict decoder produced unambiguous text at the minimum "
            "confidence threshold "
            f"({MIN_DECODING_CONFIDENCE:.2f}); source was not imported"
        )
        warnings.append(warning)
        raise AmbiguousEncodingError(warning, warnings)