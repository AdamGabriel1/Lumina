"""`mut X: T` no top-level sem inicializador vira global zero-init.

Antes, `mut X: int` (sem `=`) era descartado silenciosamente pelo
codegen: a leitura caía em `ir.Constant(i64, 0)` e o write era no-op.
Sintoma típico: variável sempre 0, mesmo depois de atribuir.

Cobre:
  - `mut X: int` sem init, atribuído e lido em `main`
  - `mut X: ptr` sem init, `X = alloc(10)` funciona
  - `mut X: float` sem init, atribuído
  - `let X = ...` no topo continua inline-constante
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
        r2 = subprocess.run([path[:-3]], capture_output=True, text=True, timeout=timeout)
        return r2.stdout, r2.returncode
    finally:
        for p in (path, path[:-3] + ".ll", path[:-3]):
            if os.path.exists(p):
                os.remove(p)


def test_mut_int_no_init_zero_then_assign():
    src = (
        'mut counter: int\n'
        '\n'
        'fn main() -> int:\n'
        '    print(counter)\n'      # 0 (zero-init)
        '    counter = 42\n'
        '    print(counter)\n'      # 42
        '    return 0\n'
    )
    out, rc = _run(src)
    lines = [l.strip() for l in out.splitlines() if l.strip() in ("0", "42")]
    assert lines == ["0", "42"], f"out={out!r}"


def test_mut_ptr_no_init_assignable():
    src = (
        'mut buf: ptr\n'
        '\n'
        'fn main() -> int:\n'
        '    buf = alloc(3)\n'
        '    buf[0] = 7\n'
        '    buf[1] = 8\n'
        '    buf[2] = 9\n'
        '    print(buf[0], buf[1], buf[2])\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "7 8 9" in out, f"out={out!r}"


def test_mut_float_no_init():
    src = (
        'mut pi: float\n'
        '\n'
        'fn main() -> int:\n'
        '    print(pi)\n'          # 0.0
        '    pi = 3.14\n'
        '    print(pi)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "0.0" in out or "0.000000" in out, f"out={out!r}"
    assert "3.14" in out or "3.140000" in out, f"out={out!r}"


def test_mut_int_with_init_still_works():
    """Regressão: `mut X = 10` continua funcionando."""
    src = (
        'mut x = 10\n'
        '\n'
        'fn main() -> int:\n'
        '    print(x)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "10" in out


def test_let_toplevel_still_inline_constant():
    """`let X = 42` no topo continua inline (não vira global)."""
    src = (
        'let MY_CONST = 42\n'
        '\n'
        'fn main() -> int:\n'
        '    print(MY_CONST)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "42" in out

