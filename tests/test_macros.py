"""Macros (@macro) via expansão de AST.

Cobre:
  - Substituição simples (`return x * 2`)
  - Substituição com expressão como argumento
  - Composição (macro chamando macro)
  - `quote:` / `~` (ADR 0003 Fase 2)
  - Erros: quote fora de macro
"""
import os
import pathlib
import subprocess
import sys
import tempfile

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


def _run(src, timeout=30):
    """Compila e executa. Retorna (stdout, returncode)."""
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


def _build(src, timeout=30):
    """Só compila. Retorna `CompletedProcess`."""
    with tempfile.NamedTemporaryFile("w", suffix=".lm", delete=False) as f:
        f.write(src)
        path = f.name
    try:
        return subprocess.run(
            [sys.executable, "-m", "lumina_cli", "build", path],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=timeout,
        )
    finally:
        for p in (path, path[:-3] + ".ll", path[:-3]):
            if os.path.exists(p):
                os.remove(p)


def _build_fails(src, timeout=30):
    """Compila e espera falha. Retorna (stdout+stderr, rc)."""
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
# Substituição básica
# ============================================================
def test_macro_simple():
    src = (
        '@macro\n'
        'fn dobro(x: int) -> int:\n'
        '    return x * 2\n'
        '\n'
        'fn main() -> int:\n'
        '    print(dobro(5))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "10" in out


def test_macro_with_expression_arg():
    """Precedência: dobro(a + 1) → (a + 1) * 2, não a + 1*2."""
    src = (
        '@macro\n'
        'fn dobro(x: int) -> int:\n'
        '    return x * 2\n'
        '\n'
        'fn main() -> int:\n'
        '    let a = 5\n'
        '    print(dobro(a + 1))   # (5+1)*2 = 12\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "12" in out, f"out={out!r}"


def test_macro_two_args():
    """Macro com 2 args; sem ternário, usa chamada dupla."""
    src = (
        '@macro\n'
        'fn sq(x: int) -> int:\n'
        '    return x * x\n'
        '\n'
        'fn main() -> int:\n'
        '    print(sq(3) + sq(4))\n'   # 9 + 16 = 25
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "25" in out, f"out={out!r}"


# ============================================================
# Composição
# ============================================================
def test_macro_composes_with_other_calls():
    src = (
        '@macro\n'
        'fn dobro(x: int) -> int:\n'
        '    return x * 2\n'
        '\n'
        '@macro\n'
        'fn quadruplo(x: int) -> int:\n'
        '    return dobro(dobro(x))\n'   # macro chamando macro
        '\n'
        'fn main() -> int:\n'
        '    print(quadruplo(3))\n'   # 3*4 = 12
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "12" in out, f"out={out!r}"


# ============================================================
# Multi-statement via QuoteInterpreter (ADR 0003)
# ============================================================
def test_macro_multistatement_ok_via_interpreter():
    """Corpo multi-statement é interpretado em compile-time (v0.9.0).

    A partir da ADR 0003 Fase 2, o `QuoteInterpreter` avalia `let`
    e `return` dentro do corpo da macro. O teste antigo verificava
    que isso falhava; agora o comportamento é intencionalmente
    diferente.
    """
    src = (
        '@macro\n'
        'fn bad(x: int) -> int:\n'
        '    let y = x + 1\n'
        '    return y * 2\n'
        '\n'
        'fn main() -> int:\n'
        '    return bad(3)\n'   # (3+1)*2 = 8
    )
    r = _build(src)
    assert r.returncode == 0, (
        f"macro multi-statement como expressão deveria compilar:\n{r.stdout}\n{r.stderr}"
    )


# ============================================================
# Argumentos `ptr` / composição com codegen
# ============================================================
def test_macro_with_ptr_arg():
    src = (
        '@macro\n'
        'fn deref_first(p: ptr) -> int:\n'
        '    return p[0]\n'
        '\n'
        'fn main() -> int:\n'
        '    mut arr = alloc(3)\n'
        '    arr[0] = 77\n'
        '    print(deref_first(arr))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "77" in out, f"out={out!r}"


# ============================================================
# ADR 0003 — `quote:` / `~`
# ============================================================
def test_quote_identity():
    src = (
        '@macro\n'
        'fn passthrough(x):\n'
        '    quote:\n'
        '        ~x\n'
        '\n'
        'fn main() -> int:\n'
        '    print(passthrough(42))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "42" in out, f"out={out!r}"