import argparse
import sys
from pathlib import Path
from typing import List

# 语法与工具
from service.grammer import build_grammar, EPSILON, END_SYMBOL
from service.first_follow import (
    compute_first_sets,
    compute_follow_sets,
    compute_select_sets,
    first_of_sequence,
)
from service.parse_table import ParseTable
from service.ast_builder import ASTNode, build_ast
from service.parser import Parser, ParseError, ParseTreeNode
from service.xlsx_util import export_grid_xlsx


def _tree_label(node: ParseTreeNode) -> str:
    if node.lexeme is None or node.lexeme == "" or node.lexeme == node.symbol:
        return node.symbol
    return f"{node.symbol}: {node.lexeme}"


def render_tree_lines(node: ParseTreeNode, prefix: str = "", is_last: bool = True) -> List[str]:
    connector = "`- " if is_last else "|- "
    head = _tree_label(node) if prefix == "" else f"{connector}{_tree_label(node)}"
    lines = [f"{prefix}{head}"]
    child_prefix = prefix + ("   " if is_last else "|  ")
    for idx, child in enumerate(node.children):
        lines.extend(render_tree_lines(child, prefix=child_prefix, is_last=(idx == len(node.children) - 1)))
    return lines


def render_ast_lines(node: ASTNode, prefix: str = "", is_last: bool = True) -> List[str]:
    connector = "`- " if is_last else "|- "
    label = node.kind if node.value is None else f"{node.kind}: {node.value}"
    head = label if prefix == "" else f"{connector}{label}"
    lines = [f"{prefix}{head}"]
    child_prefix = prefix + ("   " if is_last else "|  ")
    for idx, child in enumerate(node.children):
        lines.extend(render_ast_lines(child, prefix=child_prefix, is_last=(idx == len(node.children) - 1)))
    return lines


def render_trace_table(entries, limit: int) -> str:
    # Basic fixed-width table, similar to textbook LL(1) analysis tables.
    rows = entries if limit == 0 else entries[:limit]
    headers = ["步骤", "分析栈", "符号串", "产生式", "下一步动作"]
    data = []
    for e in rows:
        data.append([str(e.step), e.stack, e.input, e.production, e.action])

    widths = [len(h) for h in headers]
    for row in data:
        for idx, cell in enumerate(row):
            widths[idx] = max(widths[idx], len(cell))

    def fmt_row(row):
        return " | ".join(cell.ljust(widths[idx]) for idx, cell in enumerate(row))

    out_lines = [fmt_row(headers), "-+-".join("-" * w for w in widths)]
    out_lines.extend(fmt_row(r) for r in data)
    return "\n".join(out_lines)


def render_ll1_table_lines(table: ParseTable, grammar, nonterminal: str | None, limit: int) -> List[str]:
    nts = [nonterminal] if nonterminal else sorted(grammar.nonterminals)
    lines: List[str] = []
    total = 0
    printed = 0

    for nt in nts:
        row = table.table.get(nt, {})
        total += len(row)

    for nt in nts:
        row = table.table.get(nt, {})
        if not row:
            continue
        for term in sorted(row.keys()):
            prod = row[term]
            rhs = " ".join(sym if sym != EPSILON else "epsilon" for sym in prod.body)
            lines.append(f"M[{nt}, {term}] = {prod.head} -> {rhs}")
            printed += 1
            if limit != 0 and printed >= limit:
                remaining = total - printed
                if remaining > 0:
                    lines.append(f"... omitted {remaining} table entries (increase --table-limit or set 0 for all)")
                return lines

    return lines


def _used_nonterminals_from_productions(grammar, prods) -> List[str]:
    used = set()
    for p in prods:
        used.add(p.head)
        for s in p.body:
            if grammar.is_nonterminal(s):
                used.add(s)
    return sorted(used)


def main():
    ap = argparse.ArgumentParser(description="LL(1) parser for a C-subset (parser_c)")
    ap.add_argument("source", nargs="?", default=None, help="C source file to parse")
    ap.add_argument("--show-ff", action="store_true", help="Show FIRST/FOLLOW/SELECT and table size")
    ap.add_argument(
        "--show-ff-used",
        action="store_true",
        help="Show FIRST/FOLLOW/SELECT only for nonterminals/productions used while parsing the source file.",
    )
    ap.add_argument(
        "--ff-lookahead-only",
        action="store_true",
        help="When used with --show-ff-used: filter set elements to only terminals actually seen as lookahead during parsing (plus EOF/epsilon).",
    )
    ap.add_argument("--show-select-all", action="store_true", help="Show SELECT sets for all productions (can be long)")
    ap.add_argument("--show-table", action="store_true", help="Print LL(1) parse table (can be very long)")
    ap.add_argument(
        "--show-table-used",
        action="store_true",
        help="Print only the LL(1) table entries actually used while parsing the source file.",
    )
    ap.add_argument("--table-nt", default=None, help="Only print one nonterminal row for --show-table (e.g. Expr)")
    ap.add_argument(
        "--table-limit",
        type=int,
        default=200,
        help="How many table entries to print (0 = all, default: 200). Requires --show-table.",
    )
    ap.add_argument("--trace", action="store_true", help="Trace parsing steps")
    ap.add_argument(
        "--trace-limit",
        type=int,
        default=200,
        help="How many trace lines to print (0 = all, default: 200). Requires --trace.",
    )
    ap.add_argument(
        "--trace-table",
        action="store_true",
        help="Print LL(1) analysis as a step-by-step table (stack/input/production/action).",
    )
    ap.add_argument(
        "--trace-table-limit",
        type=int,
        default=200,
        help="How many trace-table rows to print (0 = all, default: 200). Requires --trace-table.",
    )
    ap.add_argument(
        "--export-trace-xlsx",
        nargs="?",
        const="trace_table.xlsx",
        default=None,
        help="Export the LL(1) trace table to an .xlsx file (default: trace_table.xlsx).",
    )
    ap.add_argument("--show-tree", action="store_true", help="Print parse tree (syntax tree)")
    ap.add_argument("--show-ast", action="store_true", help="Print a simplified AST (abstract syntax tree)")
    ap.add_argument(
        "--export-xlsx",
        nargs="?",
        const="parse_table.xlsx",
        default=None,
        help="Export LL(1) parse table to an .xlsx file (default: parse_table.xlsx)",
    )
    ap.add_argument(
        "--export-xlsx-used",
        nargs="?",
        const="parse_table_used.xlsx",
        default=None,
        help="Export only the LL(1) table entries used while parsing the source file (default: parse_table_used.xlsx)",
    )
    args = ap.parse_args()

    if not args.source:
        print("Usage: python main.py <source.c> [--show-ff] [--trace]")
        sys.exit(2)

    src_path = Path(args.source)
    if not src_path.exists():
        print(f"[Error] Source file not found: {src_path}")
        sys.exit(1)

    # utf-8-sig 会自动去掉 BOM（\ufeff）
    text = src_path.read_text(encoding="utf-8-sig", errors="ignore")

    # 1) 文法
    grammar = build_grammar()

    # 2) FIRST/FOLLOW/SELECT
    first_sets = compute_first_sets(grammar)
    follow_sets = compute_follow_sets(grammar, first_sets)
    select_sets = compute_select_sets(grammar, first_sets, follow_sets)

    # 3) 预测分析表
    table = ParseTable.from_grammar(grammar, select_sets, allow_conflict=True)

    if args.export_xlsx:
        out_path = Path(args.export_xlsx)
        table.export_xlsx(out_path, grammar)
        print(f"[Export] LL(1) parse table saved to: {out_path}")

    if args.show_ff:
        print("=== FIRST Sets ===")
        for nt in sorted(grammar.nonterminals):
            items = ", ".join(sorted(first_sets[nt], key=lambda s: (s != EPSILON, s)))
            print(f"FIRST({nt}) = {{ {items} }}")
        print("\n=== FOLLOW Sets ===")
        for nt in sorted(grammar.nonterminals):
            items = ", ".join(sorted(follow_sets[nt], key=lambda s: (s != END_SYMBOL, s)))
            print(f"FOLLOW({nt}) = {{ {items} }}")
        print("\n=== SELECT Sets ===")
        if args.show_select_all:
            for prod, sel in select_sets.items():
                print(f"SELECT({prod}) = {{ {', '.join(sorted(sel))} }}")
        else:
            cnt = 0
            for prod, sel in select_sets.items():
                print(f"SELECT({prod}) = {{ {', '.join(sorted(sel))} }}")
                cnt += 1
                if cnt >= 12:
                    print("... (more omitted; use --show-select-all for full list)")
                    break

        total_cells = sum(len(row) for row in table.table.values())
        print(f"\n[Table] Nonterminals: {len(grammar.nonterminals)} | Terminals: {len(grammar.terminals)}")
        print(f"[Table] Filled cells: {total_cells}\n")

    if args.show_table:
        print("=== LL(1) Parse Table ===")
        lines = render_ll1_table_lines(table, grammar, nonterminal=args.table_nt, limit=args.table_limit)
        print("\n".join(lines))
        print("")

    # 4) 解析
    parser = Parser(grammar=grammar, table=table, debug=args.trace)
    try:
        need_tree = args.show_tree or args.show_ast
        tree = parser.parse_source(text, return_tree=need_tree)
        print("[OK] 语法分析通过")

        if args.export_xlsx_used:
            out_path = Path(args.export_xlsx_used)
            # Build a reduced table from the cells actually used during parsing.
            used_tbl = {}
            used_terms = set()
            used_nts = set()
            for nt, term, prod in parser.used_table_entries:
                used_nts.add(nt)
                used_terms.add(term)
                used_tbl.setdefault(nt, {})[term] = prod
            used_table = ParseTable(used_tbl)
            used_table.export_xlsx(
                out_path,
                grammar,
                terminal_order=sorted(used_terms),
                nonterminal_order=sorted(used_nts),
            )
            print(f"[Export] Used LL(1) table entries saved to: {out_path}")

        if args.export_trace_xlsx:
            out_path = Path(args.export_trace_xlsx)
            rows = parser.trace_entries if args.trace_table_limit == 0 else parser.trace_entries[: args.trace_table_limit]
            grid = [["步骤", "分析栈", "符号串", "产生式", "下一步动作"]]
            for e in rows:
                grid.append([str(e.step), e.stack, e.input, e.production, e.action])
            export_grid_xlsx(out_path, grid, sheet_name="TraceTable")
            print(f"[Export] LL(1) trace table saved to: {out_path}")
        if args.show_table_used:
            print("\n=== LL(1) Parse Table (used entries) ===")
            seen_cells = set()
            printed = 0
            for nt, term, prod in parser.used_table_entries:
                key = (nt, term)
                if key in seen_cells:
                    continue
                seen_cells.add(key)
                rhs = " ".join(sym if sym != EPSILON else "epsilon" for sym in prod.body)
                print(f"M[{nt}, {term}] = {prod.head} -> {rhs}")
                printed += 1
                if args.table_limit != 0 and printed >= args.table_limit:
                    print("... omitted remaining used entries (increase --table-limit or set 0 for all)")
                    break
        if args.show_ff_used:
            used_nts = _used_nonterminals_from_productions(grammar, parser.used_productions)
            lookahead_terms = {term for (_, term, _) in parser.used_table_entries}
            lookahead_terms.add(END_SYMBOL)
            lookahead_terms.add(EPSILON)

            def maybe_filter(items: set[str]) -> List[str]:
                if args.ff_lookahead_only:
                    items = set(items) & lookahead_terms
                return sorted(items, key=lambda s: (s != EPSILON and s != END_SYMBOL, s))

            print("\n=== FIRST Sets (used) ===")
            for nt in used_nts:
                items = ", ".join(maybe_filter(first_sets[nt]))
                print(f"FIRST({nt}) = {{ {items} }}")
            print("\n=== FOLLOW Sets (used) ===")
            for nt in used_nts:
                items = ", ".join(maybe_filter(follow_sets[nt]))
                print(f"FOLLOW({nt}) = {{ {items} }}")
            print("\n=== SELECT Sets (used productions) ===")
            seen = set()
            for prod in parser.used_productions:
                if prod in seen:
                    continue
                seen.add(prod)
                sel = select_sets.get(prod, set())
                items = ", ".join(maybe_filter(sel))
                print(f"SELECT({prod}) = {{ {items} }}")
        if args.trace:
            print("\n=== Trace ===")
            lines = parser.trace if args.trace_limit == 0 else parser.trace[-args.trace_limit :]
            for line in lines:
                print(line)
        if args.trace_table:
            print("\n=== Trace Table ===")
            print(render_trace_table(parser.trace_entries, limit=args.trace_table_limit))
        if args.show_tree and tree is not None:
            print("\n=== Parse Tree ===")
            print("\n".join(render_tree_lines(tree)))
        if args.show_ast and tree is not None:
            print("\n=== AST ===")
            ast = build_ast(tree)
            print("\n".join(render_ast_lines(ast)))
    except ParseError as e:
        loc = f"{e.line}:{e.col}" if e.line is not None else "?"
        print(f"[SyntaxError] 在 {loc} 处：{e.message}")
        if args.trace:
            print("\n-- Trace (last few steps) --")
            for line in parser.trace[-25:]:
                print(line)
        sys.exit(1)


if __name__ == "__main__":
    main()
