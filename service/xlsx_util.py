import zipfile
from pathlib import Path
from typing import List
from xml.sax.saxutils import escape


def export_grid_xlsx(path: Path, grid: List[List[str]], sheet_name: str = "Sheet1") -> None:
    """
    Export a 2D grid of strings to an .xlsx file without third-party deps.
    Layout: grid[row][col] as inline strings.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    def col_letter(idx: int) -> str:
        letters = []
        while idx:
            idx, rem = divmod(idx - 1, 26)
            letters.append(chr(ord("A") + rem))
        return "".join(reversed(letters))

    def render_sheet(data: List[List[str]]) -> bytes:
        rows_xml = []
        for r, row in enumerate(data, start=1):
            cells_xml = []
            for c, value in enumerate(row, start=1):
                if value == "":
                    continue
                ref = f"{col_letter(c)}{r}"
                cells_xml.append(f'<c r="{ref}" t="inlineStr"><is><t>{escape(value)}</t></is></c>')
            rows_xml.append(f'<row r="{r}">{"".join(cells_xml)}</row>')
        body = "".join(rows_xml)
        xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f"<sheetData>{body}</sheetData>"
            "</worksheet>"
        )
        return xml.encode("utf-8")

    sheet_xml = render_sheet(grid)

    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets><sheet name="{escape(sheet_name)}" sheetId="1" r:id="rId1"/></sheets>'
        "</workbook>"
    ).encode("utf-8")

    rels_root = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    ).encode("utf-8")

    rels_workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        "</Relationships>"
    ).encode("utf-8")

    styles_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"/>'
    ).encode("utf-8")

    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        "</Types>"
    ).encode("utf-8")

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels_root)
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", rels_workbook)
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)
        zf.writestr("xl/styles.xml", styles_xml)

