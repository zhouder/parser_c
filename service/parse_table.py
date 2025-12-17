import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set
from xml.sax.saxutils import escape

from .grammer import Grammar, Production, EPSILON


@dataclass
class ParseTable:
    """
    预测分析表：
      table[非终结符][终结符] = 产生式
    """
    table: Dict[str, Dict[str, Production]] = field(default_factory=dict)

    def get(self, nonterminal: str, terminal: str) -> Optional[Production]:
        return self.table.get(nonterminal, {}).get(terminal)

    @classmethod
    def from_grammar(
        cls, grammar: Grammar, select_sets: Dict[Production, Set[str]], allow_conflict: bool = True
    ) -> "ParseTable":
        tbl: Dict[str, Dict[str, Production]] = {}
        conflicts = []

        for prod, sel in select_sets.items():
            A = prod.head
            row = tbl.setdefault(A, {})
            for a in sel:
                if a == EPSILON:
                    continue
                if a in row and row[a] != prod:
                    msg = f"LL(1) 冲突: M[{A}, {a}] 已有 {row[a]}，又遇到 {prod}"
                    if allow_conflict:
                        conflicts.append(msg)
                        # 默认保留先填入的产生式，忽略后者
                        continue
                    else:
                        raise ValueError(msg)
                row[a] = prod

        # 可选：输出冲突警告（此处只保留到实例中，不打印）
        inst = cls(tbl)
        inst._conflicts = conflicts  # type: ignore[attr-defined]
        return inst

    def __str__(self) -> str:
        lines = []
        for A, row in self.table.items():
            lines.append(f"{A}: " + ", ".join(f"{a}→{p}" for a, p in row.items()))
        return "\n".join(lines)

    def export_xlsx(
        self,
        path: Path,
        grammar: Grammar,
        terminal_order: Optional[Sequence[str]] = None,
        nonterminal_order: Optional[Sequence[str]] = None,
    ) -> None:
        """
        Export the LL(1) parse table to an .xlsx file without third-party deps.
        Layout: first row = terminals header, first column = nonterminals.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Stable ordering so the sheet is deterministic
        terms: List[str] = list(terminal_order) if terminal_order else sorted(
            t for t in grammar.terminals if t != EPSILON
        )
        nonterms: List[str] = list(nonterminal_order) if nonterminal_order else sorted(grammar.nonterminals)

        # Build grid data as strings
        grid: List[List[str]] = []
        grid.append([""] + terms)
        for nt in nonterms:
            row = [nt]
            for t in terms:
                prod = self.get(nt, t)
                if prod:
                    rhs = " ".join(sym if sym != EPSILON else "epsilon" for sym in prod.body)
                    row.append(f"{prod.head} -> {rhs}")
                else:
                    row.append("")
            grid.append(row)

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
                    cells_xml.append(
                        f'<c r="{ref}" t="inlineStr"><is><t>{escape(value)}</t></is></c>'
                    )
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
            '<sheets><sheet name="ParseTable" sheetId="1" r:id="rId1"/></sheets>'
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
