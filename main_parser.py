# main_parser.py
import sys
from service.lexer import Lexer
from service.parser import Parser
from service import ast

def print_ast(node: ast.Node, indent: int = 0):
    pad = "  " * indent
    if isinstance(node, list):
        for n in node:
            print_ast(n, indent)
        return
    cls = type(node).__name__
    fields = []
    for k, v in vars(node).items():
        if isinstance(v, ast.Node):
            fields.append(f"{k}=")
        elif isinstance(v, list) and v and isinstance(v[0], ast.Node):
            fields.append(f"{k}=[...]")
        else:
            fields.append(f"{k}={v!r}")
    print(f"{pad}{cls}({', '.join(fields)})")
    # 递归打印子节点
    for k, v in vars(node).items():
        if isinstance(v, ast.Node):
            print_ast(v, indent + 1)
        elif isinstance(v, list) and v and isinstance(v[0], ast.Node):
            for it in v:
                print_ast(it, indent + 1)

def main():
    if len(sys.argv) < 2:
        print("用法: python main_parser.py path/to/source.c")
        sys.exit(1)
    with open(sys.argv[1], "r", encoding="utf-8") as f:
        src = f.read()
    lexer = Lexer(src)
    parser = Parser(lexer)
    program = parser.parse_program()

    if parser.errors:
        print(f"语法分析完成，共 {len(parser.errors)} 个错误：")
        for e in parser.errors:
            print(f"[{e.line}:{e.col}] {e.msg}")
        sys.exit(2)
    else:
        print("语法分析通过，AST 概览：")
        print_ast(program)

if __name__ == "__main__":
    main()
