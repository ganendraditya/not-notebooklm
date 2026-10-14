import sqlite3
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile
import xml.etree.ElementTree as ET

import journal_indexer
import pytest
from services.search import scopus_compiler
from services.search.scopus_compiler import _compile_index
from services.search.scopus_source_list import parse_scopus_source_list


MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def _column_name(index):
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _worksheet_xml(rows):
    root = ET.Element(f"{{{MAIN_NS}}}worksheet")
    sheet_data = ET.SubElement(root, f"{{{MAIN_NS}}}sheetData")
    for row_index, values in enumerate(rows, start=1):
        row = ET.SubElement(sheet_data, f"{{{MAIN_NS}}}row", {"r": str(row_index)})
        for column_index, value in enumerate(values, start=1):
            if value is None or value == "":
                continue
            cell = ET.SubElement(
                row,
                f"{{{MAIN_NS}}}c",
                {"r": f"{_column_name(column_index)}{row_index}", "t": "inlineStr"},
            )
            inline = ET.SubElement(cell, f"{{{MAIN_NS}}}is")
            ET.SubElement(inline, f"{{{MAIN_NS}}}t").text = str(value)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _source_workbook():
    source_headers = [
        "Sourcerecord ID",
        "Source Title",
        "ISSN",
        "EISSN",
        "Active or Inactive",
        "Coverage",
        "Titles Discontinued by Scopus",
        None,
        None,
        None,
        None,
        None,
        "Source Type",
    ]
    source_rows = [
        source_headers,
        ["1001", "Active Older Coverage Journal", "1000-0001", "1000-0002", "Active", "2001-2012", None, None, None, None, None, None, "Journal"],
        ["1002", "Discontinued Journal", "1000-0003", None, "Inactive", "2010-2025", "Discontinued by Scopus", None, None, None, None, None, "Journal"],
        ["1003", "Inactive Journal", "1000-0004", None, "Inactive", "1950-2000", None, None, None, None, None, None, "Journal"],
    ]
    discontinued_rows = [
        ["Status: September 2026"],
        ["Source record ID", "Source Title (newly added titles are highlighted in red)", "ISSN", "EISSN", "Publisher", "Indexation Change", "Year"],
        ["1002", "Discontinued Journal", "1000-0003", "", "Publisher", "Discontinuation", "2025"],
    ]

    workbook = ET.Element(f"{{{MAIN_NS}}}workbook")
    sheets = ET.SubElement(workbook, f"{{{MAIN_NS}}}sheets")
    ET.SubElement(
        sheets,
        f"{{{MAIN_NS}}}sheet",
        {"name": "Scopus Sources Sep. 2026", "sheetId": "1", f"{{{REL_NS}}}id": "rId1"},
    )
    ET.SubElement(
        sheets,
        f"{{{MAIN_NS}}}sheet",
        {"name": "Discontinued Titles Sep. 2026", "sheetId": "2", f"{{{REL_NS}}}id": "rId2"},
    )
    relationships = ET.Element(f"{{{PKG_REL_NS}}}Relationships")
    ET.SubElement(
        relationships,
        f"{{{PKG_REL_NS}}}Relationship",
        {"Id": "rId1", "Target": "worksheets/sheet1.xml"},
    )
    ET.SubElement(
        relationships,
        f"{{{PKG_REL_NS}}}Relationship",
        {"Id": "rId2", "Target": "worksheets/sheet2.xml"},
    )

    stream = BytesIO()
    with ZipFile(stream, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("xl/workbook.xml", ET.tostring(workbook, encoding="utf-8", xml_declaration=True))
        archive.writestr("xl/_rels/workbook.xml.rels", ET.tostring(relationships, encoding="utf-8", xml_declaration=True))
        archive.writestr("xl/worksheets/sheet1.xml", _worksheet_xml(source_rows))
        archive.writestr("xl/worksheets/sheet2.xml", _worksheet_xml(discontinued_rows))
    return stream.getvalue()


def _rewrite_workbook(workbook_bytes, member, mutate):
    stream = BytesIO()
    with ZipFile(BytesIO(workbook_bytes), "r") as source, ZipFile(stream, "w", ZIP_DEFLATED) as target:
        for name in source.namelist():
            contents = source.read(name)
            if name == member:
                root = ET.fromstring(contents)
                mutate(root)
                contents = ET.tostring(root, encoding="utf-8", xml_declaration=True)
            target.writestr(name, contents)
    return stream.getvalue()


class _Response:
    def __init__(self, body):
        self.stream = BytesIO(body)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.stream.close()

    def read(self, size=-1):
        return self.stream.read(size)


def test_parser_reads_source_status_and_discontinued_final_coverage():
    parsed = parse_scopus_source_list(_source_workbook())
    by_issn = {record.issn: record for record in parsed.records}

    assert parsed.snapshot == "2026-09"
    assert by_issn["10000001"].status == "active"
    assert by_issn["10000001"].coverage == "2001-2012"
    assert by_issn["10000003"].status == "discontinued"
    assert by_issn["10000003"].final_coverage_year == "2025"
    assert by_issn["10000004"].status == "inactive"


def test_parser_rejects_cell_with_out_of_range_shared_string_index():
    def corrupt_title(root):
        cell = root.find(f".//{{{MAIN_NS}}}c[@r='B2']")
        cell.attrib["t"] = "s"
        for child in list(cell):
            cell.remove(child)
        ET.SubElement(cell, f"{{{MAIN_NS}}}v").text = "9999"

    workbook = _rewrite_workbook(_source_workbook(), "xl/worksheets/sheet1.xml", corrupt_title)

    with pytest.raises(ValueError, match="out of range"):
        parse_scopus_source_list(workbook)


def test_parser_rejects_cell_without_a_reference():
    def remove_source_id_reference(root):
        root.find(f".//{{{MAIN_NS}}}c[@r='A2']").attrib.pop("r")

    workbook = _rewrite_workbook(_source_workbook(), "xl/worksheets/sheet1.xml", remove_source_id_reference)

    with pytest.raises(ValueError, match="Invalid or duplicate cell reference"):
        parse_scopus_source_list(workbook)


def test_parser_rejects_duplicate_cell_coordinates():
    def duplicate_title_cell(root):
        row = root.find(f".//{{{MAIN_NS}}}row[@r='2']")
        cell = row.find(f"{{{MAIN_NS}}}c[@r='B2']")
        row.append(ET.fromstring(ET.tostring(cell)))

    workbook = _rewrite_workbook(_source_workbook(), "xl/worksheets/sheet1.xml", duplicate_title_cell)

    with pytest.raises(ValueError, match="Invalid or duplicate cell reference 'B2'"):
        parse_scopus_source_list(workbook)


def test_parser_reports_a_missing_sheet_relationship():
    def remove_relationship_id(root):
        root.find(f".//{{{MAIN_NS}}}sheet").attrib.pop(f"{{{REL_NS}}}id")

    workbook = _rewrite_workbook(_source_workbook(), "xl/workbook.xml", remove_relationship_id)

    with pytest.raises(ValueError, match="no matching relationship entry"):
        parse_scopus_source_list(workbook)


def test_parser_rejects_duplicate_column_headers():
    def duplicate_issn_header(root):
        cell = root.find(f".//{{{MAIN_NS}}}c[@r='D1']")
        cell.find(f"{{{MAIN_NS}}}is/{{{MAIN_NS}}}t").text = "ISSN"

    workbook = _rewrite_workbook(
        _source_workbook(),
        "xl/worksheets/sheet1.xml",
        duplicate_issn_header,
    )

    with pytest.raises(ValueError, match="Duplicate source-list column header 'ISSN'"):
        parse_scopus_source_list(workbook)


def test_compiler_resolves_the_official_workbook_link(monkeypatch):
    workbook = _source_workbook()
    source_url = "https://downloads.ctfassets.net/source-list.xlsx"
    page = (
        '<a href="//downloads.ctfassets.net/source-list.xlsx">'
        "Download the Source title listopens in new tab/window</a>"
    ).encode()

    class Opener:
        def __init__(self):
            self.urls = []

        def open(self, request, timeout):
            self.urls.append((request.full_url, timeout))
            return _Response(page if len(self.urls) == 1 else workbook)

    opener = Opener()
    monkeypatch.setattr(scopus_compiler, "is_safe_external_url", lambda _: True)

    downloaded, resolved_url = scopus_compiler._current_source_workbook(opener)

    assert downloaded == workbook
    assert resolved_url == source_url
    assert [url for url, _timeout in opener.urls] == [scopus_compiler.SCOPUS_CONTENT_URL, source_url]


def test_compiler_rejects_a_non_elsevier_workbook_link(monkeypatch):
    page = b'<a href="https://attacker.example/source.xlsx">Download the Source title list</a>'

    class Opener:
        def __init__(self):
            self.urls = []

        def open(self, request, timeout):
            self.urls.append(request.full_url)
            return _Response(page)

    opener = Opener()
    monkeypatch.setattr(scopus_compiler, "is_safe_external_url", lambda _: True)

    with pytest.raises(ValueError, match="official download host"):
        scopus_compiler._current_source_workbook(opener)

    assert opener.urls == [scopus_compiler.SCOPUS_CONTENT_URL]


def test_compiler_keeps_old_coverage_metrics_separate_from_current_status(tmp_path, monkeypatch):
    csv_data = (
        "Title;Issn;SJR;SJR Best Quartile;Coverage;Total Docs. (2024)\n"
        "Active Older Coverage Journal;1000-0001;0.44;Q2;2001-2012;5\n"
        "Discontinued Journal;1000-0003;0.21;Q4;2010-2025;1\n"
    ).encode()
    db_path = tmp_path / "scopus.db"

    assert _compile_index(
        str(db_path),
        csv_data,
        _source_workbook(),
        "https://downloads.ctfassets.net/example/source.xlsx",
    )

    with sqlite3.connect(db_path) as connection:
        old_coverage_metric = connection.execute(
            "SELECT quartile, sjr FROM scopus_journals WHERE issn = '10000001'"
        ).fetchone()
        source_statuses = dict(connection.execute("SELECT issn, status FROM scopus_sources"))
        manifest = dict(connection.execute("SELECT key, value FROM scopus_manifest"))

    assert old_coverage_metric == ("Q2", 0.44)
    assert source_statuses["10000001"] == "active"
    assert source_statuses["10000003"] == "discontinued"
    assert manifest["source_list_snapshot"] == "2026-09"
    assert manifest["scimago_metric_year"] == "2024"

    monkeypatch.setattr(journal_indexer, "SCOPUS_DB_PATH", str(db_path))
    active = journal_indexer.lookup_scopus_source(
        ["1000-0001"],
        "Active Older Coverage Journal",
    )
    discontinued = journal_indexer.lookup_scopus_source(
        ["1000-0003"],
        "Discontinued Journal",
    )
    assert active["status"] == "active"
    assert active["source_snapshot"] == "2026-09"
    assert discontinued["status"] == "discontinued"
    assert discontinued["last_coverage_year"] == "2025"
    assert journal_indexer.lookup_scopus_db("10000001")["metric_year"] == "2024"


def test_compiler_preserves_sjr_when_no_quartile_is_assigned(tmp_path, monkeypatch):
    csv_data = (
        "Title;Issn;SJR;SJR Best Quartile;Coverage;Total Docs. (2024)\n"
        "Active Older Coverage Journal;1000-0001;0.44;-;2001-2012;5\n"
    ).encode()
    db_path = tmp_path / "scopus.db"

    assert _compile_index(
        str(db_path),
        csv_data,
        _source_workbook(),
        "https://downloads.ctfassets.net/example/source.xlsx",
    )

    with sqlite3.connect(db_path) as connection:
        metric = connection.execute(
            "SELECT quartile, sjr FROM scopus_journals WHERE issn = '10000001'"
        ).fetchone()
    assert metric == (None, 0.44)

    monkeypatch.setattr(journal_indexer, "SCOPUS_DB_PATH", str(db_path))
    monkeypatch.setattr(journal_indexer, "_read_sinta_cache", lambda _issn: None)
    resolved = journal_indexer.lookup_journal_index(
        issn_list=["1000-0001"],
        journal_title="Active Older Coverage Journal",
    )

    assert resolved["scopus_status"] == "active"
    assert resolved["historical_sjr_quartile"] is None
    assert resolved["historical_sjr"] == 0.44
    assert resolved["historical_sjr_year"] == "2024"
