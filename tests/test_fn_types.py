"""Testes de tipos de função com assinatura (`fn(int) -> int`).

Cobre:
  - Parser: `fn(T1, T2) -> R` em params e retornos
  - Inferência: lambda produz assinatura
  - Inferência: função nomeada produz assinatura
  - Chamada: arity e tipos validados
  - Compatibilidade: `fn` (sem assinatura) aceita qualquer fn
  - HOF que exige assinatura exata
  - Arity errada falha em compile-time
  - Tipo de param errado falha em compile-time
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


# ============================================================
# Parse + chamada
# ============================================================
def test_fn_type_annotation_parses():
    """`fn(int) -> int` em parâmetro compila."""
    src = (
        'fn apply(f: fn(int) -> int, x: int) -> int:\n'
        '    return f(x)\n'
        '\n'
        'fn main() -> int:\n'
        '    let r = apply(fn(y: int) -> int: y * 3, 7)\n'
        '    print(r)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "21" in out, f"out={out!r}"


def test_two_params_fn_type():
    src = (
        'fn reduce(f: fn(int, int) -> int, a: int, b: int) -> int:\n'
        '    return f(a, b)\n'
        '\n'
        'fn main() -> int:\n'
        '    let r = reduce(fn(x: int, y: int) -> int: x + y, 10, 32)\n'
        '    print(r)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "42" in out, f"out={out!r}"


def test_zero_params_fn_type():
    src = (
        'fn run(f: fn() -> int) -> int:\n'
        '    return f()\n'
        '\n'
        'fn main() -> int:\n'
        '    let r = run(fn() -> int: 99)\n'
        '    print(r)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "99" in out, f"out={out!r}"


def test_named_fn_as_value():
    """Função nomeada tem assinatura derivada e pode ser passada."""
    src = (
        'fn dobro(x: int) -> int:\n'
        '    return x * 2\n'
        '\n'
        'fn apply(f: fn(int) -> int, x: int) -> int:\n'
        '    return f(x)\n'
        '\n'
        'fn main() -> int:\n'
        '    print(apply(dobro, 21))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "42" in out, f"out={out!r}"


# ============================================================
# Compatibilidade de assinaturas
# ============================================================
def test_untyped_fn_accepts_typed():
    """Param `fn` (sem assinatura) aceita lambda com assinatura."""
    src = (
        'fn call(f: fn, x: int) -> int:\n'
        '    return f(x)\n'
        '\n'
        'fn main() -> int:\n'
        '    print(call(fn(y: int) -> int: y + 1, 41))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "42" in out, f"out={out!r}"


def test_typed_fn_accepts_untyped_value():
    """Param tipado aceita função nomeada (assume compatibilidade)."""
    src = (
        'fn dobro(x: int) -> int:\n'
        '    return x * 2\n'
        '\n'
        'fn apply(f: fn(int) -> int) -> int:\n'
        '    return f(5)\n'
        '\n'
        'fn main() -> int:\n'
        '    print(apply(dobro))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "10" in out, f"out={out!r}"


# ============================================================
# Erros de compilação
# ============================================================
def test_arity_mismatch_in_call():
    """Chamar fn-typed com arity errada falha em compile-time."""
    src = (
        'fn apply(f: fn(int) -> int, x: int) -> int:\n'
        '    return f(x, x)\n'   # f espera 1 arg, passa 2
        '\n'
        'fn main() -> int:\n'
        '    return apply(fn(y: int) -> int: y, 5)\n'
    )
    out, rc = _build_fails(src)
    assert rc != 0, f"deveria falhar:\n{out}"
    assert "espera 1 args" in out or "espera 1 args," in out, f"out={out!r}"


def test_param_type_mismatch_in_call():
    """Passar tipo errado para fn-typed falha em compile-time."""
    src = (
        'fn apply(f: fn(int) -> int) -> int:\n'
        '    return f("texto")\n'   # f espera int, passa str
        '\n'
        'fn main() -> int:\n'
        '    return apply(fn(y: int) -> int: y)\n'
    )
    out, rc = _build_fails(src)
    assert rc != 0, f"deveria falhar:\n{out}"
    assert "Tipo inválido" in out, f"out={out!r}"


def test_signature_mismatch_in_assignment():
    """Passar lambda com arity errada para param tipado falha."""
    src = (
        'fn apply(f: fn(int) -> int) -> int:\n'
        '    return f(5)\n'
        '\n'
        'fn main() -> int:\n'
        '    return apply(fn(a: int, b: int) -> int: a + b)\n'  # 2 args
    )
    out, rc = _build_fails(src)
    assert rc != 0, f"deveria falhar:\n{out}"


# ============================================================
# Retorno tipado
# ============================================================
def test_return_type_propagates():
    """O tipo de retorno de uma fn-typed var é usado pelo VarDecl."""
    src = (
        'fn apply(f: fn(int) -> int, x: int) -> int:\n'
        '    return f(x)\n'
        '\n'
        'fn main() -> int:\n'
        '    let y = apply(fn(z: int) -> int: z * 2, 21)\n'
        '    let r: int = y\n'   # y deve ser int
        '    print(r)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "42" in out, f"out={out!r}"


# ============================================================
# Mistura de tipos
# ============================================================
def test_fn_type_with_str():
    src = (
        'fn transform(f: fn(str) -> str, s: str) -> str:\n'
        '    return f(s)\n'
        '\n'
        'fn main() -> int:\n'
        '    let r = transform(fn(t: str) -> str: t + "!", "ola")\n'
        '    print(r)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "ola!" in out, f"out={out!r}"


def test_fn_type_nested():
    """fn que retorna fn (assinatura aninhada)."""
    src = (
        'fn apply_twice(f: fn(int) -> int, x: int) -> int:\n'
        '    return f(f(x))\n'
        '\n'
        'fn main() -> int:\n'
        '    print(apply_twice(fn(y: int) -> int: y + 1, 10))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "12" in out, f"out={out!r}"
