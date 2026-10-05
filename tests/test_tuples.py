"""Testes de tuplas literais e destructuring.

  - `let (a, b, c) = (1, 2, 3)`
  - destructuring de struct (regressão)
  - destructuring de array (regressão)
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
# Tuple destructuring
# ============================================================
def test_tuple_three():
    src = (
        'fn main() -> int:\n'
        '    let (a, b, c) = (10, 20, 30)\n'
        '    print(a, b, c)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "10 20 30" in out


def test_tuple_two():
    src = (
        'fn main() -> int:\n'
        '    let (x, y) = (7, 8)\n'
        '    print(x + y)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "15" in out


def test_tuple_mixed_types():
    """`(int, str)` mantém tipos distintos via LiteralStructType."""
    src = (
        'fn main() -> int:\n'
        '    let (n, s) = (42, "hello")\n'
        '    print(n)\n'
        '    print(s)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "42" in out
    assert "hello" in out


def test_tuple_single_element():
    """`(a,)` — Python-style. Aceito por conta do comma extra."""
    src = (
        'fn main() -> int:\n'
        '    let (a,) = (99,)\n'
        '    print(a)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "99" in out


# ============================================================
# Regressão: destructuring antigo continua
# ============================================================
def test_destructure_struct():
    src = (
        'struct P:\n'
        '    x: int\n'
        '    y: int\n'
        '\n'
        'fn main() -> int:\n'
        '    mut p: P\n'
        '    p.x = 1\n'
        '    p.y = 2\n'
        '    let (a, b) = p\n'
        '    print(a, b)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "1 2" in out


def test_destructure_array():
    src = (
        'fn main() -> int:\n'
        '    mut arr = alloc(2)\n'
        '    arr[0] = 42\n'
        '    arr[1] = 99\n'
        '    let (x, y) = arr\n'
        '    print(x, y)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "42 99" in out


# ============================================================
# Parentheses sem comma continuam sendo parênteses
# ============================================================
def test_parens_not_tuple():
    """`(1 + 2)` não deve virar tupla."""
    src = (
        'fn main() -> int:\n'
        '    let x = (1 + 2) * 3\n'
        '    print(x)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "9" in out
