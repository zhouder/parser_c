from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Set, Tuple

from .grammer import END_SYMBOL, EPSILON, Grammar, Production
from .parse_table import ParseTable

from .lexer import Lexer  # type: ignore
from .token import Token, TokenType  # type: ignore


@dataclass
class ParseError(Exception):
    message: str
    line: Optional[int] = None
    col: Optional[int] = None


@dataclass
class ParseTreeNode:
    symbol: str
    lexeme: Optional[str] = None  # only for terminals
    line: Optional[int] = None
    col: Optional[int] = None
    children: List["ParseTreeNode"] = field(default_factory=list)

    def add_child(self, node: "ParseTreeNode") -> None:
        self.children.append(node)


class Parser:
    def __init__(self, grammar: Grammar, table: ParseTable, debug: bool = False):
        self.grammar = grammar
        self.table = table
        self.debug = debug
        self.trace: List[str] = []
        self.used_productions: List[Production] = []
        self.used_table_entries: List[Tuple[str, str, Production]] = []
        # 收集 struct/union 的标签名，使其可以当作 TYPE_NAME 使用（用于兼容 `student a;` 这种写法）
        self.type_names: Set[str] = set()

    def token_to_symbol(self, tok: Token) -> str:
        """
        将 lexer 的 Token 映射为文法终结符名称：
          - ID -> "ID"（若 lexeme 在 self.type_names 中则映射为 "TYPE_NAME"）
          - NUM10/NUM8/NUM16/INT... -> "INT_CONST"
          - FLOAT -> "FLOAT_CONST"
          - CS_CHAR -> "CHAR_CONST"
          - CS_STR  -> "STRING_CONST"
          - RW/OP/DL -> 直接使用 lexeme 作为终结符（如 "if", "+", "(", ";"）
          - EOF -> END_SYMBOL
        """
        tname = getattr(tok.type, "name", str(tok.type))

        if "ERROR" in tname:
            # 用 repr 避免控制台编码问题（例如遇到 BOM \ufeff）
            raise ParseError(f"词法错误：{tok.lexeme!r}", tok.line, tok.col)
        if "EOF" in tname:
            return END_SYMBOL

        if tname == "ID":
            if tok.lexeme in self.type_names:
                return "TYPE_NAME"
            return "ID"

        if any(key in tname for key in ("NUM10", "NUM8", "NUM16", "INT", "INTEGER")):
            return "INT_CONST"
        if "FLOAT" in tname:
            return "FLOAT_CONST"

        if "CS_CHAR" in tname or "CHAR_CONST" in tname:
            return "CHAR_CONST"
        if "CS_STR" in tname or "STRING" in tname:
            return "STRING_CONST"

        if tname in ("RW", "KEYWORD", "OP", "OPERATOR", "DL", "DELIM", "DELIMITER"):
            return tok.lexeme

        return tok.lexeme

    def parse_source(self, source_text: str, return_tree: bool = False) -> Optional[ParseTreeNode]:
        lexer = Lexer(source_text)
        tokens = lexer.tokenize()

        if not tokens or getattr(tokens[-1].type, "name", "") != "EOF":
            eof_type = getattr(TokenType, "EOF", None)
            if eof_type is None:
                class _EOF:
                    name = "EOF"

                eof_type = _EOF()
            last = tokens[-1] if tokens else Token(TokenType.EOF, "", 1, 1)
            tokens.append(Token(eof_type, "", getattr(last, "line", 0), getattr(last, "col", 0)))  # type: ignore

        return self.parse_tokens(tokens, return_tree=return_tree)

    def _lookahead_symbol(self, tokens: List[Token], i: int) -> str:
        if i >= len(tokens):
            return END_SYMBOL
        return self.token_to_symbol(tokens[i])

    def parse_tokens(self, tokens: List[Token], return_tree: bool = False) -> Optional[ParseTreeNode]:
        # 分析栈
        stack: List[str] = [END_SYMBOL, self.grammar.start_symbol]
        # 与 stack 同步的“父节点栈”：弹出的符号应挂到哪个节点上（仅当 return_tree=True 时使用）
        parent_stack: List[Optional[ParseTreeNode]] = [None, None]
        # 与 stack 同步的“角色栈”：用于记录某些 ID 的特殊含义（例如 struct/union 标签名）
        role_stack: List[Optional[str]] = [None, None]

        root: Optional[ParseTreeNode] = None
        i = 0

        def preview_input(maxn: int = 12) -> str:
            out: List[str] = []
            for j in range(i, min(i + maxn, len(tokens))):
                out.append(self._lookahead_symbol(tokens, j))
            return " ".join(out)

        trace_step = 0

        def log(action: str) -> None:
            if not self.debug:
                return
            nonlocal trace_step
            trace_step += 1
            stk = " ".join(stack[::-1])
            self.trace.append(f"{trace_step:05d} {action:<20} | stack: [{stk}] | input: {preview_input()}")

        log("INIT")
        while True:
            if not stack:
                last_tok = tokens[max(0, i - 1)] if tokens else Token(TokenType.EOF, "", 1, 1)
                raise ParseError("分析栈提前耗尽，输入尚未结束", getattr(last_tok, "line", None), getattr(last_tok, "col", None))

            X = stack.pop()
            parent_node = parent_stack.pop()
            role = role_stack.pop()
            a = self._lookahead_symbol(tokens, i)

            if X == END_SYMBOL and a == END_SYMBOL:
                log("ACCEPT")
                return root if return_tree else None

            if self.grammar.is_terminal(X) or X == END_SYMBOL:
                if X == a:
                    log(f"match '{a}'")
                    tok = tokens[i]
                    if role == "tag_name" and getattr(tok, "lexeme", ""):
                        self.type_names.add(tok.lexeme)

                    if return_tree and X != END_SYMBOL:
                        leaf = ParseTreeNode(X, lexeme=tok.lexeme, line=tok.line, col=tok.col)
                        if parent_node is None:
                            root = leaf
                        else:
                            parent_node.add_child(leaf)
                    i += 1
                    continue

                tok = tokens[i] if i < len(tokens) else Token(TokenType.EOF, "", 0, 0)
                raise ParseError(f"期望终结符 {X}，但看到 {a}", getattr(tok, "line", None), getattr(tok, "col", None))

            prod = self.table.get(X, a)
            if prod is None:
                row = self.table.table.get(X, {})
                candidates = ", ".join(sorted(row.keys()))
                tok = tokens[i] if i < len(tokens) else Token(TokenType.EOF, "", 0, 0)
                raise ParseError(
                    f"在非终结符 {X} 处，对当前输入 {a} 无可用产生式（期望的是: {candidates}）",
                    getattr(tok, "line", None),
                    getattr(tok, "col", None),
                )
            self.used_productions.append(prod)
            self.used_table_entries.append((X, a, prod))

            # 生成语法树节点（若需要）
            current_node: Optional[ParseTreeNode] = None
            if return_tree:
                current_node = ParseTreeNode(X)
                if parent_node is None:
                    root = current_node
                else:
                    parent_node.add_child(current_node)

            rhs = list(prod.body)
            if len(rhs) == 1 and rhs[0] == EPSILON:
                log(f"reduce {prod}  (ε)")
                if return_tree and current_node is not None:
                    current_node.add_child(ParseTreeNode(EPSILON))
                continue

            # 为 RHS 的每个符号准备角色信息（仅对少数产生式使用）
            rhs_roles: List[Optional[str]] = [None] * len(rhs)
            if prod.head in ("StructSpec", "UnionSpec"):
                # StructSpec -> struct ID StructBodyOpt
                # UnionSpec  -> union  ID UnionBodyOpt
                if len(rhs) >= 2 and rhs[1] == "ID":
                    rhs_roles[1] = "tag_name"

            # 逆序压栈
            for sym, sym_role in zip(reversed(rhs), reversed(rhs_roles)):
                stack.append(sym)
                parent_stack.append(current_node if return_tree else None)
                role_stack.append(sym_role)
            log(f"reduce {prod}")
