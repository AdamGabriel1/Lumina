"""Testes de closures (lambda com captura de variáveis externas).

Cobre:
  - Captura de um único valor
  - Captura de múltiplos valores
  - Captura por valor (não propaga mutação posterior)
  - Lambda sem captura continua funcionando (fn ptr cru)
  - Captura dentro de loop
  - Lambda aninhada
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


def _lines(out, wanted):
    return [l.strip() for l in out.splitlines() if l.strip() in wanted]


# ============================================================
# Básico
# ============================================================
def test_closure_simple():
    src = (
        'fn main() -> int:\n'
        '    let offset = 10\n'
        '    let add = fn(x: int) -> int: x + offset\n'
        '    print(add(5))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "15" in out, f"stdout={out!r}"


def test_closure_two_captures():
    src = (
        'fn main() -> int:\n'
        '    let a = 1\n'
        '    let b = 2\n'
        '    let add = fn(x: int) -> int: x + a + b\n'
        '    print(add(10))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "13" in out, f"stdout={out!r}"


def test_closure_multiple_calls():
    src = (
        'fn main() -> int:\n'
        '    let factor = 3\n'
        '    let times = fn(x: int) -> int: x * factor\n'
        '    print(times(2))\n'
        '    print(times(5))\n'
        '    print(times(10))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert _lines(out, {"6", "15", "30"}) == ["6", "15", "30"]


def test_closure_body_block():
    src = (
        'fn main() -> int:\n'
        '    let base = 100\n'
        '    let add = fn(x: int) -> int:\n'
        '        let doubled = x * 2\n'
        '        return doubled + base\n'
        '    print(add(5))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "110" in out, f"stdout={out!r}"


# ============================================================
# Captura por valor
# ============================================================
def test_closure_capture_by_value():
    """Mutação posterior da variável externa NÃO é vista pela closure."""
    src = (
        'fn main() -> int:\n'
        '    mut x = 10\n'
        '    let get = fn() -> int: x\n'
        '    x = 99\n'
        '    print(get())\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "10" in out, f"stdout={out!r}"


# ============================================================
# Sem captura: continua fn ptr cru
# ============================================================
def test_lambda_no_capture_still_works():
    src = (
        'fn main() -> int:\n'
        '    let twice = fn(x: int) -> int: x * 2\n'
        '    print(twice(7))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "14" in out


def test_lambda_no_capture_via_param():
    """Lambda sem captura passada como callback (fn ptr cru)."""
    src = (
        'fn apply(x: int, f: fn) -> int:\n'
        '    return f(x)\n'
        '\n'
        'fn main() -> int:\n'
        '    let r = apply(5, fn(x: int) -> int: x * 3)\n'
        '    print(r)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "15" in out, f"stdout={out!r}"


# ============================================================
# Captura dentro de loop
# ============================================================
def test_closure_inside_loop_distinct_envs():
    """Cada iteração cria uma closure nova com o valor atual."""
    src = (
        'fn main() -> int:\n'
        '    mut total = 0\n'
        '    for i in 0..3:\n'
        '        let f = fn() -> int: i * 10\n'
        '        total = total + f()\n'
        '    print(total)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    # 0*10 + 1*10 + 2*10 = 30
    assert "30" in out, f"stdout={out!r}"


# ============================================================
# Lambda aninhada (2 níveis)
# ============================================================
def test_closure_nested():
    """Outer captura `a`, inner captura `a` + `b`."""
    src = (
        'fn main() -> int:\n'
        '    let a = 10\n'
        '    let outer = fn(b: int) -> int:\n'
        '        let inner = fn(c: int) -> int: a + b + c\n'
        '        return inner(100)\n'
        '    print(outer(5))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    # 10 + 5 + 100 = 115
    assert "115" in out, f"stdout={out!r}"


# ============================================================
# Coexistência com code normal
# ============================================================
def test_closure_with_other_operations():
    src = (
        'struct Ponto:\n'
        '    x: int\n'
        '    y: int\n'
        '\n'
        'fn main() -> int:\n'
        '    let base = 1000\n'
        '    mut p: Ponto\n'
        '    p.x = 10\n'
        '    p.y = 20\n'
        '    let sum = fn(p: Ponto) -> int: p.x + p.y + base\n'
        '    print(sum(p))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    # 10 + 20 + 1000 = 1030
    assert "1030" in out, f"stdout={out!r}"
