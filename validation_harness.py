import os
import glob
import re

# Импорт текущего парсера
import main as p


TEST_DIR = "tests"

REQUIRED = [
    "NAV III 92/22",
    "NAV IV 755/2026",
    "NAV IV 776/2026",
    "NAV VIII 814/26",
    "NAV VIII 823/26",
    "NAV VIII 850/26",
    "NAV VIII 808/26",
    "NAV VIII 809/26",
]


def find_message_file():
    for f in glob.glob(os.path.join(TEST_DIR, "*.txt")):
        yield f


def main():
    for f in find_message_file():
        with open(f, encoding="utf-8") as fh:
            raw = fh.read()

        normalized = p.normalize_input(raw, p.NormalizerStats())

        blocks = re.split(
            r'(?=NAVAREA\s+[A-ZIVXLC]+\s+\d+/\d+)',
            normalized,
            flags=re.IGNORECASE
        )

        for block in blocks:
            block = block.strip()
            if not block:
                continue

            nav_match = re.search(
                r'(NAVAREA\s+[A-ZIVXLC]+\s+\d+/\d+)',
                block,
                re.IGNORECASE
            )
            if not nav_match:
                continue

            navarea_name = nav_match.group(1)

            # Пропускаем только целевые сообщения
            if not any(req in navarea_name for req in REQUIRED):
                continue

            print(f"\n===== {navarea_name} =====")

            # Проверяем grouped parsing напрямую
            groups = p.extract_area_group_sections(block)

            print(f"groups returned      : {len(groups)}")
            for letter, text in groups:
                coords = p.extract_coordinates(text)
                print(f"  group {letter}: {len(coords)} coords")

            # Прогоняем полный контейнер через handle_area
            container = p.create_container("TEST")
            message = p.create_message(navarea_name)
            ctx = p.build_processing_context(block, navarea_name)
            handled = p.handle_area(ctx, container, message)

            print(f"handle_area result   : {handled}")
            print(f"areas created        : {len(message.get('areas', []))}")
            print(f"labels created       : {len(message.get('labels', []))}")
            print(f"lines created        : {len(message.get('lines', []))}")


if __name__ == "__main__":
    main()