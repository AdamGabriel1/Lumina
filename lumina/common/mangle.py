"""Mangling canônico de tipos para nomes de símbolos.

Usado pelo parser (nome de métodos de impl), semantic (registro de
métodos) e codegen (nome de tipos LLVM identificados). Manter uma
única função garante que `impl Trait for Box<int>` registra
`Box_int__metodo` e que `codegen_method_call` acha.

v0.8.0: adicionado `mangle_slice` para o tipo `[T]`.
"""


def mangle_type(type_name: str) -> str:
    """'Box<int>' → 'Box_int_'; 'Box<int,str>' → 'Box_int_str_'; 'int' → 'int'."""
    if not type_name or "<" not in type_name:
        return type_name
    return type_name.replace("<", "_").replace(">", "_").replace(",", "_").replace(" ", "")


def mangle_method(struct_name: str, method_name: str) -> str:
    """Nome completo de um método de impl: `Box<int>` + `greet` → `Box_int__greet`."""
    return f"{mangle_type(struct_name)}_{method_name}"


def mangle_slice(inner_type: str) -> str:
    """'int' → 'Slice_int_'; '[int]' → 'Slice_int_'; 'Box<int>' → 'Slice_Box_int__'.

    Aceita tanto `'T'` quanto `'[T]'` (idempotente).
    """
    inner = inner_type
    if inner.startswith("[") and inner.endswith("]"):
        inner = inner[1:-1]
    return f"Slice_{mangle_type(inner)}_"