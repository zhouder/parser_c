from typing import Dict, Iterable, List, Set, Tuple

from .grammer import Grammar, Production, EPSILON, END_SYMBOL


def first_of_sequence(seq: Iterable[str], first_sets: Dict[str, Set[str]], grammar: Grammar) -> Set[str]:
    """
    计算一个符号串（可含 终结符/非终结符）的 FIRST 集
    规则：
      FIRST(αβ...) = FIRST(α) 去掉 ε，再看 α 是否可空；若可空，再并 FIRST(β)，以此类推；
      若所有都可空，则包含 ε。
    """
    result: Set[str] = set()
    nullable = True  # 记录前缀是否都可推出 ε
    for sym in seq:
        sym_first = set()
        if grammar.is_terminal(sym) or sym == EPSILON:
            sym_first.add(sym)
        else:
            sym_first |= first_sets[sym]

        result |= (sym_first - {EPSILON})
        if EPSILON not in sym_first:
            nullable = False
            break
    if nullable:
        result.add(EPSILON)
    return result


def compute_first_sets(grammar: Grammar) -> Dict[str, Set[str]]:
    first: Dict[str, Set[str]] = {}

    # 初始化：非终结符 -> 空集
    for nt in grammar.nonterminals:
        first[nt] = set()

    changed = True
    while changed:
        changed = False
        for prod in grammar.productions:
            A = prod.head
            alpha = prod.body

            # FIRST(alpha)
            alpha_first = set()
            # 逐符号推进
            nullable = True
            for X in alpha:
                if grammar.is_terminal(X) or X == EPSILON:
                    alpha_first.add(X)
                else:
                    alpha_first |= (first[X] - {EPSILON})
                    if EPSILON in first[X]:
                        alpha_first.add(EPSILON)
                if X == EPSILON or (not grammar.is_terminal(X) and EPSILON in first[X]):
                    # 当前符号可空，继续看后面
                    pass
                elif grammar.is_terminal(X):
                    # 终结符不可空
                    nullable = False
                    break
                else:
                    # 非终结符不可空
                    if EPSILON not in first[X]:
                        nullable = False
                        break
            if nullable:
                alpha_first.add(EPSILON)

            # 更新 FIRST(A)
            before = len(first[A])
            first[A] |= (alpha_first - {EPSILON})
            if EPSILON in alpha_first:
                first[A].add(EPSILON)
            if len(first[A]) != before:
                changed = True
    return first


def compute_follow_sets(grammar: Grammar, first_sets: Dict[str, Set[str]]) -> Dict[str, Set[str]]:
    follow: Dict[str, Set[str]] = {nt: set() for nt in grammar.nonterminals}
    follow[grammar.start_symbol].add(END_SYMBOL)

    changed = True
    while changed:
        changed = False
        for prod in grammar.productions:
            A = prod.head
            body = prod.body
            for i, B in enumerate(body):
                if not grammar.is_nonterminal(B):
                    continue
                beta = body[i + 1 :]
                if beta:
                    first_beta = first_of_sequence(beta, first_sets, grammar)
                    before = len(follow[B])
                    follow[B] |= (first_beta - {EPSILON})
                    if EPSILON in first_beta:
                        follow[B] |= follow[A]
                    if len(follow[B]) != before:
                        changed = True
                else:
                    before = len(follow[B])
                    follow[B] |= follow[A]
                    if len(follow[B]) != before:
                        changed = True
    return follow


def compute_select_sets(
    grammar: Grammar, first_sets: Dict[str, Set[str]], follow_sets: Dict[str, Set[str]]
) -> Dict[Production, Set[str]]:
    select: Dict[Production, Set[str]] = {}
    for prod in grammar.productions:
        A = prod.head
        alpha = prod.body
        first_alpha = first_of_sequence(alpha, first_sets, grammar)
        sel = set(first_alpha - {EPSILON})
        if EPSILON in first_alpha:
            sel |= follow_sets[A]
        select[prod] = sel
    return select
