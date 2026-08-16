import re

import main_backup


def _build_container_and_message():
    container = main_backup.create_container('NAVAREA_TEST')
    message = main_backup.create_message('NAVAREA_TEST')
    return container, message


def test_standalone_letter_area_format_is_split():
    block = '''AREA BOUNDED BY:

A
46-04.0N 033-12.8E
46-05.0N 033-13.0E
46-05.8N 033-12.0E
46-04.9N 033-11.0E
46-04.0N 033-12.8E

B
46-06.4N 032-05.4E
46-07.0N 032-06.0E
46-06.6N 032-06.8E
46-06.4N 032-05.4E

C
46-09.0N 031-18.7E
46-09.6N 031-19.5E
46-10.1N 031-18.0E
46-09.8N 031-17.2E
46-09.0N 031-18.7E
'''
    groups = main_backup.extract_area_group_sections(block)
    assert len(groups) == 3
    assert [g[0] for g in groups] == ['A', 'B', 'C']
    assert [len(main_backup.extract_coordinates(g[1])) for g in groups] == [5, 4, 5]


def test_inline_lettered_areas_still_work():
    block = '''AREA BOUNDED BY:
(A) 46-01.0N 030-01.0E 46-02.0N 030-02.0E 46-01.5N 030-03.0E
(B) 46-03.0N 030-04.0E 46-04.0N 030-03.0E 46-03.5N 030-02.0E
(C) 46-05.0N 030-05.0E 46-06.0N 030-06.0E 46-05.5N 030-04.0E
'''
    groups = main_backup.extract_area_group_sections(block)
    assert len(groups) == 3
    assert [g[0] for g in groups] == ['A', 'B', 'C']


def test_letter_dot_format_still_work():
    block = '''AREA BOUNDED BY:
A. 46-01.0N 030-01.0E 46-02.0N 030-02.0E 46-01.5N 030-03.0E
B. 46-03.0N 030-04.0E 46-04.0N 030-03.0E 46-03.5N 030-02.0E
C. 46-05.0N 030-05.0E 46-06.0N 030-06.0E 46-05.5N 030-04.0E
'''
    groups = main_backup.extract_area_group_sections(block)
    assert len(groups) == 3
    assert [g[0] for g in groups] == ['A', 'B', 'C']


def test_handle_area_generates_separate_objects_for_standalone_letters():
    block = '''AREA BOUNDED BY:

A
46-04.0N 033-12.8E
46-05.0N 033-13.0E
46-05.8N 033-12.0E
46-04.9N 033-11.0E
46-04.0N 033-12.8E

B
46-06.4N 032-05.4E
46-07.0N 032-06.0E
46-06.6N 032-06.8E
46-06.4N 032-05.4E
'''
    container, message = _build_container_and_message()
    ctx = main_backup.build_processing_context(block, 'NAVAREA III 92/22')
    matched = main_backup.handle_area(ctx, container, message)
    assert matched is True
    assert len(message['areas']) == 2
    assert [obj['name'] for obj in message['areas']] == ['NAV III 92/22 (A)', 'NAV III 92/22 (B)']
