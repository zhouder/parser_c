# service/parser.py
from __future__ import annotations
from typing import List, Optional, Callable, Iterable, Set
from dataclasses import dataclass
from .lexer import Lexer
from .token import TokenType   # 假设你的 TokenType 定义如：RW/ID/NUM10/NUM8/NUM16/FLOAT/CS_STR/CS_CHAR/OP/DL/EOF
from . import ast

# ========== 小工具：按你的 TokenType 封装一些判断 ==========
TYPE_KEYWORDS = {"int", "char", "float", "double", "void"}
KW_UNION = "union"

def is_kw(tok, word: str) -> bool:
    return tok.type == TokenType.RW and tok.lexeme == word

def is_type_kw(tok) -> bool:
    return tok.type == TokenType.RW and tok.lexeme in TYPE_KEYWORDS

def is_union_kw(tok) -> bool:
    return tok.type == TokenType.RW and tok.lexeme == KW_UNION

def is_dl(tok, ch: str) -> bool:
    return tok.type == TokenType.DL and tok.lexeme == ch

def is_dl_or_op(tok, ch: str) -> bool:
    return (tok.type == TokenType.DL or tok.type == TokenType.OP) and tok.lexeme == ch

def is_op(tok, op: str) -> bool:
    return tok.type == TokenType.OP and tok.lexeme == op

def is_id(tok) -> bool:
    return tok.type == TokenType.ID

def is_const(tok) -> bool:
    return tok.type in (TokenType.NUM10, TokenType.NUM8, TokenType.NUM16,
                        TokenType.FLOAT, TokenType.CS_CHAR, TokenType.CS_STR)

# ========== 语法错误 ==========
@dataclass
class ParseError:
    line: int
    col: int
    msg: str

# ========== Parser ==========
class Parser:
    def __init__(self, lexer: Lexer):
        self.lexer = lexer
        self.lookahead = self.lexer.next_token()
        self.errors: List[ParseError] = []

    # ---- 基本移动/匹配 ----
    def advance(self):
        self.lookahead = self.lexer.next_token()

    def error(self, msg: str):
        self.errors.append(ParseError(getattr(self.lookahead, "line", -1),
                                      getattr(self.lookahead, "col", -1),
                                      msg))

    def match_kw(self, word: str):
        if is_kw(self.lookahead, word):
            t = self.lookahead; self.advance(); return t
        self.error(f"需要关键字 `{word}`，实际是 `{self.lookahead.lexeme}`")
        return None

    def match_dl(self, ch: str):
        if is_dl(self.lookahead, ch):
            t = self.lookahead; self.advance(); return t
        self.error(f"需要符号 `{ch}`，实际是 `{self.lookahead.lexeme}`")
        return None

    def match_op(self, op: str):
        if is_op(self.lookahead, op):
            t = self.lookahead; self.advance(); return t
        self.error(f"需要运算符 `{op}`，实际是 `{self.lookahead.lexeme}`")
        return None

    def match_id(self, expect: Optional[str]=None):
        if is_id(self.lookahead) and (expect is None or self.lookahead.lexeme == expect):
            t = self.lookahead; self.advance(); return t
        exp = expect or "标识符"
        self.error(f"需要 {exp}，实际是 `{self.lookahead.lexeme}`")
        return None

    def match_const(self):
        if is_const(self.lookahead):
            t = self.lookahead; self.advance(); return t
        self.error(f"需要常量，实际是 `{self.lookahead.lexeme}`")
        return None

    def synchronize(self, sync: Iterable[str] = (";", "}",)):
        # 简单错误恢复：丢弃直到遇到 ; 或 }
        sync_set = set(sync)
        while self.lookahead.type != TokenType.EOF and not (self.lookahead.type == TokenType.DL and self.lookahead.lexeme in sync_set):
            self.advance()
        if self.lookahead.type != TokenType.EOF:
            self.advance()

    # ========== Program / External ==========
    def parse_program(self) -> ast.Program:
        externals: List[ast.Node] = []
        while self.lookahead.type != TokenType.EOF:
            # 预处理：# include <...>
            if is_dl(self.lookahead, "#"):
                externals.append(self.parse_preprocess())
                continue
            # 类型/union 开头
            if is_type_kw(self.lookahead) or is_union_kw(self.lookahead):
                ext = self.parse_extdef()
                if ext: externals.append(ext)
                continue
            # 容错：其它开头直接报错并跳过
            self.error("文件最外层应为预处理指令、类型声明或函数定义")
            self.synchronize(sync=(";", "}"))
        return ast.Program(externals)

    def parse_preprocess(self) -> ast.Preprocess:
        # '#' 'include' '<' header '>'
        self.match_dl("#")
        if self.lookahead.lexeme == "include":  # 可能是 RW 或 ID；这里不强制类型
            self.advance()
        else:
            self.error("缺少 include")
        if is_dl_or_op(self.lookahead, "<"):
            self.advance()
            header = []
            # 聚合直到 >
            while not is_dl_or_op(self.lookahead, ">") and self.lookahead.type != TokenType.EOF:
                header.append(self.lookahead.lexeme)
                self.advance()
            if is_dl_or_op(self.lookahead, ">"):
                self.advance()
            else:
                self.error("缺少 >")
            return ast.Preprocess(header="".join(header))
        else:
            self.error("缺少 <header>")
            return ast.Preprocess(header="")

    def parse_extdef(self) -> Optional[ast.Node]:
        tps = self.parse_type_spec()
        ident = self.match_id()
        if ident is None: 
            self.synchronize(); 
            return None
        # 看看是否函数定义
        if is_dl(self.lookahead, "("):
            # 函数定义
            self.match_dl("(")
            params = self.parse_param_list_opt()
            self.match_dl(")")
            body = self.parse_compound_stmt()
            return ast.FuncDef(ret_type=tps, name=ident.lexeme, params=params, body=body)
        # 否则是变量声明列表（从第一个声明器已经读了 ID）
        items = [self.parse_init_decl_after_first(ident.lexeme)]
        while is_dl(self.lookahead, ","):
            self.advance()
            id2 = self.match_id()
            if id2 is None:
                self.synchronize(); break
            items.append(self.parse_init_decl_after_first(id2.lexeme))
        self.match_dl(";")
        return ast.Decl(type_spec=tps, items=items)

    # ========== Type / Decl ==========
    def parse_type_spec(self) -> ast.TypeSpec:
        # BasicType | UnionSpec
        if is_type_kw(self.lookahead):
            word = self.lookahead.lexeme; self.advance()
            return ast.TypeSpec(kind=word)
        if is_union_kw(self.lookahead):
            self.advance()
            name = None
            if is_id(self.lookahead):
                name = self.lookahead.lexeme; self.advance()
            members = None
            if is_dl(self.lookahead, "{"):
                members = self.parse_union_body()
            return ast.TypeSpec(kind="union", name=name, members=members)
        self.error("需要类型说明符")
        # 容错返回一个 void
        return ast.TypeSpec(kind="void")

    def parse_union_body(self) -> List[ast.MemberDecl]:
        # '{' MemberDeclList '}'
        members: List[ast.MemberDecl] = []
        self.match_dl("{")
        while not is_dl(self.lookahead, "}") and self.lookahead.type != TokenType.EOF:
            # MemberDecl → BasicType ID ArraySuffixOpt ';'
            if not (is_type_kw(self.lookahead)):
                self.error("联合体成员需要基本类型"); self.synchronize(sync=(";", "}")); 
                if is_dl(self.lookahead, "}"): break
                continue
            tps = ast.TypeSpec(kind=self.lookahead.lexeme); self.advance()
            name_tok = self.match_id()
            dims = self.parse_array_suffix_opt()
            self.match_dl(";")
            if name_tok:
                members.append(ast.MemberDecl(type_spec=tps, name=name_tok.lexeme, array_dims=dims))
        self.match_dl("}")
        return members

    def parse_array_suffix_opt(self) -> List[int]:
        dims: List[int] = []
        while is_dl(self.lookahead, "["):
            self.advance()
            if self.lookahead.type in (TokenType.NUM10, TokenType.NUM8, TokenType.NUM16):
                dims.append(int(self.lookahead.lexeme, 0))
                self.advance()
            else:
                self.error("数组维度需要整型常量")
            self.match_dl("]")
        return dims

    def parse_init_decl_after_first(self, name: str) -> ast.InitDecl:
        dims = self.parse_array_suffix_opt()
        init_expr = None
        if is_op(self.lookahead, "="):
            self.advance()
            init_expr = self.parse_expr()
        return ast.InitDecl(name=name, array_dims=dims, init=init_expr)

    # ========== Params ==========
    def parse_param_list_opt(self) -> List[ast.Param]:
        if is_dl(self.lookahead, ")"):
            return []
        # 空参数列表：允许 void()
        if is_kw(self.lookahead, "void"):
            # void) 视为空参；void,x 视为普通 void 形参
            save = self.lookahead
            self.advance()
            if is_dl(self.lookahead, ")"):
                return []
            # 回退逻辑简单：把 'void' 当成类型继续解析
            # 这里不做真正回退，直接以 'void' 已消耗为准
            tps = ast.TypeSpec(kind="void")
            name_tok = self.match_id()
            dims = self.parse_array_suffix_opt()
            params = [ast.Param(type_spec=tps, name=name_tok.lexeme if name_tok else "_", array_dims=dims)]
        else:
            params = [self.parse_param()]
        while is_dl(self.lookahead, ","):
            self.advance()
            params.append(self.parse_param())
        return params

    def parse_param(self) -> ast.Param:
        tps = self.parse_type_spec()
        name_tok = self.match_id()
        dims = self.parse_array_suffix_opt()
        return ast.Param(type_spec=tps, name=name_tok.lexeme if name_tok else "_", array_dims=dims)

    # ========== Statements ==========
    def parse_stmt(self) -> ast.Stmt:
        tok = self.lookahead
        # 局部声明
        if is_type_kw(tok) or is_union_kw(tok):
            decl = self.parse_decl_stmt()
            return decl
        # 复合语句
        if is_dl(tok, "{"):
            return self.parse_compound_stmt()
        # if
        if is_kw(tok, "if"):
            return self.parse_if_stmt()
        # while
        if is_kw(tok, "while"):
            return self.parse_while_stmt()
        # for
        if is_kw(tok, "for"):
            return self.parse_for_stmt()
        # return
        if is_kw(tok, "return"):
            return self.parse_return_stmt()
        # break/continue
        if is_kw(tok, "break"):
            self.advance(); self.match_dl(";"); return ast.BreakStmt()
        if is_kw(tok, "continue"):
            self.advance(); self.match_dl(";"); return ast.ContinueStmt()
        # 表达式/空语句
        if is_dl(tok, ";"):
            self.advance(); return ast.ExprStmt(expr=None)
        expr = self.parse_expr()
        self.match_dl(";")
        return ast.ExprStmt(expr=expr)

    def parse_decl_stmt(self) -> ast.DeclStmt:
        tps = self.parse_type_spec()
        # 至少一个 InitDecl
        first_id = self.match_id()
        items = [self.parse_init_decl_after_first(first_id.lexeme if first_id else "_")]
        while is_dl(self.lookahead, ","):
            self.advance()
            id2 = self.match_id()
            items.append(self.parse_init_decl_after_first(id2.lexeme if id2 else "_"))
        self.match_dl(";")
        return ast.DeclStmt(decl=ast.Decl(type_spec=tps, items=items))

    def parse_compound_stmt(self) -> ast.Compound:
        self.match_dl("{")
        items: List[ast.Stmt] = []
        while not is_dl(self.lookahead, "}") and self.lookahead.type != TokenType.EOF:
            try:
                items.append(self.parse_stmt())
            except Exception:
                # 兜底，避免死循环
                self.error("解析语句失败，尝试恢复")
                self.synchronize(sync=(";", "}"))
        self.match_dl("}")
        return ast.Compound(items=items)

    def parse_if_stmt(self) -> ast.IfStmt:
        self.match_kw("if")
        self.match_dl("(")
        cond = self.parse_expr()
        self.match_dl(")")
        then = self.parse_stmt()
        els = None
        if self.lookahead.type == TokenType.RW and self.lookahead.lexeme == "else":
            self.advance()
            els = self.parse_stmt()
        return ast.IfStmt(cond=cond, then=then, els=els)

    def parse_while_stmt(self) -> ast.WhileStmt:
        self.match_kw("while")
        self.match_dl("(")
        cond = self.parse_expr()
        self.match_dl(")")
        body = self.parse_stmt()
        return ast.WhileStmt(cond=cond, body=body)

    def parse_for_stmt(self) -> ast.ForStmt:
        self.match_kw("for")
        self.match_dl("(")
        init: Optional[ast.Node] = None
        if is_type_kw(self.lookahead) or is_union_kw(self.lookahead):
            init = self.parse_decl_stmt().decl
        elif not is_dl(self.lookahead, ";"):
            init = self.parse_expr()
        self.match_dl(";")
        cond = None if is_dl(self.lookahead, ";") else self.parse_expr()
        self.match_dl(";")
        step = None if is_dl(self.lookahead, ")") else self.parse_expr()
        self.match_dl(")")
        body = self.parse_stmt()
        return ast.ForStmt(init=init, cond=cond, step=step, body=body)

    def parse_return_stmt(self) -> ast.ReturnStmt:
        self.match_kw("return")
        if is_dl(self.lookahead, ";"):
            self.advance()
            return ast.ReturnStmt(value=None)
        val = self.parse_expr()
        self.match_dl(";")
        return ast.ReturnStmt(value=val)

    # ========== Expressions（按优先级多层） ==========
    def parse_expr(self) -> ast.Expr:
        return self.parse_assign_expr()

    def parse_assign_expr(self) -> ast.Expr:
        left = self.parse_or_expr()
        if is_op(self.lookahead, "="):
            # 右结合
            self.advance()
            right = self.parse_assign_expr()
            return ast.Assign(target=left, value=right)
        return left

    def parse_or_expr(self) -> ast.Expr:
        node = self.parse_and_expr()
        while self.lookahead.type == TokenType.OP and self.lookahead.lexeme == "||":
            op = self.lookahead.lexeme; self.advance()
            rhs = self.parse_and_expr()
            node = ast.Binary(op=op, left=node, right=rhs)
        return node

    def parse_and_expr(self) -> ast.Expr:
        node = self.parse_eq_expr()
        while self.lookahead.type == TokenType.OP and self.lookahead.lexeme == "&&":
            op = self.lookahead.lexeme; self.advance()
            rhs = self.parse_eq_expr()
            node = ast.Binary(op=op, left=node, right=rhs)
        return node

    def parse_eq_expr(self) -> ast.Expr:
        node = self.parse_rel_expr()
        while self.lookahead.type == TokenType.OP and self.lookahead.lexeme in ("==", "!="):
            op = self.lookahead.lexeme; self.advance()
            rhs = self.parse_rel_expr()
            node = ast.Binary(op=op, left=node, right=rhs)
        return node

    def parse_rel_expr(self) -> ast.Expr:
        node = self.parse_add_expr()
        while self.lookahead.type == TokenType.OP and self.lookahead.lexeme in ("<", ">", "<=", ">="):
            op = self.lookahead.lexeme; self.advance()
            rhs = self.parse_add_expr()
            node = ast.Binary(op=op, left=node, right=rhs)
        return node

    def parse_add_expr(self) -> ast.Expr:
        node = self.parse_mul_expr()
        while self.lookahead.type == TokenType.OP and self.lookahead.lexeme in ("+", "-"):
            op = self.lookahead.lexeme; self.advance()
            rhs = self.parse_mul_expr()
            node = ast.Binary(op=op, left=node, right=rhs)
        return node

    def parse_mul_expr(self) -> ast.Expr:
        node = self.parse_unary_expr()
        while self.lookahead.type == TokenType.OP and self.lookahead.lexeme in ("*", "/", "%"):
            op = self.lookahead.lexeme; self.advance()
            rhs = self.parse_unary_expr()
            node = ast.Binary(op=op, left=node, right=rhs)
        return node

    def parse_unary_expr(self) -> ast.Expr:
        if self.lookahead.type == TokenType.OP and self.lookahead.lexeme in ("+", "-", "!"):
            op = self.lookahead.lexeme; self.advance()
            expr = self.parse_unary_expr()
            return ast.Unary(op=op, expr=expr)
        return self.parse_postfix_expr()

    def parse_postfix_expr(self) -> ast.Expr:
        node = self.parse_primary()
        while True:
            # 函数调用
            if is_dl(self.lookahead, "("):
                self.advance()
                args = self.parse_arg_list_opt()
                self.match_dl(")")
                node = ast.Call(func=node, args=args)
                continue
            # 下标
            if is_dl(self.lookahead, "["):
                self.advance()
                idx = self.parse_expr()
                self.match_dl("]")
                node = ast.Index(seq=node, index=idx)
                continue
            # 成员访问
            if self.lookahead.type == TokenType.OP and self.lookahead.lexeme == ".":
                self.advance()
                name_tok = self.match_id()
                node = ast.Member(obj=node, name=name_tok.lexeme if name_tok else "_")
                continue
            # 后缀 ++/--
            if self.lookahead.type == TokenType.OP and self.lookahead.lexeme in ("++", "--"):
                op = self.lookahead.lexeme; self.advance()
                node = ast.Unary(op=f"post{op}", expr=node)
                continue
            break
        return node

    def parse_primary(self) -> ast.Expr:
        # ID / printf / 常量 / '(' Expr ')'
        if is_id(self.lookahead):
            name = self.lookahead.lexeme; self.advance()
            return ast.Identifier(name=name)
        # printf 被当成 RW 也能解析（按 Primary 处理）
        if self.lookahead.type == TokenType.RW and self.lookahead.lexeme == "printf":
            name = self.lookahead.lexeme; self.advance()
            return ast.Identifier(name=name)
        if is_const(self.lookahead):
            tok = self.lookahead; self.advance()
            kind = ("INT" if tok.type in (TokenType.NUM10, TokenType.NUM8, TokenType.NUM16)
                    else "FLOAT" if tok.type == TokenType.FLOAT
                    else "CHAR" if tok.type == TokenType.CS_CHAR
                    else "STRING")
            return ast.Constant(kind=kind, value=tok.lexeme)
        if is_dl(self.lookahead, "("):
            self.advance()
            e = self.parse_expr()
            self.match_dl(")")
            return e
        self.error(f"需要主表达式，实际是 `{self.lookahead.lexeme}`")
        # 返回一个占位标识符，避免后续崩溃
        bogus = ast.Identifier(name="_")
        self.advance()
        return bogus

    def parse_arg_list_opt(self) -> List[ast.Expr]:
        if is_dl(self.lookahead, ")"):
            return []
        args = [self.parse_expr()]
        while is_dl(self.lookahead, ","):
            self.advance()
            args.append(self.parse_expr())
        return args
