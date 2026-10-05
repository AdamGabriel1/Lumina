"""Helpers puros (sem estado) usados pelos visitors de expressão.

  - `_collect_var_refs` / `_collect_declared` — análise estática de
    lambdas (variáveis livres vs. declaradas).
  - `get_suggestion` — distância de Levenshtein para "did you mean?".
"""
from ...ast import VariableExpr, VarDecl, ForStmt, LambdaExpr


def _collect_var_refs(node, into):
    """Coleta todos os `VariableExpr` referenciados em `node`.

    Não recursiona em lambdas aninhadas (os params/locais delas
    não são "nossos").
    """
    if node is None:
        return
    if isinstance(node, (list, tuple)):
        for x in node:
            _collect_var_refs(x, into)
        return
    if isinstance(node, VariableExpr):
        into.add(node.name)
        return
    if isinstance(node, LambdaExpr):
        # Aninhada: só o body é nosso, os params são dela.
        _collect_var_refs(node.body, into)
        return
    if hasattr(node, '__dataclass_fields__'):
        for fname in node.__dataclass_fields__:
            if fname in ('line', 'col'):
                continue
            _collect_var_refs(getattr(node, fname, None), into)


def _collect_declared(node, into):
    """Coleta nomes declarados (VarDecl / ForStmt) dentro de `node`.

    Não recursiona em lambdas aninhadas.
    """
    if node is None:
        return
    if isinstance(node, (list, tuple)):
        for x in node:
            _collect_declared(x, into)
        return
    if isinstance(node, VarDecl):
        into.add(node.name)
        return
    if isinstance(node, ForStmt):
        into.add(node.var_name)
        _collect_declared(node.body, into)
        return
    if isinstance(node, LambdaExpr):
        return
    if hasattr(node, '__dataclass_fields__'):
        for fname in node.__dataclass_fields__:
            if fname in ('line', 'col'):
                continue
            _collect_declared(getattr(node, fname, None), into)


def get_suggestion(name, possible_names):
    """Calcula a distância de Levenshtein para sugerir nomes parecidos."""
    def levenshtein(s1, s2):
        if len(s1) < len(s2):
            return levenshtein(s2, s1)
        if len(s2) == 0:
            return len(s1)
        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        return previous_row[-1]

    best_match = None
    best_dist = 3
    for candidate in possible_names:
        dist = levenshtein(name, candidate)
        if dist < best_dist:
            best_dist = dist
            best_match = candidate
    return best_match