"""Testes de `type Alias = <tipo>`.

Cobre:
  - Alias para primitivo (int)
  - Alias para fn(...) -> R
  - Alias usado em param de função
  - Alias usado em campo de struct
  - Alias encadeado (A -> B -> C)
  - Alias dentro de assinatura de fn
  - Alias em VarDecl
  - Alias em payload de enum
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


def test_type_alias_primitive():
    src = (
        'type MyInt = int\n'
        '\n'
        'fn dobro(x: MyInt) -> MyInt:\n'
        '    return x * 2\n'
        '\n'
        'fn main() -> int:\n'
        '    print(dobro(21))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "42" in out, f"out={out!r}"


def test_type_alias_fn():
    src = (
        'type Callback = fn(int) -> int\n'
        '\n'
        'fn apply(f: Callback, x: int) -> int:\n'
        '    return f(x)\n'
        '\n'
        'fn main() -> int:\n'
        '    print(apply(fn(y: int) -> int: y * 2, 21))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "42" in out, f"out={out!r}"


def test_type_alias_struct_field():
    src = (
        'type Callback = fn(int) -> int\n'
        '\n'
        'struct Handler:\n'
        '    cb: Callback\n'
        '\n'
        'fn main() -> int:\n'
        '    mut h: Handler\n'
        '    h.cb = fn(x: int) -> int: x * 3\n'
        '    print(h.cb(14))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "42" in out, f"out={out!r}"


def test_type_alias_chained():
    src = (
        'type A = int\n'
        'type B = A\n'
        'type C = B\n'
        '\n'
        'fn f(x: C) -> C:\n'
        '    return x + 1\n'
        '\n'
        'fn main() -> int:\n'
        '    print(f(41))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "42" in out, f"out={out!r}"


def test_type_alias_inside_fn_sig():
    src = (
        'type Callback = fn(int) -> int\n'
        '\n'
        'fn apply(f: Callback, x: int) -> int:\n'
        '    return f(x)\n'
        '\n'
        'fn main() -> int:\n'
        '    print(apply(fn(y: int) -> int: y + 1, 41))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "42" in out, f"out={out!r}"


def test_type_alias_var_decl():
    src = (
        'type Callback = fn(int) -> int\n'
        '\n'
        'fn main() -> int:\n'
        '    let cb: Callback = fn(x: int) -> int: x * 4\n'
        '    print(cb(10))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "40" in out, f"out={out!r}"


def test_type_alias_enum_payload():
    src = (
        'type MyInt = int\n'
        '\n'
        'enum E:\n'
        '    V(MyInt)\n'
        '    W\n'
        '\n'
        'fn main() -> int:\n'
        '    let e = V(42)\n'
        '    match e:\n'
        '        case V(x): print(x)\n'
        '        case W:    print(0)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "42" in out, f"out={out!r}"


def test_type_alias_typedef_struct():
    src = (
        'struct Ponto:\n'
        '    x: int\n'
        '    y: int\n'
        '\n'
        'type P = Ponto\n'
        '\n'
        'fn soma(p: P) -> int:\n'
        '    return p.x + p.y\n'
        '\n'
        'fn main() -> int:\n'
        '    let p = Ponto { x: 10, y: 32 }\n'
        '    print(soma(p))\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "42" in out, f"out={out!r}"
