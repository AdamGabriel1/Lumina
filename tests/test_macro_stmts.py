"""Testes de macros multi-statement (`nome!(args)`).

Cobre:
  - Macro com corpo multi-statement invocada com `!`
  - Substituição de params em VarDecl, AssignStmt, IfStmt
  - Substituição em expressões aninhadas
  - Validação de arity
  - Erro quando `nome!(args)` não é macro
  - Macro expression continua funcionando (`nome(args)`)
  - Uso em loops
"""
import os
import pathlib
import subprocess
import sys
import tempfile

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


def _run(src, timeout=30):
    with tempfile.NamedTemporaryFile("w", suffix=".lm", delete=False) as f:
        f.write(src)
        path = f.name
    try:
        r1 = subprocess.run(
            [sys.executable, "-m", "lumina_cli", "build", path],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=timeout,
        )
        assert r1.returncode == 0, f"Build falhou:\n{r1.stdout}\n{r1.stderr}"
        binary = path[:-3]
        r2 = subprocess.run([binary], capture_output=True, text=True, timeout=timeout)
        return r2.stdout, r2.returncode
    finally:
        for p in (path, path[:-3] + ".ll", path[:-3]):
            if os.path.exists(p):
                os.remove(p)


def _build_fails(src, timeout=30):
    """Compila e retorna (stdout, returncode)."""
    with tempfile.NamedTemporaryFile("w", suffix=".lm", delete=False) as f:
        f.write(src)
        path = f.name
    try:
        r = subprocess.run(
            [sys.executable, "-m", "lumina_cli", "build", path],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=timeout,
        )
        return r.stdout + r.stderr, r.returncode
    finally:
        for p in (path, path[:-3] + ".ll", path[:-3]):
            if os.path.exists(p):
                os.remove(p)


def test_macro_stmt_simple():
    """Corpo com 3 statements — usa ptr para devolver o resultado."""
    src = (
        '@macro\n'
        'fn soma_tres(p: ptr, a: int, b: int, c: int):\n'
        '    let s1 = a + b\n'
        '    let s2 = s1 + c\n'
        '    p[0] = s2\n'
        '\n'
        'fn main() -> int:\n'
        '    mut out = alloc(1)\n'
        '    out[0] = 0\n'
        '    soma_tres!(out, 1, 2, 3)\n'
        '    print(out[0])\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "6" in out, f"out={out!r}"


def test_macro_stmt_with_assign():
    """Macro que modifica variável externa via ptr."""
    src = (
        '@macro\n'
        'fn incrementa(p: ptr, n: int):\n'
        '    mut i = 0\n'
        '    while i < n:\n'
        '        p[0] = p[0] + 1\n'
        '        i = i + 1\n'
        '\n'
        'fn main() -> int:\n'
        '    mut v = alloc(1)\n'
        '    v[0] = 10\n'
        '    incrementa!(v, 5)\n'
        '    print(v[0])\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "15" in out, f"out={out!r}"


def test_macro_stmt_with_return():
    """Return dentro da macro retorna da função chamadora."""
    src = (
        '@macro\n'
        'fn early_exit(cond: int):\n'
        '    if cond == 0:\n'
        '        return 42\n'
        '\n'
        'fn f(x: int) -> int:\n'
        '    early_exit!(x)\n'
        '    return 100\n'
        '\n'
        'fn main() -> int:\n'
        '    print(f(0))\n'
        '    print(f(1))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "42" in out, f"out={out!r}"
    assert "100" in out, f"out={out!r}"


def test_macro_stmt_arity_mismatch():
    """Chamar com número errado de args deve falhar."""
    src = (
        '@macro\n'
        'fn two(a: int, b: int):\n'
        '    print(a + b)\n'
        '\n'
        'fn main() -> int:\n'
        '    two!(1)\n'
        '    return 0\n'
    )
    out, rc = _build_fails(src)
    assert rc != 0
    assert "espera 2 args" in out, f"out={out!r}"


def test_macro_stmt_not_a_macro():
    """`nome!(args)` onde nome não é macro deve falhar."""
    src = (
        'fn normal_fn(a: int):\n'
        '    print(a)\n'
        '\n'
        'fn main() -> int:\n'
        '    normal_fn!(5)\n'
        '    return 0\n'
    )
    out, rc = _build_fails(src)
    assert rc != 0
    assert "não é uma macro" in out, f"out={out!r}"


def test_macro_expr_still_works():
    """Macro de expressão (corpo `return <expr>`) continua igual."""
    src = (
        '@macro\n'
        'fn dobro(x: int) -> int:\n'
        '    return x * 2\n'
        '\n'
        'fn main() -> int:\n'
        '    let a = 5\n'
        '    print(dobro(a + 1))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "12" in out, f"out={out!r}"


def test_macro_expr_multistatement_works():
    """Macro multi-statement como expressão funciona (v0.9.0).

    Antes da ADR 0003 Fase 2, uma macro com corpo multi-statement
    só podia ser chamada como statement (`nome!(...)`). Agora o
    `QuoteInterpreter` avalia `let`/`return` dentro do corpo,
    então a chamada como expressão é válida.
    """
    src = (
        '@macro\n'
        'fn compute(x: int) -> int:\n'
        '    let y = x + 1\n'
        '    return y * 2\n'
        '\n'
        'fn main() -> int:\n'
        '    print(compute(3))\n'   # (3+1)*2 = 8
        '    return 0\n'
    )
    out, rc = _run(src)
    assert rc == 0, f"deveria compilar:\n{out}"
    assert "8" in out, f"out={out!r}"
    

def test_macro_stmt_inside_loop():
    src = (
        '@macro\n'
        'fn soma_em(p: ptr, idx: int, val: int):\n'
        '    p[idx] = p[idx] + val\n'
        '\n'
        'fn main() -> int:\n'
        '    mut arr = alloc(3)\n'
        '    arr[0] = 0\n'
        '    arr[1] = 0\n'
        '    arr[2] = 0\n'
        '    for i in 0..3:\n'
        '        soma_em!(arr, i, i + 1)\n'
        '    print(arr[0], arr[1], arr[2])\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "1 2 3" in out, f"out={out!r}"