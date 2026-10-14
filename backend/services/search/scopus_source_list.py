from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
import re
from zipfile import ZipFile
import xml.etree.ElementTree as ET


_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_DOC_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


@dataclass(frozen=True)
class ScopusSourceRecord:
    source_id: str
    title: str
    issn: str
    source_type: str
    status: str
    coverage: str
    discontinued_flag: str
    discontinued_event: str
    final_coverage_year: str


@dataclass(frozen=True)
class ScopusSourceList:
    snapshot: str
    records: tuple[ScopusSourceRecord, ...]


def _column_name(cell_reference: str) -> str:
    return re.sub(r"[0-9]", "", cell_reference)


def _shared_strings(archive: ZipFile) -> list[str]:
    try:
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    return ["".join(node.itertext()) for node in root.findall(f"{{{_MAIN_NS}}}si")]


def _worksheet_paths(archive: ZipFile) -> dict[str, str]:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = {
        node.attrib["Id"]: node.attrib["Target"]
        for node in relationships.findall(f"{{{_PKG_REL_NS}}}Relationship")
    }
    paths = {}
    for sheet in workbook.findall(f".//{{{_MAIN_NS}}}sheet"):
        name = sheet.attrib.get("name", "<unnamed>")
        relationship_id = sheet.attrib.get(f"{{{_DOC_REL_NS}}}id")
        if not relationship_id or relationship_id not in targets:
            raise ValueError(f"Scopus workbook sheet {name!r} has no matching relationship entry")
        target = targets[relationship_id]
        paths[name] = target.lstrip("/") if target.startswith("/") else f"xl/{target}"
    return paths


def _cell_value(cell: ET.Element, shared: list[str], path: str) -> str:
    value = cell.find(f"{{{_MAIN_NS}}}v")
    if cell.attrib.get("t") == "inlineStr":
        inline = cell.find(f"{{{_MAIN_NS}}}is")
        return "".join(inline.itertext()) if inline is not None else ""
    if value is None or value.text is None:
        return ""
    if cell.attrib.get("t") == "s":
        try:
            index = int(value.text)
        except ValueError as exc:
            raise ValueError(f"Invalid shared-string index {value.text!r} in {path}") from exc
        if not 0 <= index < len(shared):
            raise ValueError(f"Shared-string index {index} is out of range in {path}")
        return shared[index]
    return value.text.strip()


def _sheet_rows(archive: ZipFile, path: str, shared: list[str]) -> list[dict[str, str]]:
    root = ET.fromstring(archive.read(path))
    raw_rows = []
    for row in root.findall(f".//{{{_MAIN_NS}}}sheetData/{{{_MAIN_NS}}}row"):
        cells = {}
        for cell in row.findall(f"{{{_MAIN_NS}}}c"):
            reference = cell.attrib.get("r", "")
            column = _column_name(reference)
            if not column or column in cells:
                raise ValueError(f"Invalid or duplicate cell reference {reference!r} in {path}")
            cells[column] = _cell_value(cell, shared, path)
        raw_rows.append(cells)

    header_index = next(
        (
            index
            for index, row in enumerate(raw_rows)
            if any(value.strip().startswith("Source Title") for value in row.values())
            and any(value.strip().lower() in {"sourcerecord id", "source record id"} for value in row.values())
        ),
        None,
    )
    if header_index is None:
        raise ValueError(f"Could not locate source-list header row in {path}")

    headers = raw_rows[header_index]
    header_names = [value.strip() for value in headers.values() if value.strip()]
    seen_headers = set()
    for header in header_names:
        if header in seen_headers:
            raise ValueError(f"Duplicate source-list column header {header!r} in {path}")
        seen_headers.add(header)

    records = []
    for row in raw_rows[header_index + 1 :]:
        record = {}
        for column, value in row.items():
            header = headers.get(column, "").strip()
            if not header:
                continue
            record[header] = value.strip()
        if record:
            records.append(record)
    return records


def _value(record: dict[str, str], *names: str) -> str:
    normalized = {re.sub(r"\s+", " ", key.strip().lower()): value for key, value in record.items()}
    for name in names:
        value = normalized.get(re.sub(r"\s+", " ", name.strip().lower()))
        if value:
            return value.strip()
    return ""


def _issns(record: dict[str, str]) -> list[str]:
    values = [_value(record, "ISSN"), _value(record, "EISSN")]
    found = []
    for value in values:
        for raw in re.findall(r"[0-9]{4}-?[0-9Xx]{4}", value):
            normalized = re.sub(r"[^0-9Xx]", "", raw).upper()
            if len(normalized) == 8 and normalized not in found:
                found.append(normalized)
    return found


def _snapshot(sheet_name: str) -> str:
    match = re.fullmatch(r"Scopus Sources\s+([A-Za-z]+)\.?\s+(\d{4})", sheet_name.strip())
    if not match:
        raise ValueError(f"Unexpected Scopus source-list sheet name: {sheet_name}")
    month = datetime.strptime(f"{match.group(1)[:3]} {match.group(2)}", "%b %Y")
    return month.strftime("%Y-%m")


def parse_scopus_source_list(workbook_bytes: bytes) -> ScopusSourceList:
    with ZipFile(BytesIO(workbook_bytes)) as archive:
        shared = _shared_strings(archive)
        paths = _worksheet_paths(archive)
        source_sheet = next((name for name in paths if name.startswith("Scopus Sources ")), None)
        discontinued_sheet = next((name for name in paths if name.startswith("Discontinued Titles ")), None)
        if not source_sheet or not discontinued_sheet:
            raise ValueError("Official Scopus workbook is missing source or discontinued titles sheet")

        source_rows = _sheet_rows(archive, paths[source_sheet], shared)
        discontinued_rows = _sheet_rows(archive, paths[discontinued_sheet], shared)
        discontinued_by_source: dict[str, list[dict[str, str]]] = {}
        for row in discontinued_rows:
            source_id = _value(row, "Source record ID", "Sourcerecord ID")
            if source_id:
                discontinued_by_source.setdefault(source_id, []).append(row)

        records = []
        for row in source_rows:
            source_id = _value(row, "Source record ID", "Sourcerecord ID")
            title = _value(row, "Source Title")
            if not source_id or not title:
                continue
            source_status = _value(row, "Active or Inactive").lower()
            discontinued_flag = _value(row, "Titles Discontinued by Scopus")
            events = discontinued_by_source.get(source_id, [])
            event = next(
                (entry for entry in events if _value(entry, "Indexation Change").lower() == "discontinuation"),
                events[0] if events else {},
            )
            event_name = _value(event, "Indexation Change")
            final_year = _value(event, "Year")
            if source_status == "active":
                status = "active"
            elif discontinued_flag or event_name.lower() == "discontinuation":
                status = "discontinued"
            elif source_status == "inactive":
                status = "inactive"
            else:
                raise ValueError(f"Unknown Scopus source status {source_status!r} for {source_id}")

            for issn in _issns(row):
                records.append(ScopusSourceRecord(
                    source_id=source_id,
                    title=title,
                    issn=issn,
                    source_type=_value(row, "Source Type"),
                    status=status,
                    coverage=_value(row, "Coverage"),
                    discontinued_flag=discontinued_flag,
                    discontinued_event=event_name,
                    final_coverage_year=final_year,
                ))

        if not records:
            raise ValueError("Official Scopus workbook contains no source records with ISSNs")
        return ScopusSourceList(snapshot=_snapshot(source_sheet), records=tuple(records))
