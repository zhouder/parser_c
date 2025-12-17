from dataclasses import dataclass
from typing import Dict, List, Set, Tuple

# 统一用这个字符代表空串
EPSILON = "ε"
# 输入结束符
END_SYMBOL = "EOF"


@dataclass(frozen=True)
class Production:
    head: str
    body: Tuple[str, ...]  # 右部符号序列（若为 ε，采用 (EPSILON,)）

    def __str__(self) -> str:
        right = " ".join(self.body) if self.body else EPSILON
        return f"{self.head} → {right}"


class Grammar:
    def __init__(self, start_symbol: str):
        self.start_symbol: str = start_symbol
        self.productions: List[Production] = []
        self.nonterminals: Set[str] = set()
        self.terminals: Set[str] = set()
        self.prods_by_head: Dict[str, List[Production]] = {}

    # 添加产生式（body 为序列；若传入空列表表示 ε）
    def add(self, head: str, body: List[str]):
        if not body:
            body = [EPSILON]
        prod = Production(head, tuple(body))
        self.productions.append(prod)
        self.nonterminals.add(head)
        self.prods_by_head.setdefault(head, []).append(prod)
        return prod

    def finalize(self):
        # 统计所有终结符（出现于右部，且不在非终结符集合中，且不是 EPSILON）
        symbols: Set[str] = set()
        for p in self.productions:
            for s in p.body:
                symbols.add(s)
        # 终结符 = 所有右部符号 - 非终结符 - {ε}
        self.terminals = {s for s in symbols if s not in self.nonterminals and s != EPSILON}
        # 把 EOF 也放入终结符集合中（用于 FOLLOW/表）
        self.terminals.add(END_SYMBOL)

    def is_nonterminal(self, s: str) -> bool:
        return s in self.nonterminals

    def is_terminal(self, s: str) -> bool:
        return s in self.terminals

    def heads(self) -> List[str]:
        return list(self.prods_by_head.keys())


def build_grammar() -> Grammar:
    """
    基于实验文档的 LL(1) 文法（C 子集）。
    说明：
      - 仅支持 # include <...> 预处理行
      - 函数定义 vs 全局变量声明通过 ExtAfterId 进行左因子提取
      - for(init; cond; post) 中，若 init 是声明，写作 TypeSpec InitDeclList（分号由 for 自身提供）
      - 常量统一抽象为 INT_CONST / FLOAT_CONST / CHAR_CONST / STRING_CONST
    """
    G = Grammar(start_symbol="P")

    # === 顶层：程序 / 外部定义 ===
    G.add("P", ["ExtList", END_SYMBOL])
    G.add("ExtList", ["ExtDef", "ExtList"])
    G.add("ExtList", [])  # ε
    # 外部定义：预处理 或 TypeSpec (声明/函数定义) 或 TypeSpec ;
    # 说明：为了支持 `struct S { ... };` / `union U { ... };` 这种“只有类型定义”的语句，
    #      这里把 `TypeSpec` 后面的部分单独抽出来。
    G.add("ExtDef", ["Preprocess"])
    G.add("ExtDef", ["TypeSpec", "ExtAfterTypeSpec"])

    # TypeSpec 后续：允许指针 * 出现在第一个 ID 前；也允许单独的 ";"
    G.add("ExtAfterTypeSpec", ["PtrOpt", "ID", "ExtAfterId"])
    G.add("ExtAfterTypeSpec", [";"])

    # 预处理：# include < header >
    G.add("Preprocess", ["#", "include", "<", "Header", ">"])
    G.add("Header", ["ID", "HeaderRest"])
    G.add("HeaderRest", [".", "ID"])
    G.add("HeaderRest", [])  # ε

    # TypeSpec / Union / Struct / 基本类型
    G.add("TypeSpec", ["BasicType"])
    G.add("TypeSpec", ["UnionSpec"])
    G.add("TypeSpec", ["StructSpec"])
    # 额外：支持将 `struct student { ... };` 的标签名 `student` 作为类型名使用（类似 C++/typedef 的效果）
    G.add("TypeSpec", ["TYPE_NAME"])
    G.add("BasicType", ["int"])
    G.add("BasicType", ["char"])
    G.add("BasicType", ["float"])
    G.add("BasicType", ["double"])
    G.add("BasicType", ["void"])

    G.add("UnionSpec", ["union", "ID", "UnionBodyOpt"])
    G.add("UnionBodyOpt", ["{", "DeclListOpt", "}"])
    G.add("UnionBodyOpt", [])  # ε

    # struct 规格说明（简化）：struct ID { ... } 或 struct ID
    G.add("StructSpec", ["struct", "ID", "StructBodyOpt"])
    G.add("StructBodyOpt", ["{", "DeclListOpt", "}"])
    G.add("StructBodyOpt", [])  # ε
    G.add("DeclListOpt", ["DeclList"])
    G.add("DeclListOpt", [])  # ε
    G.add("DeclList", ["Decl", "DeclList"])
    G.add("DeclList", [])  # ε

    # TypeSpec ID 之后：函数 or 变量声明（第一个 ID 已经消耗）
    G.add("ExtAfterId", ["(", "ParamListOpt", ")", "CompoundStmt"])  # 函数定义
    G.add("ExtAfterId", ["VarDeclRest", ";"])  # 全局变量声明

    # 变量声明（首 ID 已读）后续部分
    G.add("VarDeclRest", ["ArraySuffixOpt", "InitOpt", "VarDeclMore"])
    G.add("VarDeclMore", [",", "InitDecl", "VarDeclMore"])
    G.add("VarDeclMore", [])  # ε

    # 一般声明（局部）
    G.add("Decl", ["TypeSpec", "InitDeclList", ";"])
    G.add("InitDeclList", ["InitDecl", "InitDeclListTail"])
    G.add("InitDeclListTail", [",", "InitDecl", "InitDeclListTail"])
    G.add("InitDeclListTail", [])  # ε

    # 指针声明（简化）：允许 * 出现在 ID 前，如 char *p;
    G.add("PtrOpt", ["*", "PtrOpt"])
    G.add("PtrOpt", [])  # ε

    G.add("InitDecl", ["PtrOpt", "ID", "ArraySuffixOpt", "InitOpt"])
    G.add("ArraySuffixOpt", ["[", "INT_CONST", "]", "ArraySuffixOpt"])
    G.add("ArraySuffixOpt", [])  # ε
    # 初始化（支持表达式与初始化列表）
    G.add("InitOpt", ["=", "Initializer"])
    G.add("InitOpt", [])  # ε

    # 初始化列表：{ a, b, {c, d} }
    G.add("Initializer", ["Expr"])
    G.add("Initializer", ["{", "InitListOpt", "}"])
    G.add("InitListOpt", ["InitList"])
    G.add("InitListOpt", [])  # ε
    G.add("InitList", ["Initializer", "InitListTail"])
    G.add("InitListTail", [",", "Initializer", "InitListTail"])
    G.add("InitListTail", [])  # ε

    # 函数定义 / 形参
    G.add("FuncDef", ["TypeSpec", "ID", "(", "ParamListOpt", ")", "CompoundStmt"])
    G.add("ParamListOpt", ["ParamList"])
    G.add("ParamListOpt", [])  # ε
    G.add("ParamList", ["Param", "ParamListTail"])
    G.add("ParamListTail", [",", "Param", "ParamListTail"])
    G.add("ParamListTail", [])  # ε
    G.add("Param", ["TypeSpec", "PtrOpt", "ID", "ArraySuffixOpt"])

    # 语句
    G.add("Stmt", ["ExprStmt"])
    G.add("Stmt", ["CompoundStmt"])
    G.add("Stmt", ["IfStmt"])
    G.add("Stmt", ["WhileStmt"])
    G.add("Stmt", ["ForStmt"])
    G.add("Stmt", ["ReturnStmt"])
    G.add("Stmt", ["BreakStmt"])
    G.add("Stmt", ["ContinueStmt"])
    G.add("Stmt", ["Decl"])

    G.add("CompoundStmt", ["{", "StmtListOpt", "}"])
    G.add("StmtListOpt", ["StmtList"])
    G.add("StmtListOpt", [])  # ε
    G.add("StmtList", ["Stmt", "StmtList"])
    G.add("StmtList", [])  # ε

    G.add("ExprStmt", ["Expr", ";"])
    G.add("ExprStmt", [";"])

    G.add("IfStmt", ["if", "(", "Expr", ")", "Stmt", "ElseOpt"])
    G.add("ElseOpt", ["else", "Stmt"])
    G.add("ElseOpt", [])  # ε

    G.add("WhileStmt", ["while", "(", "Expr", ")", "Stmt"])

    # for(init; cond; post) —— init 可为 声明 | 表达式 | ε
    G.add("ForStmt", ["for", "(", "ForInitOpt", ";", "ExprOpt", ";", "ExprOpt", ")", "Stmt"])
    G.add("ForInitOpt", ["DeclForInit"])
    G.add("ForInitOpt", ["Expr"])
    G.add("ForInitOpt", [])  # ε
    G.add("DeclForInit", ["TypeSpec", "InitDeclList"])  # 无分号，分号由 for 自己提供
    G.add("ExprOpt", ["Expr"])
    G.add("ExprOpt", [])  # ε

    G.add("ReturnStmt", ["return", "ExprOpt", ";"])
    G.add("BreakStmt", ["break", ";"])
    G.add("ContinueStmt", ["continue", ";"])

    # 表达式分层
    G.add("Expr", ["AssignExpr"])
    G.add("AssignExpr", ["OrExpr", "AssignTail"])
    G.add("AssignTail", ["=", "AssignExpr"])
    G.add("AssignTail", [])  # ε

    G.add("OrExpr", ["AndExpr", "OrTail"])
    G.add("OrTail", ["||", "AndExpr", "OrTail"])
    G.add("OrTail", [])  # ε

    G.add("AndExpr", ["EqExpr", "AndTail"])
    G.add("AndTail", ["&&", "EqExpr", "AndTail"])
    G.add("AndTail", [])  # ε

    G.add("EqExpr", ["RelExpr", "EqTail"])
    G.add("EqTail", ["==", "RelExpr", "EqTail"])
    G.add("EqTail", ["!=", "RelExpr", "EqTail"])
    G.add("EqTail", [])  # ε

    G.add("RelExpr", ["AddExpr", "RelTail"])
    G.add("RelTail", ["<", "AddExpr", "RelTail"])
    G.add("RelTail", [">", "AddExpr", "RelTail"])
    G.add("RelTail", ["<=", "AddExpr", "RelTail"])
    G.add("RelTail", [">=", "AddExpr", "RelTail"])
    G.add("RelTail", [])  # ε

    G.add("AddExpr", ["MulExpr", "AddTail"])
    G.add("AddTail", ["+", "MulExpr", "AddTail"])
    G.add("AddTail", ["-", "MulExpr", "AddTail"])
    G.add("AddTail", [])  # ε

    G.add("MulExpr", ["UnaryExpr", "MulTail"])
    G.add("MulTail", ["*", "UnaryExpr", "MulTail"])
    G.add("MulTail", ["/", "UnaryExpr", "MulTail"])
    G.add("MulTail", ["%", "UnaryExpr", "MulTail"])
    G.add("MulTail", [])  # ε

    G.add("UnaryExpr", ["+", "UnaryExpr"])
    G.add("UnaryExpr", ["-", "UnaryExpr"])
    G.add("UnaryExpr", ["!", "UnaryExpr"])
    G.add("UnaryExpr", ["PostfixExpr"])

    G.add("PostfixExpr", ["Primary", "PostfixTail"])
    G.add("PostfixTail", ["(", "ArgListOpt", ")", "PostfixTail"])
    G.add("PostfixTail", ["[", "Expr", "]", "PostfixTail"])
    G.add("PostfixTail", [".", "ID", "PostfixTail"])
    G.add("PostfixTail", ["++", "PostfixTail"])
    G.add("PostfixTail", ["--", "PostfixTail"])
    G.add("PostfixTail", [])  # ε

    G.add("Primary", ["ID"])
    G.add("Primary", ["printf"])
    G.add("Primary", ["CONSTANT"])
    G.add("Primary", ["(", "Expr", ")"])

    G.add("ArgListOpt", ["ArgList"])
    G.add("ArgListOpt", [])  # ε
    G.add("ArgList", ["Expr", "ArgListTail"])
    G.add("ArgListTail", [",", "Expr", "ArgListTail"])
    G.add("ArgListTail", [])  # ε

    G.add("CONSTANT", ["INT_CONST"])
    G.add("CONSTANT", ["FLOAT_CONST"])
    G.add("CONSTANT", ["CHAR_CONST"])
    G.add("CONSTANT", ["STRING_CONST"])

    G.finalize()
    return G
