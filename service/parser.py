from dataclasses import dataclass
from typing import List, Optional, Tuple

from .grammer import Grammar, EPSILON, END_SYMBOL
from .parse_table import ParseTable

# 复用你的 lexer_c
from .lexer import Lexer  # type: ignore
from .token import TokenType  # type: ignore


@dataclass
class ParseError(Exception):
    message: str
    line: Optional[int] = None
    col: Optional[int] = None


class Parser:
    def __init__(self, grammar: Grammar, table: ParseTable, debug: bool = False):
        self.grammar = grammar
        self.table = table
        self.debug = debug
        self.trace: List[str] = []

    # —— 将词法记号映射为文法终结符 —— #
    def token_to_symbol(self, tok) -> str:
        """
        将 lexer_c 的 Token 映射为语法符号名：
          - ID -> "ID"
          - NUM10/NUM8/NUM16/INT... -> "INT_CONST"
          - FLOAT -> "FLOAT_CONST"
          - CS_CHAR -> "CHAR_CONST"
          - CS_STR  -> "STRING_CONST"
          - RW/OP/DL -> 直接使用 lexeme 作为终结符（如 "if", "+", "(", ";"）
          - EOF -> END_SYMBOL
        """
        # 兼容不同命名：通过枚举名判断
        tname = getattr(tok.type, "name", str(tok.type))

        # 错误 / EOF
        if "ERROR" in tname:
            raise ParseError(f"词法错误：{tok.lexeme}", tok.line, tok.col)
        if "EOF" in tname:
            return END_SYMBOL

        # 标识符
        if tname == "ID":
            return "ID"

        # 整数常量
        if any(key in tname for key in ("NUM10", "NUM8", "NUM16", "INT", "INTEGER")):
            return "INT_CONST"

        # 浮点
        if "FLOAT" in tname:
            return "FLOAT_CONST"

        # 字符/字符串
        if "CS_CHAR" in tname or "CHAR_CONST" in tname:
            return "CHAR_CONST"
        if "CS_STR" in tname or "STRING" in tname:
            return "STRING_CONST"

        # 关键字 / 运算符 / 界符
        if tname in ("RW", "KEYWORD", "OP", "OPERATOR", "DL", "DELIM", "DELIMITER"):
            # 直接返回词面值，如 if / + / ( / , / #
            return tok.lexeme

        # 兜底：也直接用词面值
        return tok.lexeme

    def parse_source(self, source_text: str) -> None:
        lexer = Lexer(source_text)
        tokens = lexer.tokenize()
        # 追加 EOF（若你的 lexer 已自带 EOF，也无妨，映射时会变成 END_SYMBOL）
        from .token import Token  # type: ignore

        if not tokens or getattr(tokens[-1].type, "name", "") != "EOF":
            # 构造一个 EOF token（尽量不依赖内部结构）
            eof_type = getattr(TokenType, "EOF", None)
            if eof_type is None:
                # 简单 fallback：创建一个最小对象
                class _EOF:
                    name = "EOF"

                eof_type = _EOF()
            tokens.append(Token(eof_type, "", getattr(tokens[-1], "line", 0), getattr(tokens[-1], "col", 0)))  # type: ignore

        self.parse_tokens(tokens)

    def parse_tokens(self, tokens) -> None:
        # 映射到文法符号串
        symbols: List[str] = []
        positions: List[Tuple[int, int]] = []  # (line, col)
        for tk in tokens:
            sym = self.token_to_symbol(tk)
            symbols.append(sym)
            positions.append((getattr(tk, "line", None), getattr(tk, "col", None)))

        # 初始化分析栈
        stack: List[str] = [END_SYMBOL, self.grammar.start_symbol]
        i = 0

        # 调试：栈 + 剩余输入
        def log(action: str):
            if not self.debug:
                return
            stk = " ".join(stack[::-1])
            rest = " ".join(symbols[i : min(i + 12, len(symbols))])
            self.trace.append(f"{action:<20} | stack: [{stk}] | input: {rest}")

        log("INIT")
        while True:
            if not stack:
                # 栈空而输入未结束
                line, col = positions[max(0, i - 1)]
                raise ParseError("分析栈提前耗尽，输入尚未结束", line, col)

            X = stack.pop()
            a = symbols[i] if i < len(symbols) else END_SYMBOL

            if X == END_SYMBOL and a == END_SYMBOL:
                log("ACCEPT")
                return  # 接受

            if self.grammar.is_terminal(X) or X == END_SYMBOL:
                # 终结符：必须匹配
                if X == a:
                    log(f"match '{a}'")
                    i += 1
                    continue
                else:
                    line, col = positions[i]
                    raise ParseError(f"期望终结符 {X}，但看到 {a}", line, col)

            # 非终结符：查预测分析表
            prod = self.table.get(X, a)
            if prod is None:
                # 给出一点候选提示
                row = self.table.table.get(X, {})
                candidates = ", ".join(sorted(row.keys()))
                line, col = positions[i]
                raise ParseError(
                    f"在非终结符 {X} 处，对当前输入 {a} 无可用产生式（期望的是: {candidates}）", line, col
                )

            # 应用产生式：X → Y1 Y2 ... Yk
            rhs = list(prod.body)
            if len(rhs) == 1 and rhs[0] == EPSILON:
                log(f"reduce {prod}  (ε)")
                # ε 产生式：什么也不压
            else:
                # 逆序压栈
                for s in reversed(rhs):
                    stack.append(s)
                log(f"reduce {prod}")
