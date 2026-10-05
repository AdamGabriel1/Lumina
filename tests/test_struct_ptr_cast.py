"""`x as Struct` e `struct_ptr as int`.

Cast `int → Struct` deve emitir `inttoptr` (structs Lumina são sempre
ponteiro). Cast `Struct → int` deve emitir `ptrtoint`.

Antes do fix em `visit_CastExpr`, `get_llvm_type` era usado em vez de
`get_llvm_param_type`, retornando `%Struct` em vez de `%Struct*` — o
cast era no-op silencioso, e o campo `s.names` caía no fallback
"não é struct".
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


def test_cast_int_to_struct_ptr():
    """`i64 as Ponto` deve permitir acesso a campos."""
    src = (
        'struct Ponto:\n'
        '    x: int\n'
        '    y: int\n'
        '\n'
        'fn main() -> int:\n'
        '    mut p: Ponto\n'
        '    p.x = 10\n'
        '    p.y = 20\n'
        '    let addr = &p as int\n'
        '    let p2 = addr as Ponto\n'
        '    print(p2.x, p2.y)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "10 20" in out, f"out={out!r}"


def test_cast_struct_ptr_to_int_roundtrip():
    """`&p as int` seguido de `as Ponto` é identidade."""
    src = (
        'struct Box:\n'
        '    v: int\n'
        '\n'
        'fn main() -> int:\n'
        '    mut b: Box\n'
        '    b.v = 42\n'
        '    let addr = &b as int\n'
        '    let b2 = addr as Box\n'
        '    print(b2.v)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "42" in out, f"out={out!r}"


def test_cast_ptr_to_struct():
    """`ptr` direto para struct (sem passar por int)."""
    src = (
        'struct Wrapper:\n'
        '    value: int\n'
        '\n'
        'fn main() -> int:\n'
        '    mut w: Wrapper\n'
        '    w.value = 99\n'
        '    let p: ptr = &w\n'
        '    let w2 = p as Wrapper\n'
        '    print(w2.value)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "99" in out, f"out={out!r}"


def test_cast_int_to_primitive_still_works():
    """Regressão: casts para primitivos não mudam."""
    src = (
        'fn main() -> int:\n'
        '    let x = 10 as float\n'
        '    let y = 3.14 as int\n'
        '    let z = "hello" as ptr\n'
        '    print(x, y)\n'
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "10.0" in out or "10.000000" in out, f"out={out!r}"
    assert "3" in out, f"out={out!r}"


def test_cast_int_to_other_struct():
    """Structs diferentes são interpretações distintas do mesmo endereço."""
    src = (
        'struct A:\n'
        '    x: int\n'
        '\n'
        'struct B:\n'
        '    y: int\n'
        '\n'
        'fn main() -> int:\n'
        '    mut a: A\n'
        '    a.x = 7\n'
        '    let addr = &a as int\n'
        '    let b = addr as B\n'
        '    print(b.y)\n'   # mesmo byte, lido como B.y
        '    return 0\n'
    )
    out, rc = _run(src)
    assert "7" in out, f"out={out!r}"
