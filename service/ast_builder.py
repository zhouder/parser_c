from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .grammer import EPSILON
from .parser import ParseTreeNode


@dataclass
class ASTNode:
    kind: str
    value: Optional[str] = None
    children: List["ASTNode"] = field(default_factory=list)

    def add(self, *nodes: Optional["ASTNode"]) -> "ASTNode":
        for n in nodes:
            if n is not None:
                self.children.append(n)
        return self


def _kids(node: ParseTreeNode) -> List[ParseTreeNode]:
    return [c for c in node.children if c.symbol != EPSILON]


def _first(node: ParseTreeNode) -> Optional[ParseTreeNode]:
    ks = _kids(node)
    return ks[0] if ks else None


def _tok_text(node: ParseTreeNode) -> str:
    if node.lexeme is not None and node.lexeme != "":
        return node.lexeme
    return node.symbol


def _as_leaf(node: ParseTreeNode) -> ASTNode:
    return ASTNode(kind=node.symbol, value=_tok_text(node))


def build_ast(root: ParseTreeNode) -> ASTNode:
    if root.symbol != "P":
        return ASTNode("Program").add(ASTNode("UnknownRoot", root.symbol))
    return _ast_P(root)


def _ast_P(node: ParseTreeNode) -> ASTNode:
    # P -> ExtList EOF
    ks = _kids(node)
    ext_list = ks[0] if ks else None
    prog = ASTNode("Program")
    if ext_list:
        prog.children.extend(_ast_ExtList(ext_list))
    return prog


def _ast_ExtList(node: ParseTreeNode) -> List[ASTNode]:
    # ExtList -> ExtDef ExtList | ε
    ks = _kids(node)
    if not ks:
        return []
    ext_def = ks[0]
    rest = ks[1] if len(ks) > 1 else None
    out: List[ASTNode] = []
    out.extend(_ast_ExtDef(ext_def))
    if rest is not None:
        out.extend(_ast_ExtList(rest))
    return out


def _ast_ExtDef(node: ParseTreeNode) -> List[ASTNode]:
    ks = _kids(node)
    if not ks:
        return []

    if ks[0].symbol == "Preprocess":
        return []

    # ExtDef -> TypeSpec ExtAfterTypeSpec
    type_spec = ks[0]
    after = ks[1] if len(ks) > 1 else None
    t = _ast_TypeSpec(type_spec)
    if after is None:
        return [ASTNode("External").add(t)]

    out = _ast_ExtAfterTypeSpec(after, t)
    return out


def _ast_TypeSpec(node: ParseTreeNode) -> ASTNode:
    ks = _kids(node)
    if not ks:
        return ASTNode("Type", "?")

    head = ks[0]
    if head.symbol == "BasicType":
        bt = _kids(head)
        name = _tok_text(bt[0]) if bt else "?"
        return ASTNode("Type", name)
    if head.symbol == "StructSpec":
        return _ast_StructSpec(head, as_type=True)
    if head.symbol == "UnionSpec":
        return _ast_UnionSpec(head, as_type=True)
    if head.symbol == "TYPE_NAME":
        return ASTNode("Type", _tok_text(head))
    return ASTNode("Type", head.symbol)


def _ast_StructSpec(node: ParseTreeNode, as_type: bool) -> ASTNode:
    # StructSpec -> struct ID StructBodyOpt
    ks = _kids(node)
    name = _tok_text(ks[1]) if len(ks) >= 2 else "?"
    body_opt = ks[2] if len(ks) >= 3 else None
    fields: List[ASTNode] = []
    has_body = False
    if body_opt is not None:
        body_ks = _kids(body_opt)
        if body_ks and body_ks[0].symbol == "{":
            has_body = True
            decl_list_opt = body_ks[1] if len(body_ks) >= 2 else None
            if decl_list_opt is not None:
                fields = _ast_DeclListOpt(decl_list_opt)

    if as_type:
        return ASTNode("StructType", name).add(ASTNode("Fields").add(*fields) if has_body else None)
    return ASTNode("StructDef", name).add(ASTNode("Fields").add(*fields) if has_body else None)


def _ast_UnionSpec(node: ParseTreeNode, as_type: bool) -> ASTNode:
    ks = _kids(node)
    name = _tok_text(ks[1]) if len(ks) >= 2 else "?"
    body_opt = ks[2] if len(ks) >= 3 else None
    fields: List[ASTNode] = []
    has_body = False
    if body_opt is not None:
        body_ks = _kids(body_opt)
        if body_ks and body_ks[0].symbol == "{":
            has_body = True
            decl_list_opt = body_ks[1] if len(body_ks) >= 2 else None
            if decl_list_opt is not None:
                fields = _ast_DeclListOpt(decl_list_opt)

    if as_type:
        return ASTNode("UnionType", name).add(ASTNode("Fields").add(*fields) if has_body else None)
    return ASTNode("UnionDef", name).add(ASTNode("Fields").add(*fields) if has_body else None)


def _ast_ExtAfterTypeSpec(node: ParseTreeNode, t: ASTNode) -> List[ASTNode]:
    # ExtAfterTypeSpec -> PtrOpt ID ExtAfterId | ;
    ks = _kids(node)
    if not ks:
        return [ASTNode("External").add(t)]
    if ks[0].symbol == ";":
        if t.kind in ("StructType", "UnionType") and any(c.kind == "Fields" for c in t.children):
            if t.kind == "StructType":
                return [ASTNode("StructDef", t.value).add(*t.children)]
            return [ASTNode("UnionDef", t.value).add(*t.children)]
        return [ASTNode("TypeOnly").add(t)]

    ptr_opt = ks[0]
    ident = ks[1]
    after_id = ks[2] if len(ks) > 2 else None
    name = _tok_text(ident)
    ptr = _ast_PtrOpt(ptr_opt)

    if after_id is not None and _kids(after_id) and _kids(after_id)[0].symbol == "(":
        return [ASTNode("FuncDef", name).add(t, ptr, *_ast_FuncAfterId(after_id))]
    return [ASTNode("GlobalDecl").add(t, ptr, *_ast_VarAfterId(after_id, first_name=name) if after_id else [])]


def _ast_FuncAfterId(node: ParseTreeNode) -> List[ASTNode]:
    # ExtAfterId -> ( ParamListOpt ) CompoundStmt
    ks = _kids(node)
    if not ks:
        return []
    params = ks[1] if len(ks) >= 2 else None
    body = ks[3] if len(ks) >= 4 else None
    out: List[ASTNode] = []
    if params is not None:
        out.append(ASTNode("Params").add(*_ast_ParamListOpt(params)))
    if body is not None:
        out.append(_ast_CompoundStmt(body))
    return out


def _ast_ParamListOpt(node: ParseTreeNode) -> List[ASTNode]:
    # ParamListOpt -> ParamList | ε
    ks = _kids(node)
    if not ks:
        return []
    return _ast_ParamList(ks[0])


def _ast_ParamList(node: ParseTreeNode) -> List[ASTNode]:
    # ParamList -> Param ParamListTail
    ks = _kids(node)
    if not ks:
        return []
    first = _ast_Param(ks[0])
    tail = ks[1] if len(ks) >= 2 else None
    out = [first] if first is not None else []
    if tail is not None:
        out.extend(_ast_ParamListTail(tail))
    return out


def _ast_ParamListTail(node: ParseTreeNode) -> List[ASTNode]:
    # ParamListTail -> , Param ParamListTail | ε
    ks = _kids(node)
    if not ks:
        return []
    param = _ast_Param(ks[1]) if len(ks) >= 2 else None
    rest = ks[2] if len(ks) >= 3 else None
    out = [param] if param is not None else []
    if rest is not None:
        out.extend(_ast_ParamListTail(rest))
    return out


def _ast_Param(node: ParseTreeNode) -> Optional[ASTNode]:
    # Param -> TypeSpec PtrOpt ID ArraySuffixOpt
    ks = _kids(node)
    if len(ks) < 3:
        return None
    t = _ast_TypeSpec(ks[0])
    ptr = _ast_PtrOpt(ks[1])
    name = _tok_text(ks[2])
    dims = _ast_ArraySuffixOpt(ks[3]) if len(ks) >= 4 else []
    p = ASTNode("Param", name).add(ASTNode("Type").add(t), ptr)
    if dims:
        p.add(ASTNode("ArrayDims").add(*[ASTNode("Dim", d) for d in dims]))
    return p


def _ast_VarAfterId(node: ParseTreeNode, first_name: str) -> List[ASTNode]:
    # ExtAfterId -> VarDeclRest ;
    ks = _kids(node)
    if not ks:
        return []
    var_decl_rest = ks[0]
    decls = _ast_VarDeclRest(var_decl_rest, first_name)
    return [ASTNode("Decls").add(*decls)]


def _ast_DeclListOpt(node: ParseTreeNode) -> List[ASTNode]:
    # DeclListOpt -> DeclList | ε
    ks = _kids(node)
    if not ks:
        return []
    return _ast_DeclList(ks[0])


def _ast_DeclList(node: ParseTreeNode) -> List[ASTNode]:
    # DeclList -> Decl DeclList | ε
    ks = _kids(node)
    if not ks:
        return []
    decl = ks[0]
    rest = ks[1] if len(ks) > 1 else None
    out = _ast_Decl(decl)
    if rest is not None:
        out.extend(_ast_DeclList(rest))
    return out


def _ast_Decl(node: ParseTreeNode) -> List[ASTNode]:
    # Decl -> TypeSpec InitDeclList ;
    ks = _kids(node)
    if len(ks) < 2:
        return [ASTNode("DeclUnknown")]
    t = _ast_TypeSpec(ks[0])
    decls = _ast_InitDeclList(ks[1], t)
    return decls


def _ast_PtrOpt(node: ParseTreeNode) -> Optional[ASTNode]:
    # PtrOpt -> * PtrOpt | ε
    ks = _kids(node)
    if not ks:
        return None
    count = 0
    cur = node
    while True:
        cur_ks = _kids(cur)
        if not cur_ks or cur_ks[0].symbol != "*":
            break
        count += 1
        cur = cur_ks[1] if len(cur_ks) > 1 else cur
        if cur is node:
            break
    return ASTNode("Ptr", "*" * count)


def _ast_InitDeclList(node: ParseTreeNode, t: ASTNode) -> List[ASTNode]:
    # InitDeclList -> InitDecl InitDeclListTail | ε
    ks = _kids(node)
    if not ks:
        return []
    first = _ast_InitDecl(ks[0], t)
    tail = ks[1] if len(ks) > 1 else None
    out = [first] if first is not None else []
    if tail is not None:
        out.extend(_ast_InitDeclListTail(tail, t))
    return out


def _ast_InitDeclListTail(node: ParseTreeNode, t: ASTNode) -> List[ASTNode]:
    # InitDeclListTail -> , InitDecl InitDeclListTail | ε
    ks = _kids(node)
    if not ks:
        return []
    init_decl = ks[1] if len(ks) >= 2 else None
    rest = ks[2] if len(ks) >= 3 else None
    out: List[ASTNode] = []
    if init_decl is not None:
        d = _ast_InitDecl(init_decl, t)
        if d is not None:
            out.append(d)
    if rest is not None:
        out.extend(_ast_InitDeclListTail(rest, t))
    return out


def _ast_InitDecl(node: ParseTreeNode, t: ASTNode) -> Optional[ASTNode]:
    # InitDecl -> PtrOpt ID ArraySuffixOpt InitOpt
    ks = _kids(node)
    if len(ks) < 2:
        return None
    ptr = _ast_PtrOpt(ks[0])
    name = _tok_text(ks[1])
    arr = _ast_ArraySuffixOpt(ks[2]) if len(ks) >= 3 else []
    init = _ast_InitOpt(ks[3]) if len(ks) >= 4 else None
    decl = ASTNode("VarDecl", name).add(ASTNode("Type").add(t), ptr)
    if arr:
        decl.add(ASTNode("ArrayDims").add(*[ASTNode("Dim", d) for d in arr]))
    if init is not None:
        decl.add(ASTNode("Init").add(init))
    return decl


def _ast_ArraySuffixOpt(node: ParseTreeNode) -> List[str]:
    # ArraySuffixOpt -> [ INT_CONST ] ArraySuffixOpt | ε
    ks = _kids(node)
    if not ks:
        return []
    dim = _tok_text(ks[1]) if len(ks) >= 2 else "?"
    rest = ks[3] if len(ks) >= 4 else None
    out = [dim]
    if rest is not None:
        out.extend(_ast_ArraySuffixOpt(rest))
    return out


def _ast_InitOpt(node: ParseTreeNode) -> Optional[ASTNode]:
    # InitOpt -> = Initializer | ε
    ks = _kids(node)
    if not ks:
        return None
    if len(ks) >= 2 and ks[0].symbol == "=":
        return _ast_Initializer(ks[1])
    return None


def _ast_Initializer(node: ParseTreeNode) -> ASTNode:
    # Initializer -> Expr | { InitListOpt }
    ks = _kids(node)
    if not ks:
        return ASTNode("Init", "?")
    if ks[0].symbol == "{":
        init_list_opt = ks[1] if len(ks) >= 2 else None
        items = _ast_InitListOpt(init_list_opt) if init_list_opt is not None else []
        return ASTNode("InitList").add(*items)
    return _ast_Expr(ks[0])


def _ast_InitListOpt(node: ParseTreeNode) -> List[ASTNode]:
    # InitListOpt -> InitList | ε
    ks = _kids(node)
    if not ks:
        return []
    return _ast_InitList(ks[0])


def _ast_InitList(node: ParseTreeNode) -> List[ASTNode]:
    # InitList -> Initializer InitListTail
    ks = _kids(node)
    if not ks:
        return []
    first = _ast_Initializer(ks[0])
    tail = ks[1] if len(ks) > 1 else None
    out = [first]
    if tail is not None:
        out.extend(_ast_InitListTail(tail))
    return out


def _ast_InitListTail(node: ParseTreeNode) -> List[ASTNode]:
    # InitListTail -> , Initializer InitListTail | ε
    ks = _kids(node)
    if not ks:
        return []
    init = _ast_Initializer(ks[1]) if len(ks) >= 2 else ASTNode("Init", "?")
    rest = ks[2] if len(ks) >= 3 else None
    out = [init]
    if rest is not None:
        out.extend(_ast_InitListTail(rest))
    return out


def _ast_CompoundStmt(node: ParseTreeNode) -> ASTNode:
    # CompoundStmt -> { StmtListOpt }
    ks = _kids(node)
    stmt_list_opt = ks[1] if len(ks) >= 2 else None
    stmts = _ast_StmtListOpt(stmt_list_opt) if stmt_list_opt is not None else []
    return ASTNode("Block").add(*stmts)


def _ast_StmtListOpt(node: ParseTreeNode) -> List[ASTNode]:
    ks = _kids(node)
    if not ks:
        return []
    return _ast_StmtList(ks[0])


def _ast_StmtList(node: ParseTreeNode) -> List[ASTNode]:
    ks = _kids(node)
    if not ks:
        return []
    stmt = _ast_Stmt(ks[0])
    rest = ks[1] if len(ks) > 1 else None
    out = [stmt] if stmt is not None else []
    if rest is not None:
        out.extend(_ast_StmtList(rest))
    return out


def _ast_Stmt(node: ParseTreeNode) -> Optional[ASTNode]:
    ks = _kids(node)
    if not ks:
        return None
    head = ks[0]
    if head.symbol == "ExprStmt":
        return _ast_ExprStmt(head)
    if head.symbol == "CompoundStmt":
        return _ast_CompoundStmt(head)
    if head.symbol == "IfStmt":
        return _ast_IfStmt(head)
    if head.symbol == "WhileStmt":
        return _ast_WhileStmt(head)
    if head.symbol == "ForStmt":
        return _ast_ForStmt(head)
    if head.symbol == "ReturnStmt":
        return _ast_ReturnStmt(head)
    if head.symbol == "BreakStmt":
        return ASTNode("Break")
    if head.symbol == "ContinueStmt":
        return ASTNode("Continue")
    if head.symbol == "Decl":
        decls = _ast_Decl(head)
        return ASTNode("DeclStmt").add(*decls)
    return ASTNode("Stmt", head.symbol)


def _ast_ExprStmt(node: ParseTreeNode) -> ASTNode:
    # ExprStmt -> Expr ; | ;
    ks = _kids(node)
    if not ks:
        return ASTNode("Empty")
    if len(ks) == 1 and ks[0].symbol == ";":
        return ASTNode("Empty")
    expr = _ast_Expr(ks[0]) if ks else ASTNode("Expr", "?")
    return ASTNode("ExprStmt").add(expr)


def _ast_IfStmt(node: ParseTreeNode) -> ASTNode:
    # if ( Expr ) Stmt ElseOpt
    ks = _kids(node)
    cond = _ast_Expr(ks[2]) if len(ks) >= 3 else ASTNode("Expr", "?")
    then = _ast_Stmt(ks[4]) if len(ks) >= 5 else None
    else_opt = ks[5] if len(ks) >= 6 else None
    els = _ast_ElseOpt(else_opt) if else_opt is not None else None
    return ASTNode("If").add(ASTNode("Cond").add(cond), ASTNode("Then").add(then) if then else None, ASTNode("Else").add(els) if els else None)


def _ast_ElseOpt(node: ParseTreeNode) -> Optional[ASTNode]:
    ks = _kids(node)
    if not ks:
        return None
    if ks[0].symbol == "else":
        return _ast_Stmt(ks[1]) if len(ks) >= 2 else None
    return None


def _ast_WhileStmt(node: ParseTreeNode) -> ASTNode:
    ks = _kids(node)
    cond = _ast_Expr(ks[2]) if len(ks) >= 3 else ASTNode("Expr", "?")
    body = _ast_Stmt(ks[4]) if len(ks) >= 5 else None
    return ASTNode("While").add(ASTNode("Cond").add(cond), ASTNode("Body").add(body) if body else None)


def _ast_ForStmt(node: ParseTreeNode) -> ASTNode:
    # for ( ForInitOpt ; ExprOpt ; ExprOpt ) Stmt
    ks = _kids(node)
    init = _ast_ForInitOpt(ks[2]) if len(ks) >= 3 else None
    cond = _ast_ExprOpt(ks[4]) if len(ks) >= 5 else None
    post = _ast_ExprOpt(ks[6]) if len(ks) >= 7 else None
    body = _ast_Stmt(ks[8]) if len(ks) >= 9 else None
    return ASTNode("For").add(ASTNode("Init").add(init) if init else None, ASTNode("Cond").add(cond) if cond else None, ASTNode("Post").add(post) if post else None, ASTNode("Body").add(body) if body else None)


def _ast_ForInitOpt(node: ParseTreeNode) -> Optional[ASTNode]:
    ks = _kids(node)
    if not ks:
        return None
    head = ks[0]
    if head.symbol == "DeclForInit":
        return _ast_DeclForInit(head)
    if head.symbol == "Expr":
        return _ast_Expr(head)
    return None


def _ast_DeclForInit(node: ParseTreeNode) -> ASTNode:
    # DeclForInit -> TypeSpec InitDeclList
    ks = _kids(node)
    t = _ast_TypeSpec(ks[0]) if ks else ASTNode("Type", "?")
    decls = _ast_InitDeclList(ks[1], t) if len(ks) >= 2 else []
    return ASTNode("DeclForInit").add(*decls)


def _ast_ReturnStmt(node: ParseTreeNode) -> ASTNode:
    # return ExprOpt ;
    ks = _kids(node)
    expr_opt = ks[1] if len(ks) >= 2 else None
    expr = _ast_ExprOpt(expr_opt) if expr_opt is not None else None
    return ASTNode("Return").add(expr)


def _ast_ExprOpt(node: ParseTreeNode) -> Optional[ASTNode]:
    ks = _kids(node)
    if not ks:
        return None
    return _ast_Expr(ks[0])


def _ast_Expr(node: ParseTreeNode) -> ASTNode:
    ks = _kids(node)
    if not ks:
        return ASTNode("Expr", "?")
    return _ast_AssignExpr(ks[0])


def _ast_AssignExpr(node: ParseTreeNode) -> ASTNode:
    ks = _kids(node)
    left = _ast_OrExpr(ks[0]) if ks else ASTNode("Expr", "?")
    tail = ks[1] if len(ks) >= 2 else None
    if tail is None:
        return left
    tks = _kids(tail)
    if not tks:
        return left
    if tks[0].symbol == "=":
        right = _ast_AssignExpr(tks[1]) if len(tks) >= 2 else ASTNode("Expr", "?")
        return ASTNode("Assign").add(left, right)
    return left


def _fold_tail(left: ASTNode, tail: ParseTreeNode, op_sym: str, rhs_symbol: str, next_tail_symbol: str, rhs_fn, tail_fn):
    cur = left
    t = tail
    while True:
        tks = _kids(t)
        if not tks:
            break
        if tks[0].symbol != op_sym:
            break
        rhs = rhs_fn(tks[1]) if len(tks) >= 2 else ASTNode("Expr", "?")
        cur = ASTNode("Binary", op_sym).add(cur, rhs)
        nxt = tks[2] if len(tks) >= 3 else None
        if nxt is None or nxt.symbol != next_tail_symbol:
            break
        t = nxt
    return cur


def _ast_OrExpr(node: ParseTreeNode) -> ASTNode:
    ks = _kids(node)
    left = _ast_AndExpr(ks[0]) if ks else ASTNode("Expr", "?")
    tail = ks[1] if len(ks) >= 2 else None
    return _fold_tail(left, tail, "||", "AndExpr", "OrTail", _ast_AndExpr, _ast_OrExpr) if tail else left


def _ast_AndExpr(node: ParseTreeNode) -> ASTNode:
    ks = _kids(node)
    left = _ast_EqExpr(ks[0]) if ks else ASTNode("Expr", "?")
    tail = ks[1] if len(ks) >= 2 else None
    return _fold_tail(left, tail, "&&", "EqExpr", "AndTail", _ast_EqExpr, _ast_AndExpr) if tail else left


def _ast_EqExpr(node: ParseTreeNode) -> ASTNode:
    ks = _kids(node)
    left = _ast_RelExpr(ks[0]) if ks else ASTNode("Expr", "?")
    tail = ks[1] if len(ks) >= 2 else None
    if not tail:
        return left
    tks = _kids(tail)
    cur = left
    t = tail
    while True:
        tks = _kids(t)
        if not tks:
            break
        op = tks[0].symbol
        if op not in ("==", "!="):
            break
        rhs = _ast_RelExpr(tks[1]) if len(tks) >= 2 else ASTNode("Expr", "?")
        cur = ASTNode("Binary", op).add(cur, rhs)
        t = tks[2] if len(tks) >= 3 else None
        if t is None:
            break
    return cur


def _ast_RelExpr(node: ParseTreeNode) -> ASTNode:
    ks = _kids(node)
    left = _ast_AddExpr(ks[0]) if ks else ASTNode("Expr", "?")
    tail = ks[1] if len(ks) >= 2 else None
    if not tail:
        return left
    cur = left
    t = tail
    while True:
        tks = _kids(t)
        if not tks:
            break
        op = tks[0].symbol
        if op not in ("<", ">", "<=", ">="):
            break
        rhs = _ast_AddExpr(tks[1]) if len(tks) >= 2 else ASTNode("Expr", "?")
        cur = ASTNode("Binary", op).add(cur, rhs)
        t = tks[2] if len(tks) >= 3 else None
        if t is None:
            break
    return cur


def _ast_AddExpr(node: ParseTreeNode) -> ASTNode:
    ks = _kids(node)
    left = _ast_MulExpr(ks[0]) if ks else ASTNode("Expr", "?")
    tail = ks[1] if len(ks) >= 2 else None
    if not tail:
        return left
    cur = left
    t = tail
    while True:
        tks = _kids(t)
        if not tks:
            break
        op = tks[0].symbol
        if op not in ("+", "-"):
            break
        rhs = _ast_MulExpr(tks[1]) if len(tks) >= 2 else ASTNode("Expr", "?")
        cur = ASTNode("Binary", op).add(cur, rhs)
        t = tks[2] if len(tks) >= 3 else None
        if t is None:
            break
    return cur


def _ast_MulExpr(node: ParseTreeNode) -> ASTNode:
    ks = _kids(node)
    left = _ast_UnaryExpr(ks[0]) if ks else ASTNode("Expr", "?")
    tail = ks[1] if len(ks) >= 2 else None
    if not tail:
        return left
    cur = left
    t = tail
    while True:
        tks = _kids(t)
        if not tks:
            break
        op = tks[0].symbol
        if op not in ("*", "/", "%"):
            break
        rhs = _ast_UnaryExpr(tks[1]) if len(tks) >= 2 else ASTNode("Expr", "?")
        cur = ASTNode("Binary", op).add(cur, rhs)
        t = tks[2] if len(tks) >= 3 else None
        if t is None:
            break
    return cur


def _ast_UnaryExpr(node: ParseTreeNode) -> ASTNode:
    ks = _kids(node)
    if not ks:
        return ASTNode("Expr", "?")
    if ks[0].symbol in ("+", "-", "!") and len(ks) >= 2:
        return ASTNode("Unary", ks[0].symbol).add(_ast_UnaryExpr(ks[1]))
    return _ast_PostfixExpr(ks[0])


def _ast_PostfixExpr(node: ParseTreeNode) -> ASTNode:
    ks = _kids(node)
    if not ks:
        return ASTNode("Expr", "?")
    base = _ast_Primary(ks[0])
    tail = ks[1] if len(ks) >= 2 else None
    return _ast_PostfixTail(base, tail) if tail is not None else base


def _ast_PostfixTail(base: ASTNode, node: ParseTreeNode) -> ASTNode:
    cur = base
    t = node
    while True:
        ks = _kids(t)
        if not ks:
            break
        head = ks[0].symbol
        if head == "(":
            args_opt = ks[1] if len(ks) >= 2 else None
            args = _ast_ArgListOpt(args_opt) if args_opt is not None else []
            cur = ASTNode("Call").add(cur, ASTNode("Args").add(*args))
            t = ks[3] if len(ks) >= 4 else None
        elif head == "[":
            idx = _ast_Expr(ks[1]) if len(ks) >= 2 else ASTNode("Expr", "?")
            cur = ASTNode("Index").add(cur, idx)
            t = ks[3] if len(ks) >= 4 else None
        elif head == ".":
            member = _tok_text(ks[1]) if len(ks) >= 2 else "?"
            cur = ASTNode("Member", member).add(cur)
            t = ks[2] if len(ks) >= 3 else None
        elif head == "++":
            cur = ASTNode("PostInc").add(cur)
            t = ks[1] if len(ks) >= 2 else None
        elif head == "--":
            cur = ASTNode("PostDec").add(cur)
            t = ks[1] if len(ks) >= 2 else None
        else:
            break
        if t is None:
            break
    return cur


def _ast_Primary(node: ParseTreeNode) -> ASTNode:
    ks = _kids(node)
    if not ks:
        return ASTNode("Expr", "?")
    head = ks[0]
    if head.symbol in ("ID", "TYPE_NAME"):
        return ASTNode("Id", _tok_text(head))
    if head.symbol == "printf":
        return ASTNode("Id", "printf")
    if head.symbol == "CONSTANT":
        return _ast_CONSTANT(head)
    if head.symbol == "(" and len(ks) >= 2:
        return _ast_Expr(ks[1])
    return _as_leaf(head)


def _ast_CONSTANT(node: ParseTreeNode) -> ASTNode:
    ks = _kids(node)
    if not ks:
        return ASTNode("Literal", "?")
    leaf = ks[0]
    return ASTNode("Literal", _tok_text(leaf))


def _ast_ArgListOpt(node: ParseTreeNode) -> List[ASTNode]:
    ks = _kids(node)
    if not ks:
        return []
    return _ast_ArgList(ks[0])


def _ast_ArgList(node: ParseTreeNode) -> List[ASTNode]:
    # ArgList -> Expr ArgListTail
    ks = _kids(node)
    if not ks:
        return []
    first = _ast_Expr(ks[0])
    tail = ks[1] if len(ks) >= 2 else None
    out = [first]
    if tail is not None:
        out.extend(_ast_ArgListTail(tail))
    return out


def _ast_ArgListTail(node: ParseTreeNode) -> List[ASTNode]:
    # ArgListTail -> , Expr ArgListTail | ε
    ks = _kids(node)
    if not ks:
        return []
    expr = _ast_Expr(ks[1]) if len(ks) >= 2 else ASTNode("Expr", "?")
    rest = ks[2] if len(ks) >= 3 else None
    out = [expr]
    if rest is not None:
        out.extend(_ast_ArgListTail(rest))
    return out


def _ast_VarDeclRest(node: ParseTreeNode, first_name: str) -> List[ASTNode]:
    # VarDeclRest -> ArraySuffixOpt InitOpt VarDeclMore
    ks = _kids(node)
    if len(ks) < 3:
        return [ASTNode("Var", first_name)]
    arr = _ast_ArraySuffixOpt(ks[0])
    init = _ast_InitOpt(ks[1])
    first = ASTNode("Var", first_name)
    if arr:
        first.add(ASTNode("ArrayDims").add(*[ASTNode("Dim", d) for d in arr]))
    if init is not None:
        first.add(ASTNode("Init").add(init))
    more = _ast_VarDeclMore(ks[2])
    return [first] + more


def _ast_VarDeclMore(node: ParseTreeNode) -> List[ASTNode]:
    # VarDeclMore -> , InitDecl VarDeclMore | ε
    ks = _kids(node)
    if not ks:
        return []
    init_decl = ks[1] if len(ks) >= 2 else None
    rest = ks[2] if len(ks) >= 3 else None
    out: List[ASTNode] = []
    if init_decl is not None:
        iks = _kids(init_decl)
        name = _tok_text(iks[1]) if len(iks) >= 2 else "?"
        arr = _ast_ArraySuffixOpt(iks[2]) if len(iks) >= 3 else []
        init = _ast_InitOpt(iks[3]) if len(iks) >= 4 else None
        v = ASTNode("Var", name)
        if arr:
            v.add(ASTNode("ArrayDims").add(*[ASTNode("Dim", d) for d in arr]))
        if init is not None:
            v.add(ASTNode("Init").add(init))
        out.append(v)
    if rest is not None:
        out.extend(_ast_VarDeclMore(rest))
    return out
