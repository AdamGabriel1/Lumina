"""Regras de compatibilidade de tipos do Lumina.

Única fonte de verdade para `is_assignable`. Consumida por VarDecl,
AssignStmt, ReturnStmt e (futuramente) por validação de argumentos.

v0.8.0: suporte a `[T]` (slice).
"""

PRIMITIVES = {"int", "float", "bool", "str", "ptr", "fn", "void"}


def _base(t: str) -> str:
    """Remove args de generic: 'Box<int>' -> 'Box'."""
    return t.split("<", 1)[0] if t else t


def _is_type_param(t: str) -> bool:
    """Um type param genérico é uma letra maiúscula sozinha (T, U, V, ...).

    ADR 0003: `"auto"` também é tratado como type param — é o tipo
    dos parâmetros de macro sem anotação, aceitos em qualquer posição
    sem checagem.
    """
    if not t:
        return False
    if t == "auto":
        return True
    return len(t) == 1 and t.isupper()


def _is_slice_type(t: str) -> bool:
    """`[T]` → True. `[]` → False."""
    return bool(t) and len(t) >= 2 and t[0] == "[" and t[-1] == "]"


def _slice_inner(t: str) -> str:
    """`[T]` → `T`."""
    return t[1:-1]


def _split_top_level(s):
    """Split por vírgula ignorando vírgulas dentro de parênteses ou <>."""
    result = []
    dp, da = 0, 0
    current = ""
    for c in s:
        if c == '(':
            dp += 1
            current += c
        elif c == ')':
            dp -= 1
            current += c
        elif c == '<':
            da += 1
            current += c
        elif c == '>':
            da -= 1
            current += c
        elif c == ',' and dp == 0 and da == 0:
            result.append(current.strip())
            current = ""
        else:
            current += c
    if current.strip():
        result.append(current.strip())
    return result


def parse_fn_type(type_str):
    """Se `type_str` é 'fn(T1,T2) -> R', retorna (params, ret).

    `params` é uma lista de strings de tipo Lumina. `ret` é uma string.
    Para 'fn() -> void', retorna ([], "void").
    Para qualquer outra coisa (incluindo 'fn' sem assinatura), retorna None.
    """
    if not type_str or not isinstance(type_str, str):
        return None
    if not type_str.startswith("fn("):
        return None

    rest = type_str[3:]
    depth = 1
    end = -1
    for i, c in enumerate(rest):
        if c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
            if depth == 0:
                end = i
                break

    if end == -1:
        return None

    params_str = rest[:end]
    params = _split_top_level(params_str) if params_str.strip() else []

    after = rest[end + 1:].strip()
    if not after:
        return (params, "void")
    if not after.startswith("->"):
        return None
    ret = after[2:].strip()
    return (params, ret)


def is_assignable(target: str, value: str) -> bool:
    """True se um valor do tipo `value` pode ser atribuído a `target`.

    Regras:
      - Tipos iguais → True.
      - Type param (T, U, ...) → aceita qualquer coisa.
      - Slice `[T]` ↔ `[U]` → recursão em T/U.
      - Slice → ptr: coage para `.data` (retrocompat com APIs antigas).
      - ptr → slice: **não** (perde `.len`).
      - Option ↔ Option<X>.
      - int → float (promoção).
      - int ↔ ptr.
      - arrays decaem para ponteiros.
      - `none`/`nil` para qualquer ptr/struct/fn/str/Option/slice.
    """
    if target is None or value is None:
        return True
    if target == value:
        return True

    if _is_type_param(target):
        return True
    if _is_type_param(value):
        return True

    # ----- Slice -----
    t_slice = _is_slice_type(target)
    v_slice = _is_slice_type(value)
    if t_slice and v_slice:
        return is_assignable(_slice_inner(target), _slice_inner(value))
    if t_slice and not v_slice:
        # ptr → [T]: NÃO (perde len).
        if value in ("none", "None", "null", "nil"):
            return True
        return False
    if v_slice and not t_slice:
        # [T] → ptr: coage implicitamente para `.data`.
        if target in ("ptr",):
            return True
        if target == "int":
            # slice → int: reinterpreta ponteiro como int.
            return True
        return False

    if target.startswith("Option") and value == "Option":
        return True
    if value.startswith("Option") and target == "Option":
        return True

    if value == "Option" and target in ("ptr", "fn", "str"):
        return True

    if target == "float" and value == "int":
        return True

    if target == "ptr" and value in ("int", "ptr"):
        return True
    if target == "int" and value == "ptr":
        return True

    if target in ("str", "ptr", "fn") and value in ("str", "ptr", "fn"):
        return True

    if target == "fn" and value and value.startswith("fn("):
        return True
    if value == "fn" and target and target.startswith("fn("):
        return True

    t_sig = parse_fn_type(target) if target else None
    v_sig = parse_fn_type(value) if value else None
    if t_sig is not None and v_sig is not None:
        t_params, t_ret = t_sig
        v_params, v_ret = v_sig
        if len(t_params) != len(v_params):
            return False
        if t_ret != "void" and v_ret != "void" and t_ret != v_ret:
            return False
        return all(is_assignable(tp, vp) for tp, vp in zip(t_params, v_params))

    if target == "ptr" and value == "array":
        return True
    if target == "array" and value == "ptr":
        return True

    if value in ("none", "None", "null"):
        return (
            target in ("ptr", "fn", "str", "Option")
            or target.startswith("Option")
            or _base(target) not in PRIMITIVES
        )

    if value == "nil":
        return (
            target in ("ptr", "fn", "str")
            or _base(target) not in PRIMITIVES
        )

    if "<" in target or "<" in value:
        if _base(target) != _base(value):
            return False
        if target == _base(target) or value == _base(value):
            return True
        return target.replace(" ", "") == value.replace(" ", "")

    return False


def check_assignable(target: str, value: str, err_ctx) -> None:
    """Levanta LuminaError se não for atribuível.

    `err_ctx` é uma tupla (filename, line, col, source_code).
    """
    if is_assignable(target, value):
        return
    from ..errors import LuminaError
    filename, line, col, source = err_ctx
    raise LuminaError(
        f"Tipos incompatíveis: esperado '{target}', obteve '{value}'.",
        filename, line, col, source,
    )


# ============================================================
# Helpers de genéricos aninhados
# ============================================================

def parse_generic(type_str):
    """Parse 'Box<int>' → ('Box', ['int']). 'int' → ('int', [])."""
    if not type_str or "<" not in type_str:
        return type_str, []
    base, _, rest = type_str.partition("<")
    if not rest.endswith(">"):
        return type_str, []
    args_str = rest[:-1]
    args = []
    depth = 0
    current = ""
    for c in args_str:
        if c == "<":
            depth += 1
            current += c
        elif c == ">":
            depth -= 1
            current += c
        elif c == "," and depth == 0:
            args.append(current.strip())
            current = ""
        else:
            current += c
    if current.strip():
        args.append(current.strip())
    return base, args


def substitute_generic(type_str, type_map):
    """Substitui type params recursivamente."""
    if not type_str:
        return type_str
    if type_str in type_map:
        return type_map[type_str]

    # Slice: `[T]` → `[int]`.
    if _is_slice_type(type_str):
        inner = _slice_inner(type_str)
        return f"[{substitute_generic(inner, type_map)}]"

    base, args = parse_generic(type_str)
    if not args:
        return type_str
    new_args = [substitute_generic(a, type_map) for a in args]
    return f"{base}<{','.join(new_args)}>"


def unify_type(declared, actual, type_map):
    """Unifica `declared` (com type params) contra `actual` (concreto),
    preenchendo `type_map`.
    """
    if declared == actual:
        return True

    if declared and len(declared) == 1 and declared.isupper():
        existing = type_map.get(declared)
        if existing is None:
            type_map[declared] = actual
            return True
        return existing == actual

    # Slice: `[T]` vs `[int]`.
    if _is_slice_type(declared) and _is_slice_type(actual):
        return unify_type(_slice_inner(declared), _slice_inner(actual), type_map)

    d_base, d_args = parse_generic(declared)
    a_base, a_args = parse_generic(actual)

    if d_base != a_base:
        return False

    if not d_args:
        return True

    if len(d_args) != len(a_args):
        return False

    return all(unify_type(d, a, type_map) for d, a in zip(d_args, a_args))


_ALIAS_MAX_DEPTH = 32


def expand_type_alias(type_str, aliases, _depth=0):
    """Expande aliases recursivamente em `type_str`."""
    if not type_str:
        return type_str

    if _depth > _ALIAS_MAX_DEPTH:
        from ..errors import LuminaError
        raise LuminaError(
            message=(
                f"Cadeia de type aliases excede {_ALIAS_MAX_DEPTH} níveis "
                f"começando em '{type_str}'. Provável ciclo (ex: "
                f"`type A = B` + `type B = A`)."
            ),
            filename="<semantic>",
            line=0,
            col=0,
            source_code="",
        )

    # Slice: expande o tipo interno.
    if _is_slice_type(type_str):
        inner = expand_type_alias(_slice_inner(type_str), aliases, _depth + 1)
        return f"[{inner}]"

    base, args = parse_generic(type_str)

    if base in aliases:
        params, target = aliases[base]
        if params:
            if not args:
                return type_str
            if len(args) != len(params):
                return type_str
            subst = dict(zip(params, args))
            expanded = substitute_generic(target, subst)
            return expand_type_alias(expanded, aliases, _depth + 1)
        else:
            if args:
                return type_str
            return expand_type_alias(target, aliases, _depth + 1)

    sig = parse_fn_type(type_str)
    if sig is not None:
        params, ret = sig
        new_params = [expand_type_alias(p, aliases, _depth + 1) for p in params]
        new_ret = expand_type_alias(ret, aliases, _depth + 1)
        return f"fn({','.join(new_params)}) -> {new_ret}"

    if args:
        new_args = [expand_type_alias(a, aliases, _depth + 1) for a in args]
        return f"{base}<{','.join(new_args)}>"

    return type_str