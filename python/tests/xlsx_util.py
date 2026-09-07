# ruff: noqa: E501  (raw XML string literals cannot be wrapped)
"""Shared-string xlsx writer for differential tests against the Swift binary.

openpyxl serializes string cells as ``inlineStr``, which CoreXLSX (Swift) does
not read, so openpyxl-written fixtures are NOT a valid oracle. Real Excel/WPS
files use a shared-strings table. This module writes xlsx directly with a
shared-strings table so Swift and Python read identical input.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

_XML_ESCAPE = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
}


def _esc(s: object) -> str:
    if s is None:
        return ""
    s = str(s)
    return "".join(_XML_ESCAPE.get(c, c) for c in s)


def _col_name(col0: int) -> str:
    # single letters A..Z are enough for tests (cap 26)
    return chr(ord("A") + col0)


def write_shared_string_xlsx(
    path: str | Path,
    sheets: dict[str, list[list[object]]],
    *,
    first_rows: dict[str, int] | None = None,
    merges: dict[str, list[tuple[int, int, int, int]]] | None = None,
    start_data_row: int = 1,
) -> None:
    """Write a workbook where every non-empty cell's *string* content lives in
    a shared-strings table (numbers/dates stay inline as their raw value).

    sheets: map of sheet name -> rows of cell values (1-based data rows begin
        at ``start_data_row`` within ``sheets[sheet]``'s first row).
    merges: optional map sheet name -> list of (r1, c1, r2, c2) 1-based.
    """
    merges = merges or {}

    shared: list[str] = []
    index: dict[str, int] = {}

    def sst_id(value: str) -> int:
        if value not in index:
            index[value] = len(shared)
            shared.append(value)
        return index[value]

    # Worksheet xml bodies per sheet, assigned row index = position.
    sheet_bodies: dict[str, list[str]] = {}
    for name, rows in sheets.items():
        cells_by_row: dict[int, list[str]] = {}
        row_index = start_data_row
        for row in rows:
            for col0, val in enumerate(row):
                if val is None:
                    continue
                if isinstance(val, bool):
                    xmlval = "1" if val else "0"
                    type_attr = ""
                elif isinstance(val, (int, float)):
                    # integral floats written as ints
                    if isinstance(val, float) and val.is_integer():
                        val = int(val)
                    xmlval = str(val)
                    type_attr = ""
                elif isinstance(val, str):
                    xmlval = str(sst_id(val))
                    type_attr = ' t="s"'
                else:
                    xmlval = str(val)
                    type_attr = ""
                cell_ref = f'{_col_name(col0)}{row_index}'
                cell = f'<c r="{cell_ref}"{type_attr}><v>{_esc(xmlval)}</v></c>'
                cells_by_row.setdefault(row_index, []).append(cell)
            row_index += 1

        body = [
            f'<row r="{r}">' + "".join(cells_by_row[r]) + "</row>"
            for r in sorted(cells_by_row)
        ]
        sheet_bodies[name] = body

    # Build sheet + rels + content types (handling >1 sheet minimally).
    sheet_names = list(sheets.keys())
    if len(sheet_names) == 1:
        sheet_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            "<sheetData>"
            + "".join(sheet_bodies[sheet_names[0]])
            + "</sheetData></worksheet>"
        )
        rels = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>'
            "</Relationships>"
        )
        content_types = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
            "</Types>"
        )
        wb_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            f'<sheets><sheet name="{_esc(sheet_names[0])}" sheetId="1" r:id="rId1"/></sheets></workbook>'
        )
    else:
        raise NotImplementedError("multi-sheet shared-string writer not yet needed for tests")

    sst = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="{len(shared)}" uniqueCount="{len(shared)}">'
        + "".join(f"<si><t>{_esc(s)}</t></si>" for s in shared)
        + "</sst>"
    )

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            "</Relationships>")
        z.writestr("xl/workbook.xml", wb_xml)
        z.writestr("xl/_rels/workbook.xml.rels", rels)
        z.writestr("xl/worksheets/sheet1.xml", sheet_xml)
        z.writestr("xl/sharedStrings.xml", sst)
