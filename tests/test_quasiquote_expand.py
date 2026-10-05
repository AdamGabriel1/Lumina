"""Testes de expansão de `quote:` — Fase 2 da ADR 0003.

Macros com `quote:` constroem AST em compile-time. O corpo é
interpretado por `QuoteInterpreter`, que faz substituição +
construção.
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
        r2 = subprocess.run(
            [path[:-3]], capture_output=True, text=True, timeout=timeout,
        )
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
# Baseline: substituição continua funcionando
# ============================================================
def test_macro_substitution_still_works():
    src = (
        '@macro\n'
        'fn dobro(x: int) -> int:\n'
        '    return x * 2\n'
        '\n'
        'fn main() -> int:\n'
        '    let a = 5\n'
        '    print(dobro(a + 1))\n'   # (5+1)*2 = 12
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "12" in out, f"out={out!r}"


# ============================================================
# quote: identidade
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


def test_quote_return_identity():
    src = (
        '@macro\n'
        'fn passthrough(x):\n'
        '    return quote:\n'
        '        ~x\n'
        '\n'
        'fn main() -> int:\n'
        '    print(passthrough(7))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "7" in out, f"out={out!r}"


# ============================================================
# Caso canônico: unless
# ============================================================
def test_unless_macro():
    src = (
        '@macro\n'
        'fn unless(cond, body):\n'
        '    quote:\n'
        '        if not ~cond:\n'
        '            ~body\n'
        '\n'
        'fn main() -> int:\n'
        '    let x = 10\n'
        '    unless(x > 100, print("pequeno"))\n'
        '    unless(x > 5, print("NAO deve aparecer"))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "pequeno" in out, f"out={out!r}"
    assert "NAO deve aparecer" not in out, f"out={out!r}"


# ============================================================
# Quote com expressão composta
# ============================================================
def test_quote_compound_expr():
    src = (
        '@macro\n'
        'fn add1(x):\n'
        '    quote:\n'
        '        ~x + 1\n'
        '\n'
        'fn main() -> int:\n'
        '    let a = 41\n'
        '    print(add1(a))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "42" in out, f"out={out!r}"


# ============================================================
# Quote com bloco
# ============================================================
def test_quote_let_and_expr():
    src = (
        '@macro\n'
        'fn twice(x):\n'
        '    quote:\n'
        '        let tmp = ~x\n'
        '        tmp + tmp\n'
        '\n'
        'fn main() -> int:\n'
        '    print(twice(21))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "42" in out, f"out={out!r}"


# ============================================================
# Scaffolding no corpo da macro (fora de quote:)
# ============================================================
def test_macro_body_scaffolding():
    """Uso de `let` e `if` para escolher qual quote retornar."""
    src = (
        '@macro\n'
        'fn choose(flag: int, a, b):\n'
        '    if flag > 0:\n'
        '        return quote: ~a\n'
        '    return quote: ~b\n'
        '\n'
        'fn main() -> int:\n'
        '    print(choose(1, 10, 20))\n'
        '    print(choose(0, 10, 20))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    lines = [l.strip() for l in out.splitlines() if l.strip() in ("10", "20")]
    assert lines == ["10", "20"], f"ordem: {out!r}"


# ============================================================
# Erros: quote fora de macro
# ============================================================
def test_quote_outside_macro_errors():
    src = (
        'fn main() -> int:\n'
        '    let x = quote:\n'
        '        5\n'
        '    return 0\n'
    )
    out, rc = _build_fails(src)
    assert rc != 0, f"deveria falhar:\n{out}"
    combined = out.lower()
    assert "macro" in combined or "quote" in combined, f"out={out!r}"


# ============================================================
# Erros: ~ fora de quote
# ============================================================
def test_tilde_in_macro_body_is_bitwise_not():
    """`~x` fora de quote, dentro de macro, é bitwise NOT (ADR 0003).

    Fora de `quote:`, `~` é bitwise NOT — inclusive no corpo de uma
    macro. Como `x` está ligado a um nó de AST, `~x` constrói um
    `UnaryExpr('~', ...)` que o codegen emite como `not` em runtime.

    Verificamos que isso funciona (não é erro).
    """
    src = (
        '@macro\n'
        'fn bitnot(x):\n'
        '    return ~x\n'
        '\n'
        'fn main() -> int:\n'
        '    print(bitnot(5))\n'   # ~5 = -6
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "-6" in out, f"out={out!r}"
