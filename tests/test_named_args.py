"""Testes de named arguments.

Sintaxe: `foo(x: 1, y: 2)`. Mistura posicional + nomeado permitida
enquanto os posicionais vêm primeiro. Duplicatas e nomes desconhecidos
são erros.
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


def _run_expect_fail(src, timeout=30):
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
# Básico
# ============================================================
def test_named_args_reordered():
    src = (
        'fn greet(first: str, last: str) -> int:\n'
        '    print(first, last)\n'
        '    return 0\n'
        '\n'
        'fn main() -> int:\n'
        '    greet(last: "Gabriel", first: "Adam")\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "Adam Gabriel" in out, f"stdout={out!r}"


def test_named_args_mixed():
    """Posicional primeiro, depois nomeados."""
    src = (
        'fn f(a: int, b: int, c: int) -> int:\n'
        '    print(a, b, c)\n'
        '    return 0\n'
        '\n'
        'fn main() -> int:\n'
        '    f(1, c: 3, b: 2)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "1 2 3" in out, f"stdout={out!r}"


def test_named_args_all_named():
    src = (
        'fn f(a: int, b: int) -> int:\n'
        '    print(a, b)\n'
        '    return 0\n'
        '\n'
        'fn main() -> int:\n'
        '    f(b: 2, a: 1)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "1 2" in out


# ============================================================
# Defaults
# ============================================================
def test_named_args_with_defaults():
    src = (
        'fn f(a: int = 1, b: int = 2, c: int = 3) -> int:\n'
        '    print(a, b, c)\n'
        '    return 0\n'
        '\n'
        'fn main() -> int:\n'
        '    f(c: 30)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "1 2 30" in out, f"stdout={out!r}"


# ============================================================
# Erros
# ============================================================
def test_named_args_unknown_param():
    src = (
        'fn f(a: int) -> int:\n'
        '    return a\n'
        '\n'
        'fn main() -> int:\n'
        '    f(z: 1)\n'
        '    return 0\n'
    )
    out, rc = _run_expect_fail(src)
    assert rc != 0
    assert "z" in out and "não existe" in out


def test_named_args_duplicate():
    src = (
        'fn f(a: int, b: int) -> int:\n'
        '    return a + b\n'
        '\n'
        'fn main() -> int:\n'
        '    f(1, a: 2)\n'
        '    return 0\n'
    )
    out, rc = _run_expect_fail(src)
    assert rc != 0
    assert "duplicado" in out.lower() or "duplicat" in out.lower()


def test_named_args_positional_after_named():
    src = (
        'fn f(a: int, b: int) -> int:\n'
        '    return a + b\n'
        '\n'
        'fn main() -> int:\n'
        '    f(a: 1, 2)\n'
        '    return 0\n'
    )
    out, rc = _run_expect_fail(src)
    assert rc != 0
    assert "posicional após nomeado" in out


# ============================================================
# Métodos
# ============================================================
def test_named_args_method():
    src = (
        'struct P:\n'
        '    x: int\n'
        '    y: int\n'
        '\n'
        'impl P:\n'
        '    fn set(new_x: int, new_y: int):\n'
        '        self.x = new_x\n'
        '        self.y = new_y\n'
        '\n'
        'fn main() -> int:\n'
        '    mut p: P\n'
        '    p.x = 0\n'
        '    p.y = 0\n'
        '    p.set(new_y: 99, new_x: 42)\n'
        '    print(p.x, p.y)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "42 99" in out, f"stdout={out!r}"


# ============================================================
# Coexistência com posicional
# ============================================================
def test_positional_call_still_works():
    src = (
        'fn f(a: int, b: int) -> int:\n'
        '    return a + b\n'
        '\n'
        'fn main() -> int:\n'
        '    print(f(3, 4))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "7" in out
