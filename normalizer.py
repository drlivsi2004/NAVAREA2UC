"""
NAVAREA2UC Input Normalization Layer
Version: 1.3.0

Converts raw text from any source (email, website, PDF, NavStation, SafetyNET, etc.)
into canonical maritime text for parsing.

All functions are pure and testable independently.

Architectural Principle:
  Normalizer normalizes representation.
  Parser determines meaning.

Normalizer may:
  - rename
  - canonicalize
  - standardize

Normalizer must not:
  - classify geometry
  - assign object types
  - infer chart objects
"""

import re

METADATA_PATTERNS = [
    "VSVersionInfo",
    "StringFileInfo",
    "VarFileInfo",
    "CompanyName",
    "OriginalFilename",
    "InternalName",
    "ProductName",
    "ProductVersion",
    "FileVersion",
    "NAVAREA2UC.exe",
]


def remove_metadata_blocks(text):
    """
    Удаляет служебные метаданные приложения, которые могут попасть
    в текст при копировании из скомпилированного EXE или логов.
    """
    if not isinstance(text, str):
        return text

    # Если встречается VSVersionInfo — обрезаем всё с этого места.
    if "VSVersionInfo" in text:
        text = text.split("VSVersionInfo")[0].rstrip()

    # Дополнительно удаляем одиночные строки, содержащие метаданные.
    for pattern in METADATA_PATTERNS:
        text = re.sub(
            r"^.*" + re.escape(pattern) + r".*$",
            "",
            text,
            flags=re.MULTILINE,
        )

    # Убираем возможные пустые строки, оставшиеся после удаления.
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


class NormalizerStats:
    """Collects diagnostic statistics during normalization."""

    def __init__(self):
        self.coordinates_converted = 0
        self.area_markers_normalized = 0
        self.headers_normalized = 0
        self.whitespace_fixes = 0
        self.pdf_artifacts_removed = 0

    def report(self):
        print("\nNORMALIZER REPORT")
        print(f"Headers normalized: {self.headers_normalized}")
        print(f"Coordinates converted: {self.coordinates_converted}")
        print(f"Area markers normalized: {self.area_markers_normalized}")
        print(f"Whitespace fixes: {self.whitespace_fixes}")
        print(f"PDF artifacts removed: {self.pdf_artifacts_removed}")


PHRASE_NORMALIZATIONS = [
    (r"AREA\s+BOUND\s+BY", "AREA BOUND BY"),
    (r"AREA\s+BOUNDED\s+BY", "AREA BOUNDED BY"),
    (r"AREAS\s+BOUND\s+BY", "AREAS BOUND BY"),
    (r"AREAS\s+BOUNDED\s+BY", "AREAS BOUNDED BY"),
    (r"AREA\s+BOUNDED\s+WITHIN", "AREA BOUNDED WITHIN"),
    (r"ALONG\s+TRACKLINE", "ALONG TRACKLINE"),
    (r"TRACKLINE\s+JOINING", "TRACKLINE JOINING"),
]


def normalize_navarea_phrases(text):
    """
    Объединяет разорванные переносами строк NAVAREA-фразы.
    Используется whitelist для сохранения структуры.
    """
    for pattern, replacement in PHRASE_NORMALIZATIONS:
        text = re.sub(
            pattern,
            lambda m: " ".join(m.group(0).split()),
            text,
            flags=re.IGNORECASE,
        )
    return text


def normalize_input(text, stats=None):
    if stats is None:
        stats = NormalizerStats()

    text = normalize_line_endings(text)
    text = normalize_whitespace(text, stats)
    text = normalize_pdf_artifacts(text, stats)
    text = normalize_headers(text, stats)
    text = normalize_area_phrases(text)
    text = normalize_semantic_aliases(text)
    text = normalize_coordinates(text, stats)
    text = normalize_riglist_formats(text)
    text = normalize_sections(text, stats)
    text = normalize_whitespace(text, stats)
    text = normalize_navarea_phrases(text)
    text = remove_metadata_blocks(text)
    return text


# ----------------------------------------------------------------------
# STRUCTURE NORMALIZATION
# ----------------------------------------------------------------------


def normalize_line_endings(text):
    """Unify line endings to LF."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def normalize_whitespace(text, stats=None):
    """
    Collapse multiple spaces, remove trailing spaces, reduce empty lines.
    """
    lines = []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped:
            compressed = re.sub(r"[ ]{2,}", " ", stripped)
            if stats and compressed != stripped:
                stats.whitespace_fixes += 1
            lines.append(compressed)
        else:
            lines.append("")
    result = "\n".join(lines)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result


def normalize_headers(text, stats=None):
    """
    Normalize NAVAREA headers: ensure a single space between NAVAREA, area code, and number.
    Examples:
      Navarea III - Spain 122/26 -> NAVAREA III 122/26
      NAVAREA IV998/26  -> NAVAREA IV 998/26
      NAVAREA XII998/26 -> NAVAREA XII 998/26
      NAVAREA IV 998/26 -> already correct
    """

    def fix_header(m):
        if stats:
            stats.headers_normalized += 1
        roman = m.group(1)
        number = m.group(2)
        return f"NAVAREA {roman} {number}"

    # Case: descriptive source label between the area code and warning number.
    # Keep this line-anchored so cancellation references in message bodies are
    # never promoted to headers.
    text = re.sub(
        r"(?im)^[ \t]*NAVAREA\s+([A-Z0-9]+)\s*-\s*[^0-9\n]*?(\d+/\d+)\b",
        fix_header,
        text,
    )
    # Case: NAVAREA IV998/26 (no space between area and number)
    text = re.sub(r"NAVAREA\s*([A-Z]+)(\d+/\d+)", fix_header, text, flags=re.I)
    # Case: NAVAREA  IV  998/26 (multiple spaces)
    text = re.sub(
        r"NAVAREA\s{2,}([A-Z]+)\s+(\d+/\d+)", r"NAVAREA \1 \2", text, flags=re.I
    )
    return text


def normalize_pdf_artifacts(text, stats=None):
    """
    Remove common PDF extraction artifacts:
    - line breaks inside words (hyphenation)
    - stray characters
    - page numbers
    """
    # Remove soft hyphens at line breaks (e.g., "nav- igation" -> "navigation")
    text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)
    # Remove page numbers or header/footer lines that contain only numbers.
    # Keep a degree-only line when the next line contains coordinate minutes
    # and a hemisphere; some NAVAREA sources wrap "43 05.03 N" after the
    # degree value.
    text = re.sub(
        r"(?m)^\s*\d+\s*(?!\n\s*\d{1,2}(?:[.,]\d+)?\s*[NS]\b)"
        r"(?!\n\s*\d{1,2}(?:[.,]\d+)?\s*[EW]\b)$",
        "",
        text,
    )
    if stats:
        stats.pdf_artifacts_removed = len(re.findall(r"-\s*\n", text))
    return text


def normalize_area_phrases(text):
    """
    Normalize common area boundary phrases.
    "AREA BOUNDED BY" -> "AREA BOUND BY"
    "AREAS BOUNDED BY" -> "AREAS BOUND BY"
    "AREA DELIMITED BY" -> "AREA BOUND BY"
    "AREAS DELIMITED BY" -> "AREAS BOUND BY"
    """
    text = re.sub(r"AREA\s+BOUNDED\s+BY", "AREA BOUND BY", text, flags=re.I)
    text = re.sub(r"AREAS\s+BOUNDED\s+BY", "AREAS BOUND BY", text, flags=re.I)

    # Добавлено для поддержки AREA DELIMITED BY
    text = re.sub(r"AREA\s+DELIMITED\s+BY", "AREA BOUND BY", text, flags=re.I)
    text = re.sub(r"AREAS\s+DELIMITED\s+BY", "AREAS BOUND BY", text, flags=re.I)

    return text


def normalize_sections(text, stats=None):
    """
    Convert all multi-area identifiers to canonical (A), (B), (C) style.
    Supports:
      - A.
      - A
      - (A)
    """
    # A. -> (A)
    text = re.sub(r"(?m)^\s*([A-Z])\.\s*", r"(\1) ", text)
    # Standalone letter on its own line -> (A)
    text = re.sub(r"(?m)^\s*([A-Z])\s*$", r"(\1)", text)
    if stats:
        stats.area_markers_normalized += len(re.findall(r"\([A-Z]\)", text))
    return text


# ----------------------------------------------------------------------
# SEMANTIC NORMALIZATION (terminology only)
# ----------------------------------------------------------------------


def normalize_semantic_aliases(text):
    """
    Convert semantic equivalents to canonical terminology.

    Normalizer does NOT classify geometry.
    It only standardises terms.
    Geometry decisions remain with parser handlers.
    """
    # Terminal / port instructions
    text = re.sub(r"(?i)WAITING\s+PSN", "WAITING POSITION", text)
    text = re.sub(r"(?i)WAIT\s+PSN", "WAITING POSITION", text)

    # Drift areas
    text = re.sub(r"(?i)DRIFT\s+AREA", "DRIFTING AREA", text)

    # Anchorage areas
    text = re.sub(r"(?i)ANCHORAGE\s+AREA", "ANCHORAGE AREA", text)

    # Pilot boarding
    text = re.sub(r"(?i)PILOT\s+BOARDING\s+POSITION", "PILOT BOARDING", text)
    text = re.sub(r"(?i)PILOT\s+BOARDING\s+AREA", "PILOT BOARDING", text)

    # Buoy groups (terminology, not geometry classification)
    text = re.sub(r"(?i)CHANNEL\s+BUOYS", "BUOY GROUP", text)
    text = re.sub(r"(?i)BUOY\s+LIST", "BUOY GROUP", text)
    text = re.sub(r"(?i)CHANNEL\s+MARKING\s+BUOYS", "BUOY GROUP", text)

    # Add more aliases as needed, always preserving semantic meaning.
    return text

    # ----------------------------------------------------------------------
    # GEOMETRY NORMALIZATION (coordinate formats only)
    # ----------------------------------------------------------------------


def normalize_coordinates(text, stats=None):
    """
    Convert all coordinate formats to canonical: dd-mm.mmN and dd-mm.mmE.
    Now supports:
      - DMS with double hyphens: 12-02-49.5S -> 12-02.825S
      - DM without separator: 5218.60S -> 52-18.60S
      - Trailing punctuation: 53-18.88S. -> 53-18.88S
      - Remove L- and G- prefixes
      - Remove LAT. and LONG. labels
    """
    if stats is None:
        stats = NormalizerStats()

    # Replace decimal comma with dot
    text = re.sub(r"(\d),(\d)", r"\1.\2", text)

    # Remove degree, minute, second symbols
    text = re.sub(r"°", " ", text)
    text = re.sub(r"'", " ", text)
    text = re.sub(r'"', " ", text)

    # ------------------------------------------------------------------
    # 0. Remove coordinate prefixes and labels
    #    (added for NAVAREA XV compatibility)
    # ------------------------------------------------------------------
    text = re.sub(r"\b[LG]-[ \t]*(\d)", r"\1", text, flags=re.I)
    text = re.sub(r"\bLAT\.?(?=\s|$)\s*", "", text, flags=re.I)
    text = re.sub(r"\bLONG\.?(?=\s|$)\s*", "", text, flags=re.I)
    text = re.sub(r"\bL[ \t]*(\d)", r"\1", text, flags=re.I)
    text = re.sub(r"\bG[ \t]*(\d)", r"\1", text, flags=re.I)

    # ------------------------------------------------------------------
    # 1. Convert DMS with double hyphens: 12-02-49.5S
    # ------------------------------------------------------------------
    def dms_double_hyphen_to_dm(match):
        deg = match.group(1)
        minutes_str = match.group(2)
        sec_str = match.group(3)
        hemi = match.group(4).upper()
        minutes = float(minutes_str.replace(",", "."))
        sec = float(sec_str.replace(",", "."))
        total_minutes = minutes + sec / 60.0
        if stats:
            stats.coordinates_converted += 1
        return f"{deg}-{total_minutes:.3f}{hemi}"

    text = re.sub(
        r"(?<![A-Za-z0-9])(\d{1,3})-(\d{1,2})-([\d.]+)\s*([NS])",
        dms_double_hyphen_to_dm,
        text,
        flags=re.I,
    )
    text = re.sub(
        r"(?<![A-Za-z0-9])(\d{1,3})-(\d{1,2})-([\d.]+)\s*([EW])",
        dms_double_hyphen_to_dm,
        text,
        flags=re.I,
    )

    # ------------------------------------------------------------------
    # 2. Convert DM without separator: 5218.60S -> 52-18.60S
    # ------------------------------------------------------------------
    def dm_no_separator_to_dm(match):
        deg = match.group(1)
        minutes = match.group(2)
        hemi = match.group(3).upper()
        if stats:
            stats.coordinates_converted += 1
        return f"{deg}-{minutes}{hemi}"

    text = re.sub(
        r"(?<![A-Za-z0-9])(\d{1,2})(\d{2}\.\d+)\s*([NS])",
        dm_no_separator_to_dm,
        text,
        flags=re.I,
    )
    text = re.sub(
        r"(?<![A-Za-z0-9])(\d{1,3})(\d{2}\.\d+)\s*([EW])",
        dm_no_separator_to_dm,
        text,
        flags=re.I,
    )

    # ------------------------------------------------------------------
    # 3. Remove trailing punctuation after hemisphere
    # ------------------------------------------------------------------
    # Require a digit immediately before the hemisphere.  Without this
    # guard, an RIGLIST marker such as "E." is mistaken for a coordinate
    # hemisphere and its marker dot is removed before list normalization.
    text = re.sub(r"(?<=\d)([NS])\s*[.,;:]+", r"\1", text, flags=re.I)
    text = re.sub(r"(?<=\d)([EW])\s*[.,;:]+", r"\1", text, flags=re.I)

    # ------------------------------------------------------------------
    # 4. Existing: Convert DMS with spaces to DM
    # ------------------------------------------------------------------
    def dms_to_dm(match):
        deg = match.group(1)
        minutes_str = match.group(2)
        sec_str = match.group(3)
        hemi = match.group(4).upper()
        sec = float(sec_str.replace(",", "."))
        minutes = float(minutes_str.replace(",", "."))
        total_minutes = minutes + sec / 60.0
        if stats:
            stats.coordinates_converted += 1
        return f"{deg}-{total_minutes:.3f}{hemi}"

    text = re.sub(
        r"(?<![A-Za-z0-9])(\d{1,3})\s+(\d{1,2})\s+([\d.]+)\s*([NS])",
        dms_to_dm,
        text,
        flags=re.I,
    )
    text = re.sub(
        r"(?<![A-Za-z0-9])(\d{1,3})\s+(\d{1,2})\s+([\d.]+)\s*([EW])",
        dms_to_dm,
        text,
        flags=re.I,
    )

    # Convert DM with spaces to hyphen
    text = re.sub(r"(\d{1,3})\s+([\d.]+)\s*([NS])", r"\1-\2\3", text, flags=re.I)
    text = re.sub(r"(\d{1,3})\s+([\d.]+)\s*([EW])", r"\1-\2\3", text, flags=re.I)

    # Remove extra spaces between hyphen, minutes, hemisphere
    text = re.sub(r"(\d)-([\d.]+)\s*([NS])", r"\1-\2\3", text, flags=re.I)
    text = re.sub(r"(\d)-([\d.]+)\s*([EW])", r"\1-\2\3", text, flags=re.I)

    # Replace separators between lat/lon with space
    text = re.sub(r"([NS])\s*[/;,\-]\s*(\d)", r"\1 \2", text, flags=re.I)
    text = re.sub(r"([EW])\s*[/;,\-]\s*(\d)", r"\1 \2", text, flags=re.I)

    return text


def normalize_riglist_formats(text):
    """
    Находит блоки RIGLIST/MODU и преобразует буквенные маркеры (A., B., AA., AAAA.)
    в цифровые (1., 2., …). Поддерживает записи с переносами строк.
    """
    # Разбиваем по NAVAREA блокам, чтобы не затрагивать другие части
    blocks = re.split(
        r"(?im)(?=^[ \t]*NAVAREA\s+[A-Z0-9]+\s+\d+/\d+\b)",
        text,
    )
    new_blocks = []

    for block in blocks:
        if re.search(r"RIG\s*LIST|MODU\s*LIST|MOBILE\s+OFFSHORE", block, re.IGNORECASE):
            lines = block.split("\n")
            # Проверяем наличие буквенных маркеров (A., B., ..., AA., AAAA.)
            has_lettered = False
            for line in lines:
                if re.match(r"^\s*[A-Z]{1,4}\.(?:\s+|$)", line):
                    has_lettered = True
                    break

            if has_lettered:
                counter = 1
                new_lines = []
                i = 0
                while i < len(lines):
                    line = lines[i]
                    # Если строка начинается с буквенного маркера
                    m = re.match(r"^\s*([A-Z]{1,4})\.\s*(.*)$", line)
                    if m:
                        # Остаток строки (может быть пустым, если имя на следующей строке)
                        remainder = m.group(2).strip()
                        # Собираем полную запись: если в remainder нет координат,
                        # добавляем следующие строки, пока не встретим координаты или новый маркер
                        full_entry = remainder
                        j = i + 1
                        while j < len(lines):
                            next_line = lines[j].strip()
                            # Если следующая строка начинается с маркера – останавливаемся
                            if re.match(r"^[A-Z]{1,4}\.(?:\s+|$)", next_line):
                                break
                            # Если в next_line есть координаты – добавляем и выходим
                            if re.search(r"\d{1,3}-\d+\.\d+[NS]", next_line):
                                full_entry += " " + next_line
                                j += 1
                                break
                            # Если next_line не пустая и не координаты – это часть имени
                            if next_line:
                                full_entry += " " + next_line
                            j += 1
                        # Заменяем маркер на номер
                        new_line = f"{counter}. {full_entry}".strip()
                        new_lines.append(new_line)
                        i = j  # пропускаем обработанные строки
                        counter += 1
                    else:
                        # Строка не начинается с маркера – оставляем как есть
                        new_lines.append(line)
                        i += 1
                block = "\n".join(new_lines)
        new_blocks.append(block)

    return "\n".join(new_blocks)
