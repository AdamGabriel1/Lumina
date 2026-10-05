"""Contexto mutável do codegen.

`push_context` salva e restaura um conjunto fixo de atributos do
`LLVMCodegen` que mudam ao entrar em uma função, closure, cópia
especializada de genérico ou dispatcher de SCC.

A lista `_CONTEXT_FIELDS` é a fonte única de verdade. Antes, cada
call site (`function_body`, `generics`, `aggregates`, `tco`) salvava
e restaurava esses campos manualmente — e a lista divergia. Bug
ativo: `_safe_mode` era setado `False` em `materialize_generic` sem
restauração, perdendo `@safe` em funções genéricas.
"""
from contextlib import contextmanager

# Re-export: fonte única em `lumina/common/attrs.py`. Importadores
# antigos (`from .context import normalize_attrs`) continuam funcionando.
from ..common.attrs import normalize_attrs   # noqa: F401


_CONTEXT_FIELDS = (
    "builder",
    "symbol_table",
    "var_types",
    "current_func_name",
    "current_body_bb",
    "defer_stack",
    "_safe_mode",
    "closure_vars",
    "_current_scc_slots",
    "_current_scc_ids",
    "_current_scc_id_slot",
    "_current_scc_dispatch_bb",
    "_fn_entry_block",    # PATCH: para hoisting de alloca
    "_fn_return_type",    # PATCH: para _fn_ensure_terminator
)


@contextmanager
def push_context(codegen, **overrides):
    """
    Salva e restaura todos os campos de contexto do codegen.

    Uso:
        with push_context(self, builder=novo, _safe_mode=True):
            ...
        # tudo restaurado aqui, mesmo em exceção

    Args:
        codegen: instância de `LLVMCodegen`.
        **overrides: campos a sobrescrever. Deve estar em `_CONTEXT_FIELDS`.

    Raises:
        ValueError: override com campo fora de `_CONTEXT_FIELDS`.
    """
    for field in overrides:
        if field not in _CONTEXT_FIELDS:
            raise ValueError(
                f"Campo '{field}' não está em _CONTEXT_FIELDS. "
                f"Adicione-o em lumina/codegen/context.py."
            )

    saved = {field: getattr(codegen, field, None) for field in _CONTEXT_FIELDS}

    for field, value in overrides.items():
        setattr(codegen, field, value)

    try:
        yield codegen
    finally:
        for field, value in saved.items():
            setattr(codegen, field, value)


__all__ = ["push_context", "normalize_attrs", "_CONTEXT_FIELDS"]