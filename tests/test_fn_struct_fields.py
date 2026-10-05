"""Testes de `fn` como campo de struct.

Cobre:
  - Atribuir lambda a campo fn-typed
  - Chamar via `h.cb(args)`
  - Campo fn com múltiplos params
  - Campo fn sem assinatura (`cb: fn`)
  - Erros de arity/tipo em compile-time
  - Struct com múltiplos campos fn
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


def test_fn_field_basic():
    src = (
        'struct Handler:\n'
        '    cb: fn(int) -> int\n'
        '    name: str\n'
        '\n'
        'fn main() -> int:\n'
        '    mut h: Handler\n'
        '    h.name = "dobro"\n'
        '    h.cb = fn(x: int) -> int: x * 2\n'
        '    print(h.cb(21))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "42" in out, f"out={out!r}"


def test_fn_field_two_params():
    src = (
        'struct Op:\n'
        '    f: fn(int, int) -> int\n'
        '\n'
        'fn main() -> int:\n'
        '    mut o: Op\n'
        '    o.f = fn(a: int, b: int) -> int: a + b\n'
        '    print(o.f(10, 32))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "42" in out, f"out={out!r}"


def test_fn_field_capture():
    """Lambda com captura armazenada em struct."""
    src = (
        'struct Handler:\n'
        '    cb: fn(int) -> int\n'
        '\n'
        'fn main() -> int:\n'
        '    let offset = 100\n'
        '    mut h: Handler\n'
        '    h.cb = fn(x: int) -> int: x + offset\n'
        '    print(h.cb(5))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "105" in out, f"out={out!r}"


def test_fn_field_named_function():
    """Atribuir função nomeada a campo fn-typed."""
    src = (
        'struct Handler:\n'
        '    cb: fn(int) -> int\n'
        '\n'
        'fn triplo(x: int) -> int:\n'
        '    return x * 3\n'
        '\n'
        'fn main() -> int:\n'
        '    mut h: Handler\n'
        '    h.cb = triplo\n'
        '    print(h.cb(14))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "42" in out, f"out={out!r}"


def test_two_fn_fields():
    src = (
        'struct Calc:\n'
        '    add: fn(int, int) -> int\n'
        '    mul: fn(int, int) -> int\n'
        '\n'
        'fn main() -> int:\n'
        '    mut c: Calc\n'
        '    c.add = fn(a: int, b: int) -> int: a + b\n'
        '    c.mul = fn(a: int, b: int) -> int: a * b\n'
        '    print(c.add(5, 6))\n'
        '    print(c.mul(5, 6))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "11" in out, f"out={out!r}"
    assert "30" in out, f"out={out!r}"


def test_fn_field_arity_mismatch():
    src = (
        'struct H:\n'
        '    cb: fn(int) -> int\n'
        '\n'
        'fn main() -> int:\n'
        '    mut h: H\n'
        '    h.cb = fn(x: int) -> int: x\n'
        '    print(h.cb(1, 2))\n'    # 2 args, espera 1
        '    return 0\n'
    )
    out, rc = _build_fails(src)
    assert rc != 0, f"deveria falhar:\n{out}"
    assert "espera 1 args" in out, f"out={out!r}"


def test_fn_field_type_mismatch():
    src = (
        'struct H:\n'
        '    cb: fn(int) -> int\n'
        '\n'
        'fn main() -> int:\n'
        '    mut h: H\n'
        '    h.cb = fn(x: int) -> int: x\n'
        '    print(h.cb("texto"))\n'
        '    return 0\n'
    )
    out, rc = _build_fails(src)
    assert rc != 0, f"deveria falhar:\n{out}"
    assert "Tipo inválido" in out, f"out={out!r}"
