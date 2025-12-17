import argparse
import sys
from pathlib import Path

# 语法与工具
from service.grammer import build_grammar, EPSILON, END_SYMBOL
from service.first_follow import (
    compute_first_sets,
    compute_follow_sets,
    compute_select_sets,
    first_of_sequence,
)
from service.parse_table import ParseTable
from service.parser import Parser, ParseError


def main():
    ap = argparse.ArgumentParser(description="LL(1) parser for a C-subset (parser_c)")
    ap.add_argument("source", nargs="?", default=None, help="C source file to parse")
    ap.add_argument("--show-ff", action="store_true", help="Show FIRST/FOLLOW/SELECT and table size")
    ap.add_argument("--trace", action="store_true", help="Trace parsing steps")
    ap.add_argument(
        "--export-xlsx",
        nargs="?",
        const="parse_table.xlsx",
        default=None,
        help="Export LL(1) parse table to an .xlsx file (default: parse_table.xlsx)",
    )
    args = ap.parse_args()

    if not args.source:
        print("Usage: python main.py <source.c> [--show-ff] [--trace]")
        sys.exit(2)

    src_path = Path(args.source)
    if not src_path.exists():
        print(f"[Error] Source file not found: {src_path}")
        sys.exit(1)

    text = src_path.read_text(encoding="utf-8", errors="ignore")

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
        print("\n=== SELECT (sample) ===")
        cnt = 0
        for prod, sel in select_sets.items():
            print(f"SELECT({prod}) = {{ {', '.join(sorted(sel))} }}")
            cnt += 1
            if cnt >= 12:
                print("... (more omitted)")
                break

        total_cells = sum(len(row) for row in table.table.values())
        print(f"\n[Table] Nonterminals: {len(grammar.nonterminals)} | Terminals: {len(grammar.terminals)}")
        print(f"[Table] Filled cells: {total_cells}\n")

    # 4) 解析
    parser = Parser(grammar=grammar, table=table, debug=args.trace)
    try:
        parser.parse_source(text)
        print("[OK] 语法分析通过")
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
