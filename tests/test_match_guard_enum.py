"""Testes de match com guard sobre enums.

Bug corrigido: `_codegen_match_with_guard` para enum
  1. não testava a tag da variante (sempre `pattern_match = 1`)
  2. avaliava o guard ANTES de extrair o payload, então
     `case Circle(r) if r > 10` via `r` como 0 (não declarado)
     e o guard sempre falhava — caindo no próximo case.
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
        r2 = subprocess.run(
            [binary], capture_output=True, text=True, timeout=timeout,
        )
        return r2.stdout, r2.returncode
    finally:
        for p in (path, path[:-3] + ".ll", path[:-3]):
            if os.path.exists(p):
                os.remove(p)


# ============================================================
# Bug original: guard ignora o valor do payload
# ============================================================
def test_enum_guard_uses_payload_value():
    src = (
        'enum Shape:\n'
        '    Circle(int)\n'
        '    Square(int)\n'
        '\n'
        'fn area(s: Shape) -> int:\n'
        '    match s:\n'
        '        case Circle(r) if r > 10:\n'
        '            print("grande")\n'
        '            return 100\n'
        '        case Circle(r):\n'
        '            print("pequeno")\n'
        '            return 1\n'
        '        case Square(side):\n'
        '            print("quadrado")\n'
        '            return 2\n'
        '    return 0\n'
        '\n'
        'fn main() -> int:\n'
        '    print(area(Circle(5)))\n'
        '    print(area(Circle(20)))\n'
        '    print(area(Square(7)))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert rc == 0
    # Ordem esperada: pequeno(1), grande(100), quadrado(2)
    lines = [l for l in out.strip().split("\n") if l in ("1", "2", "100")]
    assert lines == ["1", "100", "2"], f"ordem/valores errados: {out!r}"


def test_enum_guard_different_variant_skipped():
    """Guard em Circle não deve casar Square."""
    src = (
        'enum Shape:\n'
        '    Circle(int)\n'
        '    Square(int)\n'
        '\n'
        'fn kind(s: Shape) -> str:\n'
        '    match s:\n'
        '        case Circle(r) if r > 100:\n'
        '            return "big circle"\n'
        '        case Square(side) if side > 100:\n'
        '            return "big square"\n'
        '        case Circle(r):\n'
        '            return "circle"\n'
        '        case Square(side):\n'
        '            return "square"\n'
        '    return "?"\n'
        '\n'
        'fn main() -> int:\n'
        '    print(kind(Square(200)))\n'
        '    print(kind(Circle(5)))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    # NOTA: usar splitlines, não split() — senão "big square" vira
    # ["big", "square"] e o filtro não casa.
    lines = [
        l.strip() for l in out.splitlines()
        if l.strip() in ("big circle", "big square", "circle", "square")
    ]
    assert lines == ["big square", "circle"], f"ordem: {out!r}"


def test_enum_guard_falls_through_correctly():
    src = (
        'enum N:\n'
        '    Val(int)\n'
        '\n'
        'fn classify(n: N) -> str:\n'
        '    match n:\n'
        '        case Val(x) if x == 0:\n'
        '            return "zero"\n'
        '        case Val(x) if x < 0:\n'
        '            return "neg"\n'
        '        case Val(x):\n'
        '            return "pos"\n'
        '    return "?"\n'
        '\n'
        'fn main() -> int:\n'
        '    print(classify(Val(0)))\n'
        '    print(classify(Val(-5)))\n'
        '    print(classify(Val(42)))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    lines = [
        l.strip() for l in out.splitlines()
        if l.strip() in ("zero", "neg", "pos")
    ]
    assert lines == ["zero", "neg", "pos"], f"ordem: {out!r}"


# ============================================================
# Regressão: guard em int continua funcionando
# ============================================================
def test_int_guard_still_works():
    src = (
        'fn classify(n: int) -> str:\n'
        '    match n:\n'
        '        case x if x > 10:\n'
        '            return "big"\n'
        '        case x:\n'
        '            return "small"\n'
        '    return "?"\n'
        '\n'
        'fn main() -> int:\n'
        '    print(classify(50))\n'
        '    print(classify(3))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "big" in out
    assert "small" in out
