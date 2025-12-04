# service/ast.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Union

# ---- 基类 ----
@dataclass
class Node: 
    pass

# ---- 顶层 ----
@dataclass
class Program(Node):
    externals: List[Node] = field(default_factory=list)

@dataclass
class Preprocess(Node):
    header: str

# ---- 类型 / 声明 ----
@dataclass
class TypeSpec(Node):
    kind: str                 # 'int'/'char'/'float'/'double'/'void'/'union'
    name: Optional[str] = None  # union 的标签名
    members: Optional[List["MemberDecl"]] = None

@dataclass
class MemberDecl(Node):
    type_spec: TypeSpec
    name: str
    array_dims: List[int] = field(default_factory=list)

@dataclass
class Decl(Node):
    type_spec: TypeSpec
    items: List["InitDecl"]   # a, b=1, c[2]...

@dataclass
class InitDecl(Node):
    name: str
    array_dims: List[int] = field(default_factory=list)
    init: Optional["Expr"] = None

# ---- 函数 ----
@dataclass
class Param(Node):
    type_spec: TypeSpec
    name: str
    array_dims: List[int] = field(default_factory=list)

@dataclass
class FuncDef(Node):
    ret_type: TypeSpec
    name: str
    params: List[Param]
    body: "Compound"

# ---- 语句 ----
class Stmt(Node):
    pass

@dataclass
class Compound(Stmt):
    items: List[Stmt] = field(default_factory=list)

@dataclass
class IfStmt(Stmt):
    cond: "Expr"
    then: Stmt
    els: Optional[Stmt] = None

@dataclass
class WhileStmt(Stmt):
    cond: "Expr"
    body: Stmt

@dataclass
class ForStmt(Stmt):
    init: Optional[Union[Decl, "Expr"]]  # Decl 或 Expr 或 None
    cond: Optional["Expr"]
    step: Optional["Expr"]
    body: Stmt

@dataclass
class ReturnStmt(Stmt):
    value: Optional["Expr"]

@dataclass
class BreakStmt(Stmt):
    pass

@dataclass
class ContinueStmt(Stmt):
    pass

@dataclass
class DeclStmt(Stmt):
    decl: Decl

@dataclass
class ExprStmt(Stmt):
    expr: Optional["Expr"]   # None 表示空语句（若你不需要空语句，可改为必填）

# ---- 表达式 ----
class Expr(Node):
    pass

@dataclass
class Assign(Expr):
    target: "Expr"
    value: "Expr"

@dataclass
class Binary(Expr):
    op: str
    left: Expr
    right: Expr

@dataclass
class Unary(Expr):
    op: str
    expr: Expr

@dataclass
class Call(Expr):
    func: "Expr"
    args: List[Expr]

@dataclass
class Index(Expr):
    seq: Expr
    index: Expr

@dataclass
class Member(Expr):
    obj: Expr
    name: str

@dataclass
class Identifier(Expr):
    name: str

@dataclass
class Constant(Expr):
    kind: str     # INT/FLOAT/CHAR/STRING
    value: str
