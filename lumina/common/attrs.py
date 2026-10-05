"""Normalização de atributos `@nome(args)`.

Fonte única de verdade para parsing e normalização de attrs em todo
o compilador. Consumido por:
  - `lumina/codegen/context.py` (re-export)
  - `lumina/semantic/analyzer.py`
  - `lumina/semantic/derives.py`
  - `lumina/codegen/registration.py`
  - `lumina/codegen/function_body.py`
  - `lumina/codegen/generics.py`
  - `lumina/codegen/tco.py`

Formato canônico na AST: `List[Tuple[str, List[str]]]`.

    [("derive", ["Eq", "Debug"]), ("inline", [])]

Parsers antigos emitiam `List[str]`. Este módulo aceita ambos e
normaliza para o formato canônico, evitando que cada consumidor
tenha que adivinhar o formato.
"""
from typing import Any, List, Optional, Tuple


AttrTuple = Tuple[str, List[str]]


def normalize_attrs(attrs: Any) -> List[AttrTuple]:
    """Normaliza `attrs` para `List[Tuple[str, List[str]]]`.

    Aceita:
      - `None`                          → `[]`
      - `List[str]`                      → `[("inline", []), ...]`
      - `List[Tuple[str, List]]`         → normaliza args para strings
      - `List[Tuple[str, str, str]]`     → args viram lista
      - `List[List[str]]`                → args viram lista

    Entradas desconhecidas são **silenciosamente ignoradas** (não é
    papel desta função levantar erro de sintaxe — o parser já fez isso).
    """
    if not attrs:
        return []

    result: List[AttrTuple] = []
    for item in attrs:
        if isinstance(item, str):
            result.append((item, []))
        elif isinstance(item, tuple):
            if len(item) == 0:
                continue
            name = item[0]
            if not isinstance(name, str):
                continue
            raw_args = _extract_args(item)
            result.append((name, _normalize_args(raw_args)))
        elif isinstance(item, list):
            if not item:
                continue
            name = item[0]
            if not isinstance(name, str):
                continue
            raw_args = _extract_args(item)
            result.append((name, _normalize_args(raw_args)))
        # else: ignora
    return result


def _extract_args(item) -> Any:
    """Extrai o segmento de args de um item (tuple ou list).

    Formatos aceitos:
      (name,)              → []
      (name, [a, b])       → [a, b]
      (name, a, b)         → [a, b]
      [name]               → []
      [name, [a, b]]       → [a, b]
      [name, a, b]         → [a, b]

    `item` é tuple ou list. Assume `len(item) >= 1` e `item[0]` é str.
    """
    rest = list(item[1:])
    if not rest:
        return []
    # Formato canônico: (name, [args...]) — args já agrupados.
    if len(rest) == 1 and isinstance(rest[0], (list, tuple)):
        return list(rest[0])
    return rest


def _normalize_args(raw: Any) -> List[str]:
    """Converte args de um attr para `List[str]`."""
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, (list, tuple)):
        out: List[str] = []
        for a in raw:
            if isinstance(a, str):
                out.append(a)
            elif a is not None:
                out.append(str(a))
        return out
    return [str(raw)]


def attr_names(attrs: Any) -> List[str]:
    """Retorna apenas os nomes dos atributos (`["derive", "inline"]`)."""
    return [name for name, _args in normalize_attrs(attrs)]


def has_attr(attrs: Any, name: str) -> bool:
    """Retorna `True` se o atributo `name` está presente."""
    return any(n == name for n, _args in normalize_attrs(attrs))


def get_attr_args(attrs: Any, name: str) -> Optional[List[str]]:
    """Retorna os args do primeiro atributo `name`, ou `None` se ausente."""
    for n, args in normalize_attrs(attrs):
        if n == name:
            return args
    return None


__all__ = [
    "normalize_attrs",
    "attr_names",
    "has_attr",
    "get_attr_args",
    "AttrTuple",
]